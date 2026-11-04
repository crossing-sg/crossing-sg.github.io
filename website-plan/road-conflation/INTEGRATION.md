# Proposal-road integration, release web1

This branch prepares local source and static data for review. It does not deploy the website, change the live Apps Script or write to the production Google Sheet. `SITE.appsScriptUrl` is deliberately empty until a compatible backend has passed isolated deployment tests. Never point local tests at the current pilot deployment.

## Data and identity

The proposal network contains 69,121 segments: all 55,115 original website segments and 14,006 supplementary segments. Every original ID, property and coordinate is preserved. New IDs are 57,988–71,993; old ID holes are reserved. Additions are split into pieces of at most 50 m. `website/data/gap_segments.geojson`, Walking Detour datasets and story analytical datasets are unchanged.

`website/data/proposal-roads/` is the Git-trackable static release, not raw input data. The manifest pins the network version, all road/guard tiles and canonical registry blocks with SHA-256 hashes. The form displays visible 2 km road tiles at zoom 16 or above, with at most four concurrent requests and a bounded 48-entry cache. An explicit road deep link prefetches its destination during the fly-to. Restriction/grade guard tiles load before A/B matching, rather than delaying road display, and remain mandatory for selection. Small pans within the same tile set do not re-upload GeoJSON. Oversized viewports requiring more than 16 tiles ask the user to zoom in. Features repeated across tile edges are deduplicated by `seg_id`.

Canonical 128-ID blocks resolve Explore geometry and deep links without loading the full island or the obsolete 1,000-ID index. The full 11.04 MB GeoJSON remains an ignored review/rebuild artifact; it is not an extra startup download. The selected browser format is small ordinary GeoJSON files, supported by GitHub Pages without custom compression headers.

The supplementary roads are reasonably supported vehicular candidates, not certified public-access roads. Missing access tags remain unknown. Named NUS connectors can qualify through positive vehicular-role and corridor evidence. Uncertain service roads, private/restricted roads, parallel/displaced representations and unverified source geometry remain local review records. Parking aisles, private/unverified driveways and pedestrian/cycle/step features were not automatically added. Existing analytical roads are retained, with conservative guard checks applied when making a new submission.

The team-provided processed primary network has unverified original provenance and processing history. Attribute names and agreement with OSM do not establish provenance. OSM tags/geometry use the preserved 24 October 2026 PBF snapshot. Coordinate disagreements in some supplied source ways were quarantined rather than repaired silently. Source masks use the locally provided Master Plan 2025 land boundary plus 20 m.

OSM data © OpenStreetMap contributors, licensed under the [Open Database Licence](https://www.openstreetmap.org/copyright). Maps and manifest provide attribution. Verify primary/boundary licensing, source provenance and ODbL redistribution requirements before a public release. No raw sources or GeoPackages are included in the static release.

All new `dist_m` values are null. Both UI and backend keep null distinct from zero; the UI says “Not available”. Distances to the incomplete crossing-marker snapshot are QA-only and must not be substituted for an actual nearest-crossing distance.

## Matching and submissions

`website/js/road-geometry.js` and the generated `apps-script/RoadGeometry.gs` are byte-identical. They use the full canonical coordinates, not Mapbox-rendered or tile-clipped geometry. The server repeats the checks using hash-pinned tiles; it never trusts client distance or a range-only ID check.

The A/B line must be 2–80 m long, cross a centreline at least 1 m from each end, and cross at an angle of at least 30 degrees. Multiple distinct centreline intersections, uncertain parallel roads and complex junctions are refused. Adjacent collinear pieces meeting at the same point use a deterministic minimum ID. Crossings within 3 m of relevant grade-separated or explicit pedestrian-restriction guard geometry are refused for review. These deliberately conservative checks may reject valid locations; they do not certify physical crossing safety. There is no pending unmatched-road submission path in this release.

Before sending any proposal or support POST, clients require a read-only `capabilities` response confirming the v2 protocol, matching network version, both publication thresholds, moderation requirement and 80 m maximum. An incompatible pilot API receives no submission POST. A 30-second timeout and an in-flight selection lock protect proposal retries and acknowledgement state.

Coordinates are quantised to six decimals for private validation/storage, avoiding the old four-decimal collapse of short crossings. Identical request retries reuse a random submission token and do not create additional proposals. The token identifies an HTTP request, not a person or device. Anonymous participation cannot prove that three submissions came from three different residents.

Every new submission is stored with `status=pending` and `review_status=pending`. Public eligibility requires `status=ok` and `review_status=approved`, a valid registry ID and valid choices. Free text remains private. Do not infer approval from the old pilot's automatically assigned `ok` status: legacy rows need an explicit review decision in the appended review column. Setup preserves old rows and headers; no bulk approval is provided.

## Publication and privacy

Both `MIN_PROPOSALS` and `LINE_MIN` are 3. Lower values fail closed. Segment responses, CSV, public summary totals, last-updated dates, Explore and Home Story Map all use the same published-only population. A segment with fewer than three approved proposals contributes no ID, location, count, support or timestamp. Submission acknowledgements reveal no aggregate count.

Public representative lines require at least three approved current-schema validated submissions and four-decimal aggregation. Degenerate/off-road aggregate lines are omitted. Legacy proposals can contribute after explicit approval, but their old individually rounded coordinates are not promoted into new representative lines. Home points use canonical segment coordinates rounded to about 100 m. Rejecting an approved row can remove a segment and its summary contribution on the next refresh. Support is accepted only for published segments, remains separate from proposal counts and does not unlock publication.

The old live pilot remains unchanged by this branch. Its historical behaviour is not retroactively fixed until a separately authorised deployment is completed.

## Reproduce without raw datasets

The immutable `registry/supplementary-v1.csv` contains supplementary UID, numeric ID, native geometry hash, source and retirement metadata. `snapshot-v1.json` pins its hash, the original analytical GeoJSON hash, release manifest hash and next allocation number. Website baseline identities are reconstructed from the unchanged analytical GeoJSON.

From the repository root, using the configured Python environment:

```powershell
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' 'website-plan/road-conflation/export_proposal_release.py' --verify
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' 'website-plan/road-conflation/export_proposal_release.py' --restore-registry 'local-outputs/integration-qa/another-registry.sqlite'
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' 'website-plan/road-conflation/export_proposal_release.py' --rebuild-geojson 'local-outputs/integration-qa/another-network.geojson'
```

Use a new SQLite destination: restore refuses to overwrite an existing registry. Verification/restoration/rebuilding use only Git-trackable processed assets and Python standard-library/SQLite support; source conflation inputs and the GeoPackage are unnecessary. The full GeoJSON rebuild is byte-identical to the validated 11.04 MB artifact. Exporting a new release without flags requires the original validated local production outputs and geospatial environment, and regenerates the pinned backend config/shared geometry file.

Never allocate published IDs afresh from rounded delivery geometry or discard the registry. Native geometry hashes have millimetre semantics; delivery coordinates have six-decimal semantics. Synchronise the approved snapshot before future allocations. Separate clones can allocate conflicting unpublished IDs: resolve those conflicts against the last published registry before release, never by renumbering already published segments. Retired identities are retained and never reused.

## Local tests

Node 20 or later is required. `package.json` and `package-lock.json` pin Playwright 1.62.1. Install with `npm ci` in an ordinary development checkout if the bundled runtime is unavailable. Python standard-library verification needs no geospatial installation; full source export uses the existing local environment.

```text
npm test
npm run test:coverage
npm run prepare:browser
npm run serve:integration
```

The normal server binds `127.0.0.1:8765` and preserves the original `mapbox://styles/mapbox/dark-v11` basemap. It rewrites only the API URL to the in-memory Sheet mock. No production credentials are changed. Unchanged static responses support ETag/304 revalidation; API/test-control responses remain uncached. Test controls exist only in this development server outside `website/`; they are never published. Stop the server with Ctrl+C.

For explicitly offline automated tests, start a separate server and run the suite in another terminal:

```text
npm run serve:isolated
npm run test:browser
```

`serve:isolated` passes `--isolated-tests --port 8766`. Only that explicit flag enables `/__test/style.json`; the endpoint is 404 on the normal preview. The browser suite defaults to port 8766 and checks the server mode before running, so it cannot quietly replace the normal developer basemap. Committed synthetic fixtures require no ignored pilot outputs.

Offline browser tests use real Chromium/Mapbox GL JS 2.11.0 and local copies of public libraries/glyphs. Separate real-network verification in `verify_basemap.cjs` confirms the unchanged token works on both 127.0.0.1 and localhost, including Mapbox roads, buildings and labels; see `BASEMAP_QA.md`. The offline suite still blocks external requests. Deployed Apps Script permissions/CORS and real mobile/network performance remain deployment checks. If Chrome is not installed at the Windows default path, set `QA_CHROME_PATH`, or install Chromium with `npx playwright install chromium`.

The ignored `local-outputs/integration-qa/vendor/` needs `mapbox-gl.js`, `mapbox-gl.css`, `scrollama.js`, `intersection-observer.js` and valid `glyphs-0-255.pbf` from the public versions used by the site. They are test dependencies, not redistributed source datasets. The QA report records local test results, exact limits and screenshots.

The explicit `prepare:browser` command downloads these public dependencies using the existing public Mapbox token and records checksums locally. It reuses present files. `.gitattributes` preserves exact bytes for pinned static data and the identity snapshot across operating systems.

`test:coverage` checks every supplementary ID at up to nine perpendicular sample placements (25/50/75% along the segment, crossing lengths 24/12/6 m). It found a reliable geometric selection for 13,516 IDs; 490 need targeted inspection because the sampled placements were ambiguous, restricted/grade-adjacent or canonically associated with an adjacent piece. Their geometry and IDs remain in the release. The ignored selection-review GeoJSON/CSV preserves the failed sample cases; this is not proof that no other valid placement exists, nor a physical road-width or crossing-safety assessment.

## Future production deployment, only after approval

1. Review source/code/static release and licensing, preserve the ID snapshot, and back up the private Sheet. Keep all raw inputs and local GeoPackages out of Git.
2. Create a separate test Sheet and Apps Script project. Copy `Code.gs`, `RegistryConfig.gs` and `RoadGeometry.gs`. Run `setup()` only there and review header migration on copied legacy data.
3. Host this exact static release at a reviewed HTTPS test URL ending in `proposal-roads/`. Set Script Property `PROPOSAL_DATA_BASE_URL` to it. The manifest and every fetched block/tile must match the generated hashes. Do not change the pinned hashes to accommodate an unexplained mismatch.
4. Deploy that isolated test backend and verify real Apps Script authorisation, UrlFetch access, Sheets behaviour, redirects/CORS, quotas and latency. Validate 0/1/2/3 approved versus pending/rejected proposals across all public views. Anonymous anti-abuse controls and review practices require further operational assessment.
5. Check real Mapbox basemap labels/attribution, mobile devices, realistic connections, high-priority road access and grade cases. The offline baseline test does not replace these checks.
6. Obtain approval before committing, pushing, creating a PR or updating any production deployment. Publish matching static assets before enabling the v2 API URL; the backend fails closed on mismatched data. Coordinate the website/API switch rather than connecting new clients to the pilot API.
7. For an authorised migration, preserve every legacy row and original ID, append the review columns, review legacy records explicitly, set both thresholds to 3 and keep the Sheet private. Enable only the reviewed compatible URL in `site-config.js`.
8. Smoke-test public maps, CSV and summary privacy. Roll back the frontend/API as a compatible pair if needed; never roll back to exposing below-threshold records, reuse supplementary IDs or erase the audit history.
