"""Cut small GeoJSON files for each Home story chapter and draw preview PNGs.
Run: python make_story_data.py  (reads the processed files in Downloads and the raw LTA/HDB files)"""
import gzip
import json
import os
import zipfile
import warnings

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point, box

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DL = r"C:\Users\Gangsar Dwi Saputro\Downloads"
RAW = os.path.dirname(HERE)
OUT = os.path.join(HERE, "story-data")
PREV = os.path.join(HERE, "story-previews")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

GAP_COLORS = {"<50": "#DADCE0", "50-100": "#F7D774", "100-200": "#EE8B2B", ">200": "#C62828"}
# Bukit Batok has the most reported cases in the news sample (5, of which 3 fatal)
AREA_CASE_IDS = ["V01", "V26", "V27", "I01", "I02"]
EXAMPLE_POSTAL = 650121          # Blk 121 Bukit Batok Central, mean detour 2.90, about 250 m from case V01
EXAMPLE_DEST = "43399"           # bus stop Opp Blk 120 on Bukit Batok Central, 96 m in a straight line, 548 m on foot
FATAL_IDS = ["V01", "V10", "V13", "V15", "V17"]


def save(gdf, name):
    gdf.to_crs(4326).to_file(os.path.join(OUT, name), driver="GeoJSON")


def lta(zname, inner):
    return gpd.read_file(f"zip://{os.path.join(RAW, zname)}!{inner}").set_crs(3414, allow_override=True)


# Step 1: reported fatal cases, public fields only
inc = gpd.read_file(os.path.join(DL, "jaywalking_incidents_sg.geojson"))
cases = inc[inc["id"].isin(FATAL_IDS)][["id", "year", "location_source", "loc_precision", "media", "url", "geometry"]]
cases = cases.rename(columns={"location_source": "place"})
save(cases, "step1_reported_cases.geojson")

# Step 2: cases, crossing distance and crossing markers in Bukit Batok
area_cases = inc[inc["id"].isin(AREA_CASE_IDS)][["id", "status", "year", "location_source", "loc_precision", "url", "geometry"]]
area_cases = area_cases.rename(columns={"location_source": "place"}).to_crs(3414)
save(area_cases, "step2_area_cases.geojson")
area = box(*area_cases.total_bounds).buffer(400)
gap = gpd.read_file(os.path.join(DL, "crossing_gap_segments.geojson")).to_crs(3414)
gap_area = gap[gap.intersects(area) & ~gap.expressway]
save(gap_area[["seg_id", "RD_CD", "dist_m", "gap_class", "geometry"]], "step2_gap_segments.geojson")
cross = lta("RoadCrossing_Sep2026.zip", "RoadCrossing_Sep2026/RoadCrossing.shp")
bridge = lta("PedestrainOverheadbridge_UnderPass_Sep2026.zip",
             "PedestrainOverheadbridge_UnderPass_Sep2026/PedestrainOverheadbridge.shp")
markers = gpd.GeoDataFrame(
    {"kind": ["crossing"] * len(cross) + ["overhead_bridge" if t == "PO" else "underpass" for t in bridge.TYP_CD]},
    geometry=list(cross.geometry.centroid) + list(bridge.geometry.centroid), crs=3414)
markers = markers[markers.intersects(area)]
save(markers, "step2_crossing_markers.geojson")

# Step 3: routes of the example block
routes = []
with gzip.open(os.path.join(DL, "detour_routes_all.geojson.gz"), "rt", encoding="utf-8") as fh:
    for line in fh:
        if f'"postal": {EXAMPLE_POSTAL},' in line:
            routes.append(json.loads(line.strip().rstrip(",")))
routes = gpd.GeoDataFrame.from_features(routes, crs=4326).to_crs(3414)
routes["highlight"] = routes.dest_id.astype(str) == EXAMPLE_DEST
save(routes, "step3_routes.geojson")
hdb = gpd.read_file(os.path.join(RAW, "HDBExistingBuilding.geojson")).to_crs(3414)
blk = hdb[hdb.POSTAL_COD == str(EXAMPLE_POSTAL)][["BLK_NO", "POSTAL_COD", "geometry"]]
save(blk, "step3_block.geojson")
stops = lta("BusStopLocation_Sep2026.zip", "BusStopLocation_Sep2026/BusStop.shp")
stops = stops[stops.BUS_STOP_N.isin(routes.dest_id.astype(str))][["BUS_STOP_N", "LOC_DESC", "geometry"]]
save(stops, "step3_destinations.geojson")


# Previews
def frame(ax, geom, pad=80):
    x0, y0, x1, y1 = geom.bounds
    ax.set_xlim(x0 - pad, x1 + pad)
    ax.set_ylim(y0 - pad, y1 + pad)
    ax.set_axis_off()


land = gpd.read_file(os.path.join(RAW, "MasterPlan2019PlanningAreaBoundaryNoSea (1).geojson")).to_crs(3414)

fig, ax = plt.subplots(figsize=(10, 6))
land.plot(ax=ax, color="#EEEEEC", edgecolor="#FFFFFF", linewidth=0.6)
cases.to_crs(3414).plot(ax=ax, color="#C62828", markersize=60, edgecolor="white")
for _, r in cases.to_crs(3414).iterrows():
    ax.annotate(f"{r['id']} ({int(r['year'])})", (r.geometry.x, r.geometry.y), xytext=(6, 6), textcoords="offset points", fontsize=9)
ax.set_axis_off()
ax.set_title("Step 1  Reported fatal cases (5)", loc="left", fontsize=11)
fig.savefig(os.path.join(PREV, "step1_reported_cases.png"), dpi=130, bbox_inches="tight")

fig, ax = plt.subplots(figsize=(9, 9))
for cls, col in GAP_COLORS.items():
    gap_area[gap_area.gap_class == cls].plot(ax=ax, color=col, linewidth=3)
area_cases[area_cases.status == "verified"].plot(ax=ax, color="#C62828", markersize=80, edgecolor="white", zorder=5)
area_cases[area_cases.status != "verified"].plot(ax=ax, color="white", edgecolor="#C62828", markersize=80, zorder=5)
for _, r in area_cases.iterrows():
    ax.annotate(r["id"], (r.geometry.x, r.geometry.y), xytext=(6, 6), textcoords="offset points", fontsize=9)
hdb[hdb.intersects(area)].plot(ax=ax, color="#BBBBBB")
for kind, col in [("crossing", "#00B8D9"), ("overhead_bridge", "#6A3DE8"), ("underpass", "#12B76A")]:
    m = markers[markers.kind == kind]
    if len(m):
        m.plot(ax=ax, color=col, markersize=25, label=kind)
frame(ax, area, 0)
ax.legend(loc="lower left", fontsize=8)
ax.set_title("Step 2  Bukit Batok, reported cases and distance to the nearest crossing", loc="left", fontsize=11)
fig.savefig(os.path.join(PREV, "step2_crossing_gap.png"), dpi=130, bbox_inches="tight")

fig, ax = plt.subplots(figsize=(9, 9))
gap_area.plot(ax=ax, color="#DDDDDD", linewidth=2)
hdb[hdb.intersects(box(*routes.total_bounds).buffer(100))].plot(ax=ax, color="#D5D5D5")
blk.plot(ax=ax, color="#2F6DB3")
other = routes[~routes.highlight]
other[other.kind == "walk"].plot(ax=ax, color="#C23B3B", linewidth=0.8, alpha=0.25)
hl = routes[routes.highlight]
hl[hl.kind == "walk"].plot(ax=ax, color="#C23B3B", linewidth=3.5)
hl[hl.kind == "straight"].plot(ax=ax, color="#1A1A1A", linewidth=2, linestyle="--")
stops.plot(ax=ax, color="white", edgecolor="#1A1A1A", markersize=40)
frame(ax, routes.union_all(), 60)
r = hl[hl.kind == "walk"].iloc[0]
ax.set_title(f"Step 3  Blk 121 to bus stop {EXAMPLE_DEST}: {int(r.straight_m)} m straight, {int(r.route_m)} m on foot ({r.detour}x)",
             loc="left", fontsize=11)
fig.savefig(os.path.join(PREV, "step3_detour.png"), dpi=130, bbox_inches="tight")

print("cases", len(cases), "| gap segments", len(gap_area), "| markers", len(markers),
      "| routes", len(routes), "| stops", len(stops))
