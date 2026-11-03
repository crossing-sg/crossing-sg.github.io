"""Preserve assembled highway relation polygons alongside the line network.

Polygon areas are source features, not artificial centreline roads. Their member
references and complete tags also remain in all-highway-features.jsonl.gz.
"""
import gzip
import json
import osmium
from build import PBF, LOCAL, HERE, put


class Areas(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.features = []
        self.factory = osmium.geom.GeoJSONFactory()
        self.invalid = []

    def area(self, area):
        if area.from_way() or 'highway' not in area.tags:
            return
        try:
            geometry = json.loads(self.factory.create_multipolygon(area))
            self.features.append(dict(type='Feature', properties=dict(osm_type='relation', osm_id=area.orig_id(), **dict(area.tags)), geometry=geometry))
        except RuntimeError as error:
            self.invalid.append(dict(osm_id=area.orig_id(), error=str(error)))


class Members(osmium.SimpleHandler):
    def __init__(self, ids):
        super().__init__()
        self.ids = ids
        self.ways = {}

    def way(self, way):
        if way.id in self.ids:
            self.ways[way.id] = [[n.lon, n.lat] for n in way.nodes]


if __name__ == '__main__':
    handler = Areas()
    handler.apply_file(str(PBF), locations=True, idx='flex_mem')
    with gzip.open(LOCAL/'all-highway-features.jsonl.gz', 'rt', encoding='utf-8') as source:
        relations = [r for line in source if (r := json.loads(line))['osm_type'] == 'relation']
    assembled = {f['properties']['osm_id'] for f in handler.features}
    unresolved = [r for r in relations if r['osm_id'] not in assembled]
    members = Members({m['ref'] for r in unresolved for m in r['members'] if m['type'] == 'w'})
    members.apply_file(str(PBF), locations=True, idx='flex_mem')
    missing_members = []
    for r in unresolved:
        coords = []
        for m in r['members']:
            if m['type'] == 'w' and m['ref'] in members.ways:
                coords.append(members.ways[m['ref']])
            else:
                missing_members.append(dict(relation=r['osm_id'], member=m))
        handler.features.append(dict(type='Feature', properties=dict(osm_type='relation', osm_id=r['osm_id'],
                                      geometry_status='unassembled_member_linework', **r['tags']),
                                      geometry=dict(type='MultiLineString', coordinates=coords)))
    digest = put(LOCAL/'highway-relation-areas.geojson', dict(type='FeatureCollection', features=handler.features))
    report = dict(total_relations=len(relations), assembled_relations=len(assembled), member_linework_fallback=len(unresolved),
                  assembly_errors=handler.invalid, missing_members=missing_members,
                  osm_ids=sorted(f['properties']['osm_id'] for f in handler.features), sha256=digest)
    put(HERE/'relation-areas.json', report)
    print(json.dumps(report, indent=2))
