"""Refine the existing NUS 10 m pilot; never runs whole-island conflation.

All outputs go to a new ignored directory. Original candidate IDs/geometries and
the existing pilot, website, backend and source datasets remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from conflate import (ROOT, Config, Index, angle, candidate_duplicate_review,
                      fragment_references, geom_key, line_parts, match_stage,
                      normalize_sources, reconcile_parents, tangent, website_roads)

A, B, C = 'A_eligible', 'B_excluded', 'C_manual_review'
NON_ROADS = {'footway','pedestrian','cycleway','steps','path','bridleway','corridor','elevator','crossing','bus_stop'}
OUT_OF_SCOPE = {'motorway','motorway_link','construction','proposed','raceway','rest_area','services'}
VEHICULAR = {'residential','living_street','primary','secondary','tertiary','unclassified'}
RESTRICTED = {'private','no','customers','delivery','destination','permit','agricultural','forestry'}
COLORS = {'existing':'#244d70',A:'#00845c',B:'#9aa1a8',C:'#d16a13'}


def value(item):
    return '' if item is None or pd.isna(item) else str(item).strip().lower()


def flag(item):
    return value(item) in {'true','1','yes','t'}


def single_line(geometry):
    parts=line_parts(geometry)
    if len(parts)!=1:
        raise ValueError('A candidate interval must contain exactly one LineString.')
    return parts[0]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path,data):
    Path(path).write_text(json.dumps(data,indent=2,default=lambda v:v.item() if hasattr(v,'item') else str(v)),encoding='utf-8')


def decide(row, tags=None):
    """Road-type eligibility is separate from verified public access.

    Service-road names never prove service subtype/access; unsupported features
    stay visible for manual review. Spatial concerns override eligible types.
    """
    tags=tags or {}
    kind=value(row.get('road_class'))
    if kind in NON_ROADS:
        return B,'non_vehicular_or_path_class'
    if kind in OUT_OF_SCOPE:
        return B,'out_of_scope_or_non_operational_road'
    reasons=[]
    for key in ('access','vehicle','motor_vehicle','motorcar'):
        if value(tags.get(key)) in RESTRICTED:
            reasons.append('explicit_access_restriction')
    service=value(tags.get('service'))
    if service in {'parking_aisle','driveway','drive-through','drive_through','emergency_access'}:
        reasons.append('parking_driveway_or_restricted_service_subtype')
    if flag(row.get('parallel_evidence')):
        reasons.append('parallel_road_requires_review')
    if value(row.get('spatial_flag')):
        reasons.append(value(row['spatial_flag']))
    if numeric(row.get('parent_uncertain_m'))>1:
        reasons.append('source_parent_contains_unresolved_spatial_match')
    if flag(row.get('boundary')):
        reasons.append('pilot_boundary_clipped_source')
    if flag(row.get('bridge')) or flag(row.get('tunnel')) or numeric(row.get('layer'))!=0:
        reasons.append('grade_or_crossing_suitability_requires_review')
    if kind=='service':
        # Explicit positive access and a clear vehicular subtype are required.
        # No supplied source has these fields; none are invented from road names.
        if not (value(tags.get('access')) in {'yes','permissive','designated'} and service=='alley'):
            reasons.append('service_subtype_and_access_unavailable_or_ambiguous')
    elif kind not in VEHICULAR:
        reasons.append('road_class_requires_crossing_suitability_review')
    if reasons:
        return C,';'.join(sorted(set(reasons)))
    return A,'vehicular_class_and_no_detected_spatial_conflict_access_unverified'


def numeric(item):
    try:
        return float(item) if item is not None and pd.notna(item) else 0.
    except (ValueError,TypeError):
        return 0.


def spatial_audit(candidates, website):
    """Independent second look, with 2 m samples and wider/looser retrieval.

    Direction, projected length and actual corridor overlap are all required to
    flag a potential displaced/parallel representation. Flags cause review only.
    """
    refs=[single_line(g) for g in website.geometry]
    tree=STRtree(refs)
    buffers={}
    result=[]
    for _,row in candidates.iterrows():
        line=single_line(row.geometry)
        cuts=np.linspace(0,line.length,max(1,int(np.ceil(line.length/2)))+1)
        weights=np.diff(cuts)
        points=[line.interpolate((a+b)/2) for a,b in zip(cuts[:-1],cuts[1:])]
        distances=np.full(len(points),np.inf)
        angles=np.full(len(points),np.nan)
        ratios=np.full(len(points),np.nan)
        chosen=set()
        for n,(point,a,b) in enumerate(zip(points,cuts[:-1],cuts[1:])):
            d=tangent(line,(a+b)/2)
            possible=[]
            for j in tree.query(point,predicate='dwithin',distance=50):
                ref=refs[int(j)]
                at=ref.project(point)
                rd=tangent(ref,at)
                delta=angle(d,rd)
                ratio=abs(ref.project(line.interpolate(b))-ref.project(line.interpolate(a)))/(b-a)
                closest=ref.interpolate(at)
                longitudinal=abs(float(np.dot([point.x-closest.x,point.y-closest.y],rd)))
                if delta<=30 and ratio>=.3 and longitudinal<=5:
                    distance=point.distance(ref)
                    possible.append((distance,delta,ratio,int(j)))
            if possible:
                distance,delta,ratio,j=min(possible)
                distances[n],angles[n],ratios[n]=distance,delta,ratio
                chosen.add(j)
        stats={'fragment_uid':row.fragment_uid}
        for threshold in (3,5,10,20,30,50):
            stats[f'aligned_fraction_{threshold}m']=float(weights[distances<=threshold].sum()/line.length)
        for threshold in (5,20,30):
            corridor=[]
            for j in chosen:
                key=(j,threshold)
                if key not in buffers:
                    buffers[key]=refs[j].buffer(threshold,cap_style=2)
                corridor.append(buffers[key])
            stats[f'overlap_fraction_{threshold}m']=line.intersection(unary_union(corridor)).length/line.length if corridor else 0.
        finite=distances[np.isfinite(distances)]
        stats['aligned_distance_median_m']=float(np.median(finite)) if len(finite) else None
        stats['aligned_angle_median_deg']=float(np.nanmedian(angles)) if np.isfinite(angles).any() else None
        _,nearest=tree.query_nearest(points,all_matches=False,return_distance=True)
        stats['nearest_geometry_median_m']=float(np.median(nearest))
        stats['nearest_geometry_minimum_m']=float(np.min(nearest))
        if stats['aligned_fraction_3m']>=.8 and stats['overlap_fraction_5m']>=.8:
            stats['spatial_flag']='possible_duplicate_existing_road'
        elif stats['aligned_fraction_20m']>=.6 and stats['overlap_fraction_20m']>=.6:
            stats['spatial_flag']='possible_displacement_or_parallel_within_20m'
        elif stats['aligned_fraction_30m']>=.8 and stats['overlap_fraction_30m']>=.8:
            stats['spatial_flag']='possible_wide_displacement_or_parallel_within_30m'
        else:
            stats['spatial_flag']=''
        result.append(stats)
    return pd.DataFrame(result)


def classify(candidates, parents, audit, raw_tags):
    data=candidates.copy(deep=True)
    parent_lookup=parents.set_index('uid')
    data=data.merge(audit,on='fragment_uid',how='left',validate='one_to_one')
    data['parent_status']=[parent_lookup.loc[uid,'status'] for uid in data.parent_uid]
    data['parent_uncertain_m']=[numeric(parent_lookup.loc[uid,'uncertain_m']) for uid in data.parent_uid]
    data['access_status']='not_available'
    data['access_value']='unknown'
    data['service_subtype']='unknown'
    data['public_access_verified']=False
    data['scope']='original_763_candidates'
    data['parking_name_hint']=data.name.fillna('').str.contains(r'car\s*park|parking',case=False,regex=True)
    data['entrance_driveway_name_hint']=data.name.fillna('').str.contains(r'entrance|exit|driveway|private|condo',case=False,regex=True)
    categories,reasons,access_status,access_values,subtypes=[],[],[],[],[]
    for _,row in data.iterrows():
        tags=raw_tags.get((row.dataset,str(row.source_id)),{})
        category,reason=decide(row,tags)
        categories.append(category);reasons.append(reason)
        access={key:value(tags.get(key)) for key in ['access','vehicle','motor_vehicle','motorcar'] if value(tags.get(key))}
        access_status.append('reported_not_independently_verified' if access else 'not_available')
        access_values.append(json.dumps(access,sort_keys=True) if access else 'unknown')
        subtypes.append(value(tags.get('service')) or 'unknown')
    data['access_status']=access_status;data['access_value']=access_values;data['service_subtype']=subtypes
    data['category']=categories
    data['classification_reason']=reasons
    # The geometries and interval identifiers are unchanged, in original order.
    assert data.fragment_uid.tolist()==candidates.fragment_uid.tolist()
    assert all(shapely.equals_exact(a,b,0) for a,b in zip(data.geometry,candidates.geometry))
    assert abs(data.length_m.sum()-candidates.length_m.sum())<1e-6
    return gpd.GeoDataFrame(data,geometry='geometry',crs=candidates.crs)


def summarize(frame, groups):
    return frame.groupby(groups,dropna=False).agg(intervals=('fragment_uid','size'),
                                               source_features=('source_id','nunique'),length_m=('length_m','sum')).reset_index()


def stage_summary(label, parents, fragments):
    result=[]
    for kind in ['matched','missing','uncertain']:
        selected=[r for r in fragments if r['fragment_kind']==kind]
        result.append(dict(experiment=label,fragment_kind=kind,intervals=len(selected),
                           distinct_source_ids=len({r['source_id'] for r in selected}),
                           length_m=sum(r['length_m'] for r in selected)))
    return result


def counterfactual(output,frames,core,website_frame,config,original,prior):
    """NUS-only order control; uses the SAME legacy matcher before refinement."""
    primary=normalize_sources(frames['processed_lta'],'processed_lta',core)
    osm=normalize_sources(frames['osm'],'osm',core)
    references=website_roads(website_frame,core.buffer(config.context_halo_m))
    print('Counterfactual: supplementary OSM matched to website alone.',flush=True)
    op,of=match_stage(osm,Index(references),config)
    candidate_duplicate_review(of,config);reconcile_parents(op,of)
    missing=gpd.GeoDataFrame([row for row in of if row['fragment_kind']=='missing'],geometry='geometry',crs=3414)
    attribution=reference_attribution(output,prior['matched_roads'],original,prior['uncertain_roads'],
                                      supplement=missing,stem='osm_first_missing_primary_attribution')
    write_json(output/'osm_first_missing_primary_attribution.json',attribution)
    print('Counterfactual: processed primary added after OSM.',flush=True)
    pp,pf=match_stage(primary,Index(references+fragment_references(of,osm)),config)
    candidate_duplicate_review(pf,config);reconcile_parents(pp,pf)
    rows=stage_summary('OSM_first_vs_website',op,of)+stage_summary('primary_after_OSM',pp,pf)
    for source,label in [('processed_lta','primary_first_original'),('osm','OSM_after_primary_original')]:
        selected=original[original.dataset==source]
        rows.append(dict(experiment=label,fragment_kind='missing',intervals=len(selected),
                         distinct_source_ids=selected.source_id.nunique(),length_m=float(selected.length_m.sum())))
    pd.DataFrame(rows).to_csv(output/'source_order_comparison.csv',index=False)
    primary_keys=Counter(geom_key(r.geometry,.05) for r in primary)
    osm_keys=Counter(geom_key(r.geometry,.05) for r in osm)
    info=dict(primary_clipped_parts=len(primary),osm_clipped_parts=len(osm),
              primary_parts_also_in_OSM_at_5cm=sum(min(n,osm_keys[k]) for k,n in primary_keys.items()),
              primary_legacy_scope_parts=sum(r.eligible for r in primary),osm_legacy_scope_parts=sum(r.eligible for r in osm),
              interpretation='Current pilot geometries and order attribution only. Original provenance is not inferred.',
              counterfactual_scope='Same legacy matcher and road-class policy; order alone is changed. No whole-island run.')
    write_json(output/'source_geometry_comparison.json',info)
    class_rows=[]
    for label,roads in [('processed_lta',primary),('osm',osm)]:
        for kind in sorted({r.road_class for r in roads}):
            group=[r for r in roads if r.road_class==kind]
            class_rows.append(dict(dataset=label,road_class=kind,source_parts=len(group),length_m=sum(r.length for r in group)))
    pd.DataFrame(class_rows).to_csv(output/'pilot_source_class_comparison.csv',index=False)


def reference_attribution(output,matched,candidates,uncertain,supplement=None,stem='osm_matched_reference_attribution'):
    pieces=[];roles=[]
    for role,data in [('primary_matched_to_website',matched),('primary_original_candidate',candidates),('primary_uncertain',uncertain)]:
        for geometry in data.loc[data.dataset=='processed_lta','geometry']:
            pieces.append(single_line(geometry));roles.append(role)
    tree=STRtree(pieces)
    totals=Counter();maximum=0.
    osm=matched.loc[matched.dataset=='osm'] if supplement is None else supplement
    for geometry in osm.geometry:
        line=single_line(geometry)
        cuts=np.linspace(0,line.length,max(1,int(np.ceil(line.length/5)))+1)
        pts=[line.interpolate((a+b)/2) for a,b in zip(cuts[:-1],cuts[1:])]
        pairs,distances=tree.query_nearest(pts,all_matches=False,return_distance=True)
        maximum=max(maximum,float(np.max(distances)))
        weights=np.diff(cuts)
        for (input_index,ref_index),distance in zip(pairs.T,distances):
            role=roles[int(ref_index)] if supplement is None or distance<=.1 else 'no_coincident_primary_reference_within_10cm'
            totals[role]+=weights[int(input_index)]
    rows=[dict(primary_reference_role=key,osm_matched_length_m=value) for key,value in sorted(totals.items())]
    pd.DataFrame(rows).to_csv(output/f'{stem}.csv',index=False)
    return dict(sample_interval_m=5,maximum_sample_distance_to_primary_m=maximum,
                measured_osm_total_m=float(osm.length_m.sum()),attribution=rows,
                caveat='Nearest sampled primary interval role, not unique physical-road length or original provenance.')


def layer_style(color,dashed=False):
    # Standard QGIS single-symbol QML, stored as default GeoPackage layer style.
    root=ET.Element('qgis',version='3.34',styleCategories='Symbology')
    renderer=ET.SubElement(root,'renderer-v2',type='singleSymbol',symbollevels='0',enableorderby='0')
    symbols=ET.SubElement(renderer,'symbols')
    symbol=ET.SubElement(symbols,'symbol',name='0',type='line',alpha='1',clip_to_extent='1')
    layer=ET.SubElement(symbol,'layer',{'class':'SimpleLine','enabled':'1','locked':'0','pass':'0'})
    options=ET.SubElement(layer,'Option',type='Map')
    rgb=','.join(str(int(color[i:i+2],16)) for i in (1,3,5))+',255'
    for name,item in {'line_color':rgb,'line_width':'0.5','line_width_unit':'MM','line_style':'dash' if dashed else 'solid','joinstyle':'round','capstyle':'round'}.items():
        ET.SubElement(options,'Option',name=name,type='QString',value=item)
    return ET.tostring(root,encoding='unicode')


def write_package(output,website,refined,old_excluded,old_uncertain,core):
    excluded_context=old_excluded.copy()
    excluded_context['scope']='previously_excluded_source_context'
    excluded_context['category']=B
    nonroad_review=old_uncertain[old_uncertain.road_class.isin(NON_ROADS|OUT_OF_SCOPE)].copy()
    nonroad_review['scope']='previous_uncertain_nonroad_context';nonroad_review['category']=B
    excluded_context=pd.concat([excluded_context,nonroad_review],ignore_index=True)
    review_context=old_uncertain[~old_uncertain.road_class.isin(NON_ROADS|OUT_OF_SCOPE)].copy()
    review_context['scope']='previous_spatial_uncertainty';review_context['category']=C
    layers={'website_roads':website,
            'original_candidates':refined,
            'A_eligible_candidates':refined[refined.category==A],
            'B_excluded_candidates':refined[refined.category==B],
            'C_manual_candidates':refined[refined.category==C],
            'B_excluded_context':gpd.GeoDataFrame(excluded_context,geometry='geometry',crs=3414),
            'C_spatial_review_context':review_context,
            'pilot_boundary':gpd.GeoDataFrame({'name':['NUS pilot'],'geometry':[core]},crs=3414)}
    package=output/'nus_refined.gpkg'
    if package.exists():package.unlink()
    styles={}
    for name,data in layers.items():
        data=data.copy()
        for column in ['seg_id']:
            if column in data:data[column]=data[column].astype('Int64')
        for column in ['bridge','tunnel','boundary','parallel_evidence','component_connected','public_access_verified','parking_name_hint','entrance_driveway_name_hint']:
            if column in data:data[column]=pd.array(data[column],dtype='boolean')
        pyogrio.write_dataframe(data,package,layer=name,driver='GPKG',promote_to_multi=True)
        category='existing' if name=='website_roads' else name[0] if name[0] in 'ABC' else None
        code={'A':A,'B':B,'C':C}.get(category,category)
        if code in COLORS:styles[name]=layer_style(COLORS[code],code==B)
    with sqlite3.connect(package) as db:
        db.execute('''CREATE TABLE layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,
            f_table_catalog TEXT,f_table_schema TEXT,f_table_name TEXT,f_geometry_column TEXT,
            styleName TEXT,styleQML TEXT,styleSLD TEXT,useAsDefault BOOLEAN,description TEXT,
            owner TEXT,ui TEXT,update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        for name,qml in styles.items():
            ET.fromstring(qml)
            db.execute('INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,styleName,styleQML,styleSLD,useAsDefault,description,owner,ui) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       ('','',name,'geom','NUS crossing eligibility',qml,'',1,'Blue existing; green eligible; grey dashed excluded; orange manual review.','',''))
        db.commit()
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    for name,data in layers.items():
        actual=gpd.read_file(package,layer=name)
        assert actual.crs.to_epsg()==3414 and len(actual)==len(data)
        assert actual.geometry.is_valid.all() and not actual.geometry.is_empty.any()
        if 'fragment_uid' in data and len(data):
            assert actual.fragment_uid.tolist()==data.fragment_uid.tolist()
            assert all(shapely.equals_exact(a,b,1e-8) for a,b in zip(actual.geometry,data.geometry))
    roundtrip=gpd.read_file(package,layer='website_roads')
    assert roundtrip.seg_id.tolist()==website.seg_id.tolist()
    assert all(shapely.equals_exact(a,b,1e-8) for a,b in zip(roundtrip.geometry,website.geometry))
    return package,layers


def run(args):
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='feature/road-network-conflation':
        raise RuntimeError('Use the existing feature/road-network-conflation branch.')
    pilot=ROOT/'local-outputs/conflation/nus'
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to((ROOT/'local-outputs').resolve()) or output.is_relative_to(pilot.resolve()) or pilot.resolve().is_relative_to(output):
        raise ValueError('Use a separate ignored output directory; preserve the existing pilot.')
    output.mkdir(parents=True,exist_ok=True)
    protected={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in pilot.rglob('*') if p.is_file()}
    tracked=[ROOT/p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT,text=True).split('\0') if p]
    protected.update({str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in tracked})
    package=pilot/'nus_pilot_10m.gpkg'
    data={name:gpd.read_file(package,layer=name) for name in ['website_roads','candidate_supplements','classified_roads','matched_roads','uncertain_roads','excluded_roads']}
    original=data['candidate_supplements']
    assert len(original)==763
    manifest=json.loads((pilot/'run_manifest.json').read_text())
    config=Config(**next(r['config'] for r in manifest['runs'] if r['tolerance_m']==10))
    core=box(*manifest['core_bounds_epsg3414'])
    source_paths={'processed_lta':ROOT/'local-data/lta/road singapore.geojson','osm':ROOT/'local-data/osm/Singapore-shp/shape/roads.shp','website':ROOT/'website/data/gap_segments.geojson'}
    hashes={str(p):sha(p) for p in source_paths.values()}
    frames={name:gpd.read_file(path).to_crs(3414) for name,path in source_paths.items()}
    schemas={name:list(pyogrio.read_info(path)['fields']) for name,path in source_paths.items()}
    tag_fields=['access','vehicle','motor_vehicle','motorcar','service','foot','bicycle']
    raw_tags={}
    availability={}
    for name in ['processed_lta','osm']:
        present=[field for field in tag_fields if field in schemas[name]]
        availability[name]=dict(available_fields=schemas[name],access_or_service_fields=present,
                                missing_fields=[field for field in tag_fields if field not in present])
        if present:
            for _,row in frames[name].loc[frames[name].geometry.intersects(core)].iterrows():
                raw_tags[(name,str(row.osm_id))]={field:row[field] for field in present}
    write_json(output/'access_attribute_availability.json',availability)
    website_context=frames['website'].loc[frames['website'].geometry.intersects(core.buffer(config.context_halo_m))]
    print('Independent 2 m spatial audit of 763 original candidate intervals.',flush=True)
    audit=spatial_audit(original,website_context)
    refined=classify(original,data['classified_roads'],audit,raw_tags)
    summarize(refined,['category','dataset','road_class','access_status']).to_csv(output/'classification_summary.csv',index=False)
    summarize(refined,['dataset','road_class','access_status']).to_csv(output/'original_candidate_audit.csv',index=False)
    flat=refined.drop(columns='geometry').copy()
    points=refined.geometry.interpolate(.5,normalized=True).to_crs(4326)
    flat['review_longitude']=points.x;flat['review_latitude']=points.y
    flat.to_csv(output/'candidate_review_register.csv',index=False)
    audit.to_csv(output/'independent_spatial_audit.csv',index=False)
    counterfactual(output,frames,core,frames['website'],config,original,data)
    attribution=reference_attribution(output,data['matched_roads'],original,data['uncertain_roads'])
    write_json(output/'osm_reference_attribution.json',attribution)
    refined_package,layers=write_package(output,data['website_roads'],refined,data['excluded_roads'],data['uncertain_roads'],core)
    context=[]
    for name in ['B_excluded_context','C_spatial_review_context']:
        rows=layers[name].groupby(['dataset','road_class'],dropna=False).agg(features=('source_id','size'),length_m=('length_m','sum')).reset_index()
        rows.insert(0,'scope',name);context.append(rows)
    pd.concat(context,ignore_index=True).to_csv(output/'context_classification_audit.csv',index=False)
    counts={code:dict(intervals=int((refined.category==code).sum()),length_m=float(refined.loc[refined.category==code,'length_m'].sum())) for code in [A,B,C]}
    assert sum(v['intervals'] for v in counts.values())==763
    assert abs(sum(v['length_m'] for v in counts.values())-original.length_m.sum())<1e-6
    from refinement_report import create_maps,create_report
    examples=create_maps(output,layers,data['classified_roads'],core)
    tests_path=ROOT/'local-outputs/conflation/refinement-test-results.txt'
    result=dict(created_singapore=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                original_intervals=763,original_length_m=float(original.length_m.sum()),categories=counts,
                source_sha256=hashes,pilot_package_sha256=sha(package),refined_package=str(refined_package),
                refinement_code_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*refin*.py')},
                preserved_original_candidate_uid_and_geometry=True,public_access_verified_count=0,
                access_limit='Access restrictions and service subtypes are absent from both supplied sources; unknown is not unrestricted.',
                spatial_audit_parameters=dict(sample_m=2,search_m=50,angle_deg=30,length_ratio=.3,review_guard_m=[20,30],minimum_20m_fraction=.6,minimum_30m_fraction=.8),
                spatial_flags=refined.spatial_flag.value_counts(dropna=False).to_dict(),
                layer_counts={name:len(frame) for name,frame in layers.items()},examples=examples,
                whole_island_processing=False,provenance='Team-provided processed LTA, original provenance and history unverified.',
                tests_record=str(tests_path))
    create_report(output,result,refined,layers,attribution)
    changed=[name for name,expected in protected.items() if sha(ROOT/name)!=expected]
    assert not changed,changed
    assert all(sha(Path(path))==expected for path,expected in hashes.items())
    ids=frames['website'].seg_id.tolist()
    assert len(ids)==len(set(ids))==55115
    expected=json.loads((ROOT/'local-outputs/setup-verification.json').read_text())['seg_id_sequence_sha256']
    assert hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()==expected
    assert not subprocess.check_output(['git','ls-files','--','local-data','local-outputs'],cwd=ROOT,text=True).strip()
    result['validation']=dict(all_existing_website_ids_preserved=55115,existing_pilot_ids_preserved=len(data['website_roads']),
                              category_count_and_length_conserved=True,valid_geometries=True,gpkg_roundtrip_preserved=True,
                              prior_pilot_and_tracked_files_unchanged=len(protected),prior_analysis_hash_changes=changed,
                              original_inputs_unchanged=True,whole_island_processing=False)
    write_json(output/'refinement_manifest.json',result)
    print(json.dumps({'categories':counts,'output':str(output),'validation':result['validation']},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='local-outputs/conflation/nus-refined')
    run(parser.parse_args())
