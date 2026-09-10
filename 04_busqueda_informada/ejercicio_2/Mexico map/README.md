# Mexico as a 1,000-city graph

A geographic graph of Mexico: **1,000 cities** pinned to real latitude/longitude, linked by proximity rather than a force-directed layout.

Open [`mexico_map.html`](mexico_map.html) in a browser to explore it. Search a city, filter by state, hover a node for its neighborhood, pan/zoom the map, and find the minimum-km route between two cities with **A\*** — everything runs in the browser. Circle size is log population.

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

## Route search (A*)

In the map, type an origin and a destination and press **Find route** (or hit
Enter). The route is painted on the map: green edges and nodes, blue origin,
red destination, with the rest of the graph dimmed. The panel reports the
**cost in km**, **depth in hops**, **nodes expanded**, and the heuristic used.

- Repeated city names (~39, e.g. `Puebla`, `Guadalupe`) are never assumed: the
  search stops and lists every match with its id and population. Type
  `City, State` — e.g. `Puebla, Baja California` — or `#id` — e.g. `#580` — to
  pick a specific one (same policy as the Python CLI).
- Clicking a node fills the origin field first, then the destination.
- Unknown names show accent-folded suggestions (`Cancun` → `Cancún`).

### How it works

`astar/mexico-astar.js` is a dependency-free browser library (classic
`<script>` tag, global `MexicoAstar`) that runs A* over the same graph JSON
embedded in the HTML — no server, no build step:

| Piece | Detail |
| --- | --- |
| State | city `id` (integer, unambiguous even with repeated names) |
| Actions / cost | go to a neighbor; `edges[].km`, undirected (valid both ways) |
| Heuristic | `h(n)` = haversine straight-line km from `n` to the destination (port of `haversine` in `generate_mexico_graph.py`) |
| Search | frontier ordered by `f(n) = g(n) + h(n)` (binary min-heap, lazy deletion); goal test on expansion |

`h` never overestimates: edge costs are haversine distances too, so the
triangle inequality keeps the heuristic admissible and A* returns
minimum-km routes.

Main entry points: `new MexicoAstar.GeoGraph({ nodes, edges })` and
`MexicoAstar.findRoute(graph, fromId, toId, { heuristic })`, plus a generic
`MexicoAstar.astarSearch({ start, isGoal, successors, h })`. Pass
`heuristic: "zero"` to get uniform-cost search (Dijkstra) for comparison.

### Verified pairs

A* and UCS return the same cost; A* expands fewer nodes:

| Route | Cost | Hops | A* expanded | UCS expanded |
| --- | --- | --- | --- | --- |
| Tijuana → Cancún | 4,528.20 km | 125 | 949 | 998 |
| Mexico City → Monterrey | 1,041.87 km | 27 | 428 | 783 |
| Guadalajara → Mérida | 1,984.75 km | 70 | 736 | 955 |
| Hermosillo → Oaxaca | 2,361.45 km | 62 | 408 | 821 |

### Command line: `find_route.py`

The same A* search, heuristic, and disambiguation policy, from a terminal:

```bash
python find_route.py                                          # Mexico City → Monterrey
python find_route.py --from-city Tijuana --to Cancun
python find_route.py --from-city "Puebla, Baja California" --to "#4"
```

Parameters — none is mandatory; both are optional and have defaults:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `--from-city` | `Mexico City` | origin: `'City'`, `'City, State'`, or `'#id'` |
| `--to` | `Monterrey` | destination: same three forms |

Names match ignoring case and accents (`cancun` → `Cancún`), and a partial
`'City, State'` such as `'Puebla, Baja'` also works. A repeated name is never
assumed: the run exits with code 1 and lists every match with its id and
population, so you can rerun with `'City, State'` or `'#id'`. Look up ids with
`python city_info.py <name>` (it also accepts `'City, State'` and `'#id'`, and
runs interactively with no arguments).

### Tests

The library itself uses no Node APIs; the tests only exercise its logic with
Node's built-in test runner (10 tests, no dependencies):

```bash
node --test astar/test/astar.test.js
```

## Regenerating

The A* route UI and its styles (including the commented-out height tweaks)
are part of `HTML_TEMPLATE` in the script, so `mexico_map.html` can be
regenerated without losing them — the template currently reproduces the map
byte-for-byte as long as `data/cities1000.txt` is unchanged. One requirement:
keep `astar/mexico-astar.js` next to the HTML; the map loads it with a
relative `<script>` tag and the generator does not inline it.

Python 3, no extra packages for the graph and HTML:

```bash
python3 generate_mexico_graph.py
```

That writes:

- `mexico_cities_graph.json` — nodes, edges, coast outline, and metadata
- `mexico_map.html` — interactive map + A* route search (graph JSON inlined; loads `astar/mexico-astar.js`)
- `mexico_adjacency_matrix.json` — dense 0/1 adjacency matrix

Optional static PNG (needs matplotlib):

```bash
python3 emit_viz.py
```

Writes `mexico_graph_preview.png` from the current graph JSON.

## Files

```
generate_mexico_graph.py   build graph, HTML, and adjacency matrix
find_route.py              A* route search CLI (--from-city / --to)
city_info.py               city lookup: info, neighbors, ids of repeated names
emit_viz.py                PNG preview from mexico_cities_graph.json
mexico_map.html            interactive map + A* route search
astar/*.py                 Python A* package used by find_route.py
astar/mexico-astar.js      browser A* library (haversine, GeoGraph, findRoute)
astar/test/astar.test.js   library tests (node --test astar/test/astar.test.js)
mexico_cities_graph.json   graph payload
data/cities1000.txt        GeoNames dump (CC-BY 3.0)
data/mexico.geojson        country outline
```

## Data

City coordinates and populations come from [GeoNames](https://www.geonames.org/) `cities1000`, licensed [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Admin-1 codes in that dump are the historic GeoNames numbering, mapped to state names in `generate_mexico_graph.py`.
