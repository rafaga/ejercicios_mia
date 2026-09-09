"""Heuristic for the Mexico map: haversine straight-line km to the goal."""

from __future__ import annotations

from collections.abc import Callable

from .mexico import Location, haversine_km


def heuristic_for(goal: str, locations: dict[str, Location]) -> tuple[Callable[[str], float], str]:
    """Return h(state) and a short label describing which heuristic is used.

    h(n) = great-circle km from n to the goal. Admissible and consistent:
    every edge cost is itself a haversine distance, so the triangle
    inequality keeps h from overestimating the remaining cost.
    """
    goal_loc = locations[goal]

    def h(state: str) -> float:
        return haversine_km(locations[state], goal_loc)

    return h, f"haversine straight-line km to {goal}"
