# Mexico as a 1,000-city graph

A geographic graph of Mexico: **1,000 cities** pinned to real latitude/longitude, linked by proximity rather than a force-directed layout.

Open [`mexico_map.html`](mexico_map.html) in a browser to explore it. Search a city, filter by state, hover a node for its neighborhood, and pan/zoom the map. Circle size is log population.

| | |
| --- | --- |
| Nodes | 1,000 |
| Edges | 2,565 |
| Mean edge | 31.55 km |
| MST bridges | 10 |

## How the graph is built

1. Load Mexican populated places from [GeoNames `cities1000`](https://download.geonames.org/export/dump/) (`data/cities1000.txt`).
2. Keep the most populous 1,000 places with at least **3 km** of separation, so stacked suburbs do not collapse into one pixel.
3. Connect each city to its **4 nearest neighbors** by haversine distance. That local mesh already looks like a road sketch.
4. Union a **minimum spanning tree** so remote ends (Baja California, Yucatán, the northern border) stay in one connected component. Ten of those MST edges are bridges that were not already in the 4-NN mesh.

Layout is longitude × latitude, not a scramble.

## Regenerating

Python 3, no extra packages for the graph and HTML:

```bash
python3 generate_mexico_graph.py
```

That writes:

- `mexico_cities_graph.json` — nodes, edges, coast outline, and metadata
- `mexico_map.html` — self-contained interactive map (graph JSON inlined)

Optional static PNG (needs matplotlib):

```bash
python3 emit_viz.py
```

Writes `mexico_graph_preview.png` from the current graph JSON.

## Files

```
generate_mexico_graph.py   build graph, HTML, and adjacency matrix
emit_viz.py                PNG preview from mexico_cities_graph.json
mexico_map.html            interactive map
mexico_cities_graph.json   graph payload
data/cities1000.txt        GeoNames dump (CC-BY 3.0)
data/mexico.geojson        country outline
```

## Data

City coordinates and populations come from [GeoNames](https://www.geonames.org/) `cities1000`, licensed [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Admin-1 codes in that dump are the historic GeoNames numbering, mapped to state names in `generate_mexico_graph.py`.
