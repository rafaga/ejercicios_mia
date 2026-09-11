"""Images loaded from YAML: a gray matrix, RGB planes, or a tiny generated scene."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cvision.filters import KERNELS, PAD_MODES, _as_kernel


def _matrix(raw: Any, label: str) -> tuple[tuple[float, ...], ...]:
    if not raw:
        raise ValueError(f"{label}: need a list of rows")
    rows = []
    width = None
    for r, row in enumerate(raw):
        if not isinstance(row, (list, tuple)):
            raise ValueError(f"{label}: row {r} is not a list")
        vals = tuple(float(v) for v in row)
        if width is None:
            width = len(vals)
        elif len(vals) != width:
            raise ValueError(f"{label}: row {r} has {len(vals)} cols, expected {width}")
        if width == 0:
            raise ValueError(f"{label}: empty row")
        rows.append(vals)
    return tuple(rows)


def _luma(channels: tuple[tuple[tuple[float, ...], ...], ...]) -> tuple[tuple[float, ...], ...]:
    r, g, b = channels
    out = []
    for i in range(len(r)):
        out.append(tuple((r[i][j] + g[i][j] + b[i][j]) / 3.0 for j in range(len(r[0]))))
    return tuple(out)


def make_scene(n: int) -> tuple[tuple[float, ...], ...]:
    """Circle + rectangle, same layout as the lecture plot (coords scaled from 120)."""
    if n < 8:
        raise ValueError("scene size must be at least 8")
    s = n / 120.0
    cx, cy, rad = 38 * s, 55 * s, 22 * s
    r0, r1 = int(70 * s), int(100 * s)
    c0, c1 = int(72 * s), int(108 * s)
    rows = []
    for i in range(n):
        row = []
        for j in range(n):
            v = 0.88
            if (j - cx) ** 2 + (i - cy) ** 2 < rad ** 2:
                v = 0.18
            if r0 <= i < r1 and c0 <= j < c1:
                v = 0.32
            row.append(v)
        rows.append(tuple(row))
    return tuple(rows)


def make_rgb_bars(rows: int, cols: int) -> tuple[tuple[tuple[float, ...], ...], ...]:
    """Three vertical bars plus a gold rectangle (lecture RGB figure, small)."""
    if rows < 4 or cols < 6:
        raise ValueError("rgb_bars needs at least 4 rows and 6 columns")
    w = cols // 3
    r = [[0.0] * cols for _ in range(rows)]
    g = [[0.0] * cols for _ in range(rows)]
    b = [[0.0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            if j < w:
                r[i][j] = 0.85
            elif j < 2 * w:
                g[i][j] = 0.75
            else:
                b[i][j] = 0.90
    r0, r1 = rows // 5, (4 * rows) // 5
    c0, c1 = cols // 6, cols - cols // 6
    for i in range(r0, r1):
        for j in range(c0, c1):
            r[i][j], g[i][j], b[i][j] = 0.82, 0.62, 0.18
    pack = lambda m: tuple(tuple(v for v in row) for row in m)
    return pack(r), pack(g), pack(b)


@dataclass(frozen=True)
class Image:
    name: str
    kind: str
    pixels: tuple[tuple[float, ...], ...]
    channels: tuple[tuple[tuple[float, ...], ...], ...] | None
    template: tuple[tuple[float, ...], ...] | None
    probe: tuple[int, int]
    pad: str
    threshold: float
    kernel: str
    show_kernels: tuple[str, ...]
    custom_kernel: tuple[tuple[float, ...], ...] | None
    source: Path | None = None

    @property
    def height(self) -> int:
        return len(self.pixels)

    @property
    def width(self) -> int:
        return len(self.pixels[0]) if self.pixels else 0

    def kernel_matrix(self, name: str | None = None) -> tuple[tuple[float, ...], ...]:
        key = (name or self.kernel).strip().lower().replace("-", "_")
        if key in {"custom", "yaml"} and self.custom_kernel is not None:
            return self.custom_kernel
        if key in KERNELS:
            return KERNELS[key]
        if self.custom_kernel is not None and name is None:
            return self.custom_kernel
        from cvision.filters import get_kernel

        return get_kernel(key)


def load_image(path: str | Path) -> Image:
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return parse_image(raw, source=path)


def parse_image(raw: dict[str, Any], source: Path | None = None) -> Image:
    kind = str(raw.get("kind") or "gray")
    channels = None
    template = None

    if kind == "gray":
        pixels = _matrix(raw.get("pixels"), "pixels")
    elif kind == "scene":
        pixels = make_scene(int(raw.get("size") or 28))
    elif kind == "rgb":
        ch = raw.get("channels") or {}
        if not (ch.get("r") and ch.get("g") and ch.get("b")):
            raise ValueError("rgb: need channels.r, channels.g, channels.b")
        channels = (_matrix(ch["r"], "r"), _matrix(ch["g"], "g"), _matrix(ch["b"], "b"))
        h = len(channels[0])
        w = len(channels[0][0])
        for name, plane in zip("rgb", channels):
            if len(plane) != h or len(plane[0]) != w:
                raise ValueError(f"rgb: channel {name} is not {h}×{w}")
        pixels = _luma(channels)
    elif kind == "rgb_bars":
        channels = make_rgb_bars(int(raw.get("rows") or 8), int(raw.get("cols") or 12))
        pixels = _luma(channels)
    else:
        raise ValueError(f"unknown kind {kind!r} (gray | scene | rgb | rgb_bars)")

    if raw.get("template"):
        template = _matrix(raw.get("template"), "template")

    h, w = len(pixels), len(pixels[0])
    probe_raw = raw.get("probe") or [h // 2, w // 2]
    if not isinstance(probe_raw, (list, tuple)) or len(probe_raw) != 2:
        raise ValueError("probe: [row, col]")
    probe = (int(probe_raw[0]), int(probe_raw[1]))
    if not (0 <= probe[0] < h and 0 <= probe[1] < w):
        raise ValueError(f"probe {probe} is outside the {h}×{w} image")

    pad = str(raw.get("pad") or "edge")
    if pad not in PAD_MODES:
        raise ValueError(f"pad must be one of {PAD_MODES}")

    custom = None
    kernel_field = raw.get("kernel", "mean3")
    if isinstance(kernel_field, list):
        custom = _as_kernel(kernel_field)
        kernel_name = "custom"
    else:
        kernel_name = str(kernel_field)

    show = raw.get("show_kernels")
    if show:
        show_kernels = tuple(str(s) for s in show)
    else:
        show_kernels = (kernel_name,)

    return Image(
        name=str(raw.get("name") or "image"),
        kind=kind,
        pixels=pixels,
        channels=channels,
        template=template,
        probe=probe,
        pad=pad,
        threshold=float(raw.get("threshold", 0.28)),
        kernel=kernel_name,
        show_kernels=show_kernels,
        custom_kernel=custom,
        source=source,
    )
