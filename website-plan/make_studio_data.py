"""Copy the website data into one folder per map, ready to upload to Mapbox Studio as tilesets.
Mapbox uploads expect GeoJSON in WGS84 (EPSG:4326), which is what the website data uses.
Run: python make_studio_data.py"""
import os
import shutil
import warnings

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "website", "data")
OUT = os.path.join(HERE, "mapbox-studio")

FILES = {
    "1_crossing_gap": [("gap_segments.geojson", "crossing_gap_segments.geojson")],
    "2_walking_detour": [("detour_blocks.geojson", "detour_blocks.geojson")],
    "3_reference_points": [("crossing_markers.geojson", "crossings_bridges_underpasses.geojson"),
                           ("bus_stops.geojson", "bus_stops.geojson"),
                           ("mrt_exits.geojson", "mrt_exits.geojson")],
    "5_blk121_detour": [("story/step3_block.geojson", "blk121_block.geojson"),
                        ("story/step3_routes.geojson", "blk121_routes.geojson"),
                        ("story/step3_destinations.geojson", "blk121_destinations.geojson")],
}

for folder, items in FILES.items():
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    for src, dst in items:
        shutil.copyfile(os.path.join(SITE, src), os.path.join(OUT, folder, dst))
        print(folder, dst)

# Map 4 combines the island-wide fatal cases and the Bukit Batok cases in one file
os.makedirs(os.path.join(OUT, "4_reported_cases"), exist_ok=True)
fatal = gpd.read_file(os.path.join(SITE, "story", "step1_reported_cases.geojson"))
fatal["status"] = "verified"
fatal["group"] = "fatal_singapore"
area = gpd.read_file(os.path.join(SITE, "story", "step2_area_cases.geojson"))
area["group"] = "bukit_batok"
cols = ["id", "status", "group", "year", "place", "url", "geometry"]
cases = gpd.GeoDataFrame(pd.concat([fatal[cols], area[cols]], ignore_index=True), crs=4326)
cases.to_file(os.path.join(OUT, "4_reported_cases", "reported_cases.geojson"), driver="GeoJSON")
print("4_reported_cases reported_cases.geojson", len(cases))
