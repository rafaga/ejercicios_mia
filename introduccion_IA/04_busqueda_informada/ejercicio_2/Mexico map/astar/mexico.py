"""Mexico 1,000-city graph loaded from mexico_cities_graph.json.

The search state is the node id (an integer), mirroring the JS library.
"""

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
    """Graph plus per-city lookup structures; the state is the node id."""

    graph: Graph
    locations: dict[int, Location]
    populations: dict[int, int]
    names: dict[int, str]
    by_fold: dict[str, list[int]] = field(default_factory=dict)

    def display(self, city_id: int) -> str:
        return self.names[city_id]

    def resolve(self, name: str) -> int:
        """'City', 'City, State', or '#id'; repeated names are never assumed."""
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

    def _resolve_id(self, text: str, original: str) -> int:
        text = text.strip()
        if not text.isdigit():
            raise ValueError(f"invalid id {original!r}: use '#<number>'")
        city_id = int(text)
        if city_id not in self.names:
            raise ValueError(f"unknown city id {text} (valid ids: 0-{max(self.names)})")
        return city_id

    def _qualified_prefix(self, key: str) -> list[int]:
        return [
            city_id
            for city_id, display in self.names.items()
            if "," in display and _fold(display).startswith(key)
        ]

    def _ambiguous(self, name: str, candidates: list[int]) -> str:
        ranked = sorted(candidates, key=lambda c: -self.populations[c])
        lines = [f"{name!r} matches {len(candidates)} cities:"]
        for city_id in ranked[:10]:
            lines.append(
                f"  - {self.names[city_id]} (id {city_id}, "
                f"population {self.populations[city_id]:,})"
            )
        if len(ranked) > 10:
            lines.append(f"  ... and {len(ranked) - 10} more")
        lines.append("disambiguate with 'City, State' or '#id'.")
        return "\n".join(lines)

    def _suggestions(self, key: str) -> str:
        ids = [nid for nid, display in self.names.items() if _fold(display).startswith(key)]
        if not ids:
            ids = [nid for nid, display in self.names.items() if key in _fold(display)]
        if not ids:
            return ""
        sample = ", ".join(sorted(self.names[nid] for nid in ids)[:5])
        return f" — did you mean: {sample}?"


def _display_names(nodes: list[dict]) -> list[str]:
    """Display name per node: plain name, or 'Name, State' for repeats.

    Repeats within the same state share the display; the node id told apart
    by resolve() is the only disambiguator needed.
    """
    base_counts = Counter(n["name"] for n in nodes)
    return [
        n["name"] if base_counts[n["name"]] == 1 else f"{n['name']}, {n['state']}"
        for n in nodes
    ]


def load_mexico(path: Path = JSON_PATH) -> MexicoData:
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)

    displays = _display_names(payload["nodes"])
    graph = Graph()
    locations: dict[int, Location] = {}
    populations: dict[int, int] = {}
    names: dict[int, str] = {}
    by_fold: dict[str, list[int]] = {}
    for node, display in zip(payload["nodes"], displays):
        city_id = node["id"]
        locations[city_id] = (node["lat"], node["lon"])
        populations[city_id] = node["population"]
        names[city_id] = display
        for key in (_fold(display), _fold(node["name"])):
            candidates = by_fold.setdefault(key, [])
            if city_id not in candidates:
                candidates.append(city_id)

    for edge in payload["edges"]:
        graph.add_undirected(edge["source"], edge["target"], edge["km"])
    return MexicoData(
        graph=graph,
        locations=locations,
        populations=populations,
        names=names,
        by_fold=by_fold,
    )
