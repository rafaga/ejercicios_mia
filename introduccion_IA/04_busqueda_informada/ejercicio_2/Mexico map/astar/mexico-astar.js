(function (global) {
  "use strict";

  const EARTH_RADIUS_KM = 6371.0;

  function haversine(lat1, lon1, lat2, lon2) {
    const rad = Math.PI / 180;
    const p1 = lat1 * rad;
    const p2 = lat2 * rad;
    const dphi = (lat2 - lat1) * rad;
    const dlmb = (lon2 - lon1) * rad;
    const a =
      Math.sin(dphi / 2) ** 2 +
      Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
    return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(Math.min(1, a)));
  }

  class MinHeap {
    constructor(compare) {
      this.compare = compare || function (a, b) { return a - b; };
      this.items = [];
    }

    get size() {
      return this.items.length;
    }

    push(item) {
      const items = this.items;
      items.push(item);
      let i = items.length - 1;
      while (i > 0) {
        const parent = (i - 1) >> 1;
        if (this.compare(items[i], items[parent]) < 0) {
          const tmp = items[i];
          items[i] = items[parent];
          items[parent] = tmp;
          i = parent;
        } else {
          break;
        }
      }
    }

    pop() {
      const items = this.items;
      if (items.length === 0) return undefined;
      const top = items[0];
      const last = items.pop();
      if (items.length > 0) {
        items[0] = last;
        let i = 0;
        for (;;) {
          const left = 2 * i + 1;
          const right = left + 1;
          let smallest = i;
          if (left < items.length && this.compare(items[left], items[smallest]) < 0) {
            smallest = left;
          }
          if (right < items.length && this.compare(items[right], items[smallest]) < 0) {
            smallest = right;
          }
          if (smallest === i) break;
          const tmp = items[i];
          items[i] = items[smallest];
          items[smallest] = tmp;
          i = smallest;
        }
      }
      return top;
    }
  }

  class CityResolutionError extends Error {
    constructor(message, candidates) {
      super(message);
      this.name = "CityResolutionError";
      this.candidates = candidates || [];
    }
  }

  function foldName(value) {
    return String(value)
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase()
      .trim();
  }

  function fmtInt(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  class GeoGraph {
    constructor(payload) {
      const nodes = payload && payload.nodes;
      const edges = payload && payload.edges;
      if (!Array.isArray(nodes) || !Array.isArray(edges)) {
        throw new TypeError("GeoGraph expects { nodes: [...], edges: [...] }");
      }
      this.nodeList = nodes.slice();
      this.nodesById = new Map();
      this.adjacency = new Map();
      for (const n of this.nodeList) {
        if (this.nodesById.has(n.id)) {
          throw new RangeError("duplicate node id: " + n.id);
        }
        this.nodesById.set(n.id, n);
        if (typeof n.id === "number" && (this.maxId === undefined || n.id > this.maxId)) {
          this.maxId = n.id;
        }
        this.adjacency.set(n.id, []);
      }
      this.edgeCount = edges.length;
      for (const e of edges) {
        if (!this.adjacency.has(e.source) || !this.adjacency.has(e.target)) {
          throw new RangeError(
            "edge references unknown node: " + e.source + "-" + e.target
          );
        }
        this.adjacency.get(e.source).push({ to: e.target, km: e.km, kind: e.kind });
        this.adjacency.get(e.target).push({ to: e.source, km: e.km, kind: e.kind });
      }
      this.citiesByName = new Map();
      for (const n of this.nodeList) {
        if (!this.citiesByName.has(n.name)) this.citiesByName.set(n.name, []);
        this.citiesByName.get(n.name).push(n);
      }
    }

    get order() {
      return this.nodeList.length;
    }

    get size() {
      return this.edgeCount;
    }

    node(id) {
      return this.nodesById.get(id);
    }

    hasNode(id) {
      return this.nodesById.has(id);
    }

    neighbors(id) {
      const list = this.adjacency.get(id);
      if (!list) throw new RangeError("unknown node id: " + id);
      return list;
    }

    distance(aId, bId) {
      const a = this.node(aId);
      const b = this.node(bId);
      if (!a || !b) throw new RangeError("distance: unknown node id");
      return haversine(a.lat, a.lon, b.lat, b.lon);
    }

    findCities(name) {
      return (this.citiesByName.get(name) || []).slice();
    }

    resolveCity(name, options) {
      const state = options && options.state ? String(options.state).trim() : null;
      if (typeof name === "string" && name.charAt(0) === "#") {
        return this._resolveById(name);
      }
      const exact = this.citiesByName.get(name) || [];
      if (exact.length === 0) {
        const fold = foldName(name);
        const seen = new Set();
        const suggestions = [];
        for (const n of this.nodeList) {
          const f = foldName(n.name);
          if (fold && f.indexOf(fold) !== -1 && !seen.has(f)) {
            seen.add(f);
            suggestions.push(n.name);
            if (suggestions.length >= 8) break;
          }
        }
        throw new CityResolutionError(
          "City not found: '" + name + "'" +
            (suggestions.length
              ? ". Did you mean: " + suggestions.join(", ") + "?"
              : "")
        );
      }
      let candidates = exact;
      if (state) {
        candidates = exact.filter(function (n) {
          return foldName(n.state) === foldName(state);
        });
        if (candidates.length === 0) {
          throw new CityResolutionError(
            "No city named '" + name + "' in state '" + state + "'. Matches: " +
              exact.map(function (n) { return n.name + ", " + n.state; }).join(" | "),
            exact
          );
        }
      }
      if (candidates.length > 1) {
        throw new CityResolutionError(this._ambiguousMessage(name, candidates), candidates);
      }
      return { node: candidates[0], candidates: candidates, note: null };
    }

    _resolveById(spec) {
      const text = String(spec).slice(1).trim();
      if (!/^\d+$/.test(text)) {
        throw new CityResolutionError("Invalid id '" + spec + "': use '#<number>'");
      }
      const node = this.nodesById.get(Number(text));
      if (!node) {
        const range = this.maxId === undefined ? "" : " (valid ids: 0-" + this.maxId + ")";
        throw new CityResolutionError("Unknown city id " + text + range);
      }
      return { node: node, candidates: [node], note: null };
    }

    _ambiguousMessage(name, candidates) {
      const ranked = candidates.slice().sort(function (a, b) {
        return (b.population || 0) - (a.population || 0) || a.id - b.id;
      });
      const lines = ["'" + name + "' matches " + ranked.length + " cities:"];
      for (const n of ranked.slice(0, 10)) {
        lines.push(
          "  - " + n.name + ", " + n.state +
            " (id " + n.id + ", population " + fmtInt(n.population || 0) + ")"
        );
      }
      if (ranked.length > 10) lines.push("  ... and " + (ranked.length - 10) + " more");
      lines.push("disambiguate with 'City, State' or '#id'.");
      return lines.join("\n");
    }
  }

  function astarSearch(problem) {
    const start = problem.start;
    const isGoal = problem.isGoal;
    const successors = problem.successors;
    const h = typeof problem.h === "function" ? problem.h : zeroHeuristic();
    if (typeof isGoal !== "function") {
      throw new TypeError("astarSearch: isGoal(state) => boolean is required");
    }
    if (typeof successors !== "function") {
      throw new TypeError("astarSearch: successors(state) => { state, cost }[] is required");
    }

    const compare = function (a, b) {
      return a.f - b.f || a.h - b.h || a.seq - b.seq;
    };
    const open = new MinHeap(compare);
    const bestG = new Map();
    const parent = new Map();
    let seq = 0;
    let expanded = 0;
    let generated = 1;

    const hStart = h(start);
    if (!Number.isFinite(hStart) || hStart < 0) {
      throw new TypeError("astarSearch: h(start) must be a finite non-negative number");
    }
    bestG.set(start, 0);
    open.push({ f: hStart, g: 0, h: hStart, state: start, seq: seq++ });

    while (open.size > 0) {
      const entry = open.pop();
      const state = entry.state;
      if (entry.g > bestG.get(state)) continue;
      if (isGoal(state)) {
        const path = buildPath(parent, state);
        return {
          status: "success",
          path: path,
          depth: path.length - 1,
          cost: entry.g,
          expanded: expanded,
          generated: generated,
        };
      }
      expanded++;
      const steps = successors(state);
      for (const step of steps) {
        const next = step.state;
        const cost = step.cost;
        if (!Number.isFinite(cost) || cost < 0) {
          throw new TypeError("astarSearch: step cost must be a finite non-negative number");
        }
        const gNext = entry.g + cost;
        const known = bestG.get(next);
        if (known === undefined || gNext < known) {
          bestG.set(next, gNext);
          parent.set(next, state);
          const hNext = h(next);
          if (!Number.isFinite(hNext) || hNext < 0) {
            throw new TypeError("astarSearch: h(state) must be a finite non-negative number");
          }
          open.push({ f: gNext + hNext, g: gNext, h: hNext, state: next, seq: seq++ });
          generated++;
        }
      }
    }
    return {
      status: "failure",
      path: [],
      depth: null,
      cost: null,
      expanded: expanded,
      generated: generated,
    };
  }

  function buildPath(parent, state) {
    const path = [state];
    let s = state;
    while (parent.has(s)) {
      s = parent.get(s);
      path.push(s);
    }
    return path.reverse();
  }

  function haversineHeuristic(graph, goalId) {
    const goal = graph.node(goalId);
    if (!goal) throw new RangeError("haversineHeuristic: unknown goal id " + goalId);
    const lat = goal.lat;
    const lon = goal.lon;
    return function (id) {
      const n = graph.node(id);
      if (!n) throw new RangeError("haversineHeuristic: unknown node id " + id);
      return haversine(n.lat, n.lon, lat, lon);
    };
  }

  function zeroHeuristic() {
    return function () { return 0; };
  }

  function findRoute(graph, sourceId, targetId, options) {
    const opts = options || {};
    const heuristic = opts.heuristic === undefined ? "haversine" : opts.heuristic;
    if (!graph.hasNode(sourceId)) {
      throw new RangeError("findRoute: unknown source id " + sourceId);
    }
    if (!graph.hasNode(targetId)) {
      throw new RangeError("findRoute: unknown target id " + targetId);
    }
    let hFn;
    let hName;
    if (typeof heuristic === "function") {
      hFn = heuristic;
      hName = "custom";
    } else if (heuristic === "haversine") {
      hFn = haversineHeuristic(graph, targetId);
      hName = "haversine";
    } else if (heuristic === "zero") {
      hFn = zeroHeuristic();
      hName = "zero";
    } else {
      throw new TypeError('findRoute: heuristic must be "haversine", "zero", or a function');
    }
    const result = astarSearch({
      start: sourceId,
      isGoal: function (s) { return s === targetId; },
      successors: function (s) {
        return graph.neighbors(s).map(function (e) {
          return { state: e.to, cost: e.km };
        });
      },
      h: hFn,
    });
    return Object.assign({}, result, {
      heuristic: hName,
      pathNodes: result.path.map(function (id) { return graph.node(id); }),
    });
  }

  global.MexicoAstar = {
    EARTH_RADIUS_KM: EARTH_RADIUS_KM,
    haversine: haversine,
    MinHeap: MinHeap,
    CityResolutionError: CityResolutionError,
    GeoGraph: GeoGraph,
    astarSearch: astarSearch,
    haversineHeuristic: haversineHeuristic,
    zeroHeuristic: zeroHeuristic,
    findRoute: findRoute,
  };
})(globalThis);
