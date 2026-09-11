#!/usr/bin/env python3
"""Program 4: lecture numbers, padding, threshold, and a template search."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cvision.cli import ROOT as PROJ  # noqa: E402
from cvision.filters import conv2d, conv_at, get_kernel, sobel_magnitude, ssd_match, threshold  # noqa: E402
from cvision.format import format_ascii, format_matrix, fmt_num  # noqa: E402
from cvision.image import load_image  # noqa: E402

DATA = PROJ / "data"


def lecture_demo() -> None:
    im = load_image(DATA / "step.yaml")
    print("1. Lecture arithmetic on the 0|9 step")
    print("-" * 72)
    print(im.name)
    print("probe (2, 2), pad = edge")
    print()
    print(format_matrix(im.pixels, "I"))
    print()
    print(f"{'kernel':<10}  {'I′[2,2]':>8}  expected")
    for name, expected in (("mean3", 3.0), ("sobel_x", 36.0), ("sobel_y", 0.0)):
        val, _, _ = conv_at(im.pixels, 2, 2, get_kernel(name), pad="edge")
        mark = "ok" if abs(val - expected) < 1e-9 else "MISMATCH"
        print(f"{name:<10}  {fmt_num(val, 8)}  {fmt_num(expected, 8).strip()}  {mark}")
    print()
    print("Mean: six 0s and three 9s → 27/9 = 3.  Sobel-X sees the vertical wall; Sobel-Y does not.")


def pad_demo() -> None:
    im = load_image(DATA / "step.yaml")
    k = get_kernel("mean3")
    print("2. Padding changes the border, not the interior")
    print("-" * 72)
    print("Same 3×3 mean. Interior of the step stays 3. Corners differ.")
    print()
    for mode in ("edge", "zero", "none"):
        out = conv2d(im.pixels, k, pad=mode)
        print(f"pad = {mode}    I′ is {len(out)}×{len(out[0])}")
        print(format_matrix(out, None, max_size=16))
        print()
    print("pad=none drops the frame (the kernel would hang off). zero pulls border values toward 0.")


def threshold_demo() -> None:
    im = load_image(DATA / "scene.yaml")
    mag = sobel_magnitude(im.pixels, pad=im.pad)
    print("3. Threshold on Sobel magnitude")
    print("-" * 72)
    print(im.name)
    print("On a clean scene the contour is already strong, so a low τ still traces the same two shapes.")
    print("Raise τ enough and corners start to disappear.")
    print()
    print(f"{'τ × max':>8}  {'edge pixels':>12}")
    for tau in (0.10, 0.28, 0.70):
        edges = threshold(mag, tau, relative=True)
        n_on = sum(1 for row in edges for v in row if v >= 1.0)
        print(f"{tau:8.2f}  {n_on:12d}")
    print()
    print("ASCII at τ = 0.28")
    print(format_ascii(threshold(mag, 0.28, relative=True)))


def template_demo() -> None:
    im = load_image(DATA / "find_e.yaml")
    if im.template is None:
        raise SystemExit(f"{im.source}: add a template: matrix")
    row, col, ssd = ssd_match(im.pixels, im.template)
    print("4. Template matching (sum of squared differences)")
    print("-" * 72)
    print(im.name)
    print("Slide the template; the fit is the (row, col) with the smallest SSD.")
    print()
    print(format_ascii(im.pixels, "Canvas"))
    print()
    print(format_ascii(im.template, "Template"))
    print()
    print(f"best SSD = {ssd:g} at row {row}, col {col}")
    print("Lecture E sits at (2, 4). A bar of 8s elsewhere is similar but not the same shape.")
    if (row, col) == (2, 4) and ssd == 0:
        print("Exact copy found (SSD = 0). Rotate or scale the E in the YAML and this breaks.")


def rgb_demo() -> None:
    im = load_image(DATA / "rgb_bars.yaml")
    print("5. Color is three gray images")
    print("-" * 72)
    print(im.name)
    print("Filters in this lab run on gray = (R+G+B)/3, or on one channel at a time.")
    print()
    from cvision.format import format_image

    print(format_image(im, numeric_max=12))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare padding, thresholds, and templates.")
    parser.add_argument(
        "--only",
        choices=("lecture", "pad", "threshold", "template", "rgb", "all"),
        default="all",
    )
    args = parser.parse_args()
    demos = {
        "lecture": lecture_demo,
        "pad": pad_demo,
        "threshold": threshold_demo,
        "template": template_demo,
        "rgb": rgb_demo,
    }
    names = list(demos) if args.only == "all" else [args.only]
    for i, name in enumerate(names):
        if i:
            print()
            print()
        demos[name]()


if __name__ == "__main__":
    main()
