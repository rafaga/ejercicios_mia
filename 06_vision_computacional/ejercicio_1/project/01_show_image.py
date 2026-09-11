#!/usr/bin/env python3
"""Program 1: print the image as numbers (and a crude ASCII gray)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cvision.cli import build_parser, load  # noqa: E402
from cvision.format import format_image  # noqa: E402


def main() -> None:
    parser = build_parser("Show a YAML image as a grid of numbers.")
    args = parser.parse_args()
    im = load(args)
    print(format_image(im))
    print()
    print("A program does not see a letter or a circle. It sees I[i, j].")
    print("Edit the YAML file, then rerun this program.")


if __name__ == "__main__":
    main()
