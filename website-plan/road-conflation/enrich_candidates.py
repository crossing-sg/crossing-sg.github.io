"""NUS-only OSM tag enrichment and grouped review; never modifies prior outputs.

Run fetch_osm_pbf.py and extract_nus_pbf.py first. Current OSM way IDs require
geometric corroboration; a primary source_id is never treated as proof alone.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

from conflate import ROOT,angle,tangent
from refine_candidates import A,B,C,COLORS,NON_ROADS,OUT_OF_SCOPE,VEHICULAR,layer_style,single_line,value,flag,numeric
from extract_nus_pbf import TAGS

POSITIVE={'yes','permissive','designated'}
RESTRICTED={'no','private','customers','delivery','destination','permit','agricultural','forestry'}
CAMPUS_NAMES={'kent ridge crescent','kent ridge drive','lower kent ridge road','computing drive',
              'research link','sports drive','business link','arts link','architecture drive',
              'conservatory drive','estate office drive','hon sui sen drive','college link',
              "prince george's park",'kent ridge terminal','arrival plaza'} | {
                  f'{stem} {n}' for stem in ['engineering drive','science drive'] for n in range(1,5)}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path,data):
    Path(path).write_text(json.dumps(data,indent=2,default=lambda v:v.item() if hasattr(v,'item') else str(v)),encoding='utf-8')


def geometry_evidence(candidate,way):
    line=single_line(candidate)
    cuts=np.linspace(0,line.length,max(2,int(np.ceil(line.length/2)))+1)
    measures=np.unique(np.r_[cuts,(cuts[:-1]+cuts[1:])/2])
    distances=[];angles=[]
    for at in measures:
        point=line.interpolate(float(at));position=way.project(point)
        distances.append(point.distance(way))
        angles.append(angle(tangent(line,float(at)),tangent(way,position)))
    projected=[way.project(line.interpolate(float(at))) for at in measures]
    ratio=(max(projected)-min(projected))/line.length
    overlap=line.intersection(way.buffer(1,cap_style=2)).length/line.length
    maximum=float(max(distances));p95=float(np.quantile(distances,.95));median_angle=float(np.median(angles))
    accepted=(maximum<=1 and p95<=.5 and ratio>=.75 and overlap>=.95
              and (median_angle<=15 or maximum<.02))
    return dict(max_offset_m=maximum,p95_offset_m=p95,median_angle_deg=median_angle,
                length_correspondence_ratio=ratio,one_m_corridor_overlap=overlap,accepted=bool(accepted))


def compatible_class(old,highway):
    return old==highway or (old in VEHICULAR and highway in VEHICULAR)


def link_one(row,ways,lookup,tree):
    sid=int(row.source_id) if str(row.source_id).isdigit() else None
    same=lookup.get(sid)
    id_evidence=geometry_evidence(row.geometry,ways.geometry.iloc[same]) if same is not None else None
    untrusted_tags=ways.iloc[same].all_tags_json if same is not None else '{}'
    candidates=[]
    if id_evidence and id_evidence['accepted']:
        chosen=same;method='identifier_plus_geometry';metrics=id_evidence
    else:
        for j in tree.query(row.geometry,predicate='dwithin',distance=5):
            j=int(j);way=ways.iloc[j]
            if not compatible_class(value(row.road_class),value(way.highway)):continue
            if value(row['name']) and value(way['name']) and value(row['name'])!=value(way['name']):continue
            metrics=geometry_evidence(row.geometry,way.geometry)
            if metrics['accepted']:candidates.append((j,metrics))
        if len(candidates)==1:
            chosen,metrics=candidates[0];method='unique_spatial_fallback'
        else:
            chosen=None;metrics=id_evidence or {};method='unresolved_geometry_or_ambiguous_fallback'
    result=dict(fragment_uid=row.fragment_uid,id_found=same is not None,id_geometry_valid=bool(id_evidence and id_evidence['accepted']),
                id_geometry_max_offset_m=id_evidence['max_offset_m'] if id_evidence else None,
                match_method=method,matched_way_id=int(ways.iloc[chosen].way_id) if chosen is not None else None,
                fallback_qualified_count=len(candidates),fallback_way_ids_json=json.dumps([int(ways.iloc[j].way_id) for j,_ in candidates]),
                tags_applied=chosen is not None,unverified_same_id_tags_json=untrusted_tags if method!='identifier_plus_geometry' else '{}',
                evidence_metrics_json=json.dumps(metrics),match_max_offset_m=metrics.get('max_offset_m'),
                match_angle_median_deg=metrics.get('median_angle_deg'),match_overlap_fraction=metrics.get('one_m_corridor_overlap'))
    tags=json.loads(ways.iloc[chosen].all_tags_json) if chosen is not None else {}
    result.update({f'osm_{key}':tags.get(key,'') for key in TAGS})
    result['osm_all_tags_json']=json.dumps(tags,sort_keys=True)
    result['osm_node_ids_json']=ways.iloc[chosen].node_ids_json if chosen is not None else '[]'
    result['osm_version']=int(ways.iloc[chosen].osm_version) if chosen is not None else None
    result['osm_timestamp']=ways.iloc[chosen].osm_timestamp if chosen is not None else ''
    result['class_conflict']=bool(chosen is not None and value(row.road_class)!=value(tags.get('highway')))
    return result


def effective_access(tags,keys):
    for key in keys:
        tag=value(tags.get(key))
        if tag:return tag,key
    return 'unknown','not_tagged'


def service_evidence(tags,linked):
    if not linked:return 'insufficient_link_evidence'
    highway=value(tags.get('highway'));service=value(tags.get('service'))
    motor,_=effective_access(tags,['motor_vehicle','vehicle','access'])
    foot,_=effective_access(tags,['foot','access'])
    if motor in RESTRICTED or foot in RESTRICTED:return 'explicit_access_restriction'
    if service in {'parking_aisle','driveway','drive-through','drive_through','emergency_access'}:return 'parking_driveway_or_special_access'
    if highway=='service' and motor in POSITIVE:return 'positive_motor_access_service_road'
    if highway=='service':return 'service_purpose_or_access_insufficient'
    return 'other_vehicular_class'


def classify_enriched(row,tags):
    """Conservative eligibility. Missing access never supplies positive permission."""
    if not flag(row.get('tags_applied')):
        return C,'unresolved_original_id_or_spatial_link'
    highway=value(tags.get('highway'));service=value(tags.get('service'))
    if flag(row.get('class_conflict')):
        return C,'OSM_highway_class_differs_from_original_requires_review'
    if highway in NON_ROADS|OUT_OF_SCOPE:return B,'verified_non_road_or_out_of_scope_OSM_class'
    motor,motor_key=effective_access(tags,['motor_vehicle','vehicle','access'])
    pedestrian,foot_key=effective_access(tags,['foot','access'])
    reasons=[]
    # More-specific mode tags may override general access, but conflicting positive
    # overrides of explicit private/no are kept for review rather than silently public.
    if motor in RESTRICTED:reasons.append(f'explicit_motor_access_{motor}')
    if pedestrian in RESTRICTED:reasons.append(f'explicit_pedestrian_access_{pedestrian}')
    if value(tags.get('access')) in RESTRICTED and motor in POSITIVE:
        reasons.append('conflicting_general_and_motor_access_needs_review')
    if flag(row.get('barrier_restriction')):reasons.append('associated_OSM_barrier_restriction')
    if flag(row.get('parallel_evidence')):reasons.append('independent_parallel_still_requires_review')
    if value(row.get('spatial_flag')):reasons.append('prior_displacement_or_parallel_flag')
    if numeric(row.get('parent_uncertain_m'))>1:reasons.append('prior_parent_spatial_uncertainty')
    if flag(row.get('boundary')):reasons.append('pilot_boundary_clipping')
    if value(tags.get('bridge')) in {'yes','true','1'} or value(tags.get('tunnel')) in {'yes','true','1'} or numeric(tags.get('layer'))!=0:
        reasons.append('grade_or_crossing_suitability_review')
    if service in {'parking_aisle','driveway','drive-through','drive_through','emergency_access'}:
        reasons.append(f'identified_service_{service}_policy_review')
    if highway=='service':
        if motor not in POSITIVE:reasons.append('no_positive_motor_access_tag')
        if value(tags.get('name')) and any(word in value(tags.get('name')) for word in ['car park','parking','condo','entrance','exit']):
            reasons.append('parking_or_development_access_name_context')
        # Lanes/sidewalk/turn markings are positive evidence of a vehicular route,
        # not evidence of public access. They are exposed to reviewers separately.
        if not (numeric(tags.get('lanes'))>=1 or service=='alley' or value(tags.get('name'))):
            reasons.append('vehicular_connector_role_not_established')
    elif highway not in VEHICULAR:
        reasons.append('road_class_crossing_policy_review')
    if reasons:return C,';'.join(sorted(set(reasons)))
    if highway=='service':return A,f'OSM_{motor_key}_{motor}_plus_vehicular_route_evidence'
    return A,'vehicular_road_class_retained_access_unknown' if motor=='unknown' else f'vehicular_road_with_OSM_{motor_key}_{motor}'


def attach_barriers(data,barriers):
    by_node={int(r.node_id):r for _,r in barriers.iterrows()} if len(barriers) else {}
    result=[]
    for _,row in data.iterrows():
        ids=[n for n in json.loads(row.osm_node_ids_json) if int(n) in by_node]
        restrictions=[]
        for n in ids:
            item=by_node[int(n)]
            # A whole-way node can lie outside this particular source interval.
            if item.geometry.distance(row.geometry)>2:continue
            if any(value(item.get(key)) in RESTRICTED for key in ['access','vehicle','motor_vehicle','foot']):
                restrictions.append(int(n))
        result.append((json.dumps(ids),json.dumps(restrictions),bool(restrictions)))
    data['associated_barrier_ids_json']=[r[0] for r in result]
    data['restricted_barrier_ids_json']=[r[1] for r in result]
    data['barrier_restriction']=[r[2] for r in result]
    return data


def grouping_partition(row,tile_m=200):
    name=value(row.get('review_name'))
    point=row.geometry.interpolate(.5,normalized=True)
    location=f'name:{name}' if name else f'neighbourhood:{int(np.floor(point.x/tile_m))}:{int(np.floor(point.y/tile_m))}'
    risk='geometry' if row.match_method.startswith('unresolved') or value(row.spatial_flag) or flag(row.parallel_evidence) else 'ordinary'
    return (row.enriched_category,location,row.service_group,value(row.get('osm_service')) or 'not_tagged',row.effective_motor_access,row.effective_foot_access,risk)


def make_groups(data):
    """Two review levels: way identity, then named routes/compact connected areas."""
    g=data.copy();g['review_name']=[str(r.osm_name or r['name'] or '') for _,r in g.iterrows()]
    g['campus_named']=[value(name) in CAMPUS_NAMES for name in g.review_name]
    g['atomic_way_key']=[f'osm-way:{int(r.matched_way_id)}' if pd.notna(r.matched_way_id) else f'unlinked:{r.fragment_uid}' for _,r in g.iterrows()]
    geometry=[single_line(shape) for shape in g.geometry]
    tree=STRtree(geometry);graph=nx.Graph();graph.add_nodes_from(range(len(g)))
    partitions=[grouping_partition(row) for _,row in g.iterrows()]
    node_sets=[set(json.loads(item)) for item in g.osm_node_ids_json]
    atomic=defaultdict(list)
    for i,(_,row) in enumerate(g.iterrows()):atomic[(row.atomic_way_key,partitions[i])].append(i)
    for members in atomic.values():
        for i in members[1:]:graph.add_edge(members[0],i)
    for i,line in enumerate(geometry):
        row=g.iloc[i]
        for j in tree.query(line,predicate='dwithin',distance=15):
            j=int(j)
            if j<=i or partitions[i]!=partitions[j]:continue
            other=g.iloc[j]
            if value(row.osm_layer)!=value(other.osm_layer) or value(row.osm_bridge)!=value(other.osm_bridge) or value(row.osm_tunnel)!=value(other.osm_tunnel):continue
            if value(row.review_name):connect=True
            else:
                shared=bool(node_sets[i]&node_sets[j])
                endpoints=[Point(line.coords[0]),Point(line.coords[-1])]
                other_ends=[Point(geometry[j].coords[0]),Point(geometry[j].coords[-1])]
                connect=shared or any(p.distance(geometry[j])<=3 for p in endpoints) or any(p.distance(line)<=3 for p in other_ends)
            if connect:graph.add_edge(i,j)
    rows=[];membership={}
    for members in nx.connected_components(graph):
        indices=sorted(members);subset=g.iloc[indices]
        ids=sorted(subset.fragment_uid)
        group_id='RG-'+hashlib.sha256('|'.join(ids).encode()).hexdigest()[:12]
        names=sorted({n for n in subset.review_name if n})
        campus=bool(subset.campus_named.any());kent=any(value(n) in {'kent ridge crescent','kent ridge drive'} for n in names)
        risk=bool(subset.match_method.str.startswith('unresolved').any() or subset.spatial_flag.fillna('').ne('').any() or subset.parallel_evidence.fillna(False).any())
        bucket=subset.service_group.iloc[0]
        if kent:priority,action=1,'Confirm Kent Ridge corridor access and candidate eligibility'
        elif campus:priority,action=1,'Verify NUS internal-road access and crossing eligibility as one corridor'
        elif risk:priority,action=2,'Resolve identifier/geometry or displaced-versus-parallel road evidence'
        elif bucket in {'insufficient_link_evidence','service_purpose_or_access_insufficient'}:
            priority,action=2,'Inspect connected vehicular function and access; do not infer public from missing tags'
        elif bucket=='explicit_access_restriction':priority,action=3,'Review restricted access policy; retain possible campus crossing locations'
        elif bucket=='parking_driveway_or_special_access':priority,action=4,'Bulk-review identified parking/driveway subtype against crossing proposal policy'
        else:priority,action=3,'Confirm road-class and public proposal eligibility'
        center=unary_union(subset.geometry.tolist()).centroid
        rows.append(dict(group_id=group_id,priority=priority,category=subset.enriched_category.iloc[0],
                         road_names='; '.join(names) or '(unnamed local connected group)',
                         interval_count=len(subset),distinct_verified_ways=subset.matched_way_id.nunique(),length_m=float(subset.length_m.sum()),
                         service_group=bucket,effective_motor_access=subset.effective_motor_access.iloc[0],
                         effective_foot_access=subset.effective_foot_access.iloc[0],campus_named=campus,kent_corridor=kent,geometry_risk=risk,
                         service_subtypes='; '.join(sorted({value(s) or 'not_tagged' for s in subset.osm_service})),
                         access_tag_values='; '.join(sorted({value(s) or 'not_tagged' for s in subset.osm_access})),
                         decision_reasons_json=json.dumps(sorted(set(subset.enrichment_decision))),
                         barrier_restriction_intervals=int(subset.barrier_restriction.sum()),
                         max_link_offset_m=float(subset.match_max_offset_m.max()) if subset.match_max_offset_m.notna().any() else None,
                         link_methods='; '.join(sorted(set(subset.match_method))),
                         review_action=action,fragment_uids_json=json.dumps(ids),
                         verified_way_ids_json=json.dumps(sorted({int(x) for x in subset.matched_way_id.dropna()})),
                         original_source_ids_json=json.dumps(sorted(set(subset.source_id))),
                         easting=center.x,northing=center.y,geometry=unary_union(subset.geometry.tolist())))
        for index in indices:membership[index]=group_id
    g['review_group_id']=[membership[i] for i in range(len(g))]
    groups=gpd.GeoDataFrame(rows,geometry='geometry',crs=3414).sort_values(['priority','kent_corridor','geometry_risk','campus_named','length_m','group_id'],ascending=[True,False,False,False,False,True]).reset_index(drop=True)
    groups['priority_rank']=np.arange(1,len(groups)+1)
    ranks=groups.set_index('group_id').priority_rank.to_dict()
    g['review_priority_rank']=g.review_group_id.map(ranks)
    way_rows=g.groupby(['atomic_way_key','enriched_category'],dropna=False).agg(intervals=('fragment_uid','size'),length_m=('length_m','sum'),
                                                                                 review_groups=('review_group_id','nunique')).reset_index()
    return g,groups,way_rows


def make_review_batches(data,groups):
    """Further reduce work using named-corridor or compact area-policy batches.

    Unlike road groups, a batch can contain disconnected roads and never asserts
    common physical identity. Membership and mixed evidence remain explicit.
    """
    manual=groups[groups.category==C]
    partitions=defaultdict(list)
    for index,row in manual.iterrows():
        if row.road_names!='(unnamed local connected group)':
            key=('named_corridor',value(row.road_names))
        else:
            key=('local_area_policy',int(np.floor(row.easting/400)),int(np.floor(row.northing/400)),
                 row.service_group,row.service_subtypes,row.effective_motor_access,row.effective_foot_access,bool(row.geometry_risk))
        partitions[key].append(index)
    rows=[];mapping={}
    for key,indices in partitions.items():
        subset=manual.loc[indices]
        ids=sorted(subset.group_id)
        uid='RB-'+hashlib.sha256('|'.join(ids).encode()).hexdigest()[:12]
        named=key[0]=='named_corridor'
        center=unary_union(subset.geometry.tolist()).centroid
        rows.append(dict(batch_id=uid,batch_kind=key[0],road_or_area=subset.road_names.iloc[0] if named else f'Local area at SVY21 {center.x:.0f}, {center.y:.0f}',
                         priority=int(subset.priority.min()),first_road_group_rank=int(subset.priority_rank.min()),
                         road_group_count=len(subset),interval_count=int(subset.interval_count.sum()),length_m=float(subset.length_m.sum()),
                         service_subtypes='; '.join(sorted(set(subset.service_subtypes))),
                         motor_permission_values='; '.join(sorted(set(subset.effective_motor_access))),
                         foot_permission_values='; '.join(sorted(set(subset.effective_foot_access))),
                         geometry_risk=bool(subset.geometry_risk.any()),road_group_ids_json=json.dumps(ids),
                         review_action='Review corridor with its permission/geometry subgroups; no blanket approval' if named else 'Bulk-review local roads sharing subtype and permission evidence; retain individual road decisions',
                         geometry=unary_union(subset.geometry.tolist())))
        for group_id in ids:mapping[group_id]=uid
    batches=gpd.GeoDataFrame(rows,geometry='geometry',crs=3414).sort_values(['priority','first_road_group_rank','length_m'],ascending=[True,True,False]).reset_index(drop=True)
    batches['batch_priority_rank']=np.arange(1,len(batches)+1)
    data=data.copy();groups=groups.copy()
    data['review_batch_id']=data.review_group_id.map(mapping).fillna('')
    groups['review_batch_id']=groups.group_id.map(mapping).fillna('')
    assert batches.interval_count.sum()==data.enriched_category.eq(C).sum()
    return data,groups,batches


def package_outputs(path,data,groups,batches,prior_layers,ways):
    if path.exists():path.unlink()
    layers={'website_roads':prior_layers['website_roads'],'enriched_candidates':data,
            'A_eligible_candidates':data[data.enriched_category==A],
            'B_excluded_candidates':data[data.enriched_category==B],
            'C_uncertain_candidates':data[data.enriched_category==C],
            'C_manual_review_groups':groups[groups.category==C],
            'all_priority_groups':groups,
            'C_review_batches':batches,
            'B_excluded_context':prior_layers['B_excluded_context'],
            'C_spatial_review_context':prior_layers['C_spatial_review_context'],
            'matched_PBF_ways':ways[ways.way_id.isin(data.matched_way_id.dropna())],
            'pilot_boundary':prior_layers['pilot_boundary']}
    styles={}
    for name,frame in layers.items():
        frame=frame.copy()
        if 'seg_id' in frame:frame['seg_id']=frame.seg_id.astype('Int64')
        for col in ['matched_way_id','osm_version']:
            if col in frame:frame[col]=frame[col].astype('Int64')
        for col in ['id_found','id_geometry_valid','tags_applied','class_conflict','barrier_restriction','campus_named','geometry_risk',
                    'kent_corridor','boundary','parallel_evidence','component_connected','public_access_verified','parking_name_hint','entrance_driveway_name_hint']:
            if col in frame:frame[col]=pd.array(frame[col],dtype='boolean')
        pyogrio.write_dataframe(frame,path,layer=name,driver='GPKG',promote_to_multi=True)
        code='existing' if name=='website_roads' else {'A':A,'B':B,'C':C}.get(name[:1])
        if code in COLORS:styles[name]=layer_style(COLORS[code],code==B)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,f_table_catalog TEXT,f_table_schema TEXT,f_table_name TEXT,f_geometry_column TEXT,styleName TEXT,styleQML TEXT,styleSLD TEXT,useAsDefault BOOLEAN,description TEXT,owner TEXT,ui TEXT,update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        columns=dict(db.execute('SELECT table_name,column_name FROM gpkg_geometry_columns'))
        for name,qml in styles.items():
            ET.fromstring(qml)
            db.execute('INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,styleName,styleQML,useAsDefault) VALUES (?,?,?,?,?,?,?)',
                       ('','',name,columns[name],'NUS enriched eligibility',qml,1))
        db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    for name,frame in layers.items():
        actual=gpd.read_file(path,layer=name)
        assert len(actual)==len(frame) and actual.crs.to_epsg()==3414
        assert actual.geometry.is_valid.all() and not actual.geometry.is_empty.any()
        if 'fragment_uid' in frame and len(frame):
            assert frame.fragment_uid.tolist()==actual.fragment_uid.tolist()
            assert all(shapely.equals_exact(a,b,1e-8) for a,b in zip(frame.geometry,actual.geometry))
    return layers


def run(args):
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='feature/road-network-conflation':raise RuntimeError('Wrong branch')
    output=ROOT/'local-outputs/conflation/nus-enriched'
    old=ROOT/'local-outputs/conflation/nus-refined/nus_refined.gpkg'
    source=output/'pbf_nus_extract.gpkg'
    if not source.exists():raise RuntimeError('Run extract_nus_pbf.py first.')
    prior_layers={name:gpd.read_file(old,layer=name) for name in ['website_roads','original_candidates','B_excluded_context','C_spatial_review_context','pilot_boundary']}
    data=prior_layers['original_candidates'].copy()
    assert len(data)==763 and data.fragment_uid.is_unique
    ways=gpd.read_file(source,layer='highway_ways').reset_index(drop=True)
    barriers=gpd.read_file(source,layer='barrier_nodes')
    lookup={int(row.way_id):i for i,row in ways.iterrows()};tree=STRtree(ways.geometry.to_numpy())
    print('Validating original IDs against PBF geometry; trying unique spatial fallback where needed.',flush=True)
    links=pd.DataFrame([link_one(row,ways,lookup,tree) for _,row in data.iterrows()])
    data=data.merge(links,on='fragment_uid',how='left',validate='one_to_one')
    data=attach_barriers(data,barriers)
    categories=[];reasons=[];buckets=[];motors=[];feet=[];role=[]
    for _,row in data.iterrows():
        tags=json.loads(row.osm_all_tags_json)
        category,reason=classify_enriched(row,tags)
        categories.append(category);reasons.append(reason);buckets.append(service_evidence(tags,row.tags_applied))
        motors.append(effective_access(tags,['motor_vehicle','vehicle','access'])[0]);feet.append(effective_access(tags,['foot','access'])[0])
        positive_role=numeric(tags.get('lanes'))>=1 and (value(tags.get('sidewalk')) not in {'','no','none'} or any(k.startswith('turn:lanes') for k in tags))
        role.append('lanes_plus_sidewalk_or_turn_markings' if positive_role else 'limited_route_role_evidence')
    data['enriched_category']=categories;data['enrichment_decision']=reasons;data['service_group']=buckets
    data['effective_motor_access']=motors;data['effective_foot_access']=feet;data['vehicular_route_role_evidence']=role
    data['previous_category']=data.category;data['public_access_verified']=False
    data,groups,way_groups=make_groups(data)
    data,groups,batches=make_review_batches(data,groups)
    data=gpd.GeoDataFrame(data,geometry='geometry',crs=3414)
    assert data.fragment_uid.tolist()==prior_layers['original_candidates'].fragment_uid.tolist()
    assert all(shapely.equals_exact(a,b,0) for a,b in zip(data.geometry,prior_layers['original_candidates'].geometry))
    manual=groups[groups.category==C].copy()
    manual['manual_review_rank']=np.arange(1,len(manual)+1)
    manual.drop(columns='geometry').to_csv(output/'grouped_manual_review.csv',index=False)
    groups.drop(columns='geometry').to_csv(output/'all_prioritised_road_groups.csv',index=False)
    way_groups.to_csv(output/'way_level_review_groups.csv',index=False)
    batches.drop(columns='geometry').to_csv(output/'prioritised_review_batches.csv',index=False)
    data.drop(columns='geometry').to_csv(output/'enriched_candidate_register.csv',index=False)
    data[['fragment_uid','review_group_id','review_batch_id','review_priority_rank','matched_way_id','source_id','review_name','enriched_category']].to_csv(output/'group_membership.csv',index=False)
    links.to_csv(output/'OSM_way_link_audit.csv',index=False)
    data.groupby(['previous_category','enriched_category'],dropna=False).agg(intervals=('fragment_uid','size'),length_m=('length_m','sum')).reset_index().to_csv(output/'classification_change_matrix.csv',index=False)
    data.groupby(['dataset','road_class','enriched_category','service_group','osm_service','effective_motor_access'],dropna=False).agg(intervals=('fragment_uid','size'),length_m=('length_m','sum')).reset_index().to_csv(output/'classification_summary.csv',index=False)
    coverage=[]
    for scope,subset in [('all_763',data),('service_590',data[data.road_class=='service'])]:
        for tag in TAGS:
            tagged=subset[f'osm_{tag}'].fillna('').ne('') & subset.tags_applied
            coverage.append(dict(scope=scope,tag=tag,tagged_intervals=int(tagged.sum()),tagged_length_m=float(subset.loc[tagged,'length_m'].sum()),
                                 linked_intervals=int(subset.tags_applied.sum()),total_intervals=len(subset)))
    pd.DataFrame(coverage).to_csv(output/'recovered_tag_coverage.csv',index=False)
    layers=package_outputs(output/'nus_enriched.gpkg',data,groups,batches,prior_layers,ways)
    from enrichment_report import create_maps,create_report
    create_maps(output,data,groups,prior_layers)
    stats={code:dict(intervals=int(data.enriched_category.eq(code).sum()),length_m=float(data.loc[data.enriched_category==code,'length_m'].sum())) for code in [A,B,C]}
    assert sum(x['intervals'] for x in stats.values())==763
    assert abs(sum(x['length_m'] for x in stats.values())-28688.022771200976)<1e-6
    extraction=json.loads((output/'pbf_extraction_manifest.json').read_text())
    result=dict(created_singapore=datetime.now(timezone(timedelta(hours=8))).isoformat(),counts=stats,
                previous_counts=dict(A_eligible=161,B_excluded=0,C_manual_review=602),
                matches=data.match_method.value_counts().to_dict(),tagged_service_groups=data.loc[data.road_class=='service'].service_group.value_counts().to_dict(),
                manual_intervals=int(data.enriched_category.eq(C).sum()),manual_review_groups=len(manual),manual_review_batches=len(batches),all_review_groups=len(groups),
                service_manual_intervals=int(((data.road_class=='service') & data.enriched_category.eq(C)).sum()),
                service_manual_groups=int(data.loc[(data.road_class=='service') & data.enriched_category.eq(C),'review_group_id'].nunique()),
                pbf_snapshot=extraction['header'],pbf_sha256=extraction['pbf_sha256'],raw_PBF_original_sha256=sha(ROOT/'local-data/osm/pbf/Singapore.osm.pbf'),
                source_prior_gpkg_sha256=sha(old),code_sha256={p.name:sha(p) for p in Path(__file__).parent.iterdir() if p.name in ['enrich_candidates.py','enrichment_report.py','requirements-enrichment.txt','extract_nus_pbf.py','fetch_osm_pbf.py','test_enrich_candidates.py']},
                grouped_review_policy=dict(unnamed_neighbourhood_grid_m=200,unnamed_endpoint_connect_m=3,named_continuity_gap_m=15,
                                           original_way_plus_category_access_and_geometry_evidence=True),
                source_id_provenance='ID plus geometry supports current OSM tag association, not original primary provenance.',
                public_access_verified=False,whole_island_conflation=False,
                style_and_validation=dict(candidate_ids_geometry_length_preserved=True,all_geometries_valid=True,GPKG_layers_reopened=True),
                outputs={name:len(frame) for name,frame in layers.items()})
    create_report(output,data,groups,result)
    write_json(output/'enrichment_manifest.json',result)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    run(parser.parse_args())
