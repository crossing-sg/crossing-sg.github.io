"""Package reviewed Singapore classifications without writing to the website.

Run through production_pipeline.py --stage package. The registry is append-only
under ignored local-data; every other product stays under ignored local-outputs.
"""
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import gc, gzip, hashlib, json, math, sqlite3, subprocess, time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import substring, transform
from shapely.strtree import STRtree

from conflate import ROOT, angle, tangent, geom_key, frame
from enrich_candidates import RESTRICTED
from production_policy import AUTO, REVIEW, NOT, VERSION
from production_registry import Registry, supplementary_uid
from production_prepare import sha

TO_WGS=Transformer.from_crs(3414,4326,always_xy=True)
TO_METRIC=Transformer.from_crs(4326,3414,always_xy=True)
NODE=Path('C:/Users/sherl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
COLORS={'existing':'#244d70',AUTO:'#00845c',REVIEW:'#d16a13',NOT:'#aab1b6'}


def write_json(path,value,indent=2):
    Path(path).write_text(json.dumps(value,indent=indent,ensure_ascii=False,allow_nan=False,
        default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')


def feature_bytes(features):
    return json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,
                      separators=(',',':'),allow_nan=False).encode('utf-8')


def piece_ranges(length,maximum=50):
    """Keep the last piece useful instead of creating a tiny rounding tail."""
    count=max(1,int(math.ceil((length-1e-8)/maximum)))
    return [(length*i/count,length*(i+1)/count) for i in range(count)]


def rounded_geometry(line):
    wgs=transform(TO_WGS.transform,line)
    coords=[]
    for x,y in wgs.coords:
        p=[round(x,6),round(y,6)]
        if not coords or p!=coords[-1]:coords.append(p)
    if len(coords)<2:raise ValueError('Delivery precision collapsed a proposed segment')
    return {'type':'LineString','coordinates':coords}


def audit_additions(candidates,existing):
    """Independent conservative duplicate audit, measuring candidate coverage.

    Flat-cap 0.5 m overlap must cover >=90% of the candidate, and local tangent
    agreement must be <=5 degrees. Proximity alone never rejects a road.
    Existing roads have unknown grade; automatic additions have already passed
    the conservative ground-level eligibility policy. Quarantine, never delete.
    """
    refs=[r.geometry for r in existing];tree=STRtree(refs);found=[]
    for row in candidates:
        if row['category']!=AUTO:continue
        line=row['geometry'];buffers=[];ids=[]
        for i in tree.query(line,predicate='dwithin',distance=.5):
            other=refs[int(i)]
            a,b=shapely.ops.nearest_points(line,other)
            if angle(tangent(line,line.project(a)),tangent(other,other.project(b)))<=5:
                buffers.append(other.buffer(.5,cap_style=2));ids.append(existing[int(i)].seg_id)
        covered=line.intersection(shapely.union_all(buffers)).length if buffers else 0
        if covered>=.9*line.length:
            row['category']=REVIEW;row['eligibility_reason']+=';independent_baseline_overlap_audit'
            found.append(dict(fragment_uid=row['fragment_uid'],length_m=line.length,covered_m=covered,
                              existing_seg_ids_json=json.dumps(ids)))
    return found


def make_network(candidates,existing_features):
    original=[]
    for f in existing_features:
        sid=int(f['properties']['seg_id'])
        original.append(dict(uid=f'website:{sid}',seg_id=sid,source='website',
             geometry_sha256=hashlib.sha256(json.dumps(f['geometry'],sort_keys=True,separators=(',',':')).encode()).hexdigest()))
    supplement=[];pieces=[]
    for row in sorted(candidates,key=lambda r:r['fragment_uid']):
        if row['category']!=AUTO:continue
        line=row['geometry']
        for start,end in piece_ranges(line.length):
            geometry=substring(line,start,end);digest=geom_key(geometry,.001)
            uid=supplementary_uid(row['dataset'],row['source_geometry_key'],row['from_m']+start,row['from_m']+end,digest)
            supplement.append(dict(uid=uid,geometry_sha256=digest,source=row['dataset']))
            pieces.append(dict(uid=uid,parent_fragment_uid=row['fragment_uid'],geometry=geometry,
                length_m=geometry.length,native_from_m=row['from_m']+start,native_to_m=row['from_m']+end,
                osm_way_id=row['osm_way_id'],name=row.get('osm_name') or row.get('name'),
                highway=row['highway'],service=row['service'],category=AUTO,source=row['dataset'],
                eligibility_reason=row['eligibility_reason'],access_unknown=row['access_unknown'],
                dist_m=None,crossing_distance_status='unknown_incomplete_crossing_inventory'))
    return original,supplement,pieces


def write_delivery(output,existing_features,pieces,existing_roads,fingerprint):
    delivery=Path(output)/'delivery';delivery.mkdir(exist_ok=True)
    tiles=delivery/'tiles';tiles.mkdir(exist_ok=True)
    index=delivery/'id-blocks';index.mkdir(exist_ok=True)
    new=[dict(type='Feature',id=p['seg_id'],properties={'seg_id':p['seg_id'],'dist_m':None},
              geometry=rounded_geometry(p['geometry'])) for p in pieces]
    # Original feature dictionaries are copied unchanged, including all properties.
    all_features=existing_features+new
    assert len({int(f['properties']['seg_id']) for f in all_features})==len(all_features)
    raw=feature_bytes(all_features)
    (delivery/'proposal_roads.geojson').write_bytes(raw)
    compressed=gzip.compress(raw,mtime=0)
    (delivery/'proposal_roads.geojson.gz').write_bytes(compressed)
    bucket=defaultdict(list);blocks=defaultdict(dict)
    metrics=[r.geometry for r in existing_roads]+[p['geometry'] for p in pieces]
    for f,line in zip(all_features,metrics):
        sid=int(f['properties']['seg_id']);xmin,ymin,xmax,ymax=line.bounds;keys=[]
        for tx in range(math.floor(xmin/2000),math.floor(xmax/2000)+1):
            for ty in range(math.floor(ymin/2000),math.floor(ymax/2000)+1):
                if line.intersects(box(tx*2000,ty*2000,(tx+1)*2000,(ty+1)*2000)):
                    key=f'{tx}_{ty}';keys.append(key);bucket[key].append(f)
        blocks[sid//1000][str(sid)]={'center':list(TO_WGS.transform(*line.interpolate(.5,normalized=True).coords[0])),
                                   'tiles':keys}
    manifest=[]
    for key,features in sorted(bucket.items()):
        data=feature_bytes(features);path=tiles/(key+'.geojson');path.write_bytes(data)
        tx,ty=map(int,key.split('_'));tile=transform(TO_WGS.transform,box(tx*2000,ty*2000,(tx+1)*2000,(ty+1)*2000))
        manifest.append(dict(key=key,url='tiles/'+path.name,bbox=list(tile.bounds),features=len(features),
                             bytes=len(data),gzip_bytes=len(gzip.compress(data,mtime=0)),sha256=sha(path)))
    for block,records in sorted(blocks.items()):write_json(index/f'{block}.json',records,indent=None)
    metadata=dict(schema_version=1,dataset_version=f'{VERSION}-{fingerprint}',crs='EPSG:4326',
                  metric_grid_crs='EPSG:3414',grid_size_m=2000,id_property='seg_id',
                  existing_count=len(existing_features),added_count=len(new),total_count=len(all_features),
                  full_geojson_bytes=len(raw),full_gzip_bytes=len(compressed),full_sha256=sha(delivery/'proposal_roads.geojson'),
                  tiles=manifest,id_lookup='id-blocks/{floor(seg_id/1000)}.json',
                  loading_notes=['Load visible tiles at zoom >=16; deduplicate whole features by seg_id.',
                    'A road crossing a tile boundary is repeated with the same geometry and identifier.',
                    'The .gz file is a size estimate/offline transfer artifact. GitHub Pages is not assumed to set Content-Encoding for it.',
                    'Do not replace the Crossing Gap or Walking Detour road source. New proposal-road dist_m values are null.'])
    write_json(delivery/'manifest.json',metadata)
    return metadata,all_features


def review_batches(candidates):
    """Traceable corridor/area work units, not assertions of one physical road."""
    memberships=[];groups=defaultdict(list)
    for row in candidates:
        if row['category']!=REVIEW:continue
        point=row['geometry'].interpolate(.5,normalized=True)
        name=(row.get('osm_name') or row.get('name') or '').strip()
        # Same named corridor + 1 km locality, or same unnamed 500 m work area.
        scale=1000 if name else 500
        key=(name.lower() or 'unnamed',math.floor(point.x/scale),math.floor(point.y/scale),scale)
        groups[key].append(row)
    summary=[];shapes=[]
    for key,rows in groups.items():
        group_id='review-'+hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16]
        reasons=Counter(reason for r in rows for reason in r['eligibility_reason'].split(';'))
        length=sum(r['geometry'].length for r in rows)
        campus=any(r['campus'] for r in rows)
        main_name=any(n in key[0] for n in ['kent ridge crescent','kent ridge drive'])
        spatial=any(any(w in reason for w in ['parallel','spatial','overlap','geometry_not_verified']) for reason in reasons)
        vehicle=any(r['highway'] in {'primary','secondary','tertiary','residential','service','unclassified','living_street'} for r in rows)
        priority=1 if main_name or (campus and vehicle) else 2 if spatial and vehicle or length>=500 else 3
        item=dict(group_id=group_id,priority=priority,road_name=key[0],work_grid_m=key[3],grid_x=key[1],grid_y=key[2],
                  intervals=len(rows),length_m=length,campus=campus,spatial_uncertainty=spatial,
                  osm_way_ids_json=json.dumps(sorted({r['osm_way_id'] for r in rows if r['osm_way_id'] is not None})),
                  reasons_json=json.dumps(reasons),
                  review_question='Verify legal pedestrian access, vehicular role and independent road geometry; compare source grade and dated imagery/site knowledge.')
        summary.append(item);shapes.append(dict(item,geometry=shapely.union_all([r['geometry'] for r in rows])))
        for row in rows:
            memberships.append(dict(group_id=group_id,priority=priority,fragment_uid=row['fragment_uid'],
                 source_record_uids_json=row['source_record_uids_json'],osm_way_id=row['osm_way_id'],
                 dataset=row['dataset'],name=row.get('osm_name') or row.get('name'),length_m=row['geometry'].length,
                 highway=row['highway'],service=row['service'],access=row['osm_access'],foot=row['osm_foot'],
                 motor_vehicle=row['osm_motor_vehicle'],eligibility_reason=row['eligibility_reason']))
            row['review_group_id']=group_id;row['review_priority']=priority
    summary.sort(key=lambda x:(x['priority'],-x['length_m'],x['group_id']))
    return summary,memberships,shapes


def safe_frame(rows):
    # Existing helper correctly serializes mixed booleans and nullable identifiers.
    data=frame(rows)
    for column in data.columns:
        if column=='geometry':continue
        if column in {'osm_way_id','seg_id','review_priority'}:data[column]=pd.array(data[column],dtype='Int64')
        elif data[column].dtype=='object':
            values=data[column].dropna()
            if len(values) and all(isinstance(v,(bool,np.bool_)) for v in values):data[column]=pd.array(data[column],dtype='boolean')
    return data


def same_line_coordinates(exported,original):
    """A GeoPackage may promote a LineString to a one-part MultiLineString."""
    if exported.geom_type=='MultiLineString' and len(exported.geoms)==1:exported=exported.geoms[0]
    return bool(shapely.equals_exact(exported,original,1e-8))


def package_layers(output,result,candidates,pieces,groups):
    package=Path(output)/'singapore_proposal_network.gpkg'
    if package.exists():package.unlink() # only this repeatable generated product
    counts={};styles={}
    def put(name,data,color=None):
        print(f'GeoPackage: {name} ({len(data):,})',flush=True)
        pyogrio.write_dataframe(data,package,layer=name,driver='GPKG',promote_to_multi=True)
        counts[name]=len(data)
        if color:styles[name]=color
    existing=safe_frame([dict(seg_id=r.seg_id,dist_m=r.dist_m,uid=r.uid,geometry=r.geometry,
                              role='existing',length_m=r.geometry.length) for r in result['bundle']['existing']])
    put('existing_website',existing,COLORS['existing'])
    put('new_auto_eligible',safe_frame(pieces),COLORS[AUTO])
    network=pd.concat([existing,safe_frame(pieces)],ignore_index=True)
    put('proposed_production_roads',gpd.GeoDataFrame(network,crs=3414))
    del network;gc.collect()
    for label,category in [('auto_candidate_intervals',AUTO),('review_required',REVIEW),('not_automatically_included',NOT)]:
        put(label,safe_frame([r for r in candidates if r['category']==category]),COLORS[category]);gc.collect()
    put('source_fragment_classifications',safe_frame(result['decisions']))
    put('source_parent_matches',safe_frame(result['parents']))
    for source in ['processed_lta','osm']:
        # All in-study source parts; full original files remain unchanged locally.
        rows=[]
        for r in result['bundle']['roads'][source]:
            meta=result['bundle']['metadata'][r.uid]
            rows.append(dict(uid=r.uid,source_id=r.source_id,source_geometry_key=r.source_geometry_key,
               road_class=r.road_class,name=r.name,layer=r.layer,bridge=r.bridge,tunnel=r.tunnel,
               boundary_clipped=r.boundary,geometry=r.geometry,osm_way_id=meta['matched_way_id'],
               osm_link_method=meta['link_method'],tags_json=json.dumps(meta['tags']),
               grade_conflict=meta['grade_conflict'],restricted_barriers_json=json.dumps(meta['restricted_barrier_ids'])))
        put(source+'_in_study',safe_frame(rows));del rows;gc.collect()
    put('review_work_groups',safe_frame(groups),COLORS[REVIEW])
    put('study_boundary',gpd.GeoDataFrame({'name':['Master Plan 2025 land boundary +20m'],
                'geometry':[result['bundle']['mask']]},crs=3414))
    # Default QGIS layer colours survive opening the package without a project.
    from refine_candidates import layer_style
    with sqlite3.connect(package) as db:
        db.execute('''CREATE TABLE layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,
          f_table_catalog TEXT,f_table_schema TEXT,f_table_name TEXT,f_geometry_column TEXT,
          styleName TEXT,styleQML TEXT,styleSLD TEXT,useAsDefault BOOLEAN,description TEXT,
          owner TEXT,ui TEXT,update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        for name,color in styles.items():
            db.execute('INSERT INTO layer_styles (f_table_name,f_geometry_column,styleName,styleQML,useAsDefault,description) VALUES (?,?,?,?,?,?)',
                       (name,'geom','Proposal road eligibility',layer_style(color,name=='not_automatically_included'),1,
                        'Blue existing; green auto-eligible; orange review; grey not automatically included.'))
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    for name,count in counts.items():
        info=pyogrio.read_info(package,layer=name)
        assert info['features']==count and info['crs']=='EPSG:3414'
    check=gpd.read_file(package,layer='existing_website',columns=['seg_id'])
    assert check.seg_id.tolist()==[r.seg_id for r in result['bundle']['existing']]
    assert all(same_line_coordinates(a,b.geometry) for a,b in zip(check.geometry,result['bundle']['existing']))
    return package,counts


def delivery_checks(delivery,existing_features,all_features,pieces,existing_roads,manifest):
    checks={}
    checks['existing_features_exactly_preserved']=all_features[:len(existing_features)]==existing_features
    checks['all_existing_ids_preserved']=len({f['properties']['seg_id'] for f in existing_features})==55115
    checks['unique_total_ids']=len({f['properties']['seg_id'] for f in all_features})==len(all_features)
    checks['all_new_distances_null']=all(f['properties']['dist_m'] is None for f in all_features[len(existing_features):])
    checks['valid_metric_geometry']=all(p['geometry'].is_valid and not p['geometry'].is_empty for p in pieces)
    checks['valid_rounded_delivery_geometry']=all(shape(f['geometry']).is_valid and shape(f['geometry']).length>0 for f in all_features)
    checks['new_piece_length_at_most_50m']=all(0<p['length_m']<=50.000001 for p in pieces)
    checks['new_ids_above_existing_max']=min(p['seg_id'] for p in pieces)>max(f['properties']['seg_id'] for f in existing_features)
    index={int(f['properties']['seg_id']):f for f in all_features};seen=set();duplicates=0
    for tile in manifest['tiles']:
        content=json.loads((Path(delivery)/tile['url']).read_text(encoding='utf-8'))
        assert len(content['features'])==tile['features']
        for feature in content['features']:
            sid=feature['properties']['seg_id'];assert feature==index[sid]
            if sid in seen:duplicates+=1
            seen.add(sid)
    checks['tiles_roundtrip_same_geometry_properties_ids']=seen==set(index)
    checks['id_block_lookup_complete']=sum(len(json.loads(p.read_text())) for p in (Path(delivery)/'id-blocks').glob('*.json'))==len(all_features)
    original_hashes=Counter(geom_key(r.geometry,.001) for r in existing_roads)
    added_hashes=Counter(geom_key(p['geometry'],.001) for p in pieces)
    checks['no_exact_duplicate_added_geometry']=max(added_hashes.values(),default=0)==1
    checks['no_added_exact_duplicate_of_existing_geometry']=not(set(added_hashes)&set(original_hashes))
    summary=dict(checks=checks,all_passed=all(checks.values()),tile_repeated_whole_features=duplicates,
        existing_exact_duplicate_geometry_groups=sum(n>1 for n in original_hashes.values()),
        existing_duplicate_records_preserved=sum(n-1 for n in original_hashes.values() if n>1))
    if not all(checks.values()):raise AssertionError(summary)
    return summary


def finalise(output,result):
    output=Path(output);started=time.perf_counter();print('Loading complete; final independent audits',flush=True)
    candidates=[r.copy() for r in result['candidates']]
    for path,digest in result['input_hashes'].items():
        if sha(Path(path))!=digest:raise RuntimeError('Source changed since matching: '+path)
    nus=json.loads((output/'nus-final/NUS_FINAL_VALIDATION.json').read_text())
    if nus['matching_code_hashes']!=result['matching_code_hashes']:raise RuntimeError('NUS validation and global matching code differ')
    audit=audit_additions(candidates,result['bundle']['existing'])
    pd.DataFrame(audit,columns=['fragment_uid','length_m','covered_m','existing_seg_ids_json']).to_csv(output/'independent_duplicate_audit.csv',index=False)
    # Reflect final quarantines in the complete fragment audit, including aliases.
    by_fragment={r['fragment_uid']:r for r in result['decisions']}
    for r in candidates:
        for alias in json.loads(r['source_record_uids_json']):
            by_fragment[alias]['category']=r['category'];by_fragment[alias]['eligibility_reason']=r['eligibility_reason']
    existing_features=json.loads((ROOT/'website/data/gap_segments.geojson').read_text(encoding='utf-8'))['features']
    original,supplement,pieces=make_network(candidates,existing_features)
    registry=Registry(ROOT/'local-data/conflation/segment_registry.sqlite')
    ids,allocated=registry.allocate(original,supplement,result['fingerprint'])
    replay,reallocated=registry.allocate(original,supplement,result['fingerprint'])
    assert replay==ids and reallocated==0
    for p in pieces:p['seg_id']=ids[p['uid']]
    registry.export(output/'segment_registry.csv')
    with sqlite3.connect(output/'segment_registry.sqlite') as backup:registry.db.backup(backup)
    registry.close()
    print(f'ID registry: {len(pieces):,} new production segments; replay allocated zero',flush=True)
    # QA reference distance is explicitly distinct from an unknown real crossing distance.
    crossing=gpd.read_file(ROOT/'website/data/crossing_markers.geojson').to_crs(3414)
    tree=STRtree(crossing.geometry.to_numpy())
    if len(pieces):
        _,distances=tree.query_nearest(np.array([p['geometry'] for p in pieces],dtype=object),return_distance=True,all_matches=False)
        for p,d in zip(pieces,distances):p['nearest_recorded_crossing_m']=float(d)
    groups,memberships,group_geometries=review_batches(candidates)
    pd.DataFrame(groups).to_csv(output/'prioritised_review_groups.csv',index=False)
    pd.DataFrame(memberships).to_csv(output/'review_group_membership.csv',index=False)
    meta,features=write_delivery(output,existing_features,pieces,result['bundle']['existing'],result['fingerprint'])
    tests=delivery_checks(output/'delivery',existing_features,features,pieces,result['bundle']['existing'],meta)
    tests.update(registry_repeat_allocation_identical=True,registry_repeat_allocated_count=reallocated,
                 registry_newly_allocated_this_execution=allocated,independent_baseline_overlap_quarantines=len(audit))
    write_json(output/'production_validation.json',tests)
    package,layer_counts=package_layers(output,result,candidates,pieces,group_geometries)
    from production_report import generate_report
    generate_report(output,result,candidates,pieces,groups,meta,tests,package,layer_counts,nus,started)
    print('Production review files complete: '+str(output),flush=True)
