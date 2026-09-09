"""Mexico 1,000-city graph loaded from mexico_cities_graph.json."""

from __future__ import annotations

import json
import math
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .map import Graph

Location = tuple[float, float]  # (lat, lon)

JSON_PATH = Path(__file__).resolve().parent.parent / "mexico_cities_graph.json"
EARTH_KM = 6371.0  # same radius the graph was built with (generate_mexico_graph.py)


def haversine_km(a: Location, b: Location) -> float:
    """Great-circle km; mirrors generate_mexico_graph.haversine so h stays admissible."""
    (lat1, lon1), (lat2, lon2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(min(1.0, h)))


def _fold(name: str) -> str:
    """Case- and accent-insensitive key, so 'Cancun' finds 'Cancún'."""
    decomposed = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


@dataclass
class MexicoData:
    """Graph plus per-city lookup structures keyed by display name."""

    graph: Graph
    locations: dict[str, Location]
    populations: dict[str, int]
    by_fold: dict[str, list[str]] = field(default_factory=dict)
    by_id: dict[int, str] = field(default_factory=dict)
    id_of: dict[str, int] = field(default_factory=dict)

    def resolve(self, name: str) -> str:
        """'City', 'City, State', or '#id'; repeated names are never assumed."""
        if name in self.locations:
            return name
        if name.startswith("#"):
            return self._resolve_id(name[1:], name)
        key = _fold(name)
        candidates = self.by_fold.get(key, [])
        if not candidates:
            candidates = self._qualified_prefix(key)
        if not candidates and name.strip().isdigit():
            return self._resolve_id(name.strip(), name)
        if not candidates:
            raise ValueError(f"unknown city {name!r}{self._suggestions(key)}")
        if len(candidates) > 1:
            raise ValueError(self._ambiguous(name, candidates))
        return candidates[0]

    def _resolve_id(self, text: str, original: str) -> str:
        text = text.strip()
        if not text.isdigit():
            raise ValueError(f"invalid id {original!r}: use '#<number>'")
        try:
            return self.by_id[int(text)]
        except KeyError:
            raise ValueError(
                f"unknown city id {text} (valid ids: 0-{max(self.by_id)})"
            ) from None

    def _qualified_prefix(self, key: str) -> list[str]:
        return [d for d in self.locations if "," in d and _fold(d).startswith(key)]

    def _ambiguous(self, name: str, candidates: list[str]) -> str:
        ranked = sorted(candidates, key=lambda c: -self.populations[c])
        lines = [f"{name!r} matches {len(candidates)} cities:"]
        for c in ranked[:10]:
            lines.append(f"  - {c} (id {self.id_of[c]}, population {self.populations[c]:,})")
        if len(ranked) > 10:
            lines.append(f"  ... and {len(ranked) - 10} more")
        lines.append("disambiguate with 'City, State' or '#id'.")
        return "\n".join(lines)

    def _suggestions(self, key: str) -> str:
        names = [n for n in self.locations if _fold(n).startswith(key)]
        if not names:
            names = [n for n in self.locations if key in _fold(n)]
        if not names:
            return ""
        return f" — did you mean: {', '.join(sorted(names)[:5])}?"


def _display_names(nodes: list[dict]) -> list[str]:
    """One unique display name per node: plain name, or 'Name, State' for repeats."""
    base_counts = Counter(n["name"] for n in nodes)
    displays = [
        n["name"] if base_counts[n["name"]] == 1 else f"{n['name']}, {n['state']}"
        for n in nodes
    ]
    # A few names repeat even within one state; number those.
    display_counts = Counter(displays)
    seen: Counter = Counter()
    result: list[str] = []
    for d in displays:
        if display_counts[d] == 1:
            result.append(d)
            continue
        seen[d] += 1
        result.append(f"{d} ({seen[d]})")
    return result


def load_mexico(path: Path = JSON_PATH) -> MexicoData:
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)

    displays = _display_names(payload["nodes"])
    graph = Graph()
    locations: dict[str, Location] = {}
    populations: dict[str, int] = {}
    by_fold: dict[str, list[str]] = {}
    by_id: dict[int, str] = {}
    id_of: dict[str, int] = {}
    for node, display in zip(payload["nodes"], displays):
        locations[display] = (node["lat"], node["lon"])
        populations[display] = node["population"]
        by_id[node["id"]] = display
        id_of[display] = node["id"]
        for key in (_fold(display), _fold(node["name"])):
            candidates = by_fold.setdefault(key, [])
            if display not in candidates:
                candidates.append(display)

    for edge in payload["edges"]:
        graph.add_undirected(displays[edge["source"]], displays[edge["target"]], edge["km"])
    return MexicoData(
        graph=graph,
        locations=locations,
        populations=populations,
        by_fold=by_fold,
        by_id=by_id,
        id_of=id_of,
    )
