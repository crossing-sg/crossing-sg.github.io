"""Coverage comparison and figure; all analytical inputs remain read-only."""
from collections import Counter
import csv
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from build import ROOT, HERE, LOCAL, TARGET, encoded, sha, put


def main():
    features = json.loads((LOCAL/'proposal_roads.geojson').read_bytes())['features']
    original_count = 55115
    previous_count = 69121
    duplicate_new = 0
    seen = set()
    original_ids = {f['properties']['seg_id'] for f in features[:original_count]}
    previous_ids = {f['properties']['seg_id'] for f in features[:previous_count]}
    for i, f in enumerate(features):
        geometry = f['geometry']
        if geometry['type'] == 'LineString':
            coords = tuple(tuple(round(v, 7) for v in p) for p in geometry['coordinates'])
            if len(set(coords)) < 2:
                coords = tuple(map(tuple, geometry['coordinates']))
            p = f['properties']
            key = (min(coords, coords[::-1]), tuple(p.get(k) for k in ['layer','bridge','tunnel']))
            if i >= previous_count and key in seen:
                duplicate_new += 1
            seen.add(key)
    with gzip.open(HERE/'way-coverage.csv.gz', 'rt', encoding='utf-8') as f:
        records = list(csv.DictReader(f))
    grid_counts = dict(original=0, previous=0, after=0, newly_covered_grids=0)
    manifest = json.loads((TARGET/'manifest.json').read_bytes())
    for tile in manifest['tiles']:
        values = json.loads(gzip.decompress((TARGET/tile['url']).read_bytes()))['features']
        ids = {f['properties']['seg_id'] for f in values}
        # The original IDs contain reserved holes; do not use a numeric cutoff.
        before = bool(ids & original_ids)
        previous = bool(ids & previous_ids)
        grid_counts['original'] += before
        grid_counts['previous'] += previous
        grid_counts['after'] += bool(ids)
        grid_counts['newly_covered_grids'] += bool(ids) and not previous
    summary = dict(exact_duplicate_new_segments=duplicate_new, coverage_1km_grids=grid_counts,
                   fully_represented_osm_ways=sum(int(r['added_segments']) == 0 for r in records),
                   partially_represented_osm_ways=sum(int(r['added_segments']) > 0 and float(r['represented_m']) > .000001 for r in records),
                   entirely_added_osm_ways=sum(float(r['represented_m']) <= .000001 for r in records),
                   note='Grid coverage counts any line intersection, not land area or physical-road uniqueness. Exact coordinate duplicates use seven decimal places; displaced/near-parallel corridors may remain.')
    put(HERE/'comparison.json', summary)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharex=True, sharey=True, layout='constrained')
    for ax, limit, title in zip(axes, [original_count, previous_count, len(features)],
                                [f'Original LTA: {original_count:,} segments', f'Earlier LTA + OSM: {previous_count:,}', f'All highways: {len(features):,}']):
        segments = []
        for f in features[:limit]:
            g = f['geometry']
            segments.extend([g['coordinates']] if g['type'] == 'LineString' else g['coordinates'])
        ax.add_collection(LineCollection(segments, linewidths=.18, colors='#19496b', rasterized=True))
        ax.set_title(title)
        ax.set_xlim(103.59, 104.42)
        ax.set_ylim(1.15, 1.52)
        ax.set_aspect('equal')
        ax.set_xlabel('Longitude')
    axes[0].set_ylabel('Latitude')
    fig.suptitle('Proposal network coverage — analytical layers unchanged\nCountry extract whole ways; all highway categories retained', fontsize=13)
    fig.savefig(LOCAL/'coverage-comparison.png', dpi=180)
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
