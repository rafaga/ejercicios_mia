"""Outcome of a search run."""

from __future__ import annotations

from dataclasses import dataclass

from .node import Node

SUCCESS = "success"
FAILURE = "failure"


@dataclass
class SearchResult:
    status: str
    node: Node | None = None
    nodes_expanded: int = 0
    nodes_generated: int = 0
    max_frontier: int = 0
    extra: str = ""

    @property
    def path(self) -> list[int]:
        return [] if self.node is None else self.node.path()

    @property
    def cost(self) -> float | None:
        return None if self.node is None else self.node.path_cost

    @property
    def depth(self) -> int | None:
        return None if self.node is None else self.node.depth
