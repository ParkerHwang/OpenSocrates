#!/usr/bin/env python3
"""Render contact sheets for visual QA; requires PyMuPDF and Pillow."""
from pathlib import Path
import pymupdf as fitz
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "render_checks"
OUT.mkdir(parents=True, exist_ok=True)

for filename, output, columns in [
    ("meridian_executive_report.pdf", "report_contact.png", 2),
    ("meridian_board_presentation.pdf", "presentation_contact.png", 2),
]:
    document = fitz.open(ROOT / "deliverables" / filename)
    thumbs = []
    for index, page in enumerate(document):
        full = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        full.save(OUT / f"{output.removesuffix('_contact.png')}_{index+1:02d}.png")
        pix = page.get_pixmap(matrix=fitz.Matrix(0.7, 0.7), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        image.thumbnail((500, 710 if filename.startswith("meridian_executive") else 281))
        canvas = Image.new("RGB", (image.width + 14, image.height + 36), "white")
        canvas.paste(image, (7, 26))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 6), f"Page {index+1}", fill="#14324A")
        thumbs.append(canvas)
    cell_w = max(im.width for im in thumbs)
    cell_h = max(im.height for im in thumbs)
    rows = (len(thumbs) + columns - 1) // columns
    contact = Image.new("RGB", (cell_w*columns, cell_h*rows), "#dfe7ea")
    for i, im in enumerate(thumbs):
        contact.paste(im, ((i % columns)*cell_w, (i // columns)*cell_h))
    contact.save(OUT / output)
    print(f"{filename}: {len(document)} pages -> {OUT/output}")
