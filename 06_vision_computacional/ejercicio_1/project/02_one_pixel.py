#!/usr/bin/env python3
"""Program 2: one convolution at the probe pixel (lecture mean / Sobel)."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cvision.cli import DEFAULT_STEP, build_parser, load  # noqa: E402
from cvision.filters import conv_at  # noqa: E402
from cvision.format import format_matrix, format_probe  # noqa: E402


def _lecture_note(name: str, row: int, col: int, value: float) -> str | None:
    key = name.replace("-", "_")
    if (row, col) != (2, 2):
        return None
    if key == "mean3" and abs(value - 3.0) < 1e-9:
        return "Lecture check: mean 3×3 at the step center is 3 (six 0s and three 9s → 27/9)."
    if key == "sobel_x" and abs(value - 36.0) < 1e-9:
        return "Lecture check: Gx = 9 + 18 + 9 = 36."
    if key == "sobel_y" and abs(value) < 1e-9:
        return "Lecture check: rows are equal, so Gy = 0 (vertical edge)."
    return None


def main() -> None:
    parser = build_parser("Convolve one pixel: neighborhood × kernel, then sum.", default=DEFAULT_STEP)
    args = parser.parse_args()
    im = load(args)
    if args.pad is not None:
        im = replace(im, pad=args.pad)

    print(im.name)
    print()
    print("I′[i, j]  =  Σ_u Σ_v  K[u, v]  ·  I[i+u, j+v]")
    print(f"probe = (row {im.probe[0]}, col {im.probe[1]})    pad = {im.pad}")
    print()
    print(format_matrix(im.pixels, "I"))
    print()

    names = [args.kernel] if args.kernel else list(im.show_kernels)
    for i, name in enumerate(names):
        if i:
            print()
        print(format_probe(im, name))
        total, _, _ = conv_at(im.pixels, im.probe[0], im.probe[1], im.kernel_matrix(name), pad=im.pad)
        note = _lecture_note(name, im.probe[0], im.probe[1], total)
        if note:
            print(note)


if __name__ == "__main__":
    main()
