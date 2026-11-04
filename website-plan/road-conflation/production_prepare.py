"""Immutable input preparation, PBF tag recovery, and stable native line measures."""
from pathlib import Path
import hashlib,json,pickle

import geopandas as gpd
import numpy as np
import osmium
import pandas as pd
import shapely
from shapely.geometry import LineString,Point,box

from conflate import ROOT,Road,canonical,geom_key,line_parts,numeric,truth
from enrich_candidates import geometry_evidence
from production_policy import eligibility,NOT


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    part=path.with_suffix(path.suffix+'.part')
    with part.open('wb') as f:pickle.dump(obj,f,protocol=5)
    part.replace(path)


def load(path):
    with Path(path).open('rb') as f:return pickle.load(f)


def extract_all_pbf(output):
    output=Path(output);path=output/'cache/osm_full_tags.gpkg';meta=path.with_suffix('.json')
    source=ROOT/'local-data/osm/pbf/Singapore.osm.pbf'
    source_sha=sha(source)
    if path.exists() and meta.exists() and json.loads(meta.read_text())['pbf_sha256']==source_sha:
        return path
    path.parent.mkdir(parents=True,exist_ok=True)
    class Extract(osmium.SimpleHandler):
        def __init__(self):super().__init__();self.ways=[];self.barriers=[];self.bad=0
        def node(self,node):
            if 'barrier' not in node.tags:return
            self.barriers.append(dict(node_id=int(node.id),all_tags_json=json.dumps(dict(node.tags),sort_keys=True),geometry=Point(node.location.lon,node.location.lat)))
        def way(self,way):
            if 'highway' not in way.tags:return
            if any(not n.location.valid() for n in way.nodes):self.bad+=1;return
            coordinates=[(n.lon,n.lat) for n in way.nodes]
            if len(coordinates)<2:self.bad+=1;return
            tags=dict(way.tags)
            self.ways.append(dict(way_id=int(way.id),highway=tags.get('highway',''),name=tags.get('name',''),
                                  tags_json=json.dumps(tags,sort_keys=True),node_ids_json=json.dumps([int(n.ref) for n in way.nodes]),
                                  osm_version=int(way.version),osm_timestamp=str(way.timestamp),geometry=LineString(coordinates)))
            if len(self.ways)%100000==0:print(f'PBF tagged highway ways read: {len(self.ways):,}',flush=True)
    handler=Extract();handler.apply_file(str(source),locations=True,idx='flex_mem')
    ways=gpd.GeoDataFrame(handler.ways,geometry='geometry',crs=4326).to_crs(3414)
    barriers=gpd.GeoDataFrame(handler.barriers,geometry='geometry',crs=4326).to_crs(3414)
    if path.exists():path.unlink()
    ways.to_file(path,layer='highway_ways',driver='GPKG')
    barriers.to_file(path,layer='barrier_nodes',driver='GPKG')
    meta.write_text(json.dumps(dict(pbf_sha256=source_sha,highway_ways=len(ways),barrier_nodes=len(barriers),invalid_ways=handler.bad),indent=2))
    return path


def way_lookup(pbf_frame):
    # A precision-normalized geometry hash is a fast corroboration test. All
    # nonidentical potential ID associations still receive the sampled test.
    normalized=shapely.normalize(shapely.set_precision(pbf_frame.geometry.to_numpy(),.05))
    keys=[hashlib.sha256(wkb).hexdigest() for wkb in shapely.to_wkb(normalized)]
    answer={}
    for i,row in enumerate(pbf_frame.itertuples(index=False)):
        answer[int(row.way_id)]=dict(geometry=row.geometry,shape_key=keys[i],tags=json.loads(row.tags_json),
                                    node_ids_json=row.node_ids_json,version=row.osm_version,timestamp=row.osm_timestamp)
    return answer


def prepare_roads(frame,source,mask,way_info,barriers,campus_region,clip=True):
    """Normalize/explode without changing inputs; preserve native source measures."""
    fields={name:i for i,name in enumerate(frame.columns)}
    class_field='fclass' if source=='processed_lta' else 'type'
    shapely.prepare(mask)
    intersects=shapely.intersects(mask,frame.geometry.to_numpy())
    selected=frame.loc[intersects]
    roads=[];info={};outside_count=int((~intersects).sum());invalid=[];grade_conflicts=set()
    from enrich_candidates import CAMPUS_NAMES
    supported_names=set()
    for way in way_info.values():
        tags=way['tags'];name=str(tags.get('name','')).lower()
        if name in CAMPUS_NAMES and campus_region.intersects(way['geometry']):
            lanes=numeric(tags.get('lanes'))
            if lanes>=1 and (lanes>=2 or tags.get('sidewalk','') not in ['','no','none'] or any(k.startswith('turn:lanes') for k in tags)):
                supported_names.add(name)
    for number,values in enumerate(selected.itertuples(index=False,name=None)):
        if number and number%50000==0:print(f'Preparing {source}: {number:,}/{len(selected):,} in study mask',flush=True)
        def get(name,default=None):return values[fields[name]] if name in fields else default
        sid=str(get('osm_id',''));kind=str(get(class_field,'unknown'))
        original_geometry=get(frame.geometry.name)
        source_name=str(get('name')) if pd.notna(get('name')) else ''
        way=way_info.get(int(sid)) if sid.isdigit() else None
        for original in line_parts(original_geometry):
            original=canonical(original)
            if original.length<.05 or not original.is_valid:
                invalid.append(dict(source_id=sid,reason='invalid_or_near_zero_geometry'));continue
            key=geom_key(original)
            linked=False;link_method='no_corresponding_OSM_id';max_offset=None
            if way:
                if geom_key(original,.05)==way['shape_key']:
                    linked=True;link_method='ID_plus_normalized_geometry';max_offset=0.
                else:
                    evidence=geometry_evidence(original,way['geometry'])
                    linked=evidence['accepted'];max_offset=evidence['max_offset_m']
                    link_method='ID_plus_sampled_geometry' if linked else 'ID_geometry_conflict'
            tags=way['tags'] if linked else {}
            original_layer=numeric(get('layer')) if get('layer') is not None and pd.notna(get('layer')) else None
            original_bridge=truth(get('bridge')) if get('bridge') is not None and pd.notna(get('bridge')) else None
            original_tunnel=truth(get('tunnel')) if get('tunnel') is not None and pd.notna(get('tunnel')) else None
            # Keep reported primary grade disagreements visible across both
            # representations of the same corroborated OSM way.
            grade_risk=False
            if source=='processed_lta' and linked:
                grade_risk=(original_layer not in (None,0) and numeric(tags.get('layer'))!=original_layer) or (original_bridge is True and tags.get('bridge','') in ['','no','false','0']) or (original_tunnel is True and tags.get('tunnel','') in ['','no','false','0'])
                if grade_risk:grade_conflicts.add(int(sid))
            clipped=original if not clip or mask.covers(original) else original.intersection(mask)
            for line in line_parts(clipped):
                if line.length<.05:continue
                start=original.project(Point(line.coords[0]));end=original.project(Point(line.coords[-1]))
                if end<start:line=LineString(list(line.coords)[::-1])
                start=min(start,end)
                uid=f'{source}:{sid}:{key[:16]}:{round(start*1000)}'
                boundary=clip and not mask.covers(original)
                layer=numeric(tags['layer']) if tags.get('layer') not in (None,'') else original_layer
                bridge=str(tags['bridge']).lower() not in ['no','false','0'] if tags.get('bridge') not in (None,'') else original_bridge
                tunnel=str(tags['tunnel']).lower() not in ['no','false','0'] if tags.get('tunnel') not in (None,'') else original_tunnel
                road=Road(uid,source,sid,line,kind,source_name,layer,bridge,tunnel,str(get('oneway','')),start,key,boundary)
                restricted_barriers=[]
                if linked:
                    for node_id in json.loads(way['node_ids_json']):
                        b=barriers.get(int(node_id))
                        if b and b['geometry'].distance(line)<=2:
                            if any(str(b['tags'].get(k,'')).lower() in {'no','private','permit','customers','delivery','destination'} for k in ['access','vehicle','motor_vehicle','foot']):restricted_barriers.append(int(node_id))
                campus=bool(campus_region.covers(line.interpolate(.5,normalized=True)))
                corridor_supported=campus and str(tags.get('name','')).lower() in supported_names
                node_ids=[];endpoint_nodes=[[],[]]
                if linked:
                    if 'nodes' not in way:way['nodes']=json.loads(way['node_ids_json'])
                    node_ids=way['nodes']
                    endpoints=[(node_ids[0],Point(way['geometry'].coords[0])),(node_ids[-1],Point(way['geometry'].coords[-1]))]
                    endpoint_nodes=[[node for node,p in endpoints if p.distance(Point(line.coords[which]))<=1] for which in [0,-1]]
                preliminary=eligibility(kind,tags,linked,campus=campus,connected=True,endpoint_links=2,boundary=boundary,
                                        grade_conflict=grade_risk,barrier_restriction=bool(restricted_barriers),corridor_supported=corridor_supported)
                roads.append(road)
                info[uid]=dict(tags=tags,linked=linked,link_method=link_method,link_max_offset_m=max_offset,
                               matched_way_id=int(sid) if linked else None,campus=campus,grade_conflict=grade_risk,
                               barrier_restriction=bool(restricted_barriers),restricted_barrier_ids=restricted_barriers,
                               node_ids=node_ids,endpoint_nodes=endpoint_nodes,corridor_supported=corridor_supported,
                               preliminary_category=preliminary[0],preliminary_reason=preliminary[1])
    return sorted(roads,key=lambda r:r.uid),info,dict(source_features=len(frame),in_mask_features=len(selected),outside_features=outside_count,
                                                    normalized_parts=len(roads),invalid_parts=invalid),grade_conflicts


def prepare_bundle(output,*,nus=False):
    output=Path(output);cache=output/'cache';cache.mkdir(parents=True,exist_ok=True)
    pbf_path=ROOT/'local-outputs/conflation/nus-enriched/pbf_nus_extract.gpkg' if nus else extract_all_pbf(output)
    ways=gpd.read_file(pbf_path,layer='highway_ways')
    if nus:ways=ways.rename(columns={'all_tags_json':'tags_json'})
    barrier_frame=gpd.read_file(pbf_path,layer='barrier_nodes')
    barriers={int(r.node_id):dict(geometry=r.geometry,tags=json.loads(r.all_tags_json)) for r in barrier_frame.itertuples()}
    lookup=way_lookup(ways)
    prior=json.loads((ROOT/'local-outputs/conflation/nus/run_manifest.json').read_text())
    campus=box(*prior['core_bounds_epsg3414'])
    boundary=ROOT/'local-data/boundaries/MasterPlan2025PlanningAreaBoundaryNoSea.geojson'
    if nus:mask=campus
    else:
        areas=gpd.read_file(boundary).to_crs(3414)
        mask=shapely.union_all(areas.geometry.to_numpy()).buffer(20)
    paths={'processed_lta':ROOT/'local-data/lta/road singapore.geojson',
           'osm':ROOT/'local-data/osm/Singapore-shp/shape/roads.shp',
           'website':ROOT/'website/data/gap_segments.geojson'}
    source_hashes={name:sha(path) for name,path in paths.items()}
    frames={name:gpd.read_file(path).to_crs(3414) for name,path in paths.items()}
    roads={};metadata={};profiles={};conflicts=set()
    for name in ['processed_lta','osm']:
        r,info,profile,grade=prepare_roads(frames[name],name,campus.buffer(300) if nus else mask,lookup,barriers,campus.buffer(300),clip=not nus)
        roads[name]=r;metadata.update(info);profiles[name]=profile;conflicts.update(grade)
    for uid,info in metadata.items():
        if info['matched_way_id'] in conflicts:info['grade_conflict']=True
    from conflate import website_roads
    reference=website_roads(frames['website'],mask.buffer(375) if nus else None)
    existing=website_roads(frames['website'],mask if nus else None)
    run_data=dict(roads=roads,metadata=metadata,reference=reference,existing=existing,source_hashes=source_hashes,
                  mask=mask,profiles=profiles,grade_conflict_way_ids=sorted(conflicts),pbf_cache=str(pbf_path),nus=nus)
    dump(cache/'prepared.pkl',run_data)
    (output/'input_profiles.json').write_text(json.dumps(profiles,indent=2))
    gpd.GeoDataFrame({'name':['NUS pilot' if nus else 'Master Plan 2025 study area +20m'],'geometry':[mask]},crs=3414).to_file(cache/'study_area.gpkg',layer='study_area',driver='GPKG')
    return run_data
