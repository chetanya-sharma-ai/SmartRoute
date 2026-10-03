# SmartRoute — Portfolio Launch Guide

## Run the local demo

1. In PowerShell, go to the project folder and start the API:
   `uvicorn api.main:app --reload --port 8000`
2. Open `http://localhost:8000/app` or open `frontend/index.html` in a browser.
3. Try the route picker and congestion heatmap. Use node IDs from `data/graph_nodes.csv`.
4. The local terminal demo is `python demo.py --nodes 300 --trials 3`.

The included road graph is an OpenStreetMap extract for Indiranagar (322 nodes, 838 edges). Congestion predictions are based on generated synthetic traffic data; this project does not use live traffic feeds. If you refresh the map with OSMnx, the export command in the README needs internet access.

## Evidence to capture

- The map with a route and the selected hour/weather.
- The API documentation at `http://localhost:8000/docs`.
- The terminal demo output.
- Optionally, a short recording showing the map controls.

Only describe behavior visible in the current build. The supplied Python benchmark shows fewer explored nodes for A*, but higher wall-clock time than Dijkstra on its tested graph sizes. It does not benchmark the C++ engine.

## LinkedIn draft

🚦 I built SmartRoute, a traffic-routing portfolio prototype using C++17, Python, machine learning, and an interactive map.

It combines:
- A* and Dijkstra pathfinding in a C++17 graph engine
- A FastAPI backend and Leaflet map using an Indiranagar OpenStreetMap sample
- Congestion predictions trained on generated synthetic traffic data
- A* and Dijkstra benchmark results, with the measured tradeoffs documented

On the synthetic-data holdout, the saved metrics report XGBoost R² of 0.9524 and Random Forest accuracy of 88.52%. The included test suite passes 13 tests. These results are from synthetic data, not live traffic.

GitHub: https://github.com/chetanya-sharma-ai/SmartRoute

#MachineLearning #CPlusPlus #Python #FastAPI #OpenStreetMap #AIandML #SmartRoute