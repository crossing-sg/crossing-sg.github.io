"""Conservative, review-first road conflation. Inputs and website files are read only.

Default: NUS Kent Ridge pilot, outputs under ignored local-outputs/conflation/nus.
Use --all for a subsequent whole-island run; --bbox accepts WGS84 west south east north.
No network requests, source rewrites, website export, or ID renumbering are performed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path
import subprocess

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import LineString, Point, box
from shapely.ops import substring, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
CRS = 'EPSG:3414'
DRIVABLE = {'service', 'residential', 'living_street', 'unclassified', 'tertiary',
            'secondary', 'primary', 'trunk', 'busway', 'tertiary_link',
            'secondary_link', 'primary_link', 'trunk_link'}
REVIEW_CLASSES = {'track', 'track_grade1', 'track_grade2', 'track_grade3',
                  'track_grade4', 'track_grade5', 'road', 'unknown', 'pedestrian'}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def geom_key(geometry, precision=.001):
    return digest(shapely.to_wkb(shapely.normalize(shapely.set_precision(geometry, precision))))


def canonical(line):
    return shapely.normalize(shapely.force_2d(line))


def line_parts(geometry):
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == 'LineString':
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return [part for child in geometry.geoms for part in line_parts(child)]
    return []


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2, default=lambda v: v.item() if hasattr(v, 'item') else str(v)), encoding='utf-8')


def numeric(value, default=0):
    try:
        return float(value) if pd.notna(value) else default
    except (TypeError, ValueError):
        return default


def truth(value):
    return str(value).lower() in {'t', 'true', '1', 'yes'}


@dataclass(frozen=True)
class Config:
    tolerance_m: float = 10
    sample_m: float = 5
    angle_deg: float = 25
    correspondence_ratio: float = .45
    minimum_run_overlap_fraction: float = .80
    near_duplicate_m: float = 3
    min_fragment_m: float = 10
    endpoint_snap_m: float = 1
    reference_attach_m: float = 3
    parallel_min_separation_m: float = 3
    supporting_sibling_distance_m: float = 1.5
    ambiguity_search_m: float = 20
    context_halo_m: float = 75


@dataclass
class Road:
    uid: str
    source: str
    source_id: str
    geometry: LineString
    road_class: str = ''
    name: str = ''
    layer: float | None = None
    bridge: bool | None = None
    tunnel: bool | None = None
    oneway: str = ''
    original_offset_m: float = 0
    source_geometry_key: str = ''
    boundary: bool = False
    confidence: str = 'confirmed'
    seg_id: int | None = None
    dist_m: float | None = None

    @property
    def length(self):
        return self.geometry.length

    @property
    def eligible(self):
        return self.road_class in DRIVABLE or self.road_class in REVIEW_CLASSES


def grade_conflict(left, right):
    if left.layer is not None and right.layer is not None and left.layer != right.layer:
        return True
    for field in ('bridge', 'tunnel'):
        a, b = getattr(left, field), getattr(right, field)
        if a is not None and b is not None and a != b:
            return True
    return False


def missing_grade_risk(source, reference):
    def unknown(a,b):
        return (a.layer not in (None,0) and b.layer is None) or (a.bridge is True and b.bridge is None) or (a.tunnel is True and b.tunnel is None)
    return unknown(source,reference) or unknown(reference,source)


def tangent(line, at, half=2.5):
    a = line.interpolate(max(0, at-half))
    b = line.interpolate(min(line.length, at+half))
    vector = np.array([b.x-a.x, b.y-a.y])
    norm = float(np.linalg.norm(vector))
    return vector/norm if norm > 1e-9 else np.zeros(2)


def angle(a, b):
    return math.degrees(math.acos(float(np.clip(abs(np.dot(a, b)), 0, 1))))


class Index:
    def __init__(self, roads):
        self.roads = list(roads)
        self.geometries = np.array([r.geometry for r in self.roads], dtype=object)
        self.tree = STRtree(self.geometries)

    def nearby(self, point, distance):
        return self.tree.query(point, predicate='dwithin', distance=distance)

    def endpoint_links(self, road, distance, exclude_self=False, trusted_only=False):
        counts = []
        for point in (Point(road.geometry.coords[0]), Point(road.geometry.coords[-1])):
            counts.append(sum(
                1 for i in self.nearby(point, distance)
                if (not exclude_self or self.roads[i].uid != road.uid)
                and (not trusted_only or self.roads[i].confidence != 'uncertain')
                and (not trusted_only or not missing_grade_risk(road,self.roads[i]))
                and not grade_conflict(road, self.roads[i])
            ))
        return counts


def normalize_sources(frame, source, core=None):
    roads = []
    key = 'fclass' if source == 'processed_lta' else 'type'
    if core is not None:
        frame = frame.loc[frame.geometry.intersects(core)]
    for _, row in frame.iterrows():
        source_id = str(row.get('osm_id', ''))
        for original in line_parts(row.geometry):
            original = canonical(original)
            geometry_key = geom_key(original)
            source_id_used = source_id or geometry_key[:24]
            clipped = original if core is None else original.intersection(core)
            for line in line_parts(clipped):
                if line.length < .05:
                    continue
                a = original.project(Point(line.coords[0]))
                b = original.project(Point(line.coords[-1]))
                if b < a:
                    line = LineString(list(line.coords)[::-1])
                start = min(a, b)
                uid = f'{source}:{source_id_used}:{geometry_key[:16]}:{round(start*1000)}'
                roads.append(Road(
                    uid=uid, source=source, source_id=source_id_used, geometry=line,
                    road_class=str(row.get(key, 'unknown')),
                    name=str(row['name']) if pd.notna(row.get('name')) else '',
                    layer=numeric(row['layer']) if 'layer' in row and pd.notna(row['layer']) else None,
                    bridge=truth(row['bridge']) if 'bridge' in row and pd.notna(row['bridge']) else None,
                    tunnel=truth(row['tunnel']) if 'tunnel' in row and pd.notna(row['tunnel']) else None,
                    oneway=str(row.get('oneway', '')),
                    original_offset_m=start, source_geometry_key=geometry_key,
                    boundary=core is not None and (core.boundary.distance(line) < .01),
                ))
    return sorted(roads, key=lambda r: r.uid)


def website_roads(frame, region=None):
    if region is not None:
        frame = frame.loc[frame.geometry.intersects(region)]
    return [Road(uid=f'website:{int(row.seg_id)}', source='website', source_id=str(int(row.seg_id)),
                 geometry=row.geometry, seg_id=int(row.seg_id), dist_m=float(row.dist_m))
            for _, row in frame.iterrows()]


def class_reason(road):
    if road.road_class in {'motorway', 'motorway_link'}:
        return 'expressway_class_excluded'
    return 'non_road_or_out_of_scope_class'


def source_connected(roads, references, config):
    """Grade-aware endpoint-to-line graph, including T junctions, without XY-crossing joins."""
    idx = Index(roads)
    graph = nx.Graph()
    graph.add_nodes_from(range(len(roads)))
    seeds = set()
    for i, road in enumerate(roads):
        if any(references.endpoint_links(road, config.reference_attach_m, trusted_only=True)):
            seeds.add(i)
        for point in (Point(road.geometry.coords[0]), Point(road.geometry.coords[-1])):
            for j in idx.nearby(point, config.endpoint_snap_m):
                if i != j and not grade_conflict(road, roads[j]):
                    graph.add_edge(i, int(j))
    connected = {}
    for component in nx.connected_components(graph):
        value = bool(component & seeds)
        for i in component:
            connected[roads[i].uid] = value
    return idx, connected


def sample_cells(road, config):
    # Cell boundaries anchored to native source measures, independent of AOI clipping.
    offset, end = road.original_offset_m, road.original_offset_m + road.length
    first = (math.floor(offset/config.sample_m)+1)*config.sample_m
    breaks = [0.] + [x-offset for x in np.arange(first, end-1e-7, config.sample_m)] + [road.length]
    return [(a, b) for a, b in zip(breaks[:-1], breaks[1:]) if b-a > 1e-6]


def cell_evidence(road, a, b, references, config):
    at = (a+b)/2
    point = road.geometry.interpolate(at)
    direction = tangent(road.geometry, at)
    candidates = []
    conflicts = False
    for i in references.nearby(point, max(config.tolerance_m, config.ambiguity_search_m)):
        ref = references.roads[i]
        position = ref.geometry.project(point)
        nearest = ref.geometry.interpolate(position)
        ref_direction = tangent(ref.geometry, position)
        delta_angle = angle(direction, ref_direction)
        delta = np.array([point.x-nearest.x, point.y-nearest.y])
        longitudinal = abs(float(np.dot(delta, ref_direction)))
        pa = ref.geometry.project(road.geometry.interpolate(a))
        pb = ref.geometry.project(road.geometry.interpolate(b))
        ratio = abs(pb-pa)/(b-a)
        # Prevent short lines, crossings and line-end buffer caps proving correspondence.
        if delta_angle > config.angle_deg or ratio < config.correspondence_ratio or longitudinal > 2:
            continue
        if grade_conflict(road, ref):
            conflicts = True
            continue
        distance = point.distance(ref.geometry)
        unknown_grade = bool(missing_grade_risk(road, ref))
        candidates.append((distance + delta_angle*.02, distance, delta_angle, ratio,
                           int(i), unknown_grade))
    if not candidates:
        return {'kind': 'missing', 'reason': 'grade_separated_geometry' if conflicts else 'no_corresponding_line',
                'distance': None, 'angle': None, 'ratio': None, 'ref': None}
    best = min(candidates)
    _, distance, delta_angle, ratio, i, unknown_grade = best
    ref = references.roads[i]
    if unknown_grade:
        kind, reason = 'uncertain', 'reference_grade_unknown'
    elif ref.confidence == 'uncertain':
        kind, reason = 'uncertain', 'overlaps_unresolved_primary'
    elif distance > config.tolerance_m:
        kind, reason = 'uncertain', 'aligned_line_outside_match_radius'
    elif distance > config.near_duplicate_m:
        kind, reason = 'uncertain', 'displacement_or_parallel'
    else:
        kind, reason = 'matched', 'aligned_corresponding_length'
    return {'kind': kind, 'reason': reason, 'distance': distance, 'angle': delta_angle,
            'ratio': ratio, 'ref': i}


def parallel_evidence(road, source_index, references, config):
    """Evidence of coexisting distinct lines in ONE input, with connectivity support.

    Different names/oneway alone never suffice. We require a sibling near reference,
    aligned at >=2 of 3 interior positions, lateral separation, and source connections.
    """
    if not all(source_index.endpoint_links(road, config.endpoint_snap_m, exclude_self=True)):
        return False
    supported = 0
    for fraction in (.2, .5, .8):
        point = road.geometry.interpolate(fraction, normalized=True)
        source_direction = tangent(road.geometry, road.length*fraction)
        found = False
        for ri in references.nearby(point, config.tolerance_m):
            ref = references.roads[ri]
            rp = ref.geometry.interpolate(ref.geometry.project(point))
            d = point.distance(ref.geometry)
            if d < config.parallel_min_separation_m or grade_conflict(road, ref):
                continue
            if angle(source_direction, tangent(ref.geometry, ref.geometry.project(point))) > config.angle_deg:
                continue
            for si in source_index.nearby(rp, config.supporting_sibling_distance_m):
                sibling = source_index.roads[si]
                if sibling.uid == road.uid or grade_conflict(road, sibling):
                    continue
                # Distinct coexisting sibling aligned with reference, not a crossing connector.
                if point.distance(sibling.geometry) < config.parallel_min_separation_m:
                    continue
                if angle(source_direction, tangent(sibling.geometry, sibling.geometry.project(rp))) > config.angle_deg:
                    continue
                if missing_grade_risk(road, ref):
                    continue
                found = True
                break
            if found:
                break
        supported += found
    return supported >= 2


def row_for(road, **extra):
    return dict(uid=road.uid, dataset=road.source, source_id=road.source_id,
                road_class=road.road_class, name=road.name, layer=road.layer,
                bridge=road.bridge, tunnel=road.tunnel, oneway=road.oneway,
                seg_id=road.seg_id, dist_m=road.dist_m, boundary=road.boundary,
                length_m=road.length, geometry=road.geometry, **extra)


def match_stage(roads, references, config):
    eligible = [r for r in roads if r.eligible and r.geometry.is_valid]
    source_index, connected = source_connected(eligible, references, config)
    parents, fragments = [], []
    seen = set()
    for number, road in enumerate(roads):
        if number and number % 1000 == 0:
            print(f'  {road.source}: {number:,}/{len(roads):,} source parts', flush=True)
        if not road.geometry.is_valid or not road.eligible:
            parents.append(row_for(road, status='excluded', reason='invalid_geometry' if not road.geometry.is_valid else class_reason(road),
                                   tolerance_m=config.tolerance_m))
            continue
        key = geom_key(road.geometry)
        if key in seen:
            parents.append(row_for(road, status='matched', reason='exact_duplicate_in_same_source', tolerance_m=config.tolerance_m))
            continue
        seen.add(key)
        cells = sample_cells(road, config)
        evidence = [cell_evidence(road, a, b, references, config) for a, b in cells]
        independent = parallel_evidence(road, source_index, references, config) if any(e['reason'] == 'displacement_or_parallel' for e in evidence) else False
        component = connected.get(road.uid, False)
        class_review = road.road_class in REVIEW_CLASSES or road.road_class in {'busway','trunk','trunk_link'}
        for entry in evidence:
            if independent and entry['reason'] == 'displacement_or_parallel':
                entry.update(kind='missing', reason='independent_parallel_source_topology')
            if entry['kind'] == 'missing':
                if class_review:
                    entry.update(kind='uncertain', reason='class_or_access_requires_review')
                elif not component:
                    entry.update(kind='uncertain', reason='no_grade_compatible_reference_connection')
        # Merge adjacent sample intervals by outcome, leaving unmatched portions intact.
        runs = []
        for (a, b), entry in zip(cells, evidence):
            label = entry['kind']
            if runs and runs[-1]['kind'] == label:
                runs[-1]['b'] = b
                runs[-1]['reasons'].add(entry['reason'])
            else:
                runs.append(dict(a=a, b=b, kind=label, reasons={entry['reason']}))
        aligned_refs={entry['ref'] for entry in evidence if entry['ref'] is not None}
        corridor=unary_union([references.roads[i].geometry.buffer(config.tolerance_m,cap_style=2) for i in aligned_refs])
        corridor_overlap_m=road.geometry.intersection(corridor).length if aligned_refs else 0.
        for run in runs:
            if run['kind']=='matched':
                interval=substring(road.geometry,run['a'],run['b'])
                overlap=interval.intersection(corridor).length/interval.length
                if overlap<config.minimum_run_overlap_fraction:
                    run['kind']='uncertain'
                    run['reasons'].add('insufficient_continuous_overlap')
            if run['kind'] == 'missing' and run['b']-run['a'] < config.min_fragment_m:
                run['kind'] = 'uncertain'
                run['reasons'].add('short_missing_fragment')
        lengths = Counter()
        for run in runs:
            lengths[run['kind']] += run['b']-run['a']
        fraction = lengths['matched']/road.length
        if lengths['matched'] > 0 and (lengths['missing'] > 0 or lengths['uncertain'] > 0):
            status = 'partially_matched'
        elif lengths['matched'] > 0:
            status = 'matched'
        elif lengths['missing'] > 0 and lengths['uncertain'] == 0:
            status = 'unmatched'
        else:
            status = 'uncertain'
        distances = [e['distance'] for e in evidence if e['distance'] is not None]
        angles = [e['angle'] for e in evidence if e['angle'] is not None]
        ratios = [e['ratio'] for e in evidence if e['ratio'] is not None]
        reasons = sorted({reason for run in runs for reason in run['reasons']})
        metrics = dict(status=status, reason=';'.join(reasons), tolerance_m=config.tolerance_m,
                       matched_m=lengths['matched'], missing_m=lengths['missing'], uncertain_m=lengths['uncertain'],
                       matched_frac=fraction, corresponding_frac=sum((b-a) for (a,b),e in zip(cells,evidence) if e['distance'] is not None)/road.length,
                       corridor_overlap_m=corridor_overlap_m,corridor_overlap_frac=corridor_overlap_m/road.length,
                       median_offset_m=float(np.median(distances)) if distances else None,
                       median_angle_deg=float(np.median(angles)) if angles else None,
                       median_length_ratio=float(np.median(ratios)) if ratios else None,
                       reference_uids=json.dumps(sorted({references.roads[e['ref']].uid for e in evidence if e['ref'] is not None})),
                       reference_sources=';'.join(sorted({references.roads[e['ref']].source for e in evidence if e['ref'] is not None})),
                       parallel_evidence=independent, component_connected=component,
                       source_connections_start=source_index.endpoint_links(road, config.endpoint_snap_m, True)[0],
                       source_connections_end=source_index.endpoint_links(road, config.endpoint_snap_m, True)[1])
        parents.append(row_for(road, **metrics))
        for run in runs:
            geometry = substring(road.geometry, run['a'], run['b'])
            native_a = road.original_offset_m+run['a']
            native_b = road.original_offset_m+run['b']
            stable = digest(f'v1|{road.source}|{road.source_id}|{road.source_geometry_key}|{round(native_a*1000)}|{round(native_b*1000)}'.encode())[:24]
            fragments.append(row_for(road, fragment_uid=f'supp-v1-{stable}',
                                     parent_uid=road.uid, fragment_kind=run['kind'], reason=';'.join(sorted(run['reasons'])),
                                     tolerance_m=config.tolerance_m, from_m=native_a, to_m=native_b,
                                     component_connected=component, parallel_evidence=independent))
            fragments[-1]['geometry'] = geometry
            fragments[-1]['length_m'] = geometry.length
    return parents, fragments


def fragment_references(rows, source_roads):
    originals = {r.uid: r for r in source_roads}
    references = []
    for row in rows:
        source = originals[row['parent_uid']]
        references.append(replace(source, uid=row['fragment_uid'], geometry=row['geometry'],
                                  confidence='uncertain' if row['fragment_kind'] == 'uncertain' else 'candidate'))
    return references


def frame(rows):
    if not rows:
        columns={name:pd.Series(dtype='str') for name in ['uid','dataset','source_id','name','road_class','status','reason','fragment_uid','fragment_kind','network_uid','role']}
        columns.update(seg_id=pd.Series(dtype='Int64'),length_m=pd.Series(dtype='float64'),geometry=gpd.GeoSeries([],crs=CRS))
        data=gpd.GeoDataFrame(columns,crs=CRS)
    else:
        data = gpd.GeoDataFrame(rows, geometry='geometry', crs=CRS)
    if 'seg_id' in data:
        data['seg_id'] = data.seg_id.astype('Int64')
    for column in ('bridge','tunnel','boundary','parallel_evidence','component_connected'):
        data[column] = pd.array(data[column] if column in data else [None]*len(data),dtype='boolean')
    for column in ('matched_m','missing_m','uncertain_m'):
        if column not in data:
            data[column]=pd.Series([float('nan')]*len(data),dtype='float64')
    return data


def candidate_duplicate_review(fragments, config):
    """Quarantine overlapping candidate intervals; do not publish a duplicate preview."""
    candidates = sorted([r for r in fragments if r['fragment_kind'] == 'missing'], key=lambda r: (r['dataset'] != 'processed_lta', r['fragment_uid']))
    tree = STRtree([r['geometry'] for r in candidates])
    quarantined = set()
    duplicate_pairs = []
    for i, row in enumerate(candidates):
        if i in quarantined:
            continue
        geometry = row['geometry']
        for j in tree.query(geometry, predicate='dwithin', distance=.5):
            j = int(j)
            if j <= i or j in quarantined:
                continue
            other = candidates[j]
            if row['parent_uid'] == other['parent_uid']:
                continue
            # Length overlap and direction, rather than distance-only deduplication.
            overlap = geometry.intersection(other['geometry'].buffer(.5, cap_style=2)).length
            # Quarantine only when almost all of the OTHER line is represented.
            # A short overlapping first line must not suppress a long extension.
            if overlap < .9*other['geometry'].length:
                continue
            p = geometry.interpolate(.5, normalized=True)
            if angle(tangent(geometry, geometry.length/2), tangent(other['geometry'], other['geometry'].project(p))) > 5:
                continue
            quarantined.add(j)
            other.update(fragment_kind='uncertain', reason=other['reason']+';candidate_overlap_requires_review')
            duplicate_pairs.append({'kept_uid':row['fragment_uid'], 'review_uid':other['fragment_uid'], 'overlap_m':overlap})
    return duplicate_pairs


def reconcile_parents(parents, fragments):
    grouped=defaultdict(list)
    for row in fragments:
        grouped[row['parent_uid']].append(row)
    for row in parents:
        children=grouped[row['uid']]
        if not children:
            continue
        lengths=Counter()
        for child in children:
            lengths[child['fragment_kind']]+=child['geometry'].length
        row.update(matched_m=lengths['matched'],missing_m=lengths['missing'],uncertain_m=lengths['uncertain'],
                   matched_frac=lengths['matched']/row['geometry'].length,
                   reason=';'.join(sorted({reason for c in children for reason in c['reason'].split(';')})))
        row['status']=('partially_matched' if lengths['matched'] and (lengths['missing'] or lengths['uncertain']) else
                       'matched' if lengths['matched'] else 'unmatched' if lengths['missing'] and not lengths['uncertain'] else 'uncertain')


def preview_network(website, fragments):
    rows = [row_for(r, network_uid=r.uid, role='existing', approval='existing_website') for r in website]
    for row in fragments:
        if row['fragment_kind'] != 'missing':
            continue
        line = row['geometry']
        cuts=list(np.arange(0, line.length-1e-7, 50))+[line.length]
        if len(cuts)>2 and cuts[-1]-cuts[-2]<.01:
            cuts.pop(-2)
        for a,b in zip(cuts[:-1],cuts[1:]):
            item = row.copy()
            item.update(geometry=substring(line,a,b), seg_id=None, role='supplementary_preview', approval='requires_review',
                        network_uid=row['fragment_uid']+f'-{round(a*1000)}-{round(b*1000)}', length_m=b-a)
            rows.append(item)
    return rows


def summary_rows(parents, fragments, tolerance):
    result = []
    for scope, rows, field in [('source_parts',parents,'status'),('fragments',fragments,'fragment_kind')]:
        groups = defaultdict(list)
        for row in rows:
            groups[(row['dataset'],row[field])].append(row)
        for (dataset, category), values in sorted(groups.items()):
            result.append(dict(tolerance_m=tolerance, scope=scope, dataset=dataset, category=category,
                               count=len(values), length_m=sum(v['geometry'].length for v in values)))
    return result


def validate(website, parents, fragments, preview, duplicate_pairs):
    all_ids = [r.seg_id for r in website]
    existing = [row for row in preview if row['role'] == 'existing']
    expected = {r.seg_id:shapely.to_wkb(r.geometry) for r in website}
    assert len(all_ids) == len(set(all_ids))
    assert {r['seg_id']:shapely.to_wkb(r['geometry']) for r in existing} == expected
    assert len({r['network_uid'] for r in preview}) == len(preview)
    assert all(r['seg_id'] is None for r in preview if r['role'] != 'existing')
    invalid=[(r.get('uid'),r.get('network_uid'),r['geometry'].wkt) for r in parents+fragments+preview
             if not r['geometry'].is_valid or r['geometry'].is_empty]
    assert not invalid, invalid[:10]
    fragment_ids = [r['fragment_uid'] for r in fragments]
    assert len(fragment_ids) == len(set(fragment_ids))
    by_parent = defaultdict(list)
    for row in fragments:
        by_parent[row['parent_uid']].append(row)
    for row in parents:
        children = by_parent[row['uid']]
        if children:
            assert abs(sum(r['geometry'].length for r in children)-row['geometry'].length) < 1e-5
    addition_keys = [geom_key(r['geometry']) for r in preview if r['role'] != 'existing']
    assert len(addition_keys) == len(set(addition_keys))
    return dict(passed=True, existing_ids_preserved=len(existing), unique_network_uids=len(preview),
                existing_geometry_preserved=True, valid_geometry=True, interval_length_conservation=True,
                exact_duplicate_preview_additions=0, near_duplicate_candidates_quarantined=len(duplicate_pairs),
                supplementary_numeric_ids_assigned=False,
                limits='Near-duplicate audit uses 0.5 m, >=90% of the quarantined line length and <=5 degree direction; displaced/parallel uncertainties remain for human review.')


def write_package(path, website, primary, osm, parents, fragments, preview, core):
    layers = {
        'website_roads': [row_for(r) for r in website],
        'processed_lta_roads': [row_for(r) for r in primary],
        'osm_roads': [row_for(r) for r in osm],
        'classified_roads': parents,
        'matched_roads': [r for r in fragments if r['fragment_kind']=='matched'],
        'candidate_supplements': [r for r in fragments if r['fragment_kind']=='missing'],
        'partially_matched_roads': [r for r in parents if r['status']=='partially_matched'],
        'uncertain_roads': [r for r in fragments if r['fragment_kind']=='uncertain'],
        'excluded_roads': [r for r in parents if r['status']=='excluded'],
        'network_preview': preview,
    }
    if core is not None:
        layers['pilot_boundary'] = [dict(uid='pilot_boundary',geometry=core)]
    if path.exists():
        path.unlink()  # Only the explicit output GeoPackage inside the validated output directory.
    for name, rows in layers.items():
        data = frame(rows)
        pyogrio.write_dataframe(data, path, layer=name, driver='GPKG', promote_to_multi=True)
    # Reopen exported layers: serialization must preserve IDs and metric geometry lengths.
    reopened = gpd.read_file(path, layer='website_roads')
    assert set(reopened.seg_id)=={r.seg_id for r in website}
    original={r.seg_id:r.geometry for r in website}
    for _,row in reopened.iterrows():
        expected=original[int(row.seg_id)]
        parts=line_parts(row.geometry)
        assert len(parts)==1 and shapely.equals_exact(parts[0],expected,tolerance=1e-8)
    for name in ('candidate_supplements','matched_roads','uncertain_roads'):
        data = gpd.read_file(path, layer=name)
        assert data.crs.to_epsg()==3414
        assert data.geometry.is_valid.all()
    return {name:len(rows) for name,rows in layers.items()}


def investigate(frames, output):
    website, primary, osm = frames['website'], frames['processed_lta'], frames['osm']
    rows = []
    reference_tree = STRtree(website.geometry.to_numpy())
    for source, data in [('processed_lta',primary),('osm',osm)]:
        class_col = 'fclass' if source=='processed_lta' else 'type'
        lengths = data.geometry.length
        points = shapely.line_interpolate_point(data.geometry.to_numpy(), .5, normalized=True)
        _, distances = reference_tree.query_nearest(points, all_matches=False, return_distance=True)
        grouped = data.assign(length_m=lengths, midpoint_within_10m=distances<=10)
        for kind, group in grouped.groupby(class_col):
            rows.append(dict(dataset=source, road_class=kind, features=len(group),
                             length_km=float(group.length_m.sum()/1000),
                             midpoint_within_10m_percent=float(group.midpoint_within_10m.mean()*100),
                             policy='review' if kind in REVIEW_CLASSES or kind in {'busway','trunk','trunk_link'} else 'eligible' if kind in DRIVABLE else 'excluded'))
    pd.DataFrame(rows).to_csv(output/'island_class_profile.csv',index=False)
    # Compare geometry directly for shared input identifiers. This is evidence of shared
    # representation only; it does not establish which organisation originated geometry.
    osm_lookup = {str(row.osm_id):row.geometry for _,row in osm.iterrows()}
    shared, exact, close = 0, 0, 0
    for _,row in primary.iterrows():
        other = osm_lookup.get(str(row.osm_id))
        if other is None:
            continue
        shared += 1
        parts = line_parts(row.geometry)
        if len(parts)==1 and geom_key(parts[0],.05)==geom_key(other,.05):
            exact += 1
        elif row.geometry.hausdorff_distance(other)<=.1:
            close += 1
    report = dict(
        datasets={label:dict(features=len(data),length_km=float(data.geometry.length.sum()/1000),
                             median_feature_length_m=float(data.geometry.length.median())) for label,data in frames.items()},
        evidence=['Website exports a previously segmented crossing_gap_segments.geojson, not the supplied processed road singapore.geojson.',
                  'make_site_data.py removes expressways, simplifies by 2 m, preserves seg_id, exports only seg_id/dist_m, rounds geographic coordinates to 5 decimals.',
                  'Website methodology describes approximately 50 m LTA sections and CAT1 exclusion; the supplied primary input has a different schema and includes footways, steps, cycleways and many service roads.',
                  'Feature counts are not interchangeable road coverage measures. Source class lengths and proximity diagnostics are provided separately.'],
        shared_identifier_geometry_diagnostic=dict(shared_attribute_values=shared, equal_geometry_at_5cm=exact, additional_hausdorff_within_10cm=close,
            interpretation='Empirical overlap of current files only; attribute names and shared geometry do not verify original provenance or processing direction.'),
        limitations=['Original segmentation input and its upstream creation code are absent; exact causal attribution of the count difference cannot be reconstructed.',
                     'Class proximity percentages are nearest-midpoint diagnostics only, not proof of duplicate roads.'],
    )
    json_write(output/'network_investigation.json',report)
    return report


def plot_map(output, website, parents, fragments, core):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(1,2,figsize=(15,9),layout='constrained')
    for ax in axes:
        ax.set_aspect('equal')
        ax.set_facecolor('#f6f5f1')
        frame([row_for(r) for r in website]).plot(ax=ax,color='#30465b',linewidth=1.5,zorder=3)
        ax.ticklabel_format(useOffset=False,style='plain')
        ax.set_xlabel('SVY21 easting (m)')
        ax.set_ylabel('SVY21 northing (m)')
        if core is not None:
            west,south,east,north=core.bounds
            ax.set_xlim(west,east);ax.set_ylim(south,north)
    for source,color in [('processed_lta','#dfb45b'),('osm','#63a4aa')]:
        data=frame([r for r in parents if r['dataset']==source and r['status']!='excluded'])
        if len(data): data.plot(ax=axes[0],color=color,linewidth=.6,alpha=.6,zorder=1)
    for kind,color,width in [('matched','#a9b2b7',.6),('missing','#087f5b',1.4),('uncertain','#bc3879',1.1)]:
        data=frame([r for r in fragments if r['fragment_kind']==kind])
        if len(data): data.plot(ax=axes[1],color=color,linewidth=width,alpha=.8,zorder=4 if kind!='matched' else 1)
    named=[r for r in parents if r['name'] in {'Kent Ridge Crescent','Kent Ridge Drive'}]
    for name in sorted({r['name'] for r in named}):
        geoms=[r['geometry'] for r in named if r['name']==name and r['dataset']=='processed_lta']
        if geoms:
            line=max(geoms,key=lambda g:g.length)
            p=line.interpolate(.5,normalized=True)
            for ax in axes:
                ax.annotate(name,(p.x,p.y),xytext=(5,7),textcoords='offset points',fontsize=8,
                            bbox=dict(facecolor='white',edgecolor='none',alpha=.8))
    axes[0].set_title('Input comparison: existing website and eligible source roads')
    axes[1].set_title('10 m pilot: candidate additions and review cases')
    axes[0].legend(handles=[Line2D([0],[0],color=c,label=n,lw=2) for n,c in [('Existing website','#30465b'),('Processed primary','#dfb45b'),('Supplementary OSM','#63a4aa')]],loc='lower left')
    axes[1].legend(handles=[Line2D([0],[0],color=c,label=n,lw=2) for n,c in [('Existing website','#30465b'),('Candidate missing sections','#087f5b'),('Uncertain: review','#bc3879'),('Matched source sections','#a9b2b7')]],loc='lower left')
    fig.suptitle('NUS Kent Ridge road conflation pilot | EPSG:3414 | review outputs, not published',fontsize=14)
    fig.savefig(output/'nus_comparison.png',dpi=180)
    plt.close(fig)


def run(args):
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='feature/road-network-conflation':
        raise RuntimeError('Run on feature/road-network-conflation.')
    output=(ROOT/(args.output or ('local-outputs/conflation/singapore' if args.all else 'local-outputs/conflation/nus'))).resolve()
    if not output.is_relative_to((ROOT/'local-outputs').resolve()):
        raise ValueError('Outputs must stay inside ignored local-outputs/.')
    output.mkdir(parents=True,exist_ok=True)
    paths={'website':ROOT/'website/data/gap_segments.geojson',
           'processed_lta':ROOT/'local-data/lta/road singapore.geojson',
           'osm':ROOT/'local-data/osm/Singapore-shp/shape/roads.shp'}
    input_paths=list(paths.values())+list(paths['osm'].parent.glob('roads.*'))
    before={str(p):digest(p.read_bytes()) for p in set(input_paths)}
    frames={name:gpd.read_file(path).to_crs(CRS) for name,path in paths.items()}
    assert len(frames['website'].seg_id)==len(set(frames['website'].seg_id))
    if args.all:
        core=None
    elif args.bbox:
        core=gpd.GeoSeries([box(*args.bbox)],crs=4326).to_crs(CRS).iloc[0]
    else:
        target=frames['processed_lta'][frames['processed_lta']['name'].fillna('').str.lower().isin(['kent ridge crescent','kent ridge drive'])]
        if not len(target): raise ValueError('Named pilot roads not found.')
        west,south,east,north=target.total_bounds
        core=box(west-500,south-500,east+500,north+500)
    if not args.skip_investigation:
        print('Investigating island-wide feature classes and shared geometry.',flush=True)
        investigate(frames,output)
    config=Config()
    context=None if core is None else core.buffer(config.context_halo_m)
    website=website_roads(frames['website'],core)
    references=website_roads(frames['website'],context)
    primary=normalize_sources(frames['processed_lta'],'processed_lta',core)
    osm=normalize_sources(frames['osm'],'osm',core)
    print(f'Pilot: {len(website)} website roads, {len(primary)} primary parts, {len(osm)} OSM parts.',flush=True)
    all_summary=[]
    runs=[]
    for tolerance in args.tolerances:
        config=replace(config,tolerance_m=tolerance)
        print(f'Running {tolerance:g} m tolerance, primary then supplementary OSM.',flush=True)
        primary_parents,primary_fragments=match_stage(primary,Index(references),config)
        primary_duplicates=candidate_duplicate_review(primary_fragments,config)
        reconcile_parents(primary_parents,primary_fragments)
        # All primary intervals remain visible to OSM, including uncertainty. OSM
        # cannot silently resolve an uncertain primary interval by duplicating it.
        osm_refs=references+fragment_references(primary_fragments,primary)
        osm_parents,osm_fragments=match_stage(osm,Index(osm_refs),config)
        parents=primary_parents+osm_parents
        fragments=primary_fragments+osm_fragments
        duplicate_pairs=primary_duplicates+candidate_duplicate_review(fragments,config)
        reconcile_parents(parents,fragments)
        preview=preview_network(website,fragments)
        validation=validate(website,parents,fragments,preview,duplicate_pairs)
        stem='singapore' if args.all else 'custom_pilot' if args.bbox else 'nus_pilot'
        package=output/f'{stem}_{tolerance:g}m.gpkg'
        layer_counts=write_package(package,website,primary,osm,parents,fragments,preview,core)
        all_summary.extend(summary_rows(parents,fragments,tolerance))
        cases=sorted([r for r in parents if r['status'] in {'uncertain','partially_matched'}],
                     key=lambda r:(not bool(r.get('name')), -r['length_m']))[:20]
        json_write(output/f'ambiguous_examples_{tolerance:g}m.json',
                   [{k:v for k,v in r.items() if k!='geometry'}|{'review_point_epsg3414':list(r['geometry'].interpolate(.5,normalized=True).coords)[0]} for r in cases])
        run=dict(tolerance_m=tolerance,config=asdict(config),layer_counts=layer_counts,validation=validation,
                 candidate_duplicate_pairs=duplicate_pairs,package=str(package))
        runs.append(run)
        if tolerance==10 and not args.no_map and not args.all:
            plot_map(output,website,parents,fragments,core)
        print(f'  Saved {package.name}; validation passed.',flush=True)
    pd.DataFrame(all_summary).to_csv(output/'category_summary.csv',index=False)
    after={str(p):digest(p.read_bytes()) for p in set(input_paths)}
    assert before==after, 'Input file changed during analysis.'
    manifest=dict(created_singapore=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                  code_sha256=digest(Path(__file__).read_bytes()),input_sha256=before,
                  workflow_sha256={p.name:digest(p.read_bytes()) for p in sorted(Path(__file__).parent.iterdir()) if p.suffix in {'.py','.txt'}},
                  input_files_unchanged=True,website_global_id_count=len(frames['website']),
                  provenance='Primary is team-provided processed LTA per user statement; original source and GIS history unverified. No provenance inferred from names or geometry.',
                  core_bounds_epsg3414=list(core.bounds) if core is not None else None,
                  mode='all_island' if args.all else 'nus_pilot' if not args.bbox else 'custom_bbox',runs=runs)
    json_write(output/'run_manifest.json',manifest)
    from qa_report import generate_report
    generate_report(output,manifest,all_summary)
    print(json.dumps({'output':str(output),'runs':[{'tolerance_m':r['tolerance_m'],'counts':r['layer_counts']} for r in runs]},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    region=parser.add_mutually_exclusive_group()
    region.add_argument('--all',action='store_true',help='Process whole input extent; does not publish outputs.')
    region.add_argument('--bbox',type=float,nargs=4,metavar=('WEST','SOUTH','EAST','NORTH'))
    parser.add_argument('--tolerances',type=float,nargs='+',default=[5,10,20])
    parser.add_argument('--output',default=None)
    parser.add_argument('--skip-investigation',action='store_true')
    parser.add_argument('--no-map',action='store_true')
    run(parser.parse_args())
