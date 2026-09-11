"""CLI helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from cvision.image import Image, load_image

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STEP = ROOT / "data" / "step.yaml"
DEFAULT_LETTER = ROOT / "data" / "letter_e.yaml"
DEFAULT_SCENE = ROOT / "data" / "scene.yaml"


def build_parser(description: str, default: Path | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--image", type=Path, default=default or DEFAULT_LETTER, help="YAML image")
    parser.add_argument("--kernel", type=str, default=None, help="Override YAML kernel name")
    parser.add_argument("--pad", type=str, default=None, help="edge | zero | none")
    parser.add_argument("--threshold", type=float, default=None, help="Override YAML τ (fraction of max)")
    return parser


def load(args: argparse.Namespace) -> Image:
    return load_image(args.image)
