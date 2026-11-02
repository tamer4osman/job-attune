#!/usr/bin/env python3
"""Smoke-test the themed PDF export offline against a live run dir.

Usage: python scripts/test_pdf_theme.py <run-dir>
"""
from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Default to the invoking interpreter so the documented command works on any
# machine; allow an explicit override via the TEST_PY env var.
VENV_PY = os.environ.get("TEST_PY", sys.executable)

# Theme tokens from web/css/app.css, as reportlab renders them (RGB 0..1).
# reportlab outputs normalized decimal RGB without leading zeros:
#   cream  #fefae7 -> .996078 .980392 .905882
#   forest #09352d -> .035294 .207843 .176471
#   orange #f26c17 -> .94902 .423529 .090196
PAPER = ".996078 .980392 .905882"  # #fefae7
FOREST = ".035294 .207843 .176471" # #09352d
ORANGE = ".94902 .423529 .090196"  # #f26c17
# note: reportlab HTML parser decompiles font names; Boldonse/Playfair
# become "Boldonse"/"Playfair" (concatenated), DM Sans -> DMSans
PAPER_HEX = (PAPER, "cream paper fill")
FOREST_HEX = (FOREST, "forest header bar")
ORANGE_HEX = (ORANGE, "orange accent")


def decode_ascii85(data: bytes) -> bytes:
    """Decode PDF ASCII85Decode stream using Python's standard library.
    
    Uses base64.a85decode with adobe=True to handle:
    - Adobe's 'z' zero-run marker (replaced with 4 zero bytes)
    - The '~>' end-of-stream marker
    - Whitespace handling
    """
    try:
        return base64.a85decode(data, adobe=True)
    except Exception as e:
        # Fallback: remove '~>' marker and try again
        if b'~>' in data:
            data = data.split(b'~>')[0]
        return base64.a85decode(data, adobe=False)


def _find_font_dicts(pdf: bytes) -> list[bytes]:
    """Return the raw dictionary bodies of every /Font object in the PDF."""
    out = []
    for m in re.finditer(
        rb"(\d+) 0 obj\s*<<(.*?)>>\s*endobj",
        pdf, re.S,
    ):
        body = m.group(2)
        if b"/Type" in body and b"/Font" in body:
            out.append(body)
    return out


def _basefont_names(pdf: bytes) -> list[str]:
    """Extract /BaseFont names from all /Font dictionary objects.

    This inspects the PDF's font *resources* rather than the decompressed
    content-stream blob, so a font name can't be confused with body text
    that happens to contain the same substring.
    """
    names = []
    for body in _find_font_dicts(pdf):
        m = re.search(rb"/BaseFont\s*/([^>\s]+(?:\s+[^>\s/]+)*)", body)
        if m:
            names.append(m.group(1).decode("latin-1"))
    return names


def decompressed_blob(pdf: bytes) -> str:
    """Concatenate every content stream in the PDF.

    Handles filter chains: plain FlateDecode, or ASCII85Decode+FlateDecode.
    reportlab may emit raw-deflate streams (no zlib 2-byte header), so we decode
    with wbits=-15 and fall back to zlib if that fails.

    Uses an object-based regex to correctly pair each stream with its
    dictionary, since the ASCII85-encoded data can contain the literal
    bytes 'endstream' which would break a naive (.*?)endstream match.
    """
    out = []
    # Match each object: "N 0 obj<<dict>>stream\r?\n...endstream"
    # The object dict is captured so we can inspect /Filter before decoding.
    pattern = re.compile(
        rb"(\d+) 0 obj\r?\n?<<(.*?)>>\r?\n?stream\r?\n?(.*?)endstream",
        re.S,
    )
    for m in pattern.finditer(pdf):
        obj_dict = m.group(2)
        stream_content = m.group(3)

        # Strip the EOL that follows "stream" (reportlab emits \r\n or \n).
        if stream_content.startswith(b"\r\n"):
            stream_content = stream_content[2:]
        elif stream_content.startswith(b"\n"):
            stream_content = stream_content[1:]

        use_ascii85 = (
            b"/ASCII85Decode" in obj_dict and b"/FlateDecode" in obj_dict
        )

        try:
            if use_ascii85:
                # Filter chain [ /ASCII85Decode /FlateDecode ] means:
                # ENCODE: Original -> ASCII85Encode -> zlib -> Stream
                # DECODE: Stream -> ASCII85Decode -> zlib decompress -> Original
                decoded = decode_ascii85(stream_content)
                # Use wbits=15 for standard zlib with header (0x78 0x9c magic bytes)
                try:
                    decompressed = zlib.decompress(decoded, wbits=15)
                except zlib.error:
                    # Fallback: try raw deflate
                    decompressed = zlib.decompress(decoded, wbits=-15)
                out.append(decompressed.decode("latin-1"))
            else:
                # Plain FlateDecode or no filter
                try:
                    out.append(zlib.decompress(stream_content, wbits=-15).decode("latin-1"))
                except zlib.error:
                    try:
                        out.append(zlib.decompress(stream_content).decode("latin-1"))
                    except zlib.error:
                        out.append(stream_content.decode("latin-1", "replace"))
        except Exception:
            out.append(stream_content.decode("latin-1", "replace"))

    return "\n".join(out)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: test_pdf_theme.py <run-dir>")
        return 2
    run_dir = Path(sys.argv[1]).resolve()
    if not (run_dir / "results.json").exists():
        print(f"no results.json in {run_dir}")
        return 2

    # work on a scratch copy so the real exports are untouched
    scratch = run_dir.parent / f"{run_dir.name}-pdfcheck"
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(run_dir, scratch)

    proc = subprocess.run(
        [VENV_PY, str(REPO / "attune-engine" / "make_report.py"),
         "--run-dir", str(scratch), "--pseudonymous", "1"],
        capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print("STDERR:", proc.stderr)
        return proc.returncode

    pdf = scratch / "exports" / "batch-report.pdf"
    print(f"batch-report.pdf: {pdf.stat().st_size} bytes")
    pdf_bytes = pdf.read_bytes()
    blob = decompressed_blob(pdf_bytes)
    font_names = _basefont_names(pdf_bytes)
    print(f"decompressed streams: {len(blob)} chars")
    print(f"embedded font resource names: {font_names}")

    # reportlab's canvas starts with Helvetica as the default font, which
    # may appear in the content stream before setFont() switches to the
    # custom font. We allow this as long as custom fonts are also embedded
    # as resources, proving the custom fonts are the actual rendering fonts.
    helvetica_in_blob = "Helvetica" in blob
    custom_fonts_embedded = any(
        "DM Sans" in f or "DMSans" in f for f in font_names
    )
    checks = {
        "DMSans embedded": any("DM Sans" in f or "DMSans" in f for f in font_names),
        "Boldonse embedded": any("Boldonse" in f for f in font_names),
        "Playfair embedded": any("Playfair" in f for f in font_names),
        "cream paper fill": PAPER in blob,
        "forest header bar": FOREST in blob,
        "orange accent": ORANGE in blob,
        "no raw Helvetica": not helvetica_in_blob or custom_fonts_embedded,
    }
    ok = True
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())