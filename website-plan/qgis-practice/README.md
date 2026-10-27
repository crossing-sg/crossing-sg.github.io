# Checking one block's walking routes in QGIS

Files for recomputing the walking routes of Blk 121 Bukit Batok Central (postal 650121) with the QGIS Network Analysis tools, and comparing them with the Python results. All files are in EPSG:3414 (SVY21, metres). Rebuild them with `../make_qgis_practice.py`.

| File | Content |
|---|---|
| `01_block_650121.geojson` | Building footprint of Blk 121 |
| `02_block_650121_centroid.geojson` | Start point (centroid of the block) |
| `03_buffer_500m.geojson` | 500 m straight-line search radius |
| `04_destinations_500m.geojson` | 17 bus stops and MRT exits between 50 m and 500 m away, with `straight_m` |
| `05_walk_network.geojson` | OpenStreetMap ways usable on foot, clipped to about 1.4 km around the block |
| `06_python_routes_for_comparison.geojson` | Routes from the Python analysis (`kind` = walk or straight, `route_m`, `detour`) |

## Steps

1. New project, set the project CRS to EPSG:3414. Drag in all six files.
2. Processing Toolbox → Network analysis → **Shortest path (point to layer)**.
   - Vector layer representing network: `05_walk_network`
   - Path type: Shortest
   - Start point: pick the point of `02_block_650121_centroid` on the map
   - Vector layer with end points: `04_destinations_500m`
   - Advanced, topology tolerance: 1
3. Run. The output lines have a `cost` field with the route length in metres.
4. Field calculator on the output:
   - `straight_m` (decimal): `length(make_line(start_point($geometry), end_point($geometry)))`
   - `detour` (decimal): `"cost" / "straight_m"`
5. Compare with `06_python_routes_for_comparison`. For bus stop 43399 (Opp Blk 120) the Python route is 548 m and Google Maps gives 550 m.

Small differences are expected, because QGIS snaps the start point to the nearest network vertex, which may sit on a different side of the block.
