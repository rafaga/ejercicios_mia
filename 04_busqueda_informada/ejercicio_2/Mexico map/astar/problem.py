"""Route-finding problem on a road map (AIMA ch. 3)."""

from __future__ import annotations

from .map import Graph


class RouteFindingProblem:
    """State = city. Action = drive to a neighboring city. Step cost = km."""

    def __init__(self, graph: Graph, start: str, goal: str) -> None:
        if not graph.has_city(start):
            raise ValueError(f"unknown start city: {start}")
        if not graph.has_city(goal):
            raise ValueError(f"unknown goal city: {goal}")
        self.graph = graph
        self.start = start
        self.goal = goal

    def actions(self, state: str) -> list[str]:
        return [city for city, _km in self.graph.neighbors(state)]

    def result(self, state: str, action: str) -> str:
        return action

    def step_cost(self, state: str, action: str) -> float:
        return self.graph.cost(state, action)

    def is_goal(self, state: str) -> bool:
        return state == self.goal
