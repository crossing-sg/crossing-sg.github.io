> Historical local preparation record. For the latest-main integration, API settings, satellite styling and upload status, see [shared integration notes](../shared-integration/README.md).

# Complete Singapore OSM proposal network — local review

Work is on local branch `codex/complete-singapore-osm` in the previously cloned
`C:\Users\sherl\Documents\GitHub\crossing-sg.github.io`. The only local repository
found in `Documents\GitHub` was this clone. Before editing, `git remote -v`,
`git branch -a`, and `git status` showed the original team URL as `origin`, the
`feature/road-network-conflation` branch, and extensive existing uncommitted work.
The new branch carries that work forward. No fetch, reset, checkout of upstream
files, commit, push, merge, Sheet write, Apps Script deployment, or publication was
performed. The original remote was treated as read-only.

## Delivered data and coverage

| Network | Segments | Total line length |
| --- | ---: | ---: |
| Original LTA website network | 55,115 | 2,755.323 km |
| Earlier LTA + OSM release | 69,121 | 3,108.767 km |
| Complete proposal network | 602,199 | 21,836.455 km |
| Additions over the earlier release | 533,078 | 18,727.688 km |

All original LTA properties, coordinates, `seg_id` and `dist_m` values are exactly
preserved. All 14,006 earlier supplementary segments also retain their IDs and
geometry. New OSM numeric IDs start at 71,994. Old ID holes remain reserved.
`ids.json.gz` is an append-only UID-to-ID registry; retain it with the release.
The first two builds verified that previously allocated IDs did not change.
Native fragment geometry and OSM way identity determine UIDs; changing geometry
allocates a new ID rather than reusing one. New crossing distances remain null.

The country PBF is from
[OpenStreetMap France](https://download.openstreetmap.fr/extracts/asia/singapore.osm.pbf),
downloaded on 3 November 2026. Its OSM replication timestamp is
`2026-11-03T00:15:04Z`; SHA-256 is
`4bfc037c081bc5a5a29148c50ddcb5a868d9edd306b50be72e4f87d292363b38`.
It is separate from the preserved earlier BBBike source. The supplier's
[country polygon](https://download.openstreetmap.fr/polygons/asia/singapore.poly)
and whole-way extraction can include border-crossing geometry; there is no extra
land, coastline, planning-boundary, road-category, access or service mask.

The extraction contains **267,980 highway ways across all 32 values**, **47,428
highway nodes**, and **31 highway relations**. Complete tags and source node/member
references are retained in the local compressed source audit. No highway, access
or service value was excluded. The selectable network uses line geometry from
ways, including closed-way outlines. Nodes remain points; relation areas remain
source areas rather than fabricated road centrelines. `relations.py` assembles
30 relation polygons and preserves the remaining relation's complete member
linework. Relation 9396256 has an invalid source area; no member geometry is missing.

Additions retain `highway`, `service`, `access`, `name`, `osm_id`, `osm_type`, source,
and grade tags. The full source audit preserves all other OSM tags. The per-way
`way-coverage.csv.gz` accounts for every source way and its added/represented length.
`statistics.json` breaks down all categories; `comparison.json` records grid coverage.
Coverage expands from 623 original occupied 1 km cells, or 659 earlier-release
cells, to 1,092 cells: 433 newly occupied cells over the earlier release. These
are intersected grid cells, not land area or a claim of unique physical-road area.

Spatial deduplication removes exact line overlap and conservatively aligned
overlap within 0.75 m. Near alignments need at least 5 m of support and at most a
10° direction difference; grade-separated OSM ways do not use fuzzy matching
against grade-unknown LTA geometry. OSM-on-OSM deduplication uses exact shared
linework with matching grade. Reversed geometry is recognized. Missing tails,
short residuals, intersections and separate parallel paths remain. **3,249 source
ways were fully represented and 7,411 partially represented; 266.420 km of source
linework was not added again.** These are representation metrics, not a claim
that all nearby parallel lines are physical duplicates. Existing source overlap
is preserved with its original IDs. Displaced representations beyond the
tolerance may remain and can cause ambiguous selection; see the limitations below.
The final serialization pass removes eight additional coordinate-equivalent
pieces (included in that length accounting), retaining their reserved IDs.
The independent delivery check finds zero new duplicate coordinate geometries
at seven-decimal precision, with grade context kept separate.

The complete review GeoJSON is
`local-outputs/osm-complete/proposal_roads.geojson` (about 198 MB, ignored).
The website release is `website/data/osm-complete/proposal-roads/`, about **44.5 MB**:
1,092 visible-area gzip GeoJSON tiles, canonical 128-ID gzip blocks, an order index,
and a checksum-pinned manifest. The largest compressed road tile is about 74 KB.
Original and earlier assets in `website/data/proposal-roads/` are untouched.
The coverage figure is `local-outputs/osm-complete/coverage-comparison.png`.

## Application changes

The Proposal form and Explore use `SITE.proposalRoadsBase` and the same release
version. The loader accepts validated manifest counts rather than hardcoding the
old segment count. It decompresses `.gz` assets with `DecompressionStream`, loads
visible tiles at zoom 16+, caps requests at four and its cache at 48 entries,
deduplicates tile borders, and uses canonical blocks for deep links and Explore.
OSM attributes survive canonical lookups. Script query versions were updated on
the two affected pages; no CSS or unrelated design was changed in this task.

Apps Script fetches and decompresses the same assets, verifies SHA-256 against
the pinned manifest, repeats canonical matching, and stores the segment and
registry version with a null distance where no analysis exists. It does not trust
a client-supplied distance or review status. Membership is validated against the
registry, not an assumed ID range. The legacy schema migration remains append-only.
Approved v2 records from the preserved previous release can still supply crossing
lines; older records retain their aggregates after explicit review. Existing
moderation, publication thresholds and idempotent retry handling remain in force.

Unlike the earlier filtered release, this release has no access/grade guard
exclusions. It accepts proposals on all included highway categories for review,
including private access, driveways, parking aisles, motorway, construction and
proposed features. Ambiguous multiple-line crossings, invalid IDs, invalid points
and placements outside 2–80 m remain rejected. Dataset inclusion is not a finding
about the suitability of a proposed crossing.

`SITE.appsScriptUrl` remains empty as it was at task start. Local browser previews
rewrite it to an in-memory endpoint only. They never contact the production API.

## Reproduce and validate

Use the existing Python environment, or install the pinned geospatial dependencies
from `../road-conflation/requirements-enrichment.txt`. Node 20+ and the pinned
Playwright dependency in the root package lock are required. Chrome was already
installed; set `QA_CHROME_PATH` if needed. Browser dependencies are prepared by
the existing `npm run prepare:browser` command and reused from local ignored files.

From the repository root in PowerShell:

```powershell
$py = '.\local-outputs\road-conflation-venv\Scripts\python.exe'
& $py website-plan/osm-complete/download.py
& $py website-plan/osm-complete/build.py
& $py website-plan/osm-complete/relations.py
& $py website-plan/osm-complete/configure.py
& $py website-plan/osm-complete/compare.py
& $py website-plan/osm-complete/verify.py
& $py -m unittest discover -s website-plan/osm-complete -p test_processing.py
npm ci --ignore-scripts
npm run fixtures:osm
npm test
npm run test:osm
npm run test:browser:osm
git diff --check
```

`download.py` verifies/reuses the existing download and refuses to replace an
unverified file. `build.py` only writes this task's generated release and ignored
outputs; it never changes analytical inputs or the earlier release. `configure.py`
pins the local frontend and backend to the generated checksum/version and copies
the shared geometry validator. Rebuilding with newer source data requires keeping
the registry so IDs cannot be reused. The web assets are checksum-sensitive and
marked `-text` in `.gitattributes`. SHA checksums refer to **decompressed JSON**.

Validation results are in `validation.json`, `browser-results.json`,
`relation-areas.json`, `comparison.json`, and `statistics.json`:

- 24 existing regression tests, six new integration tests, and four processing
  tests pass. The new submission test covers all 32 real highway categories plus
  private-access, driveway, parking-aisle and existing-road fixtures.
- Browser tests use Chromium 156 and real Mapbox GL JS on desktop and a 390 px
  mobile viewport. They select OSM-only roads, store three synthetic proposals in
  memory, approve them, and assert **rendered** Explore proposal geometry. They
  also check canonical deep links, dense downtown loading and bounded requests.
- All non-loopback requests are blocked during browser tests. No live backend or
  real resident data was used. Screenshots are under
  `local-outputs/osm-complete/browser/`; all browser page-error checks passed.
- Local startup took about 0.2–0.4 seconds, with zero road tiles at island zoom.
  Simulated mobile conditions (1.6 Mbps, 150 ms latency, 4× CPU slowdown) took
  4.8 seconds for startup and 0.8 seconds to select an OSM footway. Dense downtown
  loaded about 3,235 visible segments. These are emulation measurements, not
  physical-device or production-hosting guarantees.
- The integrity check examines every new tile/block and original feature, all
  earlier canonical IDs/geometries, and 14,466 baseline file hashes. Only the two
  intentionally extended local test harnesses differ among baseline files.
  `gap_segments.geojson`, Crossing Gap, Walking Detour, original Storytelling and
  all prior road data remain byte-identical to task start. Existing uncommitted
  changes to unrelated files were left in place.

## Remaining issues and deployment steps

1. Deduplication is deliberately conservative. Offset roads beyond 0.75 m and
   existing overlapping representations can remain; complex/parallel crossings
   can still be ambiguous. Review flagged locations rather than treating the
   total length as unique physical-road kilometres. No road category was removed
   to avoid this uncertainty.
2. One invalid OSM relation area uses complete member linework instead of a
   valid polygon. Relation polygons/point features are audited source features,
   not selectable road centrelines. Category inclusion does not certify access,
   operational status, grade suitability or source accuracy.
3. Startup still downloads a roughly 753 KB manifest. Browsers need native gzip
   `DecompressionStream`. Real mobile devices and hosted network behaviour, the
   external basemap, and Apps Script UrlFetch/Sheets quotas, permissions, redirects,
   CORS and decompression remain deployment checks. The existing original-source
   provenance/licensing questions in the earlier integration guide remain open.

After review and **separate explicit deployment approval**: back up the private
Sheet and both ID registries; test the matching static release and the three Apps
Script files in an isolated Google project/Sheet; serve `.gz` files as raw gzip
bytes without `Content-Encoding: gzip` (clients explicitly decompress); set
`PROPOSAL_DATA_BASE_URL` to the HTTPS directory ending in
`data/osm-complete/proposal-roads`; verify the pinned hashes and migration against
copied legacy rows; then coordinate a compatible static/backend rollout before
setting the reviewed API URL. Preserve both old releases/registries for rollback.
No deployment step has been executed.

OSM data © OpenStreetMap contributors, under the
[ODbL](https://www.openstreetmap.org/copyright). Preserve attribution and the
processed database's licensing obligations when redistributing it.
