#!/usr/bin/env python3
"""Render the generated PDF to PNGs for local visual inspection."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / ".deps"))
import fitz


def main() -> None:
    pdf_path = ROOT / "deliverables" / "meridian_parts_executive_report.pdf"
    out = ROOT / ".render-check" / "report"
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    if len(doc) != 11:
        raise AssertionError(f"expected 11 report pages, found {len(doc)}")
    for idx, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
        pix.save(out / f"page-{idx:02d}.png")
        if pix.width < 500 or pix.height < 700:
            raise AssertionError(f"unexpected render size on page {idx}")
    print(f"Rendered {len(doc)} PDF pages to {out}")


if __name__ == "__main__":
    main()
