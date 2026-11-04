# BBBike motorable Proposal release

`proposal-bbbike-motorable-v2-a4c023f624c2e026`: 286,213 segments.

Original BBBike shapefile/PBF, rebuilt through the LTA-first spatial pipeline.
All original 55,115 LTA website geometries and IDs are preserved. Motorable Service,
private, parking and internal roads are eligible without public-access evidence;
uncertain spatial matches remain outside automatic delivery.

Gzip asset SHA-256 values in the manifest refer to decompressed JSON. Serve these
files as raw gzip bytes; clients explicitly decompress. Frontend/backend must use
the matching version, manifest hash and base directory when v2 is separately
enabled. This static release preserves the existing pilot submission URL and
fallback. `proposalApiUrl` remains empty; no Apps Script file or deployment is
changed by this release.

See root `CHANGELOG.md` for verified before/after counts, testing and remaining
limitations. Native UID-to-ID allocations are preserved in
`website-plan/road-conflation/registry/bbbike-motorable-v2.csv.gz` with integrity
metadata in `bbbike-motorable-v2.json`. Later rebuilds must seed their allocator
from that snapshot, preserve inactive IDs and holes, and start new allocations
at its `next_id`. The existing complete-OSM registry remains reserved as well.

The original LTA network and both previous releases remain available for rollback.
115 prior supplementary IDs are retired; no original 55,115 LTA ID is retired.
Historical proposals on incompatible/retired IDs may not resolve in this registry;
no production row is deleted or migrated by this static update.
OSM data © OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright
