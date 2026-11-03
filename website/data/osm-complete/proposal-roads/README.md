# Complete Singapore proposal roads

602,199 segments: all 55,115 original LTA and 14,006 earlier supplementary
segments, plus 533,078 all-highway OSM segments. No highway, access or service
category exclusions. Existing analytical datasets remain unchanged.

`manifest.json` pins the version, counts, tile index and decompressed JSON hashes.
`tiles/*.geojson.gz` contains visible-area roads; `registry/*.json.gz` contains
canonical 128-ID blocks. Serve gzip files as raw bytes, without a gzip
Content-Encoding header: the clients explicitly decompress them. Do not rename
or change these files independently of the pinned Apps Script configuration.

See [processing, comparison, validation and deployment notes](../../../../website-plan/osm-complete/README.md).
The full review GeoJSON and complete source audit are local ignored build outputs.

Data © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright).
