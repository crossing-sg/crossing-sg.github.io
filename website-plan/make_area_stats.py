"""Cases and crossing provision by URA planning area, for the transition chapter of the Home story.
Writes step1b_area_stats.geojson (planning areas with figures) and step1b_all_cases.geojson (all 32 cases,
public fields only) to story-data/ and website/data/story/.
Run: python make_area_stats.py"""
import json
import os
import warnings

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DL = r"C:\Users\Gangsar Dwi Saputro\Downloads"
OUTS = [os.path.join(HERE, "story-data"), os.path.join(ROOT, "website", "data", "story")]

inc = gpd.read_file(os.path.join(ROOT, "jaywalking_incidents_sg_v2.geojson")).to_crs(3414)
inc["fatal"] = inc.severity.eq("fatal") | inc.outcome.fillna("").str.contains("Meninggal")
pa = gpd.read_file(os.path.join(ROOT, "MasterPlan2019PlanningAreaBoundaryNoSea (1).geojson")).to_crs(3414)[["PLN_AREA_N", "geometry"]]

# Cases per planning area
j = gpd.sjoin(inc, pa, how="left")
cases = j.groupby("PLN_AREA_N").agg(cases=("id", "size"), fatal=("fatal", "sum"))

# Road length (expressways excluded) and share more than 200 m from a crossing
gap = gpd.read_file(os.path.join(DL, "crossing_gap_segments.geojson")).to_crs(3414)
gap = gap[~gap.expressway].copy()
gap["geometry"] = gap.geometry.centroid
g = gpd.sjoin(gap, pa, how="left")
road = g.groupby("PLN_AREA_N").len_m.sum() / 1000
far = g[g.gap_class == ">200"].groupby("PLN_AREA_N").len_m.sum() / 1000

# Road crossings, overhead bridges and underpasses
mk = gpd.read_file(os.path.join(ROOT, "website", "data", "crossing_markers.geojson")).to_crs(3414)
crossings = gpd.sjoin(mk, pa, how="left").groupby("PLN_AREA_N").size()

t = pd.DataFrame({"road_km": road, "crossings": crossings}).join(cases).fillna({"cases": 0, "fatal": 0})
t["pct_far"] = (far / road * 100).reindex(t.index).fillna(0)
t["crossings_per_km"] = t.crossings / t.road_km
national = {
    "crossings_per_km": round(float(t.crossings.sum() / t.road_km.sum()), 1),
    "pct_far": round(float(far.sum() / road.sum() * 100)),
}
print("Singapore", national)

areas = pa.set_index("PLN_AREA_N").join(t, how="inner").reset_index()
areas["name"] = areas.PLN_AREA_N.str.title()
areas["cases"] = areas.cases.astype(int)
areas["fatal"] = areas.fatal.astype(int)
areas["crossings_per_km"] = areas.crossings_per_km.round(1)
areas["pct_far"] = areas.pct_far.round().astype(int)
areas["geometry"] = areas.geometry.simplify(30)
areas = areas[["name", "cases", "fatal", "crossings_per_km", "pct_far", "geometry"]].to_crs(4326)

pts = inc[["id", "status", "year", "fatal", "geometry"]].to_crs(4326)

for out in OUTS:
    areas.to_file(os.path.join(out, "step1b_area_stats.geojson"), driver="GeoJSON")
    pts.to_file(os.path.join(out, "step1b_all_cases.geojson"), driver="GeoJSON")

# Rows for the chart in the story card (areas with two or more cases)
rows = areas[areas.cases >= 2].sort_values(["cases", "crossings_per_km"], ascending=[False, False])
chart = {"national": national, "rows": rows[["name", "cases", "fatal", "crossings_per_km", "pct_far"]].to_dict("records")}
print(json.dumps(chart))
