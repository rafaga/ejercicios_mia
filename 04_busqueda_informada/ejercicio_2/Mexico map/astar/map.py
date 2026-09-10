"""Undirected weighted graph on integer node ids (Mexico map)."""

from __future__ import annotations

from collections import defaultdict


class Graph:
    """Undirected weighted graph keyed by node id. Neighbors are returned in id order."""

    def __init__(self) -> None:
        self._adj: dict[int, dict[int, float]] = defaultdict(dict)

    def add_undirected(self, a: int, b: int, cost: float) -> None:
        self._adj[a][b] = cost
        self._adj[b][a] = cost

    def cities(self) -> list[int]:
        return sorted(self._adj)

    def has_city(self, city: int) -> bool:
        return city in self._adj

    def neighbors(self, city: int) -> list[tuple[int, float]]:
        return sorted(self._adj[city].items())

    def cost(self, a: int, b: int) -> float:
        if b not in self._adj[a]:
            raise KeyError(f"no road between {a} and {b}")
        return self._adj[a][b]

    def edge_count(self) -> int:
        return sum(len(nbrs) for nbrs in self._adj.values()) // 2
