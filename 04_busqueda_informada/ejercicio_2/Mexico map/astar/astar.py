"""A* search (AIMA Figure 3.24). Expands the node with lowest f(n) = g(n) + h(n)."""

from __future__ import annotations

import heapq
from collections.abc import Callable

from .node import Node
from .problem import RouteFindingProblem
from .result import FAILURE, SUCCESS, SearchResult


def a_star_search(
    problem: RouteFindingProblem,
    h: Callable[[int], float],
) -> SearchResult:
    """Optimal if h is admissible (and, for this graph-search version, consistent).

    The haversine distance to the goal is consistent on the Mexico graph:
    edge costs are haversine distances too.
    """
    node = Node(problem.start)
    frontier: list[tuple[float, int, Node]] = []
    counter = 0
    heapq.heappush(frontier, (node.path_cost + h(node.state), counter, node))
    best_g = {node.state: 0.0}
    explored: set[int] = set()
    expanded = 0
    generated = 1
    max_frontier = 1

    while frontier:
        _f, _i, node = heapq.heappop(frontier)
        if node.state in explored:
            continue
        if problem.is_goal(node.state):
            return SearchResult(
                SUCCESS,
                node,
                nodes_expanded=expanded,
                nodes_generated=generated,
                max_frontier=max_frontier,
            )

        explored.add(node.state)
        expanded += 1
        for child in node.expand(problem):
            generated += 1
            s = child.state
            if s in explored:
                continue
            if s not in best_g or child.path_cost < best_g[s]:
                best_g[s] = child.path_cost
                counter += 1
                f = child.path_cost + h(s)
                heapq.heappush(frontier, (f, counter, child))
                max_frontier = max(max_frontier, len(frontier))

    return SearchResult(
        FAILURE,
        nodes_expanded=expanded,
        nodes_generated=generated,
        max_frontier=max_frontier,
    )
