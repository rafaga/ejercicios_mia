const { test } = require("node:test");
const assert = require("node:assert/strict");

require("../mexico-astar.js");
const MA = globalThis.MexicoAstar;
const raw = require("../../mexico_cities_graph.json");
const graph = new MA.GeoGraph({ nodes: raw.nodes, edges: raw.edges });

function idOf(name, state) {
  return graph.resolveCity(name, { state: state }).node.id;
}

test("haversine: zero for identical points, symmetric, matches reference", () => {
  assert.equal(MA.haversine(19.42847, -99.12766, 19.42847, -99.12766), 0);
  const tj = graph.resolveCity("Tijuana").node;
  const ca = graph.resolveCity("Cancún").node;
  const d1 = MA.haversine(tj.lat, tj.lon, ca.lat, ca.lon);
  const d2 = MA.haversine(ca.lat, ca.lon, tj.lat, tj.lon);
  assert.ok(Math.abs(d1 - d2) < 1e-9);
  assert.ok(Math.abs(d1 - 3231.803) < 0.01, "expected ~3231.803 km, got " + d1);
});

test("GeoGraph: order, size and degrees match the JSON metadata", () => {
  assert.equal(graph.order, 1000);
  assert.equal(graph.size, 2565);
  let total = 0;
  for (const n of graph.nodeList) {
    assert.equal(graph.neighbors(n.id).length, n.degree, "degree mismatch for " + n.name);
    total += n.degree;
  }
  assert.equal(total, 2 * 2565);
});

test("resolveCity: duplicate names are flagged, never silent", () => {
  const puebla = graph.resolveCity("Puebla");
  assert.equal(puebla.ambiguous, true);
  assert.equal(puebla.node.id, 4);
  assert.equal(puebla.node.state, "Puebla");
  assert.ok(puebla.note && puebla.note.includes("Puebla"));

  const guadalupe = graph.resolveCity("Guadalupe");
  assert.equal(guadalupe.ambiguous, true);
  assert.equal(guadalupe.node.id, 22);
  assert.equal(guadalupe.node.state, "Nuevo León");

  const byState = graph.resolveCity("Guadalupe", { state: "Zacatecas" });
  assert.equal(byState.ambiguous, false);
  assert.equal(byState.node.id, 111);
  assert.equal(byState.note, null);
});

test("resolveCity: unknown names throw with accent-folded suggestions", () => {
  assert.throws(() => graph.resolveCity("CDMX"), /City not found/);
  assert.throws(() => graph.resolveCity("Cancun"), /Cancún/);
  assert.throws(
    () => graph.resolveCity("Puebla", { state: "Sonora" }),
    /No city named 'Puebla' in state 'Sonora'/
  );
});

test("astarSearch: optimal on a small graph, with h = 0 and with an admissible h", () => {
  const tiny = new MA.GeoGraph({
    nodes: [
      { id: "a", name: "A", lat: 0, lon: 0 },
      { id: "b", name: "B", lat: 0, lon: 1 },
      { id: "c", name: "C", lat: 0, lon: 2 },
      { id: "d", name: "D", lat: 0, lon: 3 },
    ],
    edges: [
      { source: "a", target: "b", km: 2 },
      { source: "b", target: "c", km: 2 },
      { source: "a", target: "c", km: 5 },
      { source: "c", target: "d", km: 3 },
      { source: "b", target: "d", km: 7 },
    ],
  });
  const steps = (s) => MA.GeoGraph.prototype.neighbors.call(tiny, s)
    .map((e) => ({ state: e.to, cost: e.km }));

  const ucs = MA.astarSearch({ start: "a", isGoal: (s) => s === "d", successors: steps });
  assert.equal(ucs.status, "success");
  assert.equal(ucs.cost, 7);
  assert.deepEqual(ucs.path, ["a", "b", "c", "d"]);

  const h = { a: 1, b: 0.2, c: 0.1, d: 0 };
  const informed = MA.astarSearch({
    start: "a",
    isGoal: (s) => s === "d",
    successors: steps,
    h: (s) => h[s],
  });
  assert.equal(informed.status, "success");
  assert.equal(informed.cost, 7);
  assert.deepEqual(informed.path, ["a", "b", "c", "d"]);

  const disconnected = new MA.GeoGraph({
    nodes: [
      { id: "a", name: "A", lat: 0, lon: 0 },
      { id: "z", name: "Z", lat: 9, lon: 9 },
    ],
    edges: [],
  });
  const fail = MA.astarSearch({
    start: "a",
    isGoal: (s) => s === "z",
    successors: () => [],
  });
  assert.equal(fail.status, "failure");
});

test("findRoute: Tijuana -> Cancún is optimal and matches the UCS cost", () => {
  const from = idOf("Tijuana");
  const to = idOf("Cancún");
  const astar = MA.findRoute(graph, from, to, { heuristic: "haversine" });
  const ucs = MA.findRoute(graph, from, to, { heuristic: "zero" });

  assert.equal(astar.status, "success");
  assert.equal(astar.heuristic, "haversine");
  assert.ok(Math.abs(astar.cost - 4528.2) < 0.01, "expected ~4528.20 km, got " + astar.cost);
  assert.ok(Math.abs(astar.cost - ucs.cost) < 0.01);
  assert.ok(astar.expanded < ucs.expanded,
    "A* expanded " + astar.expanded + ", UCS expanded " + ucs.expanded);

  assert.equal(astar.path[0], from);
  assert.equal(astar.path[astar.path.length - 1], to);
  let sum = 0;
  for (let i = 0; i < astar.path.length - 1; i++) {
    const hop = graph.neighbors(astar.path[i]).find((e) => e.to === astar.path[i + 1]);
    assert.ok(hop, "cities " + astar.path[i] + " and " + astar.path[i + 1] + " are not neighbors");
    sum += hop.km;
  }
  assert.ok(Math.abs(sum - astar.cost) < 1e-9);
  assert.equal(astar.pathNodes.length, astar.path.length);
});

test("findRoute: other exercise pairs are optimal (vs UCS reference)", () => {
  const pairs = [
    ["Mexico City", "Monterrey", 1041.87],
    ["Guadalajara", "Mérida", 1984.75],
    ["Hermosillo", "Oaxaca", 2361.45],
  ];
  for (const [a, b, expected] of pairs) {
    const r = MA.findRoute(graph, idOf(a), idOf(b));
    assert.equal(r.status, "success");
    assert.ok(Math.abs(r.cost - expected) < 0.01, a + " -> " + b + ": " + r.cost);
  }
});

test("findRoute: same origin and destination is trivial", () => {
  const id = idOf("Oaxaca");
  const r = MA.findRoute(graph, id, id);
  assert.equal(r.status, "success");
  assert.deepEqual(r.path, [id]);
  assert.equal(r.depth, 0);
  assert.equal(r.cost, 0);
  assert.equal(r.expanded, 0);
});

test("haversine heuristic is consistent with every edge cost up to 2-decimal rounding (goal: Cancún)", () => {
  const to = idOf("Cancún");
  const h = MA.haversineHeuristic(graph, to);
  const EPSILON = 0.006;
  for (const n of graph.nodeList) {
    const hn = h(n.id);
    for (const e of graph.neighbors(n.id)) {
      assert.ok(
        hn <= e.km + h(e.to) + EPSILON,
        "inconsistent h at edge " + n.id + "-" + e.to
      );
    }
  }
});
