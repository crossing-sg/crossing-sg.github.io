"""Story data for the River Valley example (case V15, Institution Hill, 2024).
A 300 m buffer around the case shows the road network and the crossings nearby.
Writes step2rv_*.geojson to story-data/ and website/data/story/.
Run: python make_river_valley.py"""
import os
import warnings

import geopandas as gpd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DL = r"C:\Users\Gangsar Dwi Saputro\Downloads"
OUTS = [os.path.join(HERE, "story-data"), os.path.join(ROOT, "website", "data", "story")]
CASE_ID = "V15"
RADIUS = 300

inc = gpd.read_file(os.path.join(ROOT, "jaywalking_incidents_sg_v2.geojson")).to_crs(3414)
case = inc[inc["id"] == CASE_ID][["id", "status", "year", "url", "geometry"]]
c = case.geometry.iloc[0]
buffer = gpd.GeoDataFrame({"radius_m": [RADIUS]}, geometry=[c.buffer(RADIUS)], crs=3414)
area = c.buffer(RADIUS * 2.2)

gap = gpd.read_file(os.path.join(DL, "crossing_gap_segments.geojson")).to_crs(3414)
gap = gap[~gap.expressway & gap.intersects(area)][["seg_id", "dist_m", "gap_class", "len_m", "geometry"]]
markers = gpd.read_file(os.path.join(ROOT, "website", "data", "crossing_markers.geojson")).to_crs(3414)
markers = markers[markers.intersects(area)]

inside = markers[markers.within(buffer.geometry.iloc[0])]
segs = gap[gap.intersects(buffer.geometry.iloc[0])]
road_km = segs.clip(buffer.geometry.iloc[0]).length.sum() / 1000
print("crossings in buffer", (inside.kind == "crossing").sum(), "bridges/underpasses", (inside.kind != "crossing").sum(),
      "road km", round(road_km, 2), "per km", round(len(inside) / road_km, 1),
      "nearest crossing m", round(markers.distance(c).min()))

for out in OUTS:
    case.to_crs(4326).to_file(os.path.join(out, "step2rv_case.geojson"), driver="GeoJSON")
    buffer.to_crs(4326).to_file(os.path.join(out, "step2rv_buffer.geojson"), driver="GeoJSON")
    gap.to_crs(4326).to_file(os.path.join(out, "step2rv_gap_segments.geojson"), driver="GeoJSON")
    markers.to_crs(4326).to_file(os.path.join(out, "step2rv_markers.geojson"), driver="GeoJSON")
print("centre", [round(v, 5) for v in case.to_crs(4326).geometry.iloc[0].coords[0]])
