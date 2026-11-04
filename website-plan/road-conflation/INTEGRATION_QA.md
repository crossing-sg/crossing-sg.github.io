# Integration QA — proposal roads web1

Follow-up: normal previews now use the real Mapbox dark-v11 basemap; the offline style is restricted to explicitly isolated automated tests on port 8766. The initial integration measurements below are historical. See [BASEMAP_QA.md](BASEMAP_QA.md) for real-network verification and subsequent loading optimisation.

Status: local source and static data prepared for review on `feature/road-network-conflation`. No live website or Apps Script deployment, production Sheet write, commit, push or PR occurred. The normal feature build deliberately leaves its API URL disabled. The loopback preview uses synthetic submissions and an in-memory backend.

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
| Actual Apps Script/shared geometry/frontend loader tests | 22 passed, 0 failed |
| Python matching/policy/registry/delivery tests | 94 passed, 0 failed |
| Real Chromium desktop/emulated-mobile checks | 23 passed; 0 uncaught JavaScript exceptions |
| Static verification | 69,121 IDs; all 55,115 original geometries/distances preserved |
| ID reconstruction from Git snapshot | 69,121 matching identities; next allocation 71,994 |
| Complete GeoJSON rebuild without raw inputs | Byte-identical; 11,039,869 bytes |
| Original source/analytical/prior-output preservation | 14,530 protected files; 0 changed |
| Syntax / Git whitespace checks | Passed |
| Staged changes / live backend calls | None / 0 |

Full network SHA-256: `a5760ddf0fc6b050f7fcce173c5d59cda5bb0f75cef9ba03b37baf0e631677a9`.

The Node suite covers existing and five NUS named-road fixtures; null/zero; parallel/junction/grade refusal; shared endpoints; registry holes, stale/forged/malformed IDs; canonical server distance; invalid coordinates; malicious self-approval; all pending/approved threshold cases; rejection; support; retry idempotence; formula-as-text storage; legacy migration; corrupt static data; pilot policy rejection; ID 0 and invalid deep links; visible-area caching and concurrency.

### Browser cases

| Case | Viewport | Result |
|---|---|---|
| existing | Desktop | Passed |
| Engineering Drive 1 | Desktop | Passed |
| Kent Ridge Crescent | Desktop | Passed |
| Kent Ridge Drive | Desktop | Passed |
| real NUS ambiguous parallel/intersection | Desktop | Passed |
| unmatched sea location and grade refusal | Desktop | Passed |
| selection frozen during slow submission | Desktop | Passed |
| Explore geometry/support/deep link, Crossing Gap and Walking Detour routes | Desktop | Passed |
| Home published-only totals/dots and suppression after count falls below three | Desktop | Passed |
| failed tile requests leave no stale road assignment | Desktop | Passed |
| incompatible pilot backend refused before any submission POST | Desktop | Passed |
| existing | Mobile | Passed |
| Engineering Drive 1 | Mobile | Passed |
| Kent Ridge Crescent | Mobile | Passed |
| Kent Ridge Drive | Mobile | Passed |
| real NUS ambiguous parallel/intersection | Mobile | Passed |
| unmatched sea location and grade refusal | Mobile | Passed |
| selection frozen during slow submission | Mobile | Passed |
| Explore geometry/support/deep link, Crossing Gap and Walking Detour routes | Mobile | Passed |
| Home mobile buttons/credit/cards have no overlap | Mobile | Passed |
| Home published-only totals/dots and suppression after count falls below three | Mobile | Passed |
| failed tile requests leave no stale road assignment | Mobile | Passed |
| incompatible pilot backend refused before any submission POST | Mobile | Passed |

Tests run real Mapbox GL JS 2.11.0 in Chrome 156.0.8078.49, with actual form clicks and visible A/B markers, geometry/support/deep links, original Gap/Detour sources and detour routes. The actual `.gs` source runs against an in-memory Sheet and local static files, with no production credentials or external backend implementation.

The test style is a local dark background with valid local Mapbox label glyphs. External basemap tiles/font CSS, Google authorisation/redirects/CORS/quotas, and physical mobile/network performance were **not** verified. Expected console messages from deliberately blocked external requests and failed-tile tests are not uncaught JavaScript application exceptions. No real resident submission was created.

## All-supplementary-ID sampling

| Outcome | IDs |
|---|---:|
| Tested | 14,006 |
| At least one reliable geometric placement | 13,516 (96.50%) |
| Needs targeted inspection after failed sampled placements | 490 |

Up to nine perpendicular placements per segment were checked at 25/50/75% and crossing lengths 24/12/6 m. All 490 review IDs and geometries remain in the release; none was deleted or renumbered. A valid unsampled placement may exist. A passing sample does not prove actual road width, public access or crossing safety.

Failure-reason presence: ambiguous 419; restricted/grade-adjacent 137; adjacent shared-point canonical ID 12. Reasons overlap across trials and are not additive category counts. Unresolved locations show a clear refusal; no unmatched pending-submission workflow is implemented.

Local review: [CSV](../../local-outputs/integration-qa/supplementary-selection.csv), [GeoJSON](../../local-outputs/integration-qa/selection-review.geojson), [priority records](../../local-outputs/integration-qa/selection-review-priority.json).

## Delivery and browser performance

The alternative full GeoJSON is 11.04 MB raw, 1.31 MB gzip in the earlier data-phase review. It would transfer every road and still need guard context. The chosen ordinary GeoJSON tiles work on GitHub Pages without assuming custom gzip response headers.

The static release is **28.71 MB on disk**, containing 198 road tiles, 198 guard files, 563 canonical 128-ID blocks, manifest, reconstruction metadata and README. It is not a page-startup download. The 2.32 MB supplementary ID snapshot sits outside the website tree. The largest static file is 404,193 bytes of reconstruction metadata. The full GeoJSON and redundant 1,000-ID lookup files are not shipped as extra website downloads. The complete website tree, including the existing analytical assets, is 215.21 MB across 14,428 files; this is hosting footprint, not per-page transfer.

| Observation, road data only | Decoded bytes | Requests | Timing/concurrency |
|---|---:|---|---|
| Desktop, 1440 × 1000: initial island view | 118,403 | 1 manifest; 0 tiles | 376 ms functional startup |
| Desktop, 1440 × 1000: cumulative existing + NUS navigation | 582,996 | 2 road tiles + 2 guard files + manifest | peak 2 concurrent |
| Mobile emulation, 390 × 844: initial island view | 118,403 | 1 manifest; 0 tiles | 152 ms functional startup |
| Mobile emulation, 390 × 844: cumulative existing + NUS navigation | 582,996 | 2 road tiles + 2 guard files + manifest | peak 2 concurrent |

Cumulative navigation bytes include the manifest, not that amount on every move. Repeated area loads use the cache; features repeated across tile edges are deduplicated by ID. Requests are capped at four concurrent, cache at 48 parsed entries, and oversized viewports requiring more than 16 tiles ask for zoom-in. No road tiles load at island-level startup. Explore retains its original analytical source loads; this table measures the separate Propose road-loading path.

These observations are loopback HTTP, a software-rendered plain Mapbox background and no network throttling. They do not certify LTE, physical-phone, full-basemap, FPS or heap performance. The backend's manifest is larger than the Apps Script cache-item budget, so it is hash-checked but not cached there; real UrlFetch latency and quotas need isolated deployment testing.

## Reproducibility and preservation

Release: `proposal-roads-v1-d2613da19116bd06-web1`. Hash-pinned canonical blocks, supplementary CSV and snapshot metadata preserve geometry/IDs/retirement records/next allocation. `.gitattributes` prevents platform newline conversion from breaking checksums. Registry restoration and exact complete GeoJSON reconstruction need no raw datasets or GeoPackage. `npm ci` uses the committed lockfile and synthetic crossing fixtures.

Original `gap_segments.geojson` remains byte-identical to HEAD, SHA-256 `09996fe54c1ea1f658936b462040a054f89de7b0ced9929aa06dc501d1f436f2`. Its ID-sequence SHA is `bd2a0de6ebe88bcfec542356f80a1763492e18343e171d2961247c1514f9b25f`. All original analytical/reference/route/story/source and prior output hashes are unchanged. Large inputs, SQLite and GeoPackages remain ignored and untracked. HEAD remains `a4dc7558d89a0192d1b830de735d8da213f2ea53`.

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
