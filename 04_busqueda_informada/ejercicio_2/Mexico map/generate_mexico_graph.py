#!/usr/bin/env python3
"""Build a 1,000-node geographic graph of Mexican cities.

Nodes are the most populous GeoNames places in Mexico, kept at true
lat/lon. Edges are the 4 nearest neighbors by haversine distance, unioned
with a minimum spanning tree so the graph is a single connected component.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CITIES_PATH = DATA / "cities1000.txt"
OUTLINE_PATH = DATA / "mexico.geojson"
GRAPH_PATH = ROOT / "mexico_cities_graph.json"
HTML_PATH = ROOT / "mexico_map.html"
ADJ_PATH = ROOT / "mexico_adjacency_matrix.json"

N_NODES = 1000
K_NEIGHBORS = 4
MIN_SEP_KM = 3.0
EARTH_KM = 6371.0

# GeoNames historic MX.admin1 codes (not INEGI 2015+ numbering).
STATES = {
    "01": "Aguascalientes",
    "02": "Baja California",
    "03": "Baja California Sur",
    "04": "Campeche",
    "05": "Chiapas",
    "06": "Chihuahua",
    "07": "Coahuila",
    "08": "Colima",
    "09": "Mexico City",
    "10": "Durango",
    "11": "Guanajuato",
    "12": "Guerrero",
    "13": "Hidalgo",
    "14": "Jalisco",
    "15": "México",
    "16": "Michoacán",
    "17": "Morelos",
    "18": "Nayarit",
    "19": "Nuevo León",
    "20": "Oaxaca",
    "21": "Puebla",
    "22": "Querétaro",
    "23": "Quintana Roo",
    "24": "San Luis Potosí",
    "25": "Sinaloa",
    "26": "Sonora",
    "27": "Tabasco",
    "28": "Tamaulipas",
    "29": "Tlaxcala",
    "30": "Veracruz",
    "31": "Yucatán",
    "32": "Zacatecas",
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(min(1.0, a)))


def load_mexico_cities() -> list[dict]:
    cities: list[dict] = []
    with CITIES_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 15 or parts[8] != "MX":
                continue
            population = int(parts[14] or 0)
            if population <= 0:
                continue
            cities.append(
                {
                    "geoname_id": int(parts[0]),
                    "name": parts[1],
                    "lat": float(parts[4]),
                    "lon": float(parts[5]),
                    "admin1": parts[10],
                    "state": STATES.get(parts[10], parts[10] or "Unknown"),
                    "population": population,
                }
            )
    cities.sort(key=lambda c: (-c["population"], c["name"]))
    return cities


def select_nodes(candidates: list[dict], n: int, min_sep_km: float) -> list[dict]:
    """Greedy: keep highest-population places that are not stacked."""
    selected: list[dict] = []
    for city in candidates:
        if len(selected) >= n:
            break
        if any(
            haversine(city["lat"], city["lon"], other["lat"], other["lon"]) < min_sep_km
            for other in selected
        ):
            continue
        selected.append(city)
    if len(selected) < n:
        for city in candidates:
            if len(selected) >= n:
                break
            if city in selected:
                continue
            selected.append(city)
    return selected[:n]


def pairwise_distances(nodes: list[dict]) -> list[list[float]]:
    n = len(nodes)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine(nodes[i]["lat"], nodes[i]["lon"], nodes[j]["lat"], nodes[j]["lon"])
            dist[i][j] = dist[j][i] = d
    return dist


def knn_edges(dist: list[list[float]], k: int) -> dict[tuple[int, int], float]:
    n = len(dist)
    edges: dict[tuple[int, int], float] = {}
    for i in range(n):
        nearest = sorted(((dist[i][j], j) for j in range(n) if j != i))[:k]
        for d, j in nearest:
            a, b = (i, j) if i < j else (j, i)
            edges[(a, b)] = d
    return edges


def mst_edges(dist: list[list[float]]) -> dict[tuple[int, int], float]:
    n = len(dist)
    in_tree = [False] * n
    best = [math.inf] * n
    parent = [-1] * n
    best[0] = 0.0
    edges: dict[tuple[int, int], float] = {}
    for _ in range(n):
        u = min((i for i in range(n) if not in_tree[i]), key=lambda i: best[i])
        in_tree[u] = True
        if parent[u] >= 0:
            a, b = (parent[u], u) if parent[u] < u else (u, parent[u])
            edges[(a, b)] = best[u]
        for v in range(n):
            if not in_tree[v] and dist[u][v] < best[v]:
                best[v] = dist[u][v]
                parent[v] = u
    return edges


def load_outline() -> list[list[float]]:
    raw = json.loads(OUTLINE_PATH.read_text(encoding="utf-8"))
    return raw["features"][0]["geometry"]["coordinates"][0]


def build_graph() -> dict:
    candidates = load_mexico_cities()
    nodes = select_nodes(candidates, N_NODES, MIN_SEP_KM)
    dist = pairwise_distances(nodes)
    knn = knn_edges(dist, K_NEIGHBORS)
    tree = mst_edges(dist)
    edges = dict(knn)
    for key, km in tree.items():
        edges.setdefault(key, km)

    degrees = [0] * len(nodes)
    edge_records = []
    for (a, b), km in sorted(edges.items()):
        degrees[a] += 1
        degrees[b] += 1
        edge_records.append(
            {
                "source": a,
                "target": b,
                "km": round(km, 2),
                "kind": "knn" if (a, b) in knn else "mst",
            }
        )

    node_records = []
    for i, city in enumerate(nodes):
        node_records.append(
            {
                "id": i,
                "name": city["name"],
                "lat": round(city["lat"], 5),
                "lon": round(city["lon"], 5),
                "population": city["population"],
                "state": city["state"],
                "admin1": city["admin1"],
                "geoname_id": city["geoname_id"],
                "degree": degrees[i],
            }
        )

    km_values = [e["km"] for e in edge_records]
    return {
        "meta": {
            "title": "Mexico 1,000-city proximity graph",
            "country": "Mexico",
            "nodes": len(node_records),
            "edges": len(edge_records),
            "k_neighbors": K_NEIGHBORS,
            "min_separation_km": MIN_SEP_KM,
            "mst_bridge_edges": sum(1 for e in edge_records if e["kind"] == "mst"),
            "mean_edge_km": round(sum(km_values) / len(km_values), 2),
            "max_edge_km": max(km_values),
            "min_edge_km": min(km_values),
            "source": "GeoNames cities1000 (CC-BY 3.0)",
            "construction": (
                f"Top populated places with ≥{MIN_SEP_KM:g} km separation; "
                f"undirected {K_NEIGHBORS}-NN by haversine, union MST."
            ),
        },
        "outline": [[round(lon, 4), round(lat, 4)] for lon, lat in load_outline()],
        "nodes": node_records,
        "edges": edge_records,
    }


def adjacency_payload(graph: dict) -> dict:
    """Dense undirected 0/1 adjacency matrix; row i matches nodes[i].id."""
    n = len(graph["nodes"])
    matrix = [[0] * n for _ in range(n)]
    for edge in graph["edges"]:
        i, j = edge["source"], edge["target"]
        matrix[i][j] = 1
        matrix[j][i] = 1
    ones = sum(sum(row) for row in matrix)
    return {
        "meta": {
            "title": "Mexico city graph adjacency matrix",
            "shape": [n, n],
            "directed": False,
            "weighted": False,
            "symmetric": True,
            "diag": 0,
            "edges": len(graph["edges"]),
            "nonzero": ones,
            "index": "Row and column i correspond to nodes[i] (same ids as mexico_cities_graph.json).",
        },
        "nodes": [
            {"id": node["id"], "name": node["name"], "state": node["state"]}
            for node in graph["nodes"]
        ],
        "matrix": matrix,
    }


def write_adjacency_matrix(graph: dict) -> None:
    ADJ_PATH.write_text(
        json.dumps(adjacency_payload(graph), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def write_html(graph: dict) -> None:
    payload = json.dumps(
        {
            "meta": graph["meta"],
            "outline": graph["outline"],
            "nodes": graph["nodes"],
            "edges": graph["edges"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    html = HTML_TEMPLATE.replace("__GRAPH_JSON__", payload)
    HTML_PATH.write_text(html, encoding="utf-8")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mexico · 1,000-city proximity graph</title>
  <style>
    :root {
      --bg: #f4efe6;
      --ink: #1c1916;
      --muted: #6b6258;
      --line: #c4b8a8;
      --panel: #fffaf2;
      --edge: #8a7d6b;
      --land: #e7dccb;
      --coast: #5c5348;
      --node: #9a3412;
      --node-hi: #c2410c;
      --accent: #1f4d3a;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; height: 100%; background: var(--bg); color: var(--ink); }
    body {
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      display: grid;
      grid-template-columns: minmax(260px, 320px) 1fr;
      min-height: 100%;
    }
    aside {
      padding: 28px 22px 24px;
      border-right: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      flex-direction: column;
      gap: 18px;
      min-height: 100vh;
    }
    h1 {
      font-size: 26px;
      line-height: 1.15;
      font-weight: 600;
      margin: 0;
      letter-spacing: -0.02em;
    }
    .lede { margin: 0; color: var(--muted); font-size: 14px; line-height: 1.45; }
    .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .stat {
      border: 1px solid var(--line);
      padding: 10px 12px;
      background: var(--bg);
    }
    .stat b { display: block; font-size: 20px; font-variant-numeric: tabular-nums; }
    .stat span { color: var(--muted); font-size: 12px; }
    label { font-size: 12px; color: var(--muted); display: block; margin-bottom: 6px; }
    input[type="search"], select {
      width: 100%;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      padding: 8px 10px;
      font: 14px ui-sans-serif, "Helvetica Neue", sans-serif;
    }
    .row { display: flex; gap: 8px; align-items: center; font-size: 13px; color: var(--muted); }
    .row input { accent-color: var(--accent); }
    .city {
      border-top: 1px solid var(--line);
      padding-top: 14px;
      min-height: 92px;
    }
    .city h2 { margin: 0 0 4px; font-size: 18px; }
    .city p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.4; }
    .legend { font-size: 12px; color: var(--muted); line-height: 1.45; }
    .swatch { display: inline-block; width: 8px; height: 8px; background: var(--node); border-radius: 50%; margin-right: 6px; }
    main { position: relative; overflow: hidden; }
    svg { width: 100%; height: 100vh; display: block; cursor: grab; }
    svg.dragging { cursor: grabbing; }
    text.lbl {
      font: 600 11px ui-sans-serif, "Helvetica Neue", sans-serif;
      fill: var(--ink);
      paint-order: stroke;
      stroke: var(--bg);
      stroke-width: 3px;
      pointer-events: none;
    }
    footer.source {
      margin-top: auto;
      font-size: 11px;
      color: var(--muted);
      line-height: 1.4;
    }
    @media (max-width: 800px) {
      body { grid-template-columns: 1fr; }
      aside { min-height: auto; }
      svg { height: 70vh; }
    }
  </style>
</head>
<body>
  <aside>
    <div>
      <h1>Mexico as a graph</h1>
      <p class="lede">1,000 cities, pinned to real coordinates and linked to their nearest neighbors.</p>
    </div>
    <div class="stats" id="stats"></div>
    <div>
      <label for="q">Find a city</label>
      <input id="q" type="search" placeholder="e.g. Oaxaca, Tijuana…" autocomplete="off" />
    </div>
    <div>
      <label for="state">State</label>
      <select id="state"><option value="">All states</option></select>
    </div>
    <div class="row">
      <input id="labels" type="checkbox" checked />
      <label for="labels" style="margin:0">Label the largest cities</label>
    </div>
    <div class="city" id="detail">
      <h2>Hover a node</h2>
      <p>Circle size is log population. Edges are 4-nearest neighbors plus a few MST bridges so remote towns stay connected.</p>
    </div>
    <p class="legend"><span class="swatch"></span>Node = city · line = proximity edge<br>Layout is longitude × latitude, not a force-directed scramble.</p>
    <p class="source" id="source"></p>
  </aside>
  <main>
    <svg id="map" viewBox="0 0 1100 720" role="img" aria-label="Map graph of Mexico"></svg>
  </main>
  <script>
    const G = __GRAPH_JSON__;
    const svg = document.getElementById("map");
    const NS = "http://www.w3.org/2000/svg";
    const W = 1100, H = 720, PAD = 28;
    const lons = G.outline.map(p => p[0]).concat(G.nodes.map(n => n.lon));
    const lats = G.outline.map(p => p[1]).concat(G.nodes.map(n => n.lat));
    const lon0 = Math.min(...lons), lon1 = Math.max(...lons);
    const lat0 = Math.min(...lats), lat1 = Math.max(...lats);
    const midLat = (lat0 + lat1) / 2 * Math.PI / 180;
    const xSpan = (lon1 - lon0) * Math.cos(midLat);
    const ySpan = (lat1 - lat0);
    const scale = Math.min((W - 2 * PAD) / xSpan, (H - 2 * PAD) / ySpan);

    function project(lon, lat) {
      const x = PAD + (lon - lon0) * Math.cos(midLat) * scale;
      const y = H - PAD - (lat - lat0) * scale;
      return [x, y];
    }

    const pops = G.nodes.map(n => n.population);
    const pmin = Math.log10(Math.max(1, Math.min(...pops)));
    const pmax = Math.log10(Math.max(...pops));
    function radius(pop) {
      const t = (Math.log10(Math.max(pop, 1)) - pmin) / (pmax - pmin || 1);
      return 1.6 + t * 7.4;
    }

    const world = document.createElementNS(NS, "g");
    world.setAttribute("id", "world");
    svg.appendChild(world);

    const land = document.createElementNS(NS, "path");
    land.setAttribute("d", G.outline.map((p, i) => {
      const [x, y] = project(p[0], p[1]);
      return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
    }).join(" ") + " Z");
    land.setAttribute("fill", "#e7dccb");
    land.setAttribute("stroke", "#5c5348");
    land.setAttribute("stroke-width", "1.2");
    world.appendChild(land);

    const edgeLayer = document.createElementNS(NS, "g");
    edgeLayer.setAttribute("stroke", "#8a7d6b");
    edgeLayer.setAttribute("stroke-opacity", "0.45");
    edgeLayer.setAttribute("fill", "none");
    world.appendChild(edgeLayer);
    const edgeEls = [];
    for (const e of G.edges) {
      const a = G.nodes[e.source], b = G.nodes[e.target];
      const [x1, y1] = project(a.lon, a.lat);
      const [x2, y2] = project(b.lon, b.lat);
      const line = document.createElementNS(NS, "line");
      line.setAttribute("x1", x1.toFixed(2));
      line.setAttribute("y1", y1.toFixed(2));
      line.setAttribute("x2", x2.toFixed(2));
      line.setAttribute("y2", y2.toFixed(2));
      line.setAttribute("stroke-width", e.kind === "mst" ? "0.7" : "0.95");
      line.dataset.s = e.source;
      line.dataset.t = e.target;
      edgeLayer.appendChild(line);
      edgeEls.push(line);
    }

    const nodeLayer = document.createElementNS(NS, "g");
    world.appendChild(nodeLayer);
    const nodeEls = G.nodes.map((n, i) => {
      const [x, y] = project(n.lon, n.lat);
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", x.toFixed(2));
      c.setAttribute("cy", y.toFixed(2));
      c.setAttribute("r", radius(n.population).toFixed(2));
      c.setAttribute("fill", "#9a3412");
      c.setAttribute("fill-opacity", "0.88");
      c.setAttribute("stroke", "#f4efe6");
      c.setAttribute("stroke-width", "0.6");
      c.dataset.i = i;
      nodeLayer.appendChild(c);
      return c;
    });

    const labelLayer = document.createElementNS(NS, "g");
    world.appendChild(labelLayer);
    const labeled = [...G.nodes].sort((a, b) => b.population - a.population).slice(0, 18);
    const labelEls = labeled.map(n => {
      const [x, y] = project(n.lon, n.lat);
      const t = document.createElementNS(NS, "text");
      t.setAttribute("class", "lbl");
      t.setAttribute("x", (x + 6).toFixed(1));
      t.setAttribute("y", (y - 6).toFixed(1));
      t.textContent = n.name;
      labelLayer.appendChild(t);
      return t;
    });

    function fmt(n) { return n.toLocaleString("en-US"); }
    document.getElementById("stats").innerHTML = [
      ["Nodes", fmt(G.meta.nodes)],
      ["Edges", fmt(G.meta.edges)],
      ["Mean hop", G.meta.mean_edge_km + " km"],
      ["MST bridges", fmt(G.meta.mst_bridge_edges)],
    ].map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");
    document.getElementById("source").textContent =
      G.meta.source + " · " + G.meta.construction;

    const stateSel = document.getElementById("state");
    [...new Set(G.nodes.map(n => n.state))].sort().forEach(s => {
      const o = document.createElement("option");
      o.value = s; o.textContent = s;
      stateSel.appendChild(o);
    });

    const detail = document.getElementById("detail");
    function show(n) {
      if (!n) {
        detail.innerHTML = "<h2>Hover a node</h2><p>Circle size is log population. Edges are 4-nearest neighbors plus a few MST bridges so remote towns stay connected.</p>";
        return;
      }
      detail.innerHTML = `<h2>${n.name}</h2><p>${n.state}<br>Population ${fmt(n.population)} · degree ${n.degree}<br>${n.lat.toFixed(3)}°, ${n.lon.toFixed(3)}°</p>`;
    }

    let active = -1;
    function highlight(i) {
      active = i;
      const neighbors = new Set();
      edgeEls.forEach(el => {
        const hit = i >= 0 && (el.dataset.s == i || el.dataset.t == i);
        el.setAttribute("stroke", hit ? "#1f4d3a" : "#8a7d6b");
        el.setAttribute("stroke-opacity", i < 0 ? "0.45" : (hit ? "0.95" : "0.08"));
        el.setAttribute("stroke-width", hit ? "1.8" : "0.9");
        if (hit) {
          neighbors.add(+el.dataset.s);
          neighbors.add(+el.dataset.t);
        }
      });
      nodeEls.forEach((el, idx) => {
        const on = i < 0 || idx === i || neighbors.has(idx);
        el.setAttribute("fill", idx === i ? "#1f4d3a" : "#9a3412");
        el.setAttribute("fill-opacity", on ? "0.95" : "0.12");
      });
      show(i >= 0 ? G.nodes[i] : null);
    }

    nodeEls.forEach((el, i) => {
      el.addEventListener("mouseenter", () => highlight(i));
      el.addEventListener("mouseleave", () => highlight(-1));
      el.addEventListener("click", () => {
        document.getElementById("q").value = G.nodes[i].name;
      });
    });

    function applyFilter() {
      const q = document.getElementById("q").value.trim().toLowerCase();
      const st = stateSel.value;
      let match = -1;
      G.nodes.forEach((n, i) => {
        const okState = !st || n.state === st;
        const okQ = !q || n.name.toLowerCase().includes(q);
        const vis = okState && okQ;
        nodeEls[i].style.display = vis ? "" : "none";
        if (vis && q && n.name.toLowerCase() === q) match = i;
        else if (vis && q && match < 0 && n.name.toLowerCase().includes(q)) match = i;
      });
      edgeEls.forEach(el => {
        const a = G.nodes[+el.dataset.s], b = G.nodes[+el.dataset.t];
        const vis = (!st || (a.state === st && b.state === st)) &&
          (!q || a.name.toLowerCase().includes(q) || b.name.toLowerCase().includes(q));
        el.style.display = vis ? "" : "none";
      });
      if (q && match >= 0) highlight(match);
      else if (!q) highlight(-1);
    }
    document.getElementById("q").addEventListener("input", applyFilter);
    stateSel.addEventListener("change", applyFilter);
    document.getElementById("labels").addEventListener("change", e => {
      labelLayer.style.display = e.target.checked ? "" : "none";
    });

    let panX = 0, panY = 0, zoom = 1, dragging = false, lastX = 0, lastY = 0;
    function applyView() {
      world.setAttribute("transform", `translate(${panX} ${panY}) scale(${zoom})`);
    }
    svg.addEventListener("pointerdown", e => {
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      svg.classList.add("dragging");
      svg.setPointerCapture(e.pointerId);
    });
    svg.addEventListener("pointerup", () => { dragging = false; svg.classList.remove("dragging"); });
    svg.addEventListener("pointermove", e => {
      if (!dragging) return;
      panX += e.clientX - lastX;
      panY += e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      applyView();
    });
    svg.addEventListener("wheel", e => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const sx = (e.clientX - rect.left) / rect.width * W;
      const sy = (e.clientY - rect.top) / rect.height * H;
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const next = Math.min(8, Math.max(0.7, zoom * factor));
      panX = sx - (sx - panX) * (next / zoom);
      panY = sy - (sy - panY) * (next / zoom);
      zoom = next;
      applyView();
    }, { passive: false });
  </script>
</body>
</html>
"""


def main() -> None:
    graph = build_graph()
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html(graph)
    write_adjacency_matrix(graph)
    meta = graph["meta"]
    print(f"Wrote {GRAPH_PATH.name}, {HTML_PATH.name}, and {ADJ_PATH.name}")
    print(
        f"{meta['nodes']} nodes, {meta['edges']} edges, "
        f"mean hop {meta['mean_edge_km']} km, MST bridges {meta['mst_bridge_edges']}"
    )
    print("Largest:", ", ".join(n["name"] for n in graph["nodes"][:8]))
    states = {}
    for n in graph["nodes"]:
        states[n["state"]] = states.get(n["state"], 0) + 1
    print("States covered:", len(states))
    print("Top states:", sorted(states.items(), key=lambda kv: -kv[1])[:6])


if __name__ == "__main__":
    main()
