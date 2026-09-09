"""Romania road map from AIMA Figure 3.2 (undirected, distances in km)."""

from __future__ import annotations

from collections import defaultdict

ROMANIA_EDGES: tuple[tuple[str, str, int], ...] = (
    ("Arad", "Zerind", 75),
    ("Arad", "Sibiu", 140),
    ("Arad", "Timisoara", 118),
    ("Bucharest", "Fagaras", 211),
    ("Bucharest", "Pitesti", 101),
    ("Bucharest", "Giurgiu", 90),
    ("Bucharest", "Urziceni", 85),
    ("Craiova", "Drobeta", 120),
    ("Craiova", "Rimnicu Vilcea", 146),
    ("Craiova", "Pitesti", 138),
    ("Drobeta", "Mehadia", 75),
    ("Eforie", "Hirsova", 86),
    ("Fagaras", "Sibiu", 99),
    ("Hirsova", "Urziceni", 98),
    ("Iasi", "Neamt", 87),
    ("Iasi", "Vaslui", 92),
    ("Lugoj", "Timisoara", 111),
    ("Lugoj", "Mehadia", 70),
    ("Oradea", "Zerind", 71),
    ("Oradea", "Sibiu", 151),
    ("Pitesti", "Rimnicu Vilcea", 97),
    ("Rimnicu Vilcea", "Sibiu", 80),
    ("Urziceni", "Vaslui", 142),
)


class Graph:
    """Undirected weighted graph. Neighbors are returned in alphabetical order."""

    def __init__(self) -> None:
        self._adj: dict[str, dict[str, float]] = defaultdict(dict)

    def add_undirected(self, a: str, b: str, cost: float) -> None:
        self._adj[a][b] = cost
        self._adj[b][a] = cost

    def cities(self) -> list[str]:
        return sorted(self._adj)

    def has_city(self, city: str) -> bool:
        return city in self._adj

    def neighbors(self, city: str) -> list[tuple[str, float]]:
        return sorted(self._adj[city].items())

    def cost(self, a: str, b: str) -> float:
        if b not in self._adj[a]:
            raise KeyError(f"no road between {a} and {b}")
        return self._adj[a][b]

    def edge_count(self) -> int:
        return sum(len(nbrs) for nbrs in self._adj.values()) // 2


def romania_map() -> Graph:
    graph = Graph()
    for a, b, km in ROMANIA_EDGES:
        graph.add_undirected(a, b, km)
    return graph
