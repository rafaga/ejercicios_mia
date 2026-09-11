"""Pretty-print gray images, RGB planes, kernels, and one convolution."""

from __future__ import annotations

from cvision.filters import conv_at
from cvision.image import Image

RAMP = " .:-=+*#%@"


def fmt_num(v: float, width: int = 6) -> str:
    if abs(v - round(v)) < 1e-9 and abs(v) < 1e6:
        return f"{int(round(v)):{width}d}"
    return f"{v:{width}.3f}"


def fmt_kernel_entry(v: float) -> str:
    for n, d in ((1, 9), (1, 25), (1, 1), (2, 1), (5, 1)):
        if abs(v - n / d) < 1e-12:
            return f"{n}/{d}" if d != 1 else str(n)
        if abs(v + n / d) < 1e-12:
            return f"-{n}/{d}" if d != 1 else f"-{n}"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.3f}"


def format_matrix(
    img: list[list[float]] | tuple[tuple[float, ...], ...],
    title: str | None = None,
    max_size: int = 16,
) -> str:
    h, w = len(img), len(img[0])
    lines = []
    if title:
        lines.append(title)
    if h > max_size or w > max_size:
        lines.append(f"{h}×{w}  (too large to print every number; ASCII is below)")
        return "\n".join(lines)
    col_w = 6
    header = "     " + "".join(f"{j:>{col_w}d}" for j in range(w))
    lines.append(header)
    for i, row in enumerate(img):
        lines.append(f"{i:>4d} " + "".join(fmt_num(v, col_w) for v in row))
    return "\n".join(lines)


def ascii_gray(
    img: list[list[float]] | tuple[tuple[float, ...], ...],
    lo: float | None = None,
    hi: float | None = None,
) -> str:
    vals = [v for row in img for v in row]
    if lo is None:
        lo = min(vals)
    if hi is None:
        hi = max(vals)
    span = hi - lo if hi > lo else 1.0
    n = len(RAMP) - 1
    lines = []
    for row in img:
        chars = []
        for v in row:
            t = (v - lo) / span
            t = 0.0 if t < 0 else 1.0 if t > 1 else t
            chars.append(RAMP[int(round(t * n))])
        lines.append("".join(chars))
    return "\n".join(lines)


def format_ascii(img: list[list[float]] | tuple[tuple[float, ...], ...], title: str | None = None) -> str:
    body = ascii_gray(img)
    if title:
        return title + "\n" + body
    return body


def format_image(im: Image, numeric_max: int = 12) -> str:
    lines = [
        im.name,
        "",
        f"kind = {im.kind}    size = {im.height}×{im.width}    pad = {im.pad}",
        f"probe = (row {im.probe[0]}, col {im.probe[1]})    kernel = {im.kernel}    threshold τ = {im.threshold:g} × max",
    ]
    if im.source:
        lines.append(f"file = {im.source}")
    lines.append("")
    if im.channels is None:
        lines.append(format_matrix(im.pixels, "I  (gray)", max_size=numeric_max))
        lines.append("")
        lines.append(format_ascii(im.pixels, "ASCII  (dark → light)"))
    else:
        names = ("R", "G", "B")
        for name, plane in zip(names, im.channels):
            lines.append(format_matrix(plane, f"channel {name}", max_size=numeric_max))
            lines.append("")
        lines.append("gray used by filters = (R + G + B) / 3")
        lines.append(format_matrix(im.pixels, None, max_size=numeric_max))
        lines.append("")
        lines.append(format_ascii(im.pixels, "ASCII of that gray"))
    if im.template is not None:
        lines.append("")
        lines.append(format_matrix(im.template, "template", max_size=numeric_max))
    return "\n".join(lines)


def format_kernel(kernel: tuple[tuple[float, ...], ...], title: str = "K") -> str:
    lines = [title]
    for row in kernel:
        lines.append("  " + "  ".join(f"{fmt_kernel_entry(v):>6}" for v in row))
    return "\n".join(lines)


def format_probe(im: Image, kernel_name: str | None = None) -> str:
    name = kernel_name or im.kernel
    k = im.kernel_matrix(name)
    row, col = im.probe
    total, win, products = conv_at(im.pixels, row, col, k, pad=im.pad)
    kh, kw = len(k), len(k[0])
    lines = [
        f"Kernel {name}  ({kh}×{kw}) at I[{row}, {col}]    pad = {im.pad}",
        "",
        "Neighborhood of I",
    ]
    for r in win:
        lines.append("  " + "  ".join(fmt_num(v, 6) for v in r))
    lines.append("")
    lines.append(format_kernel(k, "K"))
    lines.append("")
    lines.append("K · I  (cell by cell)")
    for r in products:
        lines.append("  " + "  ".join(fmt_num(v, 6) for v in r))
    lines.append("")
    lines.append(f"I′[{row}, {col}]  =  Σ K·I  =  {fmt_num(total, 0).strip()}")
    return "\n".join(lines)
