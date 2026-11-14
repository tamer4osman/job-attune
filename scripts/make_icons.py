#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Regenerate the PWA/desktop icon set from web/logo.svg.

Outputs (all rasterized from the authentic SVG via cairosvg, so the icons
always match the logo the UI ships):

  web/icons/icon-<N>.png           N in {192, 512}   - purpose "any"
  web/icons/icon-maskable-<N>.png  N in {192, 512}   - purpose "maskable"
  electron/build/icon.png          1024              - electron-builder source

Maskable variants re-pad the logo to the W3C safe zone: the full logo is
scaled to ~72% of the canvas and centered over a full-bleed forest background
(--forest, #09352d), so Android's circular/rounded masks never clip the
tuning-fork mark. The "any" variants keep the SVG's own transparent margins.

Usage:  python3 scripts/make_icons.py
Deps:   pip install cairosvg pillow  (CI never calls this - icons are
        committed, the script only runs when the logo changes).
"""

from __future__ import annotations

import io
import pathlib

import cairosvg
from PIL import Image

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGO = PROJECT_ROOT / "web" / "logo.svg"
ICONS = PROJECT_ROOT / "web" / "icons"
ELECTRON_ICON_DIR = PROJECT_ROOT / "electron" / "build"

FOREST = (9, 53, 45, 255)  # --forest / #09352d, the tile gradient midpoint
MASKABLE_SCALE = 0.72  # W3C safe zone: content inside the center 80% circle


def render(size: int) -> Image.Image:
    """Rasterize web/logo.svg at exactly size x size (transparent margins)."""
    png = cairosvg.svg2png(url=str(LOGO), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def render_maskable(size: int) -> Image.Image:
    """Full-bleed forest tile with the logo centered inside the safe zone."""
    canvas = Image.new("RGBA", (size, size), FOREST)
    inner = round(size * MASKABLE_SCALE)
    logo = render(inner)
    offset = ((size - inner) // 2, (size - inner) // 2)
    canvas.alpha_composite(logo, offset)
    return canvas


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    ELECTRON_ICON_DIR.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[Image.Image, pathlib.Path]] = []
    for size in (192, 512):
        jobs.append((render(size), ICONS / f"icon-{size}.png"))
        jobs.append((render_maskable(size), ICONS / f"icon-maskable-{size}.png"))
    jobs.append((render(1024), ELECTRON_ICON_DIR / "icon.png"))

    for img, path in jobs:
        img.save(path, format="PNG", optimize=True)
        w, h = img.size
        print(f"wrote {path.relative_to(PROJECT_ROOT)}  ({w}x{h}, {path.stat().st_size} bytes)")

    # Sanity: PNGs must be square and non-empty.
    for _, path in jobs:
        with Image.open(path) as im:
            assert im.size[0] == im.size[1] and im.size[0] >= 192, path


if __name__ == "__main__":
    main()
