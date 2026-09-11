#!/usr/bin/env python3
"""Program 3: slide the kernel over the whole image (mean, Sobel, edges)."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cvision.cli import DEFAULT_SCENE, build_parser, load  # noqa: E402
from cvision.filters import conv2d, normalize, sobel_magnitude, threshold  # noqa: E402
from cvision.format import format_ascii, format_matrix  # noqa: E402


def main() -> None:
    parser = build_parser("Filter a whole image.", default=DEFAULT_SCENE)
    parser.add_argument(
        "--filter",
        choices=("mean", "sobel", "edges"),
        default="mean",
        help="mean: YAML kernel (default mean5 on the scene). sobel: |G|. edges: threshold on |G|.",
    )
    args = parser.parse_args()
    im = load(args)
    im = replace(
        im,
        pad=args.pad if args.pad is not None else im.pad,
        threshold=args.threshold if args.threshold is not None else im.threshold,
        kernel=args.kernel if args.kernel is not None else im.kernel,
    )

    print(im.name)
    print(f"{im.height}×{im.width}    pad = {im.pad}    filter = {args.filter}")
    print()
    print(format_ascii(im.pixels, "Original"))
    print()

    if args.filter == "mean":
        kname = args.kernel if args.kernel is not None else im.kernel
        k = im.kernel_matrix(kname)
        out = conv2d(im.pixels, k, pad=im.pad)
        print(f"After {kname} ({len(k)}×{len(k[0])})")
        print(format_ascii(out))
        if im.height <= 12:
            print()
            print(format_matrix(out, "I′"))
    elif args.filter == "sobel":
        mag = sobel_magnitude(im.pixels, pad=im.pad)
        print("Sobel magnitude  √(Gx² + Gy²), scaled to [0, 1] for ASCII")
        print(format_ascii(normalize(mag)))
        if im.height <= 12:
            print()
            print(format_matrix(mag, "|G| (raw)"))
    else:
        mag = sobel_magnitude(im.pixels, pad=im.pad)
        edges = threshold(mag, im.threshold, relative=True)
        n_on = sum(1 for row in edges for v in row if v >= 1.0)
        print(f"Edges: 1 if |G| ≥ {im.threshold:g} × max(|G|).    {n_on} edge pixels.")
        print(format_ascii(edges))


if __name__ == "__main__":
    main()
