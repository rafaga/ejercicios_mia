"""Search tree node (AIMA Figure 3.6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .problem import RouteFindingProblem


@dataclass
class Node:
    state: int
    parent: Node | None = None
    action: int | None = None
    path_cost: float = 0.0
    depth: int = 0

    def path(self) -> list[int]:
        node: Node | None = self
        cities: list[int] = []
        while node is not None:
            cities.append(node.state)
            node = node.parent
        cities.reverse()
        return cities

    def expand(self, problem: RouteFindingProblem) -> list[Node]:
        return [child_node(problem, self, action) for action in problem.actions(self.state)]


def child_node(problem: RouteFindingProblem, parent: Node, action: str) -> Node:
    next_state = problem.result(parent.state, action)
    return Node(
        state=next_state,
        parent=parent,
        action=action,
        path_cost=parent.path_cost + problem.step_cost(parent.state, action),
        depth=parent.depth + 1,
    )
