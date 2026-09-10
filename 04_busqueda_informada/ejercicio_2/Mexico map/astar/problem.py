"""Route-finding problem on a road map (AIMA ch. 3). State = city id."""

from __future__ import annotations

from .map import Graph


class RouteFindingProblem:
    """State = city id. Action = drive to a neighboring id. Step cost = km."""

    def __init__(self, graph: Graph, start: int, goal: int) -> None:
        if not graph.has_city(start):
            raise ValueError(f"unknown start city id: {start}")
        if not graph.has_city(goal):
            raise ValueError(f"unknown goal city id: {goal}")
        self.graph = graph
        self.start = start
        self.goal = goal

    def actions(self, state: int) -> list[int]:
        return [city_id for city_id, _km in self.graph.neighbors(state)]

    def result(self, state: int, action: int) -> int:
        return action

    def step_cost(self, state: int, action: int) -> float:
        return self.graph.cost(state, action)

    def is_goal(self, state: int) -> bool:
        return state == self.goal
