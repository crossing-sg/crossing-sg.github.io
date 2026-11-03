# Basemap restoration and proposal loading QA

## Root cause and correction

The preview server `website-plan/road-conflation/integration_server.cjs` unconditionally rewrote the response for `site-config.js` from `mapbox://styles/mapbox/dark-v11` to `/__test/style.json`. The production source configuration itself already had the correct original style. The previous preview therefore showed a test background rather than the original Mapbox streets/buildings/labels.

The unconditional rewrite is removed. `npm run serve:integration` on port 8765 now preserves the real original basemap. Only an explicit `--isolated-tests` flag enables the simplified test style; `npm run serve:isolated` uses a separate port, 8766. The automated offline suite checks server mode before running. Normal preview returns HTTP 404 for `/__test/style.json`; the explicitly isolated server returns 200.

The actual Mapbox token and all production credential settings were not edited. The served normal-preview token is byte-identical to the source and the original HEAD token. The preview backend remains an in-memory mock, so no production Google Sheet is contacted.

## Real browser verification

Real Chrome 156.0.8078.49 loaded the original network-hosted Mapbox style on both `http://127.0.0.1:8765` and `http://localhost:8765`. No Mapbox responses were mocked. Production Google backend requests were blocked. The token **works on both loopback hostnames**: Mapbox style/tiles/glyphs loaded successfully with no HTTP 401/403 or other Mapbox HTTP errors.

Observed at NUS Kent Ridge:

| Observation | Result |
|---|---:|
| Configured style | `mapbox://styles/mapbox/dark-v11` |
| Style name | Mapbox Dark |
| Total Propose layers, including custom layers | 55 |
| Rendered basemap road features | 69 |
| Rendered building features | 64 |
| Rendered label features | 11 |
| Small pan: unnecessary proposal source uploads | 0 |
| Mapbox HTTP errors | 0 |

Labels included Clementi Rd, Kent Ridge Cr, Kent Ridge Dr, SDE1 Courtyard, Ventus and Information Technology. These counts are observed viewport values, not fixed Mapbox API contracts. All original Propose custom layers remained present. The real-basemap A/B test selected the same expected supplementary numeric ID. Explore retained its original Gap/Detour/proposal layers with the original basemap (61 total layers observed).

Screenshots: [real basemap with A/B](../../local-outputs/basemap-fix/after-loading-optimisation/real-basemap-ab.png), [NUS basemap](../../local-outputs/basemap-fix/after-loading-optimisation/real-basemap-nus.png), [Explore](../../local-outputs/basemap-fix/after-loading-optimisation/real-basemap-explore.png). Detailed evidence: [127.0.0.1](../../local-outputs/basemap-fix/after-loading-optimisation/verification.json), [localhost](../../local-outputs/basemap-fix/localhost-hostname/verification.json), [mode and cache checks](../../local-outputs/basemap-fix/preview-modes.json).

## Separate loading investigation

The before/after loading comparison used the **same real Mapbox basemap**, not the offline style. The road files were not intrinsically slow on loopback: the baseline road/guard transfers took only 3–4 ms. The primary delay was waiting for the map load event, then the fly-to `moveend`, before requesting road geometry. Every small pan also sent unchanged features to the GeoJSON worker.

Changes:

- Initialise Propose custom sources at `style.load`, while basemap tile loading can continue.
- Prefetch only an explicit deep-link destination and refresh visible roads during navigation, with a 100 ms throttle; ordinary island startup still downloads no road tiles.
- Display road geometry independently of restriction files. A/B matching still awaits all guard data and explicitly requires `guardsReady=true`; unavailable guard data fails closed. Server validation and the matching algorithm are unchanged.
- Skip `setData` when the visible metric tile set is unchanged. Existing concurrency, viewport limits and bounded cache remain in place.
- Normal local static files now support content-derived ETag/304 revalidation. API/control responses and explicitly isolated test responses remain `no-store`. New JS cache keys prevent mixing old/new loader code. Production static data, IDs and coordinates were not changed.

Single local deep-link observations:

| Measurement | Before loader optimisation | After |
|---|---:|---:|
| Road tile request start after navigation | 3775 ms | 463 ms |
| Road tile transfer duration | 3.0 ms | 3.2 ms |
| Road data submitted to renderer during fly-to | After end of animation | 1833 ms |
| Data bytes before A/B interaction, including manifest/ID lookup | 374,249 | 266,742 |
| Overall ready, including camera/basemap | 3798 ms | 3223 ms |

The 107,507-byte reduction before selection defers guard transfer; it does **not** omit the safety check. Guard data was fetched and verified before the A/B selection succeeded. The observed overall-ready difference is not a statistical benchmark; external network timing and camera animation still matter. Localhost separately completed in 3103 ms. The decisive improvement is earlier scheduling rather than faster disk/network transfer. An unchanged 130,483-byte road tile revalidated with HTTP 304 and an empty body; unchanged config also revalidated correctly.

## Regression and limitations

24 Node integration tests passed, including display-only loading with failed guards, mandatory selection failure on unavailable guards, and avoiding re-upload on same-tile pans. The 23 existing isolated desktop/mobile browser checks also passed, including A/B, null distances, privacy thresholds, support, deep links, old analytical layers, failed data loads and pilot-backend refusal. Offline tests run only on the explicitly isolated server, not normal preview.

The 69,121-segment release, 55,115 original geometries/IDs, matching rules, 80 m maximum, website styling, privacy rules and backend code were preserved. No production credentials, live website, Google Sheet or Apps Script deployment was changed. No commit, push or PR was made.

Real-network verification here is desktop Chromium with software rendering and ordinary network access. Physical mobile/network/FPS benchmarking and an actually deployed isolated Google backend remain separate deployment checks. This fix does not claim to resolve the previously documented access/provenance or 490 sampled selection-review cases.

## Commands

Normal preview with the real basemap and mock backend:

```text
npm run serve:integration
```

Explicit offline automation, in separate terminals:

```text
npm run serve:isolated
npm run test:browser
```

`verify_basemap.cjs` performs real-network verification; set `QA_BASE_URL` and `QA_PHASE` to choose the loopback hostname and an evidence directory. Refresh an already-open preview tab to discard its previously constructed test-style map. The normal source default and production remain the original Mapbox dark-v11.
