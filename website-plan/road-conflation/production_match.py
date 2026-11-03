"""Parallel execution of the pilot's direction/length/overlap matcher.

Global source connectivity and spatial indices are prepared once per worker;
chunks never truncate the road graph or reference context at tile boundaries.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib,json
from pathlib import Path

import numpy as np
import networkx as nx
from shapely.geometry import Point
from shapely.ops import substring,unary_union

from conflate import (Config,Index,cell_evidence,geom_key,parallel_evidence,row_for,
                      sample_cells,source_connected,grade_conflict)
from production_prepare import dump,load

_CONTEXT=None


class SourceIndex(Index):
    def __init__(self,roads,topology):super().__init__(roads);self.topology=topology
    def portal(self,road,end,other):
        source=self.topology.get(road.uid,{})
        target=self.topology.get(other.uid,{})
        return bool(set(source.get('endpoint_nodes',[[],[]])[end]) & set(target.get('node_ids',[])))
    def neighbours(self,road,end,distance,exclude_self=True):
        point=Point(road.geometry.coords[0 if end==0 else -1])
        return [int(i) for i in self.nearby(point,distance)
                if (not exclude_self or self.roads[i].uid!=road.uid)
                and (not grade_conflict(road,self.roads[i]) or self.portal(road,end,self.roads[i]))]
    def endpoint_links(self,road,distance,exclude_self=False,trusted_only=False):
        return [len(self.neighbours(road,end,distance,exclude_self)) for end in [0,1]]


def global_connectivity(roads,references,config,topology):
    index=SourceIndex(roads,topology);graph=nx.Graph();graph.add_nodes_from(range(len(roads)));seeds=set();portals=0
    for i,road in enumerate(roads):
        if any(references.endpoint_links(road,config.reference_attach_m,trusted_only=True)):seeds.add(i)
        for end in [0,1]:
            for j in index.neighbours(road,end,config.endpoint_snap_m):
                if grade_conflict(road,roads[j]):portals+=1
                graph.add_edge(i,j)
    connected={}
    for component in nx.connected_components(graph):
        value=bool(component&seeds)
        for i in component:connected[roads[i].uid]=value
    return index,connected,portals


def match_context(roads,references,source_index,connected,config,duplicate_uids=None):
    parents=[];fragments=[];duplicate_uids=duplicate_uids or set()
    for road in roads:
        if road.uid in duplicate_uids:
            parents.append(row_for(road,status='matched',reason='exact_same_grade_source_duplicate',matched_m=road.length,missing_m=0.,uncertain_m=0.))
            continue
        cells=sample_cells(road,config)
        evidence=[cell_evidence(road,a,b,references,config) for a,b in cells]
        independent=parallel_evidence(road,source_index,references,config) if any(e['reason']=='displacement_or_parallel' for e in evidence) else False
        component=connected.get(road.uid,False)
        for item in evidence:
            if independent and item['reason']=='displacement_or_parallel':item.update(kind='missing',reason='independent_parallel_source_topology')
            if item['kind']=='missing' and not component:item.update(kind='uncertain',reason='no_grade_compatible_reference_connection')
        runs=[]
        for (a,b),item in zip(cells,evidence):
            if runs and runs[-1]['kind']==item['kind']:
                runs[-1]['b']=b;runs[-1]['reasons'].add(item['reason'])
            else:runs.append(dict(a=a,b=b,kind=item['kind'],reasons={item['reason']}))
        chosen={item['ref'] for item in evidence if item['ref'] is not None}
        corridor=unary_union([references.roads[i].geometry.buffer(config.tolerance_m,cap_style=2) for i in chosen])
        for run in runs:
            if run['kind']=='matched':
                interval=substring(road.geometry,run['a'],run['b'])
                if interval.intersection(corridor).length/interval.length<config.minimum_run_overlap_fraction:
                    run['kind']='uncertain';run['reasons'].add('insufficient_continuous_overlap')
            if run['kind']=='missing' and run['b']-run['a']<config.min_fragment_m:
                run['kind']='uncertain';run['reasons'].add('short_missing_fragment')
        lengths=Counter()
        for run in runs:lengths[run['kind']]+=run['b']-run['a']
        status=('partially_matched' if lengths['matched'] and (lengths['missing'] or lengths['uncertain']) else
                'matched' if lengths['matched'] else 'unmatched' if lengths['missing'] and not lengths['uncertain'] else 'uncertain')
        links=source_index.endpoint_links(road,config.endpoint_snap_m,exclude_self=True)
        distances=[item['distance'] for item in evidence if item['distance'] is not None]
        angles=[item['angle'] for item in evidence if item['angle'] is not None]
        parent=row_for(road,status=status,reason=';'.join(sorted({r for run in runs for r in run['reasons']})),
                       matched_m=lengths['matched'],missing_m=lengths['missing'],uncertain_m=lengths['uncertain'],
                       matched_frac=lengths['matched']/road.length,component_connected=component,parallel_evidence=independent,
                       median_offset_m=float(np.median(distances)) if distances else None,
                       median_angle_deg=float(np.median(angles)) if angles else None,
                       source_connections_start=links[0],source_connections_end=links[1],tolerance_m=config.tolerance_m)
        parents.append(parent)
        for run in runs:
            native_a=road.original_offset_m+run['a'];native_b=road.original_offset_m+run['b']
            key=hashlib.sha256(f'v1|{road.source}|{road.source_id}|{road.source_geometry_key}|{round(native_a*1000)}|{round(native_b*1000)}'.encode()).hexdigest()[:24]
            geometry=substring(road.geometry,run['a'],run['b'])
            row=row_for(road,fragment_uid='supp-v1-'+key,parent_uid=road.uid,fragment_kind=run['kind'],
                        reason=';'.join(sorted(run['reasons'])),from_m=native_a,to_m=native_b,
                        component_connected=component,parallel_evidence=independent,
                        source_connections_start=links[0],source_connections_end=links[1])
            row.update(geometry=geometry,length_m=geometry.length)
            fragments.append(row)
    return parents,fragments


def init_worker(context_file):
    global _CONTEXT
    context=load(context_file)
    context['references']=Index(context.pop('reference_roads'))
    context['source_index']=SourceIndex(context.pop('source_roads'),context['topology'])
    _CONTEXT=context


def match_chunk(task):
    number,roads,destination=task
    destination=Path(destination)
    if destination.exists():return number,len(roads),True
    c=_CONTEXT
    result=match_context(roads,c['references'],c['source_index'],c['connected'],c['config'],c['duplicate_uids'])
    dump(destination,result)
    return number,len(roads),False


def run_stage(roads,reference_roads,output,label,config,workers=4,metadata=None):
    output=Path(output);stage=output/'cache'/label;stage.mkdir(parents=True,exist_ok=True)
    # Source graph is global, not recomputed on arbitrarily split chunks.
    print(f'{label}: building global source connectivity for {len(roads):,} parts',flush=True)
    topology={r.uid:{'node_ids':metadata[r.uid]['node_ids'],'endpoint_nodes':metadata[r.uid]['endpoint_nodes']} for r in roads} if metadata else {}
    source_index,connected,portals=global_connectivity(roads,Index(reference_roads),config,topology)
    print(f'{label}: {portals:,} grade-transition endpoint links corroborated by shared OSM nodes',flush=True)
    duplicate_uids=set();seen=set()
    for road in roads:
        key=(geom_key(road.geometry),road.layer,road.bridge,road.tunnel)
        if key in seen:duplicate_uids.add(road.uid)
        else:seen.add(key)
    context=dict(reference_roads=reference_roads,source_roads=roads,connected=connected,config=config,duplicate_uids=duplicate_uids,topology=topology)
    context_file=stage/'worker_context.pkl';dump(context_file,context)
    chunks=[(i,roads[a:a+400],str(stage/f'chunk_{i:05d}.pkl')) for i,a in enumerate(range(0,len(roads),400))]
    if workers<=1:
        init_worker(context_file)
        for task in chunks:
            _,count,cached=match_chunk(task)
            if task[0]%5==0:print(f'{label}: chunk {task[0]+1}/{len(chunks)} ({"cache" if cached else "computed"})',flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers,initializer=init_worker,initargs=(str(context_file),)) as pool:
            futures=[pool.submit(match_chunk,task) for task in chunks]
            done=0
            for future in as_completed(futures):
                future.result();done+=1
                if done%5==0 or done==len(chunks):print(f'{label}: {done}/{len(chunks)} chunks complete',flush=True)
    parents=[];fragments=[]
    for _,_,destination in chunks:
        p,f=load(destination);parents.extend(p);fragments.extend(f)
    assert len(parents)==len(roads)
    return parents,fragments
