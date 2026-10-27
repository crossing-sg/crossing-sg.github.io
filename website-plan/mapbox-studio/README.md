# Showing the project maps in Mapbox Studio

Each folder holds the data for one map, in WGS84 GeoJSON, ready to upload as a Mapbox tileset. The layer settings below reproduce the colours used on the website. Rebuild the folders with `../make_studio_data.py`.

| Folder | Map | Files |
|---|---|---|
| `1_crossing_gap` | Distance from each 50 m road segment to the nearest crossing | `crossing_gap_segments.geojson` (8 MB) |
| `2_walking_detour` | Mean detour ratio of each HDB block | `detour_blocks.geojson` |
| `3_reference_points` | Crossings, overhead bridges, underpasses, bus stops, MRT exits | 3 files |
| `4_reported_cases` | 5 fatal cases in Singapore and 5 cases in Bukit Batok | `reported_cases.geojson` |
| `5_blk121_detour` | Walking routes from Blk 121 Bukit Batok Central | 3 files |

## 1. Upload the data (once)

1. Go to studio.mapbox.com → **Data manager** (or **Tilesets**) → **New tileset** → **Upload file**.
2. Drop one GeoJSON file, keep the suggested name, and confirm. Repeat for every file you need.
3. Wait until each tileset shows as ready (a few minutes for the 8 MB file).

## 2. Make one style per map

1. **Styles** → open your Monochrome Dark style → **Duplicate**, then rename it, for example "1 Crossing gap".
2. **Add layer** (the + button) → choose the uploaded tileset as the source.
3. Set the layer type and colours from the tables below. For colours that depend on a value, click the colour field → **Use an expression** (the `</>` button) and paste the expression.
4. **Publish**. To show the lecturer, open the style in Studio or use **Share → Preview**.

## Layer settings

### Map 1. Crossing gap

| Setting | Value |
|---|---|
| Source | `crossing_gap_segments` |
| Type | Line |
| Width | 2 at zoom 11, 6 at zoom 16 |
| Colour | expression below |

```json
["step", ["get", "dist_m"], "#5C6370", 50.0001, "#F2C94C", 100.0001, "#F2994A", 200.0001, "#EB5757"]
```
Legend: under 50 m grey, 50 to 100 m yellow, 100 to 200 m orange, over 200 m red.

### Map 2. Walking detour

| Setting | Value |
|---|---|
| Source | `detour_blocks` |
| Type | Circle |
| Radius | 2 at zoom 11, 8 at zoom 16 |
| Stroke | `#1B1E23`, 1 px |
| Colour | expression below |

```json
["step", ["get", "mean_detour"], "#5C6370", 1.5, "#F2C94C", 2, "#F2994A", 2.5, "#EB5757"]
```
Legend: under 1.5 grey, 1.5 to 2.0 yellow, 2.0 to 2.5 orange, over 2.5 red.

### Map 3. Reference points

| Layer | Source | Type | Colour | Radius |
|---|---|---|---|---|
| Crossings, bridges, underpasses | `crossings_bridges_underpasses` | Circle | expression below | 2.5 |
| Bus stops | `bus_stops` | Circle | `#6B7280` | 2 |
| MRT exits | `mrt_exits` | Circle | `#2563EB` | 3 |

```json
["match", ["get", "kind"], "overhead_bridge", "#8B5CF6", "underpass", "#22C55E", "#14B8A6"]
```

### Map 4. Reported cases

| Setting | Value |
|---|---|
| Source | `reported_cases` |
| Type | Circle (Studio does not draw the warning triangle used on the website) |
| Radius | 7 |
| Colour | `#FF3B30` for verified, outline only for indicative: expressions below |
| Filter (optional) | `group` is `fatal_singapore` for the island map, or `bukit_batok` for the town map |

Colour:
```json
["match", ["get", "status"], "indicative", "#1B1E23", "#FF3B30"]
```
Stroke colour (width 2):
```json
["match", ["get", "status"], "indicative", "#FF3B30", "#FFFFFF"]
```
To use a triangle icon instead, upload an SVG warning icon in **Images** and use a Symbol layer.

### Map 5. Blk 121 walking routes

| Layer | Source | Type | Filter | Style |
|---|---|---|---|---|
| Other routes | `blk121_routes` | Line | `kind` is `walk` and `highlight` is false | `#FFFFFF`, width 1.5, opacity 0.3 |
| Example route | `blk121_routes` | Line | `kind` is `walk` and `highlight` is true | `#FFFFFF`, width 4 |
| Straight line | `blk121_routes` | Line | `kind` is `straight` and `highlight` is true | `#D1D5DB`, width 3, dash array 2 2 |
| Block | `blk121_block` | Fill | none | `#38BDF8` |
| Destinations | `blk121_destinations` | Circle | none | fill `#1B1E23`, stroke `#FFFFFF` 2 px, radius 5 |

Centre the map on 103.7479, 1.3510 at zoom 16.5. The example route goes to bus stop 43399 (Opp Blk 120): 96 m in a straight line, 548 m on foot.

## Notes

- Live data (resident proposals and support) comes from the Google Sheet through the website and is not part of these tilesets.
- The website loads these same files directly with Mapbox GL JS, so the Studio maps and the website show the same data.
