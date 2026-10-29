from pathlib import Path
from datetime import datetime
import math
import joblib
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
# Put this folder beside data/ and results/ in Routewise-Research.
PROJECT = ROOT.parent
GRAPH_FILE = PROJECT / "data" / "manhattan_drive.graphml"
MODEL_FILE = PROJECT / "results" / "validated_model.joblib"

LOCATIONS = {
    "Times Square": (40.7580, -73.9855),
    "Central Park South": (40.7661, -73.9776),
    "Empire State Building": (40.7484, -73.9857),
    "Wall Street": (40.7060, -74.0087),
    "Columbus Circle": (40.7681, -73.9819),
    "Grand Central Terminal": (40.7527, -73.9772),
    "Union Square": (40.7359, -73.9911),
}

print("Loading Manhattan graph and trained model...", flush=True)
if not GRAPH_FILE.exists() or not MODEL_FILE.exists():
    raise FileNotFoundError(f"Expected {GRAPH_FILE} and {MODEL_FILE}")
G = ox.load_graphml(GRAPH_FILE)
model = joblib.load(MODEL_FILE)
app = FastAPI(title="RouteWise Research Demo")

class RouteRequest(BaseModel):
    source: str
    destination: str

def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*6371*math.asin(min(1, math.sqrt(a)))

def bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2-lon1)
    y = math.sin(dl)*math.cos(p2)
    x = math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(y,x))+360)%360

@app.get("/api/locations")
def locations():
    return {"locations": list(LOCATIONS)}

@app.post("/api/route")
def route(req: RouteRequest):
    lookup = {name.casefold(): name for name in LOCATIONS}
    src = lookup.get(req.source.strip().casefold())
    dst = lookup.get(req.destination.strip().casefold())
    if not src or not dst:
        raise HTTPException(400, "Use one of the supported Manhattan locations listed in the input suggestions.")
    if src == dst:
        raise HTTPException(400, "Source and destination must differ.")
    lat1,lon1 = LOCATIONS[src]
    lat2,lon2 = LOCATIONS[dst]
    try:
        n1 = ox.distance.nearest_nodes(G, lon1, lat1)
        n2 = ox.distance.nearest_nodes(G, lon2, lat2)
        nodes = nx.shortest_path(G, n1, n2, weight="length")
        distance_km = nx.shortest_path_length(G, n1, n2, weight="length")/1000
    except (nx.NetworkXNoPath, nx.NodeNotFound, ValueError) as e:
        raise HTTPException(422, f"Road route unavailable: {e}")
    coords = [[float(G.nodes[n]["y"]), float(G.nodes[n]["x"])] for n in nodes]
    direct_km = haversine(lat1,lon1,lat2,lon2)
    lat_km = abs(lat2-lat1)*111.32
    lon_km = abs(lon2-lon1)*111.32*math.cos(math.radians((lat1+lat2)/2))
    now = datetime.now()
    # Demonstration uses system clock and illustrative weather; not real NYC historical/live inputs.
    features = pd.DataFrame([{
        "pickup_hour":now.hour, "weekday":now.weekday(),
        "is_weekend":int(now.weekday()>=5), "month":now.month,
        "is_peak":int(7<=now.hour<=9 or 16<=now.hour<=19),
        "haversine_km":direct_km,"manhattan_km":lat_km+lon_km,
        "bearing":bearing(lat1,lon1,lat2,lon2),
        "shortest_path_km":distance_km,"avg_temperature":15.0,
        "precipitation":0.0,"snow_depth":0.0
    }])
    estimate = float(np.expm1(model.predict(features)[0]))
    return {"source":src,"destination":dst,"distance_km":distance_km,
            "estimated_minutes":max(0,estimate)/60,
            "coordinates":coords,"start":[lat1,lon1],"end":[lat2,lon2],
            "method":"Shortest-distance path; experimental whole-trip time estimate"}

# Serve the original interface and the API on the same localhost origin.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
