"""Heuristic for the Mexico map: haversine straight-line km to the goal."""

from __future__ import annotations

from collections.abc import Callable

from .mexico import Location, haversine_km


def heuristic_for(goal: int, locations: dict[int, Location]) -> Callable[[int], float]:
    """Return h(state): great-circle km from state to the goal.

    Admissible and consistent: every edge cost is itself a haversine
    distance, so the triangle inequality keeps h from overestimating.
    """
    goal_loc = locations[goal]

    def h(state: int) -> float:
        return haversine_km(locations[state], goal_loc)

    return h
