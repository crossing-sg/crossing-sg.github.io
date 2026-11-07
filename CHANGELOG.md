# Changelog

## 2026-11-07 — Home and Methodology v2 proposal consistency

- Switched Home's live proposal cards and island-wide proposal markers from the old pilot Apps Script to the **same reviewed v2 public segments** used by Explore. The map and cards share one version-checked response rather than two potentially inconsistent requests.
- Home now counts each approved parent proposal once overall, even when it belongs to multiple road segments. The map retains one centre marker per published road association; the summary reports accepted proposals and published roads separately. If the v2 request fails, Home displays an unavailable state instead of an incorrect zero or stale pilot figures.
- Updated the Home Storytelling call to action to state clearly that new proposals require review before appearing publicly, including a crossing that spans more than one road. The latest-date card is now labelled as the most recent received *accepted* proposal.
- Updated Methodology's Proposal CSV download to `SITE.proposalApiUrl?view=csv`, the reviewed v2 published-only data source. Clarified that a multi-road proposal can contribute to several road-level counts while remaining one distinct proposal; updated the moderation, representative-line and A/B coordinate privacy explanations.
- Bumped Home Storytelling script/iframe and Methodology configuration cache keys. The old pilot endpoint remains configured elsewhere for compatibility; this change does not alter submissions, approval workflows, Crossing Gap or Walking Detour calculations.


## 2026-11-07 — Retrospective website and demo change-log backfill

These entries document changes already present in repository history but not described individually in the earlier change log. The successor Apps Script deployment remains separate.

### Demo publication, registry and site identity (6 November)

- Changed the successor backend source to allow a road to appear after its **first accepted** proposal, with `MIN_PROPOSALS = 1` and `LINE_MIN = 1`, instead of enforcing a minimum of three. Updated the publication policy, frontend compatibility checks, map filters, legends, tooltips and submission messages for the one-proposal threshold.
- Imported pilot rows with `status=ok` and blank legacy schema/review fields are eligible to count as previously accepted. New submissions continue to require explicit moderation; rejected, mismatched or unsafe records do not automatically become public. A line produced from just one proposal is an approximate rounded location, **not** a multi-person aggregate, and may disclose the suggested crossing location.
- Switched the **frontend** Proposal road registry to the 242,112-segment Clean PBF release. The separate v2 Apps Script endpoint remains unconfigured in `site-config.js`, so its source-code change does not by itself constitute production backend cutover or historical migration.
- Added the pedestrian-crossing favicon and its HTML references across Home, Explore, Proposal, Methodology and About. Updated the handoff/release guidance for the new registry and the one-proposal demo policy.

### Storytelling, maps and visual refinements (3–4 November)

- Kept the wide-screen Home headline on one line; enlarged the reported-case news screenshots to use the full card width. Adjusted story typography, readability, card stacking and scroll/section activation so long chapters and the charts remain visible.
- Kept the two planning-area bar charts together in the left story panel, with short captions. Restored story cards above the map while scrolling, positioned the next-section link below the legend, and adjusted the opening map view/card placement.
- Expanded the case-study narrative: reported fatal cases with news screenshots, a River Valley case and Street View reference, and the Bukit Batok Central case near Block 121, with its walking-detour routes and Street View. Shared the camera across the early chapters, revised the story sequence and made walking routes easier to distinguish.
- Refined the Proposal satellite basemap by suppressing unnecessary road lines, place labels and icons; kept the address-search and crossing-selection interface. Drew proposed crossings as thin white lines, and the direct shortcut on walking-detour examples as a red dashed line.
- Made Explore's selected block routes dismissible by clicking the block again or closing its card. Refined map layer interactions, chapter visibility and site layout without altering the underlying Crossing Gap or Walking Detour computations.

### Initial website and pilot interaction work (26–29 October)

- Built the public GitHub Pages website and project data-processing structure, including Home Storytelling, Explore, Proposal, Methodology and About, a shared navigation/CSS system and the Mapbox-based interactive maps.
- Added the first proposal form and Apps Script/Google Sheet pilot flow, two-point crossing input, address lookup, support handling, and pilot-mode visibility of each submitted crossing. The pilot backend was preserved separately when developing the replacement API.
- Added island-wide reference layers for crossings, bus stops and MRT exits, reference-point pictograms, crossing-gap and detour symbology using a consistent ramp, warning markers for reported cases, and the planning-area infographic.
- Switched the proposal map to satellite imagery, adjusted map hints/instructions, and established the white crossing-line styling and detour route visualization subsequently refined in November.

## 2026-11-07 — Website visual refinements

- Published the approved navigation on Home, Explore, Proposal, Methodology, About and standalone Storytelling. The uppercase `CROSSING SG` title links to Home, and the active page remains marked. Shared `website/css/navigation.css` adds 200 ms colour transitions for navigation and page CTAs, keyboard focus indicators and reduced-motion support. The Home iframe uses the outer navigation bar.
- Updated `website/css/style.css`, `website/css/proposal-responsive.css` and `website/mapbox/index.html` to keep Home's final story card centred at the end of scrolling, prevent overscroll there and centre its two CTAs with a wider gap. Explore's narrow-screen map begins below the navigation.
- Published the previously previewed Methodology and About backgrounds. `website/css/photo-pages.css` stores the approved settings, `website/js/photo-backdrop.js` positions the backgrounds below the white navigation bar, and `website/assets/` contains the two final photos. Methodology uses 1× zoom, 100% / 0% desktop position, 50% / 50% mobile position, 70% brightness, 120% contrast, 126% saturation, 0 px blur and a 70% white overlay. About uses 1× zoom, 50% / 65% position, grayscale, 90% brightness, 130% contrast, 51% saturation, 0 px blur and a 70% white overlay. The Chinese editor remains a local tool.
- Browser checks covered navigation on all six pages, hover and keyboard focus on 42 links, reduced motion, the final Home scroll position with wheel and touch input, and matching text, layout and navigation pixels with and without the photo layer at 1440, 390 and 320 px. Proposal and map regression suites passed with Windows line endings normalised for the source-text comparison. The website changes retain the latest Methodology text, map layers, road data and submission configuration.

## 2026-11-06 — PBF road network and Multi-road Crossing

- Staged the 242,112-segment LTA-first network built from the original OSM France PBF, replacing the BBBike Shapefile-derived dataset at cutover. The candidate preserves all 55,115 original LTA segments and 142,989 geometry-stable supplementary IDs. It reserves 88,109 retired supplementary IDs and adds 44,008 new IDs. Both releases are retained.
- Proposal can associate one A–B crossing with multiple road segments. Apps Script recomputes the selection, keeps one parent with unique road memberships, and preserves literal text through retries and moderation. Unknown-grade crossings remain unvalidated. Explore distinguishes overall Proposals from per-road support and retains its three-approved-Proposal threshold.
- Isolated Google TEST coverage included 64 HTTP checks, 18 Apps Script tests, and browser checks for Proposal and Explore. The final offline integration check verified the frozen asset bytes, explicit Sheet binding, pilot submission compatibility, two-road submission and retry, historical visibility and analytical layer switching. Public browser access and production history cutover remain release gates.
- The new code and data are staged with the current pilot configuration. The [release runbook](apps-script/RELEASE_MULTI_ROAD.md) covers production activation, historical records and rollback.

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
