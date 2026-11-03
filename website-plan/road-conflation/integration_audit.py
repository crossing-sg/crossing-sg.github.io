"""Non-mutating final preservation/static/syntax audit and local QA measurements."""
import hashlib,json,sqlite3,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'local-outputs/integration-qa'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def main():
    before=json.loads((OUT/'before.json').read_text(encoding='utf-8'))
    changed=[name for name,digest in before.items() if not(ROOT/name).exists() or sha(ROOT/name)!=digest]
    assert not changed,changed
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert branch=='feature/road-network-conflation' and head=='a4dc7558d89a0192d1b830de735d8da213f2ea53'
    assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).strip()
    assert not subprocess.check_output(['git','ls-files','--','local-data','local-outputs'],cwd=ROOT,text=True).strip()
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True,capture_output=True)
    manifest=json.loads((ROOT/'website/data/proposal-roads/manifest.json').read_text(encoding='utf-8'))
    registry=ROOT/'local-data/conflation/segment_registry.sqlite'
    rebuilt=OUT/'rebuilt-registry.sqlite'
    with sqlite3.connect(registry) as a,sqlite3.connect(rebuilt) as b:
        fields='uid,seg_id,geometry_sha256,source,active'
        assert a.execute('SELECT '+fields+' FROM segments ORDER BY seg_id').fetchall()==b.execute('SELECT '+fields+' FROM segments ORDER BY seg_id').fetchall()
        assert a.execute("SELECT value FROM metadata WHERE key='next_id'").fetchone()==b.execute("SELECT value FROM metadata WHERE key='next_id'").fetchone()
    assert sha(OUT/'rebuilt-proposal-roads.geojson')==manifest['full_geojson_sha256']
    public_files=list((ROOT/'website/data/proposal-roads').rglob('*'))
    public_files=[p for p in public_files if p.is_file()]
    baseline=ROOT/'website/data/gap_segments.geojson'
    ids=[f['properties']['seg_id'] for f in json.loads(baseline.read_text(encoding='utf-8'))['features']]
    sequence=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()
    assert sequence=='bd2a0de6ebe88bcfec542356f80a1763492e18343e171d2961247c1514f9b25f'
    browser=json.loads((OUT/'browser-results.json').read_text(encoding='utf-8'));assert browser['all_passed'] and not browser['consoleErrors']
    coverage=json.loads((OUT/'supplementary-selection-summary.json').read_text(encoding='utf-8'));assert coverage['tested']==14006
    assert not any('script.google.com' in u or 'googleusercontent.com' in u for u in browser['blockedExternalRequests'])
    receipt={'all_passed':True,'branch':branch,'head':head,'staged_changes':False,
        'protected_files':len(before),'changed_protected_files':changed,'existing_segment_ids':len(ids),'existing_id_sequence_sha256':sequence,
        'registry_rebuild_identical':True,'network_rebuild_byte_identical':True,
        'static_files':len(public_files),'static_bytes':sum(p.stat().st_size for p in public_files),
        'largest_static_file_bytes':max(p.stat().st_size for p in public_files),
        'tiles':len(manifest['tiles']),'canonical_blocks':len(manifest['registry_blocks']),
        'supplementary_registry_csv_bytes':(ROOT/'website-plan/road-conflation/registry/supplementary-v1.csv').stat().st_size,
        'manifest_bytes':(ROOT/'website/data/proposal-roads/manifest.json').stat().st_size,
        'manifest_sha256':sha(ROOT/'website/data/proposal-roads/manifest.json'),
        'browser_cases':len(browser['cases']),'browser_screenshots':len(browser['screenshots']),
        'supplementary_selection_tested':coverage['tested'],'supplementary_reachable_samples':coverage['reachable'],
        'supplementary_selection_review':coverage['needs_targeted_review'],
        'large_data_untracked':True,'google_sheet_or_live_backend_calls':0}
    (OUT/'FINAL_INTEGRATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
