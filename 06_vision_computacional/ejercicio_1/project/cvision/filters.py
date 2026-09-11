"""Convolution, named kernels, Sobel magnitude, threshold, template SSD."""

from __future__ import annotations

import math
from typing import Callable, Sequence

Gray = Sequence[Sequence[float]]

KERNELS: dict[str, tuple[tuple[float, ...], ...]] = {
    "identity": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0)),
    "mean3": tuple(tuple(1.0 / 9.0 for _ in range(3)) for _ in range(3)),
    "mean5": tuple(tuple(1.0 / 25.0 for _ in range(5)) for _ in range(5)),
    "sobel_x": ((-1.0, 0.0, 1.0), (-2.0, 0.0, 2.0), (-1.0, 0.0, 1.0)),
    "sobel_y": ((-1.0, -2.0, -1.0), (0.0, 0.0, 0.0), (1.0, 2.0, 1.0)),
    "sharpen": ((0.0, -1.0, 0.0), (-1.0, 5.0, -1.0), (0.0, -1.0, 0.0)),
}

PAD_MODES = ("edge", "zero", "none")


def get_kernel(name: str) -> tuple[tuple[float, ...], ...]:
    key = name.strip().lower().replace("-", "_")
    if key not in KERNELS:
        known = ", ".join(sorted(KERNELS))
        raise ValueError(f"unknown kernel {name!r} (one of: {known})")
    return KERNELS[key]


def _as_kernel(kernel: tuple[tuple[float, ...], ...] | list[list[float]]) -> tuple[tuple[float, ...], ...]:
    rows = tuple(tuple(float(v) for v in row) for row in kernel)
    if not rows or not rows[0]:
        raise ValueError("kernel must be a non-empty matrix")
    width = len(rows[0])
    for row in rows:
        if len(row) != width:
            raise ValueError("kernel rows must have the same length")
    return rows


def sample(img: Gray | tuple[tuple[float, ...], ...], i: int, j: int, pad: str) -> float:
    h, w = len(img), len(img[0])
    if pad == "none":
        if not (0 <= i < h and 0 <= j < w):
            raise IndexError(f"({i}, {j}) is outside the image and pad=none")
        return float(img[i][j])
    if pad == "zero":
        if 0 <= i < h and 0 <= j < w:
            return float(img[i][j])
        return 0.0
    if pad != "edge":
        raise ValueError(f"pad must be edge, zero, or none (got {pad!r})")
    ii = min(max(i, 0), h - 1)
    jj = min(max(j, 0), w - 1)
    return float(img[ii][jj])


def neighborhood(
    img: Gray | tuple[tuple[float, ...], ...],
    row: int,
    col: int,
    kernel: tuple[tuple[float, ...], ...],
    pad: str,
) -> list[list[float]]:
    kh, kw = len(kernel), len(kernel[0])
    ph, pw = kh // 2, kw // 2
    window = []
    for u in range(kh):
        window.append([sample(img, row - ph + u, col - pw + v, pad) for v in range(kw)])
    return window


def conv_at(
    img: Gray | tuple[tuple[float, ...], ...],
    row: int,
    col: int,
    kernel: tuple[tuple[float, ...], ...] | list[list[float]],
    pad: str = "edge",
) -> tuple[float, list[list[float]], list[list[float]]]:
    """Return (sum of products, I window, products) at one pixel."""
    k = _as_kernel(kernel)
    win = neighborhood(img, row, col, k, pad)
    products = []
    total = 0.0
    for u, krow in enumerate(k):
        prow = []
        for v, kv in enumerate(krow):
            p = kv * win[u][v]
            prow.append(p)
            total += p
        products.append(prow)
    return total, win, products


def conv2d(
    img: Gray | tuple[tuple[float, ...], ...],
    kernel: tuple[tuple[float, ...], ...] | list[list[float]],
    pad: str = "edge",
) -> Gray:
    k = _as_kernel(kernel)
    kh, kw = len(k), len(k[0])
    ph, pw = kh // 2, kw // 2
    h, w = len(img), len(img[0])
    if pad == "none":
        if h < kh or w < kw:
            raise ValueError("image smaller than kernel (pad=none)")
        row_ids = list(range(ph, h - (kh - 1 - ph)))
        col_ids = list(range(pw, w - (kw - 1 - pw)))
        return [[conv_at(img, i, j, k, pad="none")[0] for j in col_ids] for i in row_ids]
    out = []
    for i in range(h):
        out.append([conv_at(img, i, j, k, pad=pad)[0] for j in range(w)])
    return out


def hypot_mag(gx: Gray, gy: Gray) -> Gray:
    return [[math.hypot(a, b) for a, b in zip(rx, ry)] for rx, ry in zip(gx, gy)]


def sobel_magnitude(img: Gray | tuple[tuple[float, ...], ...], pad: str = "edge") -> Gray:
    gx = conv2d(img, KERNELS["sobel_x"], pad=pad)
    gy = conv2d(img, KERNELS["sobel_y"], pad=pad)
    return hypot_mag(gx, gy)


def peak(img: Gray) -> float:
    m = 0.0
    for row in img:
        for v in row:
            m = max(m, abs(v))
    return m


def normalize(img: Gray) -> Gray:
    m = peak(img)
    if m == 0:
        return [list(row) for row in img]
    return [[v / m for v in row] for row in img]


def threshold(img: Gray, tau: float, relative: bool = True) -> Gray:
    """Binary map: 1 if value >= tau (or tau × max if relative)."""
    cut = tau * peak(img) if relative else tau
    return [[1.0 if v >= cut else 0.0 for v in row] for row in img]


def map2d(img: Gray, fn: Callable[[float], float]) -> Gray:
    return [[fn(v) for v in row] for row in img]


def ssd_match(
    img: Gray | tuple[tuple[float, ...], ...],
    template: Gray | tuple[tuple[float, ...], ...],
) -> tuple[int, int, float]:
    """Slide template; return (row, col, SSD) of the best (smallest) fit."""
    th, tw = len(template), len(template[0])
    h, w = len(img), len(img[0])
    if th > h or tw > w:
        raise ValueError("template larger than image")
    best_s = None
    best = (0, 0, 0.0)
    for i in range(h - th + 1):
        for j in range(w - tw + 1):
            s = 0.0
            for u in range(th):
                for v in range(tw):
                    d = float(img[i + u][j + v]) - float(template[u][v])
                    s += d * d
            if best_s is None or s < best_s:
                best_s = s
                best = (i, j, s)
    assert best_s is not None
    return best
