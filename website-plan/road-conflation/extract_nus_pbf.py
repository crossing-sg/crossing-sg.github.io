"""Extract detailed highway tags and geometry around the existing NUS pilot only."""
from pathlib import Path
import hashlib
import json

import geopandas as gpd
import osmium
import pandas as pd
from shapely.geometry import LineString, Point, box

ROOT=Path(__file__).resolve().parents[2]
TAGS=['highway','service','access','vehicle','motor_vehicle','motorcar','foot','bicycle','name','oneway','layer','bridge','tunnel','bus','psv','operator','ownership','surface','width','lit']


def run():
    output=ROOT/'local-outputs/conflation/nus-enriched';output.mkdir(parents=True,exist_ok=True)
    source=ROOT/'local-data/osm/pbf/Singapore.osm.pbf'
    prior=ROOT/'local-outputs/conflation/nus-refined/nus_refined.gpkg'
    candidates=gpd.read_file(prior,layer='original_candidates')
    wanted={int(i) for i in candidates.source_id if str(i).isdigit()}
    original=json.loads((ROOT/'local-outputs/conflation/nus/run_manifest.json').read_text())
    core=box(*original['core_bounds_epsg3414'])
    bounds=gpd.GeoSeries([core.buffer(300)],crs=3414).to_crs(4326).total_bounds
    region=box(*bounds)
    class Extract(osmium.SimpleHandler):
        def __init__(self):
            super().__init__();self.ways=[];self.barriers=[];self.scanned=0;self.invalid=0;self.id_elsewhere=[]
        def node(self,node):
            if 'barrier' not in node.tags:return
            p=Point(node.location.lon,node.location.lat)
            if region.intersects(p):
                tags=dict(node.tags)
                self.barriers.append(dict(node_id=int(node.id),barrier=tags.get('barrier',''),access=tags.get('access',''),
                                          vehicle=tags.get('vehicle',''),motor_vehicle=tags.get('motor_vehicle',''),foot=tags.get('foot',''),
                                          all_tags_json=json.dumps(tags,sort_keys=True),geometry=p))
        def way(self,way):
            if 'highway' not in way.tags and int(way.id) not in wanted:return
            self.scanned+=1
            if self.scanned%100000==0:print(f'PBF highway ways scanned: {self.scanned:,}',flush=True)
            if any(not node.location.valid() for node in way.nodes):self.invalid+=1;return
            coords=[(node.lon,node.lat) for node in way.nodes]
            if len(coords)<2:return
            line=LineString(coords)
            local=line.intersects(region)
            if not local:
                if int(way.id) in wanted:
                    self.id_elsewhere.append(dict(way_id=int(way.id),bounds_wgs84=list(line.bounds),tags=dict(way.tags)))
                return
            tags=dict(way.tags)
            record={key:tags.get(key,'') for key in TAGS}
            record.update(way_id=int(way.id),osm_version=int(way.version),osm_timestamp=str(way.timestamp),
                          node_ids_json=json.dumps([int(n.ref) for n in way.nodes]),all_tags_json=json.dumps(tags,sort_keys=True),geometry=line)
            self.ways.append(record)
    handler=Extract()
    print('Reading PBF; retaining highway geometry only in the NUS context.',flush=True)
    handler.apply_file(str(source),locations=True,idx='flex_mem')
    ways=gpd.GeoDataFrame(handler.ways,geometry='geometry',crs=4326).to_crs(3414)
    assert ways.way_id.is_unique and ways.geometry.is_valid.all()
    path=output/'pbf_nus_extract.gpkg'
    if path.exists():path.unlink()
    ways.to_file(path,layer='highway_ways',driver='GPKG')
    if handler.barriers:
        barriers=gpd.GeoDataFrame(handler.barriers,geometry='geometry',crs=4326).to_crs(3414)
        barriers.to_file(path,layer='barrier_nodes',driver='GPKG')
    reader=osmium.io.Reader(str(source))
    header=reader.header()
    meta={key:header.get(key) for key in ['generator','osmosis_replication_timestamp','osmosis_replication_sequence_number','osmosis_replication_base_url']}
    reader.close()
    result=dict(pbf_path=str(source),pbf_bytes=source.stat().st_size,pbf_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                header=meta,extraction_bounds_wgs84=bounds.tolist(),retained_ways=len(ways),barrier_nodes=len(handler.barriers),
                scanned_highway_or_requested_ways=handler.scanned,invalid_location_ways=handler.invalid,
                candidate_ids_found_outside_nus=handler.id_elsewhere,scope='PBF streamed to recover NUS tags only; no island-wide road conflation.')
    (output/'pbf_extraction_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    print('Service access/subtypes in NUS context:',flush=True)
    print(ways[ways.highway=='service'].groupby(['service','access','vehicle','motor_vehicle'],dropna=False).size().sort_values(ascending=False).head(30).to_string())


if __name__=='__main__':run()
