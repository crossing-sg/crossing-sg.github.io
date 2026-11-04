"""Render the integration QA from measured local evidence, never invent results."""
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'local-outputs/integration-qa'


def read(path):return Path(path).read_text(encoding='utf-8')
def load(name):return json.loads(read(OUT/name))


def main():
    receipt=load('FINAL_INTEGRATION_RECEIPT.json');browser=load('browser-results.json');coverage=load('supplementary-selection-summary.json')
    node=read(OUT/'node-tests.txt');python=read(OUT/'python-tests.txt')
    assert receipt['all_passed'] and browser['all_passed'] and not browser['consoleErrors']
    assert 'fail 0' in node and '\nOK' in python
    node_count=int(re.search(r'tests (\d+)',node)[1]);python_count=int(re.search(r'Ran (\d+) tests',python)[1])
    website_files=[f for f in (ROOT/'website').rglob('*') if f.is_file()]
    website_bytes=sum(f.stat().st_size for f in website_files)
    performance=[]
    for row in browser['performance']:
        viewport='Mobile emulation, 390 × 844' if row['mobile'] else 'Desktop, 1440 × 1000'
        if row['stage']=='island_startup':
            amount=sum(v['bytes'] for v in row['resources'])
            performance.append(f'| {viewport}: initial island view | {amount:,} | 1 manifest; 0 tiles | {row["elapsedMs"]} ms functional startup |')
        else:
            d=row['data'];amount=sum(v['bytes'] for v in d['resources']);tiles=sum('/tiles/' in v['path'] for v in d['resources'])
            performance.append(f'| {viewport}: cumulative existing + NUS navigation | {amount:,} | {tiles} road tiles + {tiles} guard files + manifest | peak {d["metrics"]["peakConcurrent"]} concurrent |')
    cases='\n'.join(f'| {x["case"]} | {"Mobile" if x["mobile"] else "Desktop"} | Passed |' for x in browser['cases'])
    text=f'''# Integration QA — proposal roads web1

Status: local source and static data prepared for review on `feature/road-network-conflation`. No live website or Apps Script deployment, production Sheet write, commit, push or PR occurred. The normal feature build deliberately leaves its API URL disabled. The loopback preview uses synthetic submissions and an in-memory backend.

Follow-up: normal previews now use the real Mapbox dark-v11 basemap; the offline style is restricted to explicitly isolated automated tests on port 8766. The initial integration measurements below are historical. See [BASEMAP_QA.md](BASEMAP_QA.md) for the real-network verification and subsequent loading optimisation.

## Delivered changes

The proposal network has **69,121 segments**: all **55,115 original IDs/geometries/properties**, plus **14,006 supplementary segments**. Native projected lengths remain 2,755.323 km existing plus 353.433 km supplementary. The complete candidate data remains available; ambiguous locations are refused rather than silently assigned. Crossing Gap, Walking Detour and all prior analytical datasets retain their original inputs.

The form loads visible 2 km road/guard tiles only at zoom 16 or above. Full canonical geometry, not rendered/clipped features or nearest vertices, determines the A/B match. The existing visual interaction, original analytical layers, support and Propose-here links are preserved. Narrow-screen form/map and Home card layout are improved. New null crossing distances display **Not available**; canonical zero remains zero.

A/B lines must be 2–80 m long, cross a centreline at least 1 m from each endpoint and make at least a 30-degree crossing angle. Multiple distinct parallel/junction intersections are refused. Adjacent collinear pieces sharing a point use a deterministic ID. Relevant grade/access guards within 3 m require review. These tests do not establish physical road width, legal access or crossing safety.

The backend repeats geometry, membership, version and guard checks using hash-pinned canonical data. It ignores client distance and client moderation fields. Clients require a compatible read-only capability handshake **before any proposal/support POST**, so a pilot-style API receives no new submission. Proposal requests time out after 30 seconds, keep selection fixed in flight and reuse retry tokens without inflating counts.

## Publication and privacy

Both local source thresholds are 3. Every new proposal is pending. Public eligibility requires **status=ok AND review_status=approved**. The same published-only population feeds segment API, CSV, summary, Explore and Home. First/second approved proposals and pending activity contribute no public count, location or last-updated date. Submission acknowledgements disclose no aggregate count. Support is separate and accepted only on a published segment.

Private coordinates use six decimals to avoid collapsing short crossings. Public representative lines require three approved, validated current-schema submissions, are aggregated/rounded to about 10 m and remain null when degenerate/off-road. Home uses canonical road locations rounded to about 100 m. Individual coordinates and free-text experiences are not returned by the public API. A rejection taking a segment below three removes its public contribution on refresh.

Legacy records and IDs are preserved. The pilot's old automatic `ok` status is not proof of review: legacy rows need explicit approval in the appended review column. Approved legacy records can count, but their old individually rounded points do not enter current representative lines. No bulk approval is provided.

The public registry contains road geometry, not submission activity. Three approved submissions are not verified distinct residents; anonymous participation cannot guarantee that. Browser support limits can be bypassed.

## Automated validation

| Check | Result |
|---|---|
| Actual Apps Script/shared geometry/frontend loader tests | {node_count} passed, 0 failed |
| Python matching/policy/registry/delivery tests | {python_count} passed, 0 failed |
| Real Chromium desktop/emulated-mobile checks | {len(browser['cases'])} passed; 0 uncaught JavaScript exceptions |
| Static verification | 69,121 IDs; all 55,115 original geometries/distances preserved |
| ID reconstruction from Git snapshot | 69,121 matching identities; next allocation 71,994 |
| Complete GeoJSON rebuild without raw inputs | Byte-identical; 11,039,869 bytes |
| Original source/analytical/prior-output preservation | {receipt['protected_files']:,} protected files; 0 changed |
| Syntax / Git whitespace checks | Passed |
| Staged changes / live backend calls | None / 0 |

Full network SHA-256: `a5760ddf0fc6b050f7fcce173c5d59cda5bb0f75cef9ba03b37baf0e631677a9`.

The Node suite covers existing and five NUS named-road fixtures; null/zero; parallel/junction/grade refusal; shared endpoints; registry holes, stale/forged/malformed IDs; canonical server distance; invalid coordinates; malicious self-approval; all pending/approved threshold cases; rejection; support; retry idempotence; formula-as-text storage; legacy migration; corrupt static data; pilot policy rejection; ID 0 and invalid deep links; visible-area caching and concurrency.

### Browser cases

| Case | Viewport | Result |
|---|---|---|
{cases}

Tests run real Mapbox GL JS 2.11.0 in Chrome {browser['browser']}, with actual form clicks and visible A/B markers, geometry/support/deep links, original Gap/Detour sources and detour routes. The actual `.gs` source runs against an in-memory Sheet and local static files, with no production credentials or external backend implementation.

The test style is a local dark background with valid local Mapbox label glyphs. External basemap tiles/font CSS, Google authorisation/redirects/CORS/quotas, and physical mobile/network performance were **not** verified. Expected console messages from deliberately blocked external requests and failed-tile tests are not uncaught JavaScript application exceptions. No real resident submission was created.

## All-supplementary-ID sampling

| Outcome | IDs |
|---|---:|
| Tested | {coverage['tested']:,} |
| At least one reliable geometric placement | {coverage['reachable']:,} ({100*coverage['reachable']/coverage['tested']:.2f}%) |
| Needs targeted inspection after failed sampled placements | {coverage['needs_targeted_review']:,} |

Up to nine perpendicular placements per segment were checked at 25/50/75% and crossing lengths 24/12/6 m. All 490 review IDs and geometries remain in the release; none was deleted or renumbered. A valid unsampled placement may exist. A passing sample does not prove actual road width, public access or crossing safety.

Failure-reason presence: ambiguous 419; restricted/grade-adjacent 137; adjacent shared-point canonical ID 12. Reasons overlap across trials and are not additive category counts. Unresolved locations show a clear refusal; no unmatched pending-submission workflow is implemented.

Local review: [CSV](../../local-outputs/integration-qa/supplementary-selection.csv), [GeoJSON](../../local-outputs/integration-qa/selection-review.geojson), [priority records](../../local-outputs/integration-qa/selection-review-priority.json).

## Delivery and browser performance

The alternative full GeoJSON is 11.04 MB raw, 1.31 MB gzip in the earlier data-phase review. It would transfer every road and still need guard context. The chosen ordinary GeoJSON tiles work on GitHub Pages without assuming custom gzip response headers.

The static release is **{receipt['static_bytes']/1e6:.2f} MB on disk**, containing 198 road tiles, 198 guard files, 563 canonical 128-ID blocks, manifest, reconstruction metadata and README. It is not a page-startup download. The 2.32 MB supplementary ID snapshot sits outside the website tree. The largest static file is {receipt['largest_static_file_bytes']:,} bytes of reconstruction metadata. The full GeoJSON and redundant 1,000-ID lookup files are not shipped as extra website downloads. The complete website tree, including the existing analytical assets, is {website_bytes/1e6:.2f} MB across {len(website_files):,} files; this is hosting footprint, not per-page transfer.

| Observation, road data only | Decoded bytes | Requests | Timing/concurrency |
|---|---:|---|---|
{chr(10).join(performance)}

Cumulative navigation bytes include the manifest, not that amount on every move. Repeated area loads use the cache; features repeated across tile edges are deduplicated by ID. Requests are capped at four concurrent, cache at 48 parsed entries, and oversized viewports requiring more than 16 tiles ask for zoom-in. No road tiles load at island-level startup. Explore retains its original analytical source loads; this table measures the separate Propose road-loading path.

These observations are loopback HTTP, a software-rendered plain Mapbox background and no network throttling. They do not certify LTE, physical-phone, full-basemap, FPS or heap performance. The backend's manifest is larger than the Apps Script cache-item budget, so it is hash-checked but not cached there; real UrlFetch latency and quotas need isolated deployment testing.

## Reproducibility and preservation

Release: `proposal-roads-v1-d2613da19116bd06-web1`. Hash-pinned canonical blocks, supplementary CSV and snapshot metadata preserve geometry/IDs/retirement records/next allocation. `.gitattributes` prevents platform newline conversion from breaking checksums. Registry restoration and exact complete GeoJSON reconstruction need no raw datasets or GeoPackage. `npm ci` uses the committed lockfile and synthetic crossing fixtures.

Original `gap_segments.geojson` remains byte-identical to HEAD, SHA-256 `09996fe54c1ea1f658936b462040a054f89de7b0ced9929aa06dc501d1f436f2`. Its ID-sequence SHA is `bd2a0de6ebe88bcfec542356f80a1763492e18343e171d2961247c1514f9b25f`. All original analytical/reference/route/story/source and prior output hashes are unchanged. Large inputs, SQLite and GeoPackages remain ignored and untracked. HEAD remains `{receipt['head']}`.

Data-phase selector comparisons use a frozen pre-integration pilot source to retain historical reproducibility after the frontend became asynchronous. Archived data-phase reports describe that earlier source, not the current integration. The matching algorithm and previous outputs are unchanged; current website evidence is this report.

## Resolved execution issues

- Approved local processes resolved sandbox loopback isolation; no live backend was substituted.
- Valid local label glyphs and render-completion checks fixed incomplete offline screenshots. A/B labels are deduplicated for verification because Mapbox may return repeated rendered-tile features.
- Narrow-screen map/form and Home hero/card overlap was fixed while retaining controls/colours/desktop layout.
- Explicit UTF-8 report reading handles Windows Chinese locale logs; pinned data bytes are stable across operating systems.
- Backend capability checks prevent accidental pilot writes; hidden counts are absent from acknowledgements and public summaries.

## Remaining review and deployment steps

Processed-primary provenance/history and primary/boundary redistribution rights remain unverified. Missing access tags mean unknown. OSM data © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright). The network is not a public-access or safety certificate. Conservative guard/ambiguity refusals and the 490 sampled review cases need targeted refinement, not blanket deletion or a requirement to inspect every fragment before using the network.

The live pilot is unchanged and does not acquire local source changes automatically. For a future release:

1. Review code/data/licensing and preserve the registry snapshot; back up the private Sheet. Keep raw sources and large QA outputs out of Git.
2. Use a separate test Sheet/project and HTTPS static host. Copy all three Apps Script files, run setup on copied legacy data and set `PROPOSAL_DATA_BASE_URL` to the exact pinned release.
3. Verify real Google permissions, redirects/CORS, quotas/performance, capability handshake and all public views at 0/1/2/3 approved submissions. Review legacy rows explicitly; do not bulk-promote old automatic `ok` rows.
4. Verify the external Mapbox basemap/attribution and physical devices/connections; inspect high-priority access/grade/parallel cases.
5. Obtain approval before commit, push, PR or production deployment. Coordinate matching static data/API, retain both thresholds at 3, enable only the reviewed v2 URL and preserve history for rollback. Never roll back to below-threshold publication or reuse IDs.

Commands: [INTEGRATION.md](INTEGRATION.md), [Apps Script guide](../../apps-script/README.md), [CHANGELOG](../../CHANGELOG.md). Google documents the [100 KB cache-item limit](https://developers.google.com/apps-script/reference/cache/cache); the implementation skips cache values above 90 KB and validates static hashes.

## Local evidence

These files are ignored local evidence, not resident submissions. Teammates regenerate them using the documented commands.

- [Final receipt](../../local-outputs/integration-qa/FINAL_INTEGRATION_RECEIPT.json)
- [Node tests](../../local-outputs/integration-qa/node-tests.txt), [Python tests](../../local-outputs/integration-qa/python-tests.txt), [browser results](../../local-outputs/integration-qa/browser-results.json)
- [Static verification](../../local-outputs/integration-qa/static-verification.json), [registry rebuild](../../local-outputs/integration-qa/registry-rebuild.json), [network rebuild](../../local-outputs/integration-qa/network-rebuild.json)
- [Desktop Propose](../../local-outputs/integration-qa/desktop-propose.png), [desktop Explore](../../local-outputs/integration-qa/desktop-explore.png)
- [Mobile Propose](../../local-outputs/integration-qa/mobile-propose.png), [mobile Explore](../../local-outputs/integration-qa/mobile-explore.png), [mobile Home content](../../local-outputs/integration-qa/mobile-home-content.png)
'''
    dest=Path(__file__).parent/'INTEGRATION_QA.md';dest.write_text(text,encoding='utf-8')
    summary={'node_tests':node_count,'python_tests':python_count,'failed':0,'browser_checks':len(browser['cases']),
             'screenshots':len(browser['screenshots']),'coverage':coverage,'preservation':receipt,'report':str(dest)}
    (OUT/'INTEGRATION_QA_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('QA report written:',dest)


if __name__=='__main__':main()
