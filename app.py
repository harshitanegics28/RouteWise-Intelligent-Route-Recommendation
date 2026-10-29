
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import json
import math
import logging

import joblib
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "RouteWise_Integrated" / "frontend"

print("Loading Manhattan road network...")
G = ox.load_graphml(ROOT / "data" / "manhattan_drive.graphml")

print("Loading trained ML model...")
model = joblib.load(ROOT / "results" / "validated_model.joblib")

LOCATIONS = {
    "Times Square": (40.7580, -73.9855),
    "Empire State Building": (40.7484, -73.9857),
    "Columbus Circle": (40.7681, -73.9819),
    "Central Park South": (40.7661, -73.9776),
    "Grand Central Terminal": (40.7527, -73.9772),
    "Union Square": (40.7359, -73.9911),
    "Wall Street": (40.7060, -74.0087)
}

def calculate_route(source, destination):
    if source not in LOCATIONS or destination not in LOCATIONS:
        raise ValueError("Please select a supported location.")

    if source == destination:
        raise ValueError("Source and destination must be different.")

    lat1, lon1 = LOCATIONS[source]
    lat2, lon2 = LOCATIONS[destination]

    start_node = ox.distance.nearest_nodes(G, lon1, lat1)
    end_node = ox.distance.nearest_nodes(G, lon2, lat2)

    nodes = nx.shortest_path(
        G,
        start_node,
        end_node,
        weight="length"
    )

    distance_km = nx.shortest_path_length(
        G,
        start_node,
        end_node,
        weight="length"
    ) / 1000

    coordinates = [
        [
            float(G.nodes[node]["y"]),
            float(G.nodes[node]["x"])
        ]
        for node in nodes
    ]

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    haversine_km = (
        2 * 6371 * math.asin(min(1, math.sqrt(a)))
    )

    manhattan_km = (
        abs(lat2 - lat1) * 111.32
        + abs(lon2 - lon1)
        * 111.32
        * math.cos(math.radians((lat1 + lat2) / 2))
    )

    y = math.sin(dl) * math.cos(p2)
    x = (
        math.cos(p1) * math.sin(p2)
        - math.sin(p1) * math.cos(p2) * math.cos(dl)
    )

    bearing = (
        math.degrees(math.atan2(y, x)) + 360
    ) % 360

    now = datetime.now()

    features = pd.DataFrame([{
        "pickup_hour": now.hour,
        "weekday": now.weekday(),
        "is_weekend": int(now.weekday() >= 5),
        "month": now.month,
        "is_peak": int(
            7 <= now.hour <= 9
            or 16 <= now.hour <= 19
        ),
        "haversine_km": haversine_km,
        "manhattan_km": manhattan_km,
        "bearing": bearing,
        "shortest_path_km": distance_km,
        "avg_temperature": 15.0,
        "precipitation": 0.0,
        "snow_depth": 0.0
    }])

    predicted_seconds = max(
        0.0,
        float(np.expm1(model.predict(features)[0]))
    )

    return {
        "source": source,
        "destination": destination,
        "distance_km": float(distance_km),
        "estimated_minutes": predicted_seconds / 60,
        "coordinates": coordinates,
        "start": [lat1, lon1],
        "end": [lat2, lon2]
    }


class RouteWiseHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(FRONTEND),
            **kwargs
        )

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/api/health":
            self.send_json(
                200,
                {"status": "ready"}
            )
            return

        super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/route":
            self.send_json(
                404,
                {"detail": "Endpoint not found"}
            )
            return

        try:
            length = int(
                self.headers.get("Content-Length", 0)
            )

            if length <= 0 or length > 10000:
                raise ValueError("Invalid request size.")

            payload = json.loads(
                self.rfile.read(length).decode("utf-8")
            )

            result = calculate_route(
                payload.get("source", ""),
                payload.get("destination", "")
            )

            self.send_json(200, result)

        except (
            ValueError,
            json.JSONDecodeError,
            nx.NetworkXNoPath,
            nx.NodeNotFound
        ) as error:
            self.send_json(
                400,
                {"detail": str(error)}
            )

        except Exception:
            logging.exception("Route calculation failed")
            self.send_json(
                500,
                {"detail": "Internal route calculation error."}
            )


if __name__ == "__main__":
    if not FRONTEND.is_dir():
        raise FileNotFoundError(
            f"Frontend folder not found: {FRONTEND}"
        )

    server = ThreadingHTTPServer(
        ("127.0.0.1", 8000),
        RouteWiseHandler
    )

    print("\nRouteWise is ready!")
    print("Open: http://127.0.0.1:8000\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping RouteWise...")
    finally:
        server.server_close()
