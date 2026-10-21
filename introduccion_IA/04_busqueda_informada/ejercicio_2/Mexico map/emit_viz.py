#!/usr/bin/env python3
"""Emit a static PNG preview and a Cursor canvas from the Mexico graph."""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH_PATH = ROOT / "mexico_cities_graph.json"
PNG_PATH = ROOT / "mexico_graph_preview.png"
CANVAS_PATH = ROOT / "mexico-city-graph.canvas.tsx"


def load_graph() -> dict:
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def write_png(graph: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    outline = graph["outline"]
    nodes = graph["nodes"]
    edges = graph["edges"]

    fig, ax = plt.subplots(figsize=(11, 7.2), dpi=140)
    fig.patch.set_facecolor("#f4efe6")
    ax.set_facecolor("#f4efe6")

    ox = [p[0] for p in outline]
    oy = [p[1] for p in outline]
    ax.fill(ox, oy, color="#e7dccb", zorder=0)
    ax.plot(ox, oy, color="#5c5348", linewidth=0.9, zorder=1)

    segs = [
        [
            (nodes[e["source"]]["lon"], nodes[e["source"]]["lat"]),
            (nodes[e["target"]]["lon"], nodes[e["target"]]["lat"]),
        ]
        for e in edges
    ]
    ax.add_collection(
        LineCollection(segs, colors="#8a7d6b", linewidths=0.35, alpha=0.45, zorder=2)
    )

    xs = [n["lon"] for n in nodes]
    ys = [n["lat"] for n in nodes]
    pops = [n["population"] for n in nodes]
    sizes = [6 + 38 * (math.log10(max(p, 1)) / math.log10(max(pops))) ** 2 for p in pops]
    ax.scatter(xs, ys, s=sizes, c="#9a3412", alpha=0.85, linewidths=0, zorder=3)

    for n in nodes[:12]:
        ax.annotate(
            n["name"],
            (n["lon"], n["lat"]),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7,
            color="#1c1916",
            zorder=4,
        )

    ax.set_aspect(1 / math.cos(math.radians(23.5)))
    ax.set_xlim(min(ox) - 0.4, max(ox) + 0.4)
    ax.set_ylim(min(oy) - 0.3, max(oy) + 0.3)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Mexico · 1,000-city proximity graph (lat/lon layout)")
    ax.tick_params(colors="#6b6258", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#c4b8a8")
    fig.text(
        0.5,
        0.015,
        f"{graph['meta']['nodes']} nodes · {graph['meta']['edges']} edges · "
        f"GeoNames cities1000 · 4-NN ∪ MST",
        ha="center",
        fontsize=8,
        color="#6b6258",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(PNG_PATH, facecolor=fig.get_facecolor())
    plt.close(fig)


def js_list(values, wrap=100) -> str:
    raw = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return raw


def write_canvas(graph: dict) -> None:
    nodes = graph["nodes"]
    edges = graph["edges"]
    data = {
        "outline": [[round(x, 4), round(y, 4)] for x, y in graph["outline"]],
        "names": [n["name"] for n in nodes],
        "lon": [round(n["lon"], 4) for n in nodes],
        "lat": [round(n["lat"], 4) for n in nodes],
        "pop": [n["population"] for n in nodes],
        "state": [n["state"] for n in nodes],
        "degree": [n["degree"] for n in nodes],
        "edges": [[e["source"], e["target"]] for e in edges],
        "top": [
            {
                "name": n["name"],
                "state": n["state"],
                "population": n["population"],
                "degree": n["degree"],
            }
            for n in nodes[:15]
        ],
        "meta": graph["meta"],
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    CANVAS_PATH.write_text(CANVAS_TEMPLATE.replace("__DATA__", payload), encoding="utf-8")


CANVAS_TEMPLATE = r"""import {
  Card,
  CardBody,
  CardHeader,
  Grid,
  H1,
  H2,
  Row,
  Select,
  Stack,
  Stat,
  Table,
  Text,
  TextInput,
  useHostTheme,
  useMemo,
  useState,
} from "cursor/canvas";

type GraphData = {
  outline: Array<[number, number]>;
  names: string[];
  lon: number[];
  lat: number[];
  pop: number[];
  state: string[];
  degree: number[];
  edges: Array<[number, number]>;
  top: Array<{ name: string; state: string; population: number; degree: number }>;
  meta: {
    title: string;
    country: string;
    nodes: number;
    edges: number;
    k_neighbors: number;
    min_separation_km: number;
    mean_edge_km: number;
    max_edge_km: number;
    min_edge_km: number;
    mst_bridge_edges: number;
    source: string;
    construction: string;
  };
};

const DATA: GraphData = __DATA__;

const W = 980;
const H = 640;
const PAD = 22;

function project(lon: number, lat: number) {
  const lons = DATA.outline.map((p) => p[0]).concat(DATA.lon);
  const lats = DATA.outline.map((p) => p[1]).concat(DATA.lat);
  const lon0 = Math.min(...lons);
  const lon1 = Math.max(...lons);
  const lat0 = Math.min(...lats);
  const lat1 = Math.max(...lats);
  const mid = ((lat0 + lat1) / 2) * Math.PI / 180;
  const xSpan = (lon1 - lon0) * Math.cos(mid);
  const ySpan = lat1 - lat0;
  const scale = Math.min((W - 2 * PAD) / xSpan, (H - 2 * PAD) / ySpan);
  return {
    x: PAD + (lon - lon0) * Math.cos(mid) * scale,
    y: H - PAD - (lat - lat0) * scale,
  };
}

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

function nodeRadius(pop: number, pmin: number, pmax: number) {
  const t = (Math.log10(Math.max(pop, 1)) - pmin) / (pmax - pmin || 1);
  return 1.4 + t * 6.8;
}

export default function MexicoCityGraph() {
  const theme = useHostTheme();
  const [query, setQuery] = useState("");
  const [state, setState] = useState("all");
  const [hover, setHover] = useState<number | null>(null);

  const projected = useMemo(() => {
    const outline = DATA.outline.map(([lon, lat]) => project(lon, lat));
    const nodes = DATA.lon.map((lon, i) => ({ i, ...project(lon, DATA.lat[i]) }));
    const pmin = Math.log10(Math.max(1, Math.min(...DATA.pop)));
    const pmax = Math.log10(Math.max(...DATA.pop));
    return { outline, nodes, pmin, pmax };
  }, []);

  const states = useMemo(
    () => ["all", ...Array.from(new Set(DATA.state)).sort()],
    [],
  );

  const neighbors = useMemo(() => {
    if (hover == null) return new Set<number>();
    const next = new Set<number>([hover]);
    for (const [a, b] of DATA.edges) {
      if (a === hover || b === hover) {
        next.add(a);
        next.add(b);
      }
    }
    return next;
  }, [hover]);

  const q = query.trim().toLowerCase();
  const visible = DATA.names.map((name, i) => {
    const okState = state === "all" || DATA.state[i] === state;
    const okQ = !q || name.toLowerCase().includes(q);
    return okState && okQ;
  });

  const match = q
    ? DATA.names.findIndex((name, i) => visible[i] && name.toLowerCase().includes(q))
    : -1;
  const focus = hover ?? (match >= 0 ? match : null);

  const landPath = projected.outline
    .map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ") + " Z";

  const labels = useMemo(() => {
    return DATA.pop
      .map((pop, i) => ({ i, pop }))
      .sort((a, b) => b.pop - a.pop)
      .slice(0, 14);
  }, []);

  const selected = focus != null ? {
    name: DATA.names[focus],
    state: DATA.state[focus],
    pop: DATA.pop[focus],
    degree: DATA.degree[focus],
    lat: DATA.lat[focus],
    lon: DATA.lon[focus],
  } : null;

  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>Mexico as a 1,000-city graph</H1>
        <Text tone="secondary">
          Each node is a real place from GeoNames, drawn at its latitude and
          longitude. Edges are the 4 nearest neighbors by haversine distance,
          plus 10 MST bridges so isolated towns stay in one component.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value={fmt(DATA.meta.nodes)} label="Cities (nodes)" />
        <Stat value={fmt(DATA.meta.edges)} label="Proximity edges" />
        <Stat value={`${DATA.meta.mean_edge_km} km`} label="Mean edge length" />
        <Stat value={fmt(DATA.meta.mst_bridge_edges)} label="MST bridge edges" />
      </Grid>

      <Row gap={12} align="end" wrap>
        <Stack gap={4} style={{ minWidth: 220, flex: 1 }}>
          <Text size="small" tone="tertiary">Find a city</Text>
          <TextInput value={query} onChange={setQuery} placeholder="Oaxaca, Tijuana, León…" type="search" />
        </Stack>
        <Stack gap={4} style={{ minWidth: 200 }}>
          <Text size="small" tone="tertiary">State</Text>
          <Select
            value={state}
            onChange={setState}
            options={states.map((s) => ({ value: s, label: s === "all" ? "All 32 states" : s }))}
          />
        </Stack>
      </Row>

      <div>
        <H2>Geographic layout</H2>
        <Text size="small" tone="tertiary">
          Longitude × latitude · node radius is log population · source: {DATA.meta.source}
        </Text>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          style={{
            marginTop: 10,
            background: theme.bg.elevated,
            border: `1px solid ${theme.stroke.tertiary}`,
            display: "block",
          }}
        >
          <path d={landPath} fill={theme.fill.tertiary} stroke={theme.stroke.primary} strokeWidth={1.1} />
          <g>
            {DATA.edges.map(([a, b], idx) => {
              if (!visible[a] && !visible[b]) return null;
              const pa = projected.nodes[a];
              const pb = projected.nodes[b];
              const on = focus == null || (neighbors.has(a) && neighbors.has(b) && (a === focus || b === focus));
              const dim = focus != null && !on;
              return (
                <line
                  key={idx}
                  x1={pa.x}
                  y1={pa.y}
                  x2={pb.x}
                  y2={pb.y}
                  stroke={on && focus != null ? theme.accent.primary : theme.stroke.secondary}
                  strokeOpacity={dim ? 0.08 : 0.4}
                  strokeWidth={on && focus != null ? 1.6 : 0.7}
                />
              );
            })}
          </g>
          <g>
            {projected.nodes.map((p) => {
              if (!visible[p.i]) return null;
              const on = focus == null || neighbors.has(p.i);
              const isFocus = focus === p.i;
              return (
                <circle
                  key={p.i}
                  cx={p.x}
                  cy={p.y}
                  r={nodeRadius(DATA.pop[p.i], projected.pmin, projected.pmax)}
                  fill={isFocus ? theme.accent.primary : theme.accent.control}
                  fillOpacity={on ? 0.92 : 0.12}
                  onMouseEnter={() => setHover(p.i)}
                  onMouseLeave={() => setHover(null)}
                />
              );
            })}
          </g>
          <g>
            {labels.map(({ i }) => {
              if (!visible[i]) return null;
              const p = projected.nodes[i];
              return (
                <text
                  key={i}
                  x={p.x + 6}
                  y={p.y - 5}
                  fill={theme.text.primary}
                  fontSize={11}
                  fontWeight={600}
                  style={{ pointerEvents: "none" }}
                >
                  {DATA.names[i]}
                </text>
              );
            })}
          </g>
        </svg>
        <Text size="small" tone="tertiary" style={{ marginTop: 8 }}>
          {selected
            ? `${selected.name} · ${selected.state} · pop ${fmt(selected.pop)} · degree ${selected.degree} · ${selected.lat.toFixed(3)}°, ${selected.lon.toFixed(3)}°`
            : "Hover a city to see its local neighborhood. Baja California is the northwest peninsula; Yucatán is the eastern bulge."}
        </Text>
      </div>

      <Grid columns="1.1fr 0.9fr" gap={20}>
        <Stack gap={8}>
          <H2>Largest cities in the graph</H2>
          <Table
            headers={["City", "State", "Population", "Degree"]}
            columnAlign={["left", "left", "right", "right"]}
            rows={DATA.top.map((n) => [n.name, n.state, fmt(n.population), String(n.degree)])}
            striped
          />
        </Stack>
        <Card>
          <CardHeader>How the graph was built</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text>
                From 8,984 Mexican populated places in GeoNames cities1000,
                keep the most populous 1,000 with at least 3 km of separation
                so stacked suburbs do not collapse into one pixel.
              </Text>
              <Text>
                Connect each city to its four nearest neighbors. That local
                mesh already looks like a road sketch. Ten extra MST edges
                stitch remote ends (Baja, Yucatán, the northern border) into
                one connected map.
              </Text>
              <Text tone="secondary" size="small">
                {DATA.meta.construction}
              </Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>
    </Stack>
  );
}
"""


def main() -> None:
    graph = load_graph()
    write_png(graph)
    write_canvas(graph)
    print(f"Wrote {PNG_PATH.name} and {CANVAS_PATH.name}")


if __name__ == "__main__":
    main()
