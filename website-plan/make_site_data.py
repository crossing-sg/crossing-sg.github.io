"""Prepare light GeoJSON files for the website (data/ folder of the site).
Run: python make_site_data.py"""
import gzip
import json
import os
import warnings

import geopandas as gpd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DL = r"C:\Users\Gangsar Dwi Saputro\Downloads"
RAW = os.path.dirname(HERE)
SITE = os.path.join(RAW, "website", "data")
os.makedirs(os.path.join(SITE, "routes"), exist_ok=True)


def write(gdf, name, keep):
    gdf = gdf.to_crs(4326)[keep + ["geometry"]]
    gj = json.loads(gdf.to_json(drop_id=True))
    for f in gj["features"]:
        f["geometry"] = round_geom(f["geometry"])
    with open(os.path.join(SITE, name), "w", encoding="utf-8") as fh:
        json.dump(gj, fh, separators=(",", ":"))
    print(name, len(gdf), round(os.path.getsize(os.path.join(SITE, name)) / 1e6, 2), "MB")


def round_geom(g):
    def r(c):
        return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    g["coordinates"] = r(g["coordinates"])
    return g


def lta(zname, inner):
    return gpd.read_file(f"zip://{os.path.join(RAW, zname)}!{inner}").set_crs(3414, allow_override=True)


# Crossing gap segments, expressways removed, geometry simplified by 2 m
gap = gpd.read_file(os.path.join(DL, "crossing_gap_segments.geojson")).to_crs(3414)
gap = gap[~gap.expressway].copy()
gap["geometry"] = gap.geometry.simplify(2)
gap["dist_m"] = gap.dist_m.round().astype(int)
write(gap, "gap_segments.geojson", ["seg_id", "dist_m"])

# Detour blocks as points (block centroid) to keep the file small
blocks = gpd.read_file(os.path.join(DL, "detour_blocks_osm.geojson")).to_crs(3414)
blocks["geometry"] = blocks.geometry.centroid
blocks["mean_detour"] = blocks.mean_detour.round(2)
write(blocks, "detour_blocks.geojson", ["postal", "BLK_NO", "n_dest", "mean_detour"])

# Reference points
cross = lta("RoadCrossing_Sep2026.zip", "RoadCrossing_Sep2026/RoadCrossing.shp")
cross["geometry"] = cross.geometry.centroid
cross["kind"] = "crossing"
bridge = lta("PedestrainOverheadbridge_UnderPass_Sep2026.zip",
             "PedestrainOverheadbridge_UnderPass_Sep2026/PedestrainOverheadbridge.shp")
bridge["geometry"] = bridge.geometry.centroid
bridge["kind"] = bridge.TYP_CD.map({"PO": "overhead_bridge", "PU": "underpass"}).fillna("overhead_bridge")
markers = gpd.GeoDataFrame(
    {"kind": list(cross.kind) + list(bridge.kind)},
    geometry=list(cross.geometry) + list(bridge.geometry), crs=3414)
write(markers, "crossing_markers.geojson", ["kind"])
stops = lta("BusStopLocation_Sep2026.zip", "BusStopLocation_Sep2026/BusStop.shp")
write(stops.rename(columns={"BUS_STOP_N": "code", "LOC_DESC": "name"}), "bus_stops.geojson", ["code", "name"])
exits = lta("TrainStationExit.zip", "TrainStationExit/TrainStationExit_Jul2026/Train_Station_Exit_Layer.shp")
write(exits, "mrt_exits.geojson", ["stn_name", "exit_code"])

# Routes, one small file per block, loaded only when a block is clicked
by_postal = {}
with gzip.open(os.path.join(DL, "detour_routes_all.geojson.gz"), "rt", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip().rstrip(",")
        if not line.startswith('{ "type": "Feature"'):
            continue
        f = json.loads(line)
        p = f["properties"]
        f["geometry"] = round_geom(f["geometry"])
        by_postal.setdefault(p["postal"], []).append(
            {"type": "Feature", "properties": {k: p[k] for k in ["dest_id", "dest_type", "route_m", "straight_m", "detour", "kind"]},
             "geometry": f["geometry"]})
total = 0
for postal, feats in by_postal.items():
    path = os.path.join(SITE, "routes", f"{postal}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
    total += os.path.getsize(path)
print("routes", len(by_postal), "files", round(total / 1e6, 1), "MB")
