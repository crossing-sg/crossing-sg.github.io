"""Export validated local results to reproducible static website/backend assets.

No native inputs, old analyses, previous outputs or authoritative registry writes.
Requires the existing local geospatial environment. --verify uses only published
assets and the Git-trackable snapshot, so collaborators need no raw source data.
"""
import argparse,csv,hashlib,json,math,shutil,sqlite3
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'local-outputs/conflation/singapore-production'
TARGET=ROOT/'website/data/proposal-roads'
SNAPSHOT=Path(__file__).parent/'registry'
BLOCK=128


def encoded(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(data):return hashlib.sha256(data).hexdigest()
def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);data=encoded(value);path.write_bytes(data);return digest(data)


def export():
    import geopandas as gpd
    from shapely.geometry import box,mapping
    from shapely.ops import transform
    from pyproj import Transformer
    validation=json.loads((LOCAL/'production_validation.json').read_text(encoding='utf-8'))
    assert validation['all_passed'] and validation['checks']['existing_features_exactly_preserved']
    TARGET.mkdir(exist_ok=True);SNAPSHOT.mkdir(exist_ok=True)
    original=json.loads((LOCAL/'delivery/manifest.json').read_text(encoding='utf-8'))
    version=original['dataset_version']+'-web1'
    for directory in ['tiles']:
        shutil.copytree(LOCAL/'delivery'/directory,TARGET/directory,dirs_exist_ok=True)
    # Canonical 128-ID blocks now handle deep links; the older 1,000-ID index is
    # redundant. Only remove known generated JSON files, never recurse elsewhere.
    redundant=TARGET/'id-blocks'
    if redundant.exists():
        assert redundant.resolve().parent==TARGET.resolve()
        for p in redundant.iterdir():
            if p.is_file() and p.suffix=='.json':p.unlink()
        redundant.rmdir()
    features=json.loads((LOCAL/'delivery/proposal_roads.geojson').read_text(encoding='utf-8'))['features']
    assert len(features)==69121 and len({f['properties']['seg_id'] for f in features})==69121
    id_info={}
    for p in (LOCAL/'delivery/id-blocks').glob('*.json'):id_info.update(json.loads(p.read_text(encoding='utf-8')))
    blocks=defaultdict(dict)
    for f in features:
        sid=f['properties']['seg_id']
        blocks[sid//BLOCK][str(sid)]={'d':f['properties']['dist_m'],'g':f['geometry'],'t':id_info[str(sid)]['tiles']}
    block_hashes={}
    for number,records in sorted(blocks.items()):
        block_hashes[str(number)]=put(TARGET/'registry'/f'{number}.json',{'version':version,'segments':records})
    # Guard layers are context for conservative selection, not proposal-eligible roads.
    pbf=gpd.read_file(LOCAL/'cache/osm_full_tags.gpkg',layer='highway_ways')
    to_wgs=Transformer.from_crs(3414,4326,always_xy=True)
    guards=defaultdict(list)
    vehicular={'service','residential','living_street','unclassified','primary','secondary','tertiary',
                'trunk','motorway','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link'}
    allowed_keys={t['key'] for t in original['tiles']}
    restricted={'no','private','permit','customers','delivery','destination','agricultural','forestry'}
    guard_count=0
    for row in pbf.itertuples(index=False):
        tags=json.loads(row.tags_json)
        grade=any(str(tags.get(k,'')).lower() not in {'','no','false','0'} for k in ['bridge','tunnel','layer'])
        foot=tags.get('foot',tags.get('access','unknown')) in restricted and tags.get('highway') in vehicular
        if not grade and not foot:continue
        wgs=transform(to_wgs.transform,row.geometry)
        coordinates=[[round(x,6),round(y,6)] for x,y in wgs.coords]
        feature={'type':'Feature','id':'guard:'+str(row.way_id),'properties':{'reason':'grade' if grade else 'pedestrian_access',
                   'osm_id':int(row.way_id)},'geometry':{'type':'LineString','coordinates':coordinates}}
        xmin,ymin,xmax,ymax=row.geometry.bounds
        for x in range(math.floor((xmin-3)/2000),math.floor((xmax+3)/2000)+1):
            for y in range(math.floor((ymin-3)/2000),math.floor((ymax+3)/2000)+1):
                key=f'{x}_{y}'
                if key in allowed_keys and row.geometry.intersects(box(x*2000-3,y*2000-3,(x+1)*2000+3,(y+1)*2000+3)):
                    guards[key].append(feature)
        guard_count+=1
    tiles=[]
    for tile in original['tiles']:
        item=dict(tile)
        item['guard_url']='guards/'+tile['key']+'.geojson'
        item['guard_sha256']=put(TARGET/item['guard_url'],{'type':'FeatureCollection','features':guards[tile['key']]})
        item['guard_bytes']=(TARGET/item['guard_url']).stat().st_size
        tiles.append(item)
    order_hash=put(TARGET/'feature-order.json',[f['properties']['seg_id'] for f in features])
    manifest={'schema_version':1,'version':version,'registry_block_size':BLOCK,'registry_blocks':block_hashes,
              'feature_order_sha256':order_hash,'full_geojson_sha256':original['full_sha256'],
              'tiles':tiles,'existing_count':55115,'added_count':14006,'total_count':69121,
              'publication_min':3,'line_min':3,'min_zoom':16,
              'provenance':'Primary team-processed road provenance/history unverified; current OSM geometry corroborates tags, not source provenance.',
              'attribution':'© OpenStreetMap contributors, ODbL; https://www.openstreetmap.org/copyright',
              'new_distances':'unknown (null); analytical datasets unchanged',
              'source_fingerprint':original['dataset_version'],'guard_ways_before_study_tile_filter':guard_count}
    manifest_hash=put(TARGET/'manifest.json',manifest)
    with sqlite3.connect(ROOT/'local-data/conflation/segment_registry.sqlite') as db:
        columns=['uid','seg_id','geometry_sha256','source','first_run','last_run','active']
        rows=db.execute('SELECT '+','.join(columns)+" FROM segments WHERE source!='website' ORDER BY seg_id").fetchall()
        next_id=db.execute("SELECT value FROM metadata WHERE key='next_id'").fetchone()[0]
    with (SNAPSHOT/'supplementary-v1.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f,lineterminator='\n');writer.writerow(columns);writer.writerows(rows)
    put(SNAPSHOT/'snapshot-v1.json',{'version':version,'next_id':int(next_id),'supplementary_records':len(rows),
          'supplementary_csv_sha256':digest((SNAPSHOT/'supplementary-v1.csv').read_bytes()),
          'existing_geojson_sha256':digest((ROOT/'website/data/gap_segments.geojson').read_bytes()),
          'static_manifest_sha256':manifest_hash,'registry_block_size':BLOCK,
          'native_identity_note':'Native millimetre geometry hashes are retained. Six-decimal delivery geometry must not be rehashed as native source geometry.'})
    config='// Generated by export_proposal_release.py. Configure data URL using Script Properties.\n'+\
           'var ROAD_REGISTRY_VERSION = '+json.dumps(version)+';\n'+\
           'var ROAD_MANIFEST_SHA256 = '+json.dumps(manifest_hash)+';\n'
    (ROOT/'apps-script/RegistryConfig.gs').write_text(config,encoding='utf-8')
    shutil.copyfile(ROOT/'website/js/road-geometry.js',ROOT/'apps-script/RoadGeometry.gs')
    print(json.dumps({'version':version,'tiles':len(tiles),'manifest_sha256':manifest_hash,
                      'static_bytes':sum(p.stat().st_size for p in TARGET.rglob('*') if p.is_file())},indent=2))


def restore(destination):
    """Hydrate a NEW registry, preserving IDs/tombstones and never touching sources."""
    from production_registry import Registry
    dest=Path(destination)
    if dest.exists():raise ValueError('Restore only into a new SQLite file')
    meta=json.loads((SNAPSHOT/'snapshot-v1.json').read_text(encoding='utf-8'))
    assert digest((ROOT/'website/data/gap_segments.geojson').read_bytes())==meta['existing_geojson_sha256']
    assert digest((SNAPSHOT/'supplementary-v1.csv').read_bytes())==meta['supplementary_csv_sha256']
    features=json.loads((ROOT/'website/data/gap_segments.geojson').read_text(encoding='utf-8'))['features']
    registry=Registry(dest)
    old=[]
    for f in features:
        sid=f['properties']['seg_id'];h=digest(json.dumps(f['geometry'],sort_keys=True,separators=(',',':')).encode())
        old.append(dict(uid=f'website:{sid}',seg_id=sid,geometry_sha256=h,source='website'))
    registry.allocate(old,[],meta['version'])
    with (SNAPSHOT/'supplementary-v1.csv').open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            registry.db.execute('INSERT INTO segments VALUES (?,?,?,?,?,?,?)',
                (row['uid'],int(row['seg_id']),row['geometry_sha256'],row['source'],row['first_run'],row['last_run'],int(row['active'])))
    registry.db.execute("UPDATE metadata SET value=? WHERE key='next_id'",(str(meta['next_id']),))
    registry.db.commit();assert registry.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';registry.close()


def verify():
    manifest_bytes=(TARGET/'manifest.json').read_bytes();manifest=json.loads(manifest_bytes)
    meta=json.loads((SNAPSHOT/'snapshot-v1.json').read_text(encoding='utf-8'));assert digest(manifest_bytes)==meta['static_manifest_sha256']
    original=json.loads((ROOT/'website/data/gap_segments.geojson').read_text(encoding='utf-8'))['features'];byid={}
    for number,h in manifest['registry_blocks'].items():
        raw=(TARGET/'registry'/f'{number}.json').read_bytes();assert digest(raw)==h
        block=json.loads(raw);assert block['version']==manifest['version'];byid.update(block['segments'])
    assert len(byid)==69121
    for feature in original:
        r=byid[str(feature['properties']['seg_id'])]
        assert r['g']==feature['geometry'] and r['d']==feature['properties']['dist_m']
    all_ids=set();repeated=0
    for tile in manifest['tiles']:
        for field,hashkey in [('url','sha256'),('guard_url','guard_sha256')]:assert digest((TARGET/tile[field]).read_bytes())==tile[hashkey]
        for f in json.loads((TARGET/tile['url']).read_text(encoding='utf-8'))['features']:
            sid=f['properties']['seg_id'];r=byid[str(sid)]
            assert f['geometry']==r['g'] and f['properties']['dist_m']==r['d']
            if sid in all_ids:repeated+=1
            all_ids.add(sid)
    assert len(all_ids)==69121
    assert (ROOT/'apps-script/RoadGeometry.gs').read_bytes()==(ROOT/'website/js/road-geometry.js').read_bytes()
    result={'all_passed':True,'registry_records':len(byid),'tile_count':len(manifest['tiles']),
            'existing_exact_features':len(original),'tile_boundary_repeated_records':repeated,
            'shared_geometry_code_identical':True,'manifest_sha256':digest(manifest_bytes)}
    (ROOT/'local-outputs/integration-qa/static-verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


def rebuild_geojson(destination):
    """Rebuild the exact complete GeoJSON using only Git-trackable assets."""
    dest=Path(destination).resolve()
    if not dest.is_relative_to((ROOT/'local-outputs').resolve()):raise ValueError('Rebuild into ignored local-outputs')
    manifest=json.loads((TARGET/'manifest.json').read_text(encoding='utf-8'));raw_order=(TARGET/'feature-order.json').read_bytes()
    assert digest(raw_order)==manifest['feature_order_sha256']
    originals={f['properties']['seg_id']:f for f in json.loads((ROOT/'website/data/gap_segments.geojson').read_text(encoding='utf-8'))['features']}
    features=dict(originals)
    for number,h in manifest['registry_blocks'].items():
        raw=(TARGET/'registry'/f'{number}.json').read_bytes();assert digest(raw)==h
        for sid,record in json.loads(raw)['segments'].items():
            sid=int(sid)
            if sid not in originals:
                features[sid]={'type':'Feature','id':sid,'properties':{'seg_id':sid,'dist_m':record['d']},'geometry':record['g']}
    data=encoded({'type':'FeatureCollection','features':[features[sid] for sid in json.loads(raw_order)]})
    assert len(features)==69121 and digest(data)==manifest['full_geojson_sha256']
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    result={'all_passed':True,'features':len(features),'bytes':len(data),'sha256':digest(data),'raw_inputs_required':False}
    (ROOT/'local-outputs/integration-qa/network-rebuild.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');parser.add_argument('--restore-registry',type=Path)
    parser.add_argument('--rebuild-geojson',type=Path)
    args=parser.parse_args()
    if args.restore_registry:restore(args.restore_registry)
    elif args.rebuild_geojson:rebuild_geojson(args.rebuild_geojson)
    elif args.verify:verify()
    else:export();verify()
