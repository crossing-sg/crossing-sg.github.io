# Changelog

## 2026-11-04 — Revised BBBike Proposal Road Network

- Restored the previous BBBike Singapore shapefile/PBF sources and LTA-first
  conflation approach for the Proposal road network. OSM supplements genuinely
  missing motorable portions after direction, overlap, connectivity, topology
  and duplicate checks; uncertain parallel alignments remain outside delivery.
- Expanded eligibility to include motorable internal roads, all Service subtypes,
  private/restricted-access roads, driveways and parking aisles without requiring
  public-access evidence, road names or prior manual approval. Pedestrian-only
  and non-motorable paths, and construction/unbuilt-flagged roads, are excluded.
- Preserved all 55,115 original LTA website geometries, properties and IDs, plus
  13,891 valid earlier supplementary IDs. Reserved 115 retired earlier IDs and
  all allocation holes. Preserved genuine directional carriageways, including
  the separate eastbound/westbound Kent Ridge Crescent carriageways near NUS
  Entrance B; those inspected geometries are unchanged from the earlier release.
- Updated Proposal road tiles, canonical registry, feature order, retired-ID
  inventory, checksummed manifest and frontend dataset base/version to
  `proposal-bbbike-motorable-v2-a4c023f624c2e026`. Included the append-only native
  ID allocation snapshot for subsequent rebuilds. Previous releases remain for
  rollback; the intermediate complete-OSM and 411,252-segment local releases
  are not the active network in this update.

| Verified metric | Previous conservative BBBike | Rebuilt motorable BBBike | Replaced shared complete-OSM release |
| --- | ---: | ---: | ---: |
| Total segments | 69,121 | **286,213** | 602,199 |
| Supplementary segments above original LTA | 14,006 | 231,098 | 547,084 |
| Supplementary line length | 353.433 km | 8,103.363 km | 19,081.131 km |
| Identifiable supplementary Service segments | 416 | 153,980 | 164,179 |

Counts describe segments, not distinct physical roads. Service counts include
classifiable earlier supplements. Relative to the earlier BBBike release, the
net increase is 217,092 segments and 153,564 Service segments. With matching
outcomes held fixed, relaxed eligibility accounts for 111,496 candidate
intervals delivering 217,172 segments; this differs from the net release change
because of primary-network representation, segmentation and retired pieces.

- Preserved teammate website changes, including the newer Bukit Batok Central
  Storytelling case, Home layout, Explore interactions, satellite colour settings
  and pilot submission fallback. Crossing Gap and Walking Detour analytical
  inputs/results are unchanged. Only the frontend road base/version is changed;
  existing submission code and URLs, Apps Script files and production Sheets
  are untouched.
- Validation of the integrated release: 30 automated integration/regression tests
  and 38 desktop/mobile browser checks passed. Exhaustive validation verified
  all 2,261 canonical blocks and 264 road tiles/guard assets, matching checksums,
  exact original LTA records, ID reservations and the confirmed carriageways.
  All 21,503 existing tracked files were checked; only `.gitattributes` and the
  two road settings in `site-config.js` differ from the fetched integration base.
  Home, latest Storytelling, Explore, Proposal, Crossing Gap and Walking Detour
  interactions passed. The pilot POST/support flow used the unchanged legacy
  URL and payload, intercepted entirely in memory; zero production Google
  requests were forwarded. `git diff --check` passed.
- Remaining limitations: 64,120 canonical QA intervals across the two source
  representations are withheld from automatic delivery. Construction flags on
  ten retired processed-LTA supplements need operational-status verification.
  Historical proposals with retired/incompatible IDs may not resolve in the new
  registry; no existing submission is deleted or migrated by this update.
- Backend integration remains separate. `proposalApiUrl` stays empty and the
  existing pilot Apps Script URL/fallback remains active. The undeployed v2
  Apps Script registry pin is not changed or deployed here. Production endpoint
  acceptance and historical-record migration are not validated by memory-only
  tests and need a separately coordinated backend update if v2 is enabled.
- Multi-road crossing selection and user-drawn detour routes are discussion
  ideas only; neither feature is implemented in this update.
