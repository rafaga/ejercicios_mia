#!/usr/bin/env python3
"""Program 4: A* search on the Mexico 1,000-city graph."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from astar.astar import a_star_search  # noqa: E402
from astar.cli import make_problem, print_result, search_parser  # noqa: E402


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")
    parser = search_parser("A* search: expand lowest f(n) = g(n) + h(n).")
    args = parser.parse_args()
    problem, h, label = make_problem(args.start, args.goal)
    result = a_star_search(problem, h)
    print_result("A* search", problem, result, h, label)


if __name__ == "__main__":
    main()
