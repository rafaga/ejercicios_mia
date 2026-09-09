"""Shared CLI and result printing for searches on the Mexico map."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from .heuristics import heuristic_for
from .mexico import load_mexico
from .node import Node
from .problem import RouteFindingProblem
from .result import SearchResult

DEFAULT_FROM = "Mexico City"
DEFAULT_TO = "Monterrey"


def search_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--from-city", dest="start", default=DEFAULT_FROM,
        help="start city: 'City', 'City, State', or '#id' when the name repeats",
    )
    parser.add_argument(
        "--to", dest="goal", default=DEFAULT_TO,
        help="goal city: 'City', 'City, State', or '#id' when the name repeats",
    )
    return parser


def make_problem(start: str, goal: str) -> tuple[RouteFindingProblem, Callable[[str], float], str]:
    data = load_mexico()
    try:
        start_key = data.resolve(start)
        goal_key = data.resolve(goal)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from None
    problem = RouteFindingProblem(data.graph, start_key, goal_key)
    h, label = heuristic_for(goal_key, data.locations)
    return problem, h, label


def print_result(
    name: str,
    problem: RouteFindingProblem,
    result: SearchResult,
    h: Callable[[str], float],
    h_label: str,
) -> None:
    print(f"Algorithm: {name}")
    print(f"Problem:   {problem.start} → {problem.goal}")
    print(f"Heuristic: {h_label}")
    print(f"Status:    {result.status}")
    if result.extra:
        print(f"Detail:    {result.extra}")
    if result.node is not None:
        print(f"Path:      {' → '.join(result.path)}")
        print(f"Depth:     {result.depth} hops")
        print(f"Cost:      {result.cost:.1f} km")
        rows = _g_h_f_along(result.node, h)
        width = max((len(city) for city, _g, _h, _f in rows), default=0)
        print()
        print(f"  {'city':<{width}} {'g':>7} {'h':>7} {'f':>7}")
        for city, g, hv, f in rows:
            print(f"  {city:<{width}} {g:7.1f} {hv:7.1f} {f:7.1f}")
    print()
    print(f"Expanded:  {result.nodes_expanded} nodes")
    print(f"Generated: {result.nodes_generated} nodes")
    print(f"Frontier:  max size {result.max_frontier}")


def _g_h_f_along(node: Node, h: Callable[[str], float]) -> list[tuple[str, float, float, float]]:
    rows = []
    chain: list[Node] = []
    cur: Node | None = node
    while cur is not None:
        chain.append(cur)
        cur = cur.parent
    chain.reverse()
    for n in chain:
        hv = h(n.state)
        rows.append((n.state, n.path_cost, hv, n.path_cost + hv))
    return rows
