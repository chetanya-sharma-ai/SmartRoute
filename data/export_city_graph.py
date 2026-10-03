"""
export_city_graph.py
──────────────────────────────────────────────────────────────────────────────
Downloads the Bangalore road network via OSMnx and exports it to
graph_data.json (consumed by the C++ engine) and graph_nodes.csv /
graph_edges.csv (used by ML pipeline and frontend).

Usage:
    python export_city_graph.py
    python export_city_graph.py --place "Indiranagar, Bangalore, India" --simplify
"""

import argparse
import json
import os

import osmnx as ox

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_PLACE = "Bangalore, Karnataka, India"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GRAPH_JSON   = os.path.join(OUTPUT_DIR, "graph_data.json")
NODES_CSV    = os.path.join(OUTPUT_DIR, "graph_nodes.csv")
EDGES_CSV    = os.path.join(OUTPUT_DIR, "graph_edges.csv")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "graph_summary.json")


def download_graph(place: str, network_type: str = "drive",
                   simplify: bool = True):
    """Download road network graph from OpenStreetMap."""
    print(f"[OSMnx] Downloading road network: {place}")
    G = ox.graph_from_place(place, network_type=network_type,
                             simplify=simplify)
    G = ox.add_edge_speeds(G, fallback=40.0)        # adds speed_kph attribute with 40 km/h fallback
    G = ox.add_edge_travel_times(G)  # adds travel_time (seconds)
    print(f"[OSMnx] Graph: {G.number_of_nodes()} nodes, "
          f"{G.number_of_edges()} edges")
    return G


def graph_to_json(G) -> dict:
    """Convert OSMnx graph to C++-compatible JSON format."""
    nodes = []
    for node_id, data in G.nodes(data=True):
        nodes.append({
            "id": int(node_id),
            "lat": float(data.get("y", 0.0)),
            "lon": float(data.get("x", 0.0)),
            "name": str(data.get("name", ""))
        })

    edges = []
    for u, v, data in G.edges(data=True):
        length     = float(data.get("length", 0.0))          # meters
        speed_kph  = float(data.get("speed_kph", 40.0))
        edges.append({
            "from":      int(u),
            "to":        int(v),
            "length":    round(length, 2),
            "speed_kph": round(speed_kph, 1),
            "name":      str(data.get("name", ""))
        })

    return {"nodes": nodes, "edges": edges}


def save_csvs(G):
    """Save nodes and edges as CSVs for ML feature engineering."""
    nodes_df, edges_df = ox.graph_to_gdfs(G)

    # Clean up nodes
    node_cols = ["y", "x", "street_count"]
    node_cols = [c for c in node_cols if c in nodes_df.columns]
    nodes_df = nodes_df[node_cols].rename(columns={"y": "lat", "x": "lon"})
    nodes_df.index.name = "node_id"
    nodes_df.reset_index(inplace=True)
    nodes_df["node_id"] = nodes_df["node_id"].astype(int)
    nodes_df.to_csv(NODES_CSV, index=False)
    print(f"[CSV] Saved {len(nodes_df)} nodes -> {NODES_CSV}")

    # Clean up edges
    edge_cols = ["length", "speed_kph", "travel_time", "highway", "name",
                 "oneway", "lanes", "maxspeed"]
    edge_cols = [c for c in edge_cols if c in edges_df.columns]
    edges_df = edges_df[edge_cols]
    edges_df.index.names = ["from", "to", "key"]
    edges_df.reset_index(inplace=True)
    edges_df["from"] = edges_df["from"].astype(int)
    edges_df["to"]   = edges_df["to"].astype(int)
    edges_df.to_csv(EDGES_CSV, index=False)
    print(f"[CSV] Saved {len(edges_df)} edges -> {EDGES_CSV}")

    return nodes_df, edges_df


def save_summary(G, place: str):
    """Save graph summary metadata."""
    try:
        bounds = ox.geocode_to_gdf(place).geometry.iloc[0].bounds
        min_lon, min_lat, max_lon, max_lat = bounds[0], bounds[1], bounds[2], bounds[3]
    except Exception:  # noqa: BLE001 - fall back to graph bounds if geocoding fails
        # Fallback to computing bounding box from actual nodes
        lats = [data.get("y", 0.0) for _, data in G.nodes(data=True)]
        lons = [data.get("x", 0.0) for _, data in G.nodes(data=True)]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

    summary = {
        "place": place,
        "num_nodes": G.number_of_nodes(),
        "num_edges": G.number_of_edges(),
        "bounds": {
            "min_lon": min_lon, "min_lat": min_lat,
            "max_lon": max_lon, "max_lat": max_lat
        },
        "center_lat": (min_lat + max_lat) / 2,
        "center_lon": (min_lon + max_lon) / 2
    }
    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[JSON] Graph summary -> {SUMMARY_JSON}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Export city graph from OSM")
    parser.add_argument("--place", default=DEFAULT_PLACE,
                        help="City/area name to query from OpenStreetMap")
    parser.add_argument("--network", default="drive",
                        choices=["drive", "walk", "bike", "all"],
                        help="Road network type")
    parser.add_argument("--simplify", action="store_true",
                        help="Simplify the graph topology")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Download
    G = download_graph(args.place, args.network, args.simplify)

    # Export graph JSON for C++ engine
    graph_data = graph_to_json(G)
    with open(GRAPH_JSON, "w") as f:
        json.dump(graph_data, f)
    print(f"[JSON] Graph data -> {GRAPH_JSON} "
          f"({os.path.getsize(GRAPH_JSON)//1024} KB)")

    # Export CSVs for ML
    save_csvs(G)

    # Save summary
    summary = save_summary(G, args.place)
    print("\n[OK] Export complete!")
    print(f"   Nodes : {summary['num_nodes']}")
    print(f"   Edges : {summary['num_edges']}")
    print(f"   Center: {summary['center_lat']:.4f}, {summary['center_lon']:.4f}")


if __name__ == "__main__":
    main()
