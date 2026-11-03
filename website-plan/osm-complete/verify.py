"""Independent static-release integrity, reconstruction and preservation checks."""
import gzip
import hashlib
import json
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
TARGET = ROOT/'website/data/osm-complete/proposal-roads'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(base_ref=None):
    manifest = json.loads((TARGET/'manifest.json').read_bytes())
    stats = json.loads((HERE/'statistics.json').read_bytes())
    assert sha((TARGET/'manifest.json').read_bytes()) == stats['manifest_sha256']
    byid = {}
    for number, expected in manifest['registry_blocks'].items():
        data = gzip.decompress((TARGET/'registry'/f'{number}.json.gz').read_bytes())
        assert sha(data) == expected
        block = json.loads(data)
        assert block['version'] == manifest['version']
        for row in block['segments'].values():
            if row['p'].get('source') == 'osm':
                assert len(set(map(tuple, row['g']['coordinates']))) >= 2
        byid.update(block['segments'])
    assert len(byid) == manifest['total_count']
    print('Verified canonical blocks:', len(byid), flush=True)
    order_bytes = (TARGET/'feature-order.json').read_bytes()
    assert sha(order_bytes) == manifest['feature_order_sha256']
    order = json.loads(order_bytes)
    assert len(set(order)) == len(order) == len(byid)
    for tile in manifest['tiles']:
        for url, expected in [(tile['url'],tile['sha256']),(tile['guard_url'],tile['guard_sha256'])]:
            data = gzip.decompress((TARGET/url).read_bytes())
            assert sha(data) == expected
            for f in json.loads(data)['features']:
                row = byid[str(f['properties']['seg_id'])]
                assert f['geometry'] == row['g'] and f['properties'] == row['p']
    print('Verified road/guard tiles:', len(manifest['tiles']), flush=True)
    original = json.loads((ROOT/'website/data/gap_segments.geojson').read_bytes())['features']
    for f in original:
        row = byid[str(f['properties']['seg_id'])]
        assert row['g'] == f['geometry'] and row['p'] == f['properties']
    old_manifest = json.loads((ROOT/'website/data/proposal-roads/manifest.json').read_bytes())
    for number in old_manifest['registry_blocks']:
        old = json.loads((ROOT/'website/data/proposal-roads/registry'/f'{number}.json').read_bytes())
        for sid, row in old['segments'].items():
            assert byid[sid]['g'] == row['g'] and byid[sid]['d'] == row['d']
    assert not manifest['excluded_highway_categories']
    assert set(stats['extracted_by_type']['way']) == set(stats['highway_categories'])
    assert sum(v['source_ways'] for v in stats['highway_categories'].values()) == sum(stats['extracted_by_type']['way'].values())
    for row in stats['highway_categories'].values():
        assert abs(row['source_m']-row['added_m']-row['represented_m']) < .001
    ids = json.loads(gzip.decompress((HERE/'ids.json.gz').read_bytes()))['ids']
    assert len(set(ids.values())) == len(ids)
    first_added_id = min(ids.values())
    previous_max = max(int(sid) for sid in byid if int(sid) < first_added_id)
    assert first_added_id > previous_max
    assert {int(sid) for sid,r in byid.items() if r['p'].get('source') == 'osm'} <= set(ids.values())
    if base_ref:
        approved_changes = {'.gitignore','README.md','apps-script/Code.gs','apps-script/README.md','website/README.md',
                            'website/js/propose.js','website/js/explore.js','website/js/site-config.js','website/propose.html','website/map.html'}
        changed = subprocess.check_output(['git','diff','--name-only','--diff-filter=M',base_ref,'--'],cwd=ROOT,text=True).splitlines()
        deleted = subprocess.check_output(['git','diff','--name-only','--no-renames','--diff-filter=D',base_ref,'--'],cwd=ROOT,text=True).splitlines()
        assert not deleted, deleted
        assert set(changed) <= approved_changes, changed
        baseline = subprocess.check_output(['git','ls-tree','-r','--name-only',base_ref],cwd=ROOT,text=True).splitlines()
    else:
        baseline = json.loads((HERE/'baseline-sha256.json').read_bytes())
        approved_changes = {'website-plan/road-conflation/backend_harness.cjs', 'website-plan/road-conflation/integration_server.cjs'}
        def altered(item):
            s, h = item
            return s if sha((ROOT/s).read_bytes()) != h else None
        with ThreadPoolExecutor(max_workers=8) as pool:
            changed = [s for s in pool.map(altered, baseline.items()) if s]
        assert set(changed) <= approved_changes, changed
    report = dict(passed=True, canonical_segments=len(byid), original_segments_exactly_preserved=len(original),
                  previous_segments_preserved=old_manifest['total_count'], road_tiles=len(manifest['tiles']),
                  categories=len(stats['highway_categories']), baseline_files_checked=len(baseline), baseline_ref=base_ref,
                  intentional_changes=changed)
    (HERE/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-ref',help='Verify protected tracked files against the shared integration base instead of the historical local snapshot')
    verify(parser.parse_args().base_ref)
