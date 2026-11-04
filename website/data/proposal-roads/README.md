# Proposal-road release web1

Processed static submission-road data: 55,115 original segments plus 14,006 supplementary segments, preserving all original coordinates and IDs. This is a proposal-only source. Do not use it to silently replace Crossing Gap or Walking Detour analytical inputs.

`manifest.json` pins the release and checksums. `tiles/` contains 198 visible-area GeoJSON road tiles; `guards/` contains conservative grade/pedestrian-access context for those areas. `registry/` contains canonical geometry and nullable distance in blocks of 128 numeric IDs. `feature-order.json` permits exact reconstruction of the complete compact GeoJSON. No resident submission records or raw source datasets are included.

Load visible road/guard tiles only at zoom 16 or above, deduplicate `seg_id`, and use canonical blocks for deep links. New `dist_m` values are null, not zero. Guard features are not automatically proposal-eligible roads.

Data © OpenStreetMap contributors, under the [ODbL](https://www.openstreetmap.org/copyright). The team-provided processed primary road network's original provenance/processing history and primary/boundary redistribution permissions remain to be verified. Missing access tags are unknown, not public-access certification. Road geometry is not a safety assessment.

See [the integration guide](../../../website-plan/road-conflation/INTEGRATION.md) for registry restoration, byte-identical network reconstruction, classification limitations, test results and deployment requirements. No live website, Sheet or Apps Script deployment is changed by these local files.
