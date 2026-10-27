"""Build GeoJSON files for checking one block's walking routes by hand in QGIS (Network Analysis).
Example block: Blk 121 Bukit Batok Central (postal 650121). All outputs are in EPSG:3414 (metres).
Run: python make_qgis_practice.py"""
import gzip
import json
import os
import warnings

import geopandas as gpd
from shapely.geometry import box

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DL = r"C:\Users\Gangsar Dwi Saputro\Downloads"
RAW = os.path.dirname(HERE)
OUT = os.path.join(HERE, "qgis-practice")
os.makedirs(OUT, exist_ok=True)

POSTAL = "650121"
RADIUS = 500          # destinations within this straight-line distance
NETWORK_MARGIN = 900  # network extent around the block, wide enough for detours
# OSM highway values that pedestrians cannot use
NOT_WALKABLE = {"motorway", "motorway_link", "trunk_link", "construction", "proposed", "raceway", "bus_guideway"}


def save(gdf, name):
    path = os.path.join(OUT, name)
    gdf.to_file(path, driver="GeoJSON")
    print(name, len(gdf))


def lta(zname, inner):
    return gpd.read_file(f"zip://{os.path.join(RAW, zname)}!{inner}").set_crs(3414, allow_override=True)


hdb = gpd.read_file(os.path.join(RAW, "HDBExistingBuilding.geojson")).to_crs(3414)
block = hdb[hdb.POSTAL_COD == POSTAL][["BLK_NO", "POSTAL_COD", "geometry"]]
centroid = block.copy()
centroid["geometry"] = block.geometry.centroid
save(block, "01_block_650121.geojson")
save(centroid, "02_block_650121_centroid.geojson")

c = centroid.geometry.iloc[0]
buffer = gpd.GeoDataFrame({"radius_m": [RADIUS]}, geometry=[c.buffer(RADIUS)], crs=3414)
save(buffer, "03_buffer_500m.geojson")

stops = lta("BusStopLocation_Sep2026.zip", "BusStopLocation_Sep2026/BusStop.shp")
stops = gpd.GeoDataFrame({"dest_id": stops.BUS_STOP_N, "dest_type": "bus_stop", "name": stops.LOC_DESC}, geometry=stops.geometry, crs=3414)
exits = lta("TrainStationExit.zip", "TrainStationExit/TrainStationExit_Jul2026/Train_Station_Exit_Layer.shp")
exits = gpd.GeoDataFrame({"dest_id": exits.stn_name + " " + exits.exit_code, "dest_type": "train_exit", "name": exits.stn_name},
                         geometry=exits.geometry, crs=3414)
dest = gpd.GeoDataFrame(gpd.pd.concat([stops, exits], ignore_index=True), crs=3414)
dist = dest.distance(c)
dest = dest[(dist <= RADIUS) & (dist >= 50)].copy()   # same rule as the Python analysis
dest["straight_m"] = dest.distance(c).round(1)
save(dest, "04_destinations_500m.geojson")

# Walking network from the OpenStreetMap extract, clipped around the block
area = c.buffer(RADIUS + NETWORK_MARGIN).envelope
area_ll = gpd.GeoSeries([area], crs=3414).to_crs(4326).total_bounds
roads = gpd.read_file(os.path.join(DL, "malaysia-singapore-brunei-251103.osm.pbf"), layer="lines", bbox=tuple(area_ll))
roads = roads[roads.highway.notna() & ~roads.highway.isin(NOT_WALKABLE)].to_crs(3414)
roads = gpd.clip(roads, area)
roads = roads[roads.geom_type.isin(["LineString", "MultiLineString"])].explode(index_parts=False)
save(roads[["osm_id", "name", "highway", "geometry"]], "05_walk_network.geojson")

# Routes from the Python analysis for comparison
feats = []
with gzip.open(os.path.join(DL, "detour_routes_all.geojson.gz"), "rt", encoding="utf-8") as fh:
    for line in fh:
        if f'"postal": {int(POSTAL)},' in line:
            feats.append(json.loads(line.strip().rstrip(",")))
routes = gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(3414)
save(routes, "06_python_routes_for_comparison.geojson")
