#!/usr/bin/env python3
"""Convert self-hosted Google Fonts (woff2) to TTF for reportlab PDF embedding.

The web UI uses woff2 files under web/fonts/; reportlab's TTFont loader wants
TTF/OTF. fontTools reads woff2 and writes plain TTF, and instantiates variable
fonts (DM Sans / Playfair Display) at fixed weights, so the same font files
back both the browser and the exported PDFs - one visual language.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

# reportlab's TTFont loader (and most tooling) expects a TrueType sfntVersion,
# not the WOFF2 'wOF2' magic that fontTools keeps by default when saving.
_TTF_SFNT = "\x00\x01\x00\x00"  # TrueType sfnt magic


def _to_ttf(font: TTFont) -> TTFont:
    # fontTools keeps the WOFF2 flavour after loading, and SFNTWriter refuses to
    # write anything else. Reset both the sfntVersion and the flavour so the
    # output is a plain TrueType container that reportlab can load.
    font.sfntVersion = _TTF_SFNT
    font.flavor = None
    font.flavorData = None
    # WOFF2 stores its metadata in a table that has no counterpart in plain TTF;
    # drop it so the file is a clean TrueType container.
    for extra in ("WOFF2", "meta", "MATH"):
        if extra in font:
            del font[extra]
    return font


def save(font: TTFont, dst: Path) -> None:
    font.save(str(dst))
    print(f"  -> {dst.name} ({dst.stat().st_size} bytes)")


def convert_variable(src: Path, out_dir: Path, base: str, instances: dict) -> None:
    font = TTFont(str(src))
    for tag, wght in instances.items():
        inst = instantiateVariableFont(font, {"wght": wght}, inplace=False)
        # drop the fvar table so reportlab sees a static font
        if "fvar" in inst:
            del inst["fvar"]
        if "avar" in inst:
            del inst["avar"]
        save(_to_ttf(inst), out_dir / f"{base}-{tag}.ttf")


def convert_static(src: Path, out_dir: Path, name: str) -> None:
    font = TTFont(str(src))
    if "fvar" in font:
        del font["fvar"]
    if "avar" in font:
        del font["avar"]
    save(_to_ttf(font), out_dir / name)


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    src_dir = repo / "web" / "fonts"
    out_dir = repo / "attune-engine" / "data" / "pdf-fonts"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("DM Sans (variable):")
    convert_variable(src_dir / "dmsans-var.woff2", out_dir, "DM Sans",
                     {"Regular": 400, "Bold": 700})
    print("DM Sans italic (static):")
    convert_static(src_dir / "dmsans-400i.woff2", out_dir, "DM Sans-Italic.ttf")
    print("Boldonse (static):")
    convert_static(src_dir / "boldonse-400.woff2", out_dir, "Boldonse-Regular.ttf")
    print("Playfair Display (variable):")
    convert_variable(src_dir / "playfairdisplay-var.woff2", out_dir, "Playfair Display",
                     {"Regular": 400})
    print("Playfair Display italic (static):")
    convert_static(src_dir / "playfairdisplay-400i.woff2", out_dir,
                   "Playfair Display-Italic.ttf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())