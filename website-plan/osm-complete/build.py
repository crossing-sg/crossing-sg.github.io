"""All highway=* features, additive proposal network, immutable prior release.

No category/access/service exclusions, land mask, minimum fragment length or
analytical recalculation. Re-run from repository root using the existing venv.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time

import osmium
from pyproj import Transformer
import shapely
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import substring, transform

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
PBF = ROOT / 'local-data/osm/complete-singapore/singapore.osm.pbf'
PREVIOUS = ROOT / 'website/data/proposal-roads'
TARGET = ROOT / 'website/data/osm-complete/proposal-roads'
LOCAL = ROOT / 'local-outputs/osm-complete'
TO_M = Transformer.from_crs(4326, 3414, always_xy=True).transform
TO_WGS = Transformer.from_crs(3414, 4326, always_xy=True).transform
BLOCK = 128
GRID = 1000
TOLERANCE = .75


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = encoded(value)
    output = gzip.compress(data, mtime=0) if path.suffix == '.gz' else data
    if not path.exists() or path.read_bytes() != output:
        path.write_bytes(output)
    return sha(data)


def lines(g):
    if g.geom_type == 'LineString':
        return [g] if g.length > 1e-7 else []
    if hasattr(g, 'geoms'):
        return [line for part in g.geoms for line in lines(part)]
    return []


def grade(tags):
    return tuple(str(tags.get(k, '')).lower() if str(tags.get(k, '')).lower() not in ('no', 'false', '0') else ''
                 for k in ('layer', 'bridge', 'tunnel'))


def difference(source, refs, fuzzy=True):
    """Remove exact/shared alignments; near matches require >=5m and <=10deg.

    The small metric tolerance avoids swallowing separate roadside paths. No
    broad corridor buffer, connectivity policy or road type is an inclusion gate.
    Grade-separated OSM features never use fuzzy matching against unknown LTA.
    """
    masks = []
    for ref in refs:
        common = source.intersection(ref)
        if common.length > 1e-7:
            masks.append(common)
        if not fuzzy or source.distance(ref) > TOLERANCE:
            continue
        for piece in lines(source.intersection(ref.buffer(TOLERANCE, cap_style=2))):
            if piece.length < 5:
                continue
            a, b = Point(piece.coords[0]), Point(piece.coords[-1])
            ra, rb = ref.interpolate(ref.project(a)), ref.interpolate(ref.project(b))
            v = (b.x-a.x, b.y-a.y)
            w = (rb.x-ra.x, rb.y-ra.y)
            denominator = math.hypot(*v)*math.hypot(*w)
            if denominator and abs(v[0]*w[1]-v[1]*w[0])/denominator <= math.sin(math.radians(10)):
                masks.append(piece)
    return source.difference(shapely.union_all(masks)) if masks else source


class Extract(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []
        self.counts = defaultdict(Counter)
        self.invalid = []
        self.stream = None
        self.node_count = 0
        self.relation_count = 0

    def record(self, kind, obj, geometry, **extra):
        tags = dict(obj.tags)
        self.counts[kind][tags['highway']] += 1
        self.stream.write(encoded(dict(osm_type=kind, osm_id=obj.id, tags=tags, geometry=geometry, **extra)) + b'\n')
        return tags

    def node(self, n):
        if 'highway' in n.tags:
            self.record('node', n, dict(type='Point', coordinates=[n.location.lon, n.location.lat]))

    def way(self, w):
        if 'highway' not in w.tags:
            return
        coords = [[n.lon, n.lat] for n in w.nodes if n.location.valid()]
        valid = len(coords) == len(w.nodes) and len(coords) >= 2
        tags = self.record('way', w, dict(type='LineString', coordinates=coords) if valid else None,
                           node_ids=[n.ref for n in w.nodes])
        if valid:
            geometry = transform(TO_M, LineString(coords))
            if geometry.length > 1e-7:
                self.ways.append(dict(osm_id=w.id, tags=tags, geometry=geometry))
                return
        self.invalid.append(w.id)

    def relation(self, r):
        if 'highway' in r.tags:
            self.record('relation', r, None, members=[dict(type=m.type, ref=m.ref, role=m.role) for m in r.members])


def previous_features():
    by_id = {}
    manifest = json.loads((PREVIOUS / 'manifest.json').read_bytes())
    # Original tiles preserve every original property and coordinate.
    for tile in manifest['tiles']:
        for feature in json.loads((PREVIOUS / tile['url']).read_bytes())['features']:
            by_id[feature['properties']['seg_id']] = feature
    order = json.loads((PREVIOUS / 'feature-order.json').read_bytes())
    assert len(by_id) == manifest['total_count']
    return [by_id[sid] for sid in order], manifest


def build():
    started = time.perf_counter()
    LOCAL.mkdir(parents=True, exist_ok=True)
    source_meta = json.loads(PBF.with_suffix('.pbf.download.json').read_bytes())
    assert sha(PBF.read_bytes()) == source_meta['sha256']
    reader = osmium.io.Reader(str(PBF))
    header = reader.header()
    pbf_header = {key: header.get(key) for key in ['generator', 'osmosis_replication_timestamp', 'osmosis_replication_sequence_number']}
    reader.close()
    extractor = Extract()
    # mtime=0 makes this complete attribute/geometry audit reproducible.
    with (LOCAL / 'all-highway-features.jsonl.gz').open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as stream:
        extractor.stream = stream
        extractor.apply_file(str(PBF), locations=True, idx='flex_mem')
    print('Extracted', dict(extractor.counts['way']), 'invalid ways:', extractor.invalid, flush=True)
    if extractor.invalid:
        raise RuntimeError('Unresolved highway way geometries; inspect source audit before releasing')
    existing, old_manifest = previous_features()
    originals = json.loads((ROOT / 'website/data/gap_segments.geojson').read_bytes())['features']
    old_by_id = {f['properties']['seg_id']: f for f in existing}
    assert all(old_by_id[f['properties']['seg_id']] == f for f in originals)
    reference = [transform(TO_M, shape(f['geometry'])) for f in existing]
    # Explode multi-lines for directional tests.
    ref_lines = [part for g in reference for part in lines(g)]
    ref_tree = shapely.STRtree(ref_lines)
    ways = sorted(extractor.ways, key=lambda w: w['osm_id'])
    raw_tree = shapely.STRtree([w['geometry'] for w in ways])
    additions = []
    native_lengths = {}
    audit = []
    counts = defaultdict(lambda: dict(source_ways=0, source_m=0, added_segments=0, added_m=0, represented_m=0, fully_represented_ways=0))
    registry_path = HERE / 'ids.json.gz'
    legacy_registry = HERE / 'ids.json'
    registry = json.loads(gzip.decompress(registry_path.read_bytes())) if registry_path.exists() else (
        json.loads(legacy_registry.read_bytes()) if legacy_registry.exists() else dict(next_id=max(old_by_id)+1, ids={}))
    assert registry['next_id'] > max(old_by_id)
    allocated = dict(registry['ids'])
    for index, way in enumerate(ways):
        source, tags = way['geometry'], way['tags']
        nearby = [ref_lines[i] for i in ref_tree.query(source.buffer(TOLERANCE))]
        missing = difference(source, nearby, fuzzy=not any(grade(tags)))
        # Exact OSM-on-OSM overlap only, with matching grade. Earlier raw ways
        # cover the geometry even when themselves represented by the base.
        neighbors = [ways[i]['geometry'] for i in raw_tree.query(source)
                     if i < index and grade(ways[i]['tags']) == grade(tags)]
        missing = difference(missing, neighbors, fuzzy=False)
        added_length = 0
        number = 0
        for fragment in lines(missing):
            start = source.project(Point(fragment.coords[0]))
            # Fixed source measures and canonical native geometry define identity;
            # allocation is append-only and never fills old ID holes.
            for offset in range(max(1, math.ceil(fragment.length / 50))):
                part = substring(fragment, offset*50, min((offset+1)*50, fragment.length))
                if part.geom_type != 'LineString' or part.length <= 1e-7:
                    continue
                native_hash = sha(shapely.to_wkb(shapely.normalize(part)))
                uid = 'osm-way:%s:%s' % (way['osm_id'], native_hash)
                if uid not in registry['ids']:
                    registry['ids'][uid] = registry['next_id']
                    registry['next_id'] += 1
                sid = registry['ids'][uid]
                wgs = transform(TO_WGS, part)
                coordinates = [[round(x, 7), round(y, 7)] for x, y in wgs.coords]
                # Very short residuals must not collapse to points in delivery.
                if len(set(map(tuple, coordinates))) < 2:
                    coordinates = list(map(list, wgs.coords))
                geometry = dict(type='LineString', coordinates=coordinates)
                properties = dict(seg_id=sid, dist_m=None, source='osm', osm_id=way['osm_id'], osm_type='way',
                                  highway=tags['highway'], service=tags.get('service'), access=tags.get('access'), name=tags.get('name'),
                                  layer=tags.get('layer'), bridge=tags.get('bridge'), tunnel=tags.get('tunnel'))
                additions.append(dict(type='Feature', geometry=geometry, properties=properties))
                native_lengths[sid] = part.length
                added_length += part.length
                number += 1
        represented = source.length-added_length
        record = counts[tags['highway']]
        record['source_ways'] += 1
        record['source_m'] += source.length
        record['added_segments'] += number
        record['added_m'] += added_length
        record['represented_m'] += represented
        record['fully_represented_ways'] += number == 0
        audit.append([way['osm_id'], tags['highway'], tags.get('service', ''), tags.get('access', ''), tags.get('name', ''),
                      source.length, added_length, represented, number])
        if index % 10000 == 0:
            print('Processed', index, '/', len(ways), 'additions', len(additions), flush=True)
    # Projection/coordinate serialization can make sub-centimetre variants
    # identical in delivery. Collapse these too, retaining source accounting and
    # allocated ID tombstones. Never remove or rewrite a pre-existing feature.
    seen = set()
    canonical = []
    audit_by_way = {row[0]: row for row in audit}
    delivery_duplicates = 0
    def delivery_key(feature):
        if feature['geometry']['type'] != 'LineString':
            return None
        coords = tuple(tuple(round(v, 7) for v in p) for p in feature['geometry']['coordinates'])
        if len(set(coords)) < 2:
            coords = tuple(map(tuple, feature['geometry']['coordinates']))
        return min(coords, coords[::-1]), grade(feature['properties'])
    for feature in existing:
        seen.add(delivery_key(feature))
    for feature in additions:
        key = delivery_key(feature)
        if key in seen:
            p = feature['properties']
            length = native_lengths[p['seg_id']]
            row = audit_by_way[p['osm_id']]
            row[6] -= length
            row[7] += length
            row[8] -= 1
            record = counts[p['highway']]
            record['added_segments'] -= 1
            record['added_m'] -= length
            record['represented_m'] += length
            if row[8] == 0:
                record['fully_represented_ways'] += 1
            delivery_duplicates += 1
        else:
            canonical.append(feature)
            seen.add(key)
    additions = canonical
    assert all(registry['ids'][k] == v for k, v in allocated.items())
    put(registry_path, registry)
    if legacy_registry.exists():
        legacy_registry.unlink()  # only the uncompressed registry made by this task
    version = 'proposal-all-highways-' + sha(encoded(dict(pbf=source_meta['sha256'], base=old_manifest['version'],
                                                          script=sha(Path(__file__).read_bytes()))))[:16]
    features = existing + sorted(additions, key=lambda f: f['properties']['seg_id'])
    assert len({f['properties']['seg_id'] for f in features}) == len(features)
    full_hash = put(LOCAL / 'proposal_roads.geojson', dict(type='FeatureCollection', features=features))
    projected = reference + [transform(TO_M, shape(f['geometry'])) for f in features[len(existing):]]
    tiles = defaultdict(list)
    id_tiles = defaultdict(list)
    for feature, geometry in zip(features, projected):
        xmin, ymin, xmax, ymax = geometry.bounds
        for x in range(math.floor(xmin/GRID), math.floor(xmax/GRID)+1):
            for y in range(math.floor(ymin/GRID), math.floor(ymax/GRID)+1):
                if geometry.intersects(box(x*GRID, y*GRID, (x+1)*GRID, (y+1)*GRID)):
                    key = f'{x}_{y}'
                    tiles[key].append(feature)
                    id_tiles[feature['properties']['seg_id']].append(key)
    tile_meta = []
    for key, values in sorted(tiles.items()):
        x, y = map(int, key.split('_'))
        bounds = transform(TO_WGS, box(x*GRID, y*GRID, (x+1)*GRID, (y+1)*GRID)).bounds
        url = 'tiles/' + key + '.geojson.gz'
        h = put(TARGET / url, dict(type='FeatureCollection', features=values))
        guard_url = 'guards/' + key + '.geojson.gz'
        gh = put(TARGET / guard_url, dict(type='FeatureCollection', features=[]))
        tile_meta.append(dict(key=key, bbox=bounds, url=url, sha256=h, bytes=(TARGET/url).stat().st_size,
                              count=len(values), guard_url=guard_url, guard_sha256=gh, guard_bytes=(TARGET/guard_url).stat().st_size))
    blocks = defaultdict(dict)
    for f in features:
        p = f['properties']
        blocks[p['seg_id']//BLOCK][str(p['seg_id'])] = dict(d=p['dist_m'], g=f['geometry'], t=id_tiles[p['seg_id']], p=p)
    block_hashes = {str(n): put(TARGET/'registry'/f'{n}.json.gz', dict(version=version, segments=values)) for n, values in sorted(blocks.items())}
    order_hash = put(TARGET/'feature-order.json', [f['properties']['seg_id'] for f in features])
    bounds = shapely.total_bounds(projected)
    wgs_bounds = transform(TO_WGS, box(*bounds)).bounds
    manifest = dict(schema_version=1, version=version, registry_block_size=BLOCK, registry_blocks=block_hashes, registry_suffix='.json.gz',
                    feature_order_sha256=order_hash, full_geojson_sha256=full_hash, tiles=tile_meta,
                    existing_count=len(originals), previous_count=len(existing), added_count=len(features)-len(originals),
                    new_osm_count=len(additions), total_count=len(features), min_zoom=16, publication_min=3, line_min=3,
                    selection_policy='all_highways_review', compatible_versions=[old_manifest['version']], bbox=wgs_bounds,
                    attribution='© OpenStreetMap contributors, ODbL; https://www.openstreetmap.org/copyright',
                    source=source_meta, pbf_header=pbf_header, excluded_highway_categories=[],
                    new_distances='unknown (null); analytical datasets unchanged')
    manifest_hash = put(TARGET/'manifest.json', manifest)
    # Discard only known obsolete uncompressed outputs from this task's release.
    for directory, suffix in [('tiles', '.geojson'), ('guards', '.geojson'), ('registry', '.json')]:
        parent = (TARGET/directory).resolve()
        assert parent.parent == TARGET.resolve()
        for obsolete in parent.glob('*'+suffix):
            assert obsolete.resolve().parent == parent
            obsolete.unlink()
    audit_path = HERE/'way-coverage.csv.gz'
    with audit_path.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as zipped, io.TextIOWrapper(zipped, encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['osm_id','highway','service','access','name','source_m','added_m','represented_m','added_segments'])
        writer.writerows(audit)
    stats = dict(version=version, source=source_meta, pbf_header=pbf_header, extracted_by_type=dict(extractor.counts),
                 invalid_ways=extractor.invalid, highway_categories=dict(sorted(counts.items())),
                 original=dict(count=len(originals), length_m=sum(reference[i].length for i in range(len(originals)))),
                 previous=dict(count=len(existing), length_m=sum(g.length for g in reference)),
                 after=dict(count=len(features), length_m=sum(g.length for g in projected)),
                 new_osm=dict(count=len(additions), length_m=sum(g.length for g in projected[len(existing):])),
                 fully_represented_ways=sum(r['fully_represented_ways'] for r in counts.values()),
                 delivery_duplicates_removed=delivery_duplicates,
                 duplicate_or_aligned_length_m=sum(r['represented_m'] for r in counts.values()),
                 source_length_m=sum(r['source_m'] for r in counts.values()),
                 tile_count=len(tiles), max_tile_bytes=max(t['bytes'] for t in tile_meta),
                 static_bytes=sum(p.stat().st_size for p in TARGET.rglob('*') if p.is_file()),
                 manifest_sha256=manifest_hash, full_geojson_sha256=full_hash,
                 way_audit_sha256=sha(audit_path.read_bytes()), source_audit_sha256=sha((LOCAL/'all-highway-features.jsonl.gz').read_bytes()),
                 tolerance_m=TOLERANCE, excluded_categories=[], excluded_access=[], excluded_service=[],
                 processing_seconds=time.perf_counter()-started)
    put(HERE/'statistics.json', stats)
    print(json.dumps({k:v for k,v in stats.items() if k not in ('highway_categories',)}, indent=2), flush=True)


if __name__ == '__main__':
    build()
