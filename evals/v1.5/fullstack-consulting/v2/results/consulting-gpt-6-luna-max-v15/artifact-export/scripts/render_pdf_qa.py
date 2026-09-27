"""Optional visual QA renderer; pypdfium2 is installed locally for this run."""
from pathlib import Path
import sys

from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local_packages"))
import pypdfium2 as pdfium


def contact(pdf_path, output, thumb_width=540, cols=2):
    doc = pdfium.PdfDocument(str(pdf_path))
    thumbs = []
    for i in range(len(doc)):
        page = doc[i]
        bitmap = page.render(scale=thumb_width / page.get_width())
        pil = bitmap.to_pil().convert("RGB")
        pil.thumbnail((thumb_width, 400))
        framed = ImageOps.expand(pil, border=1, fill="#aab7bf")
        thumbs.append(framed)
    cell_w = max(x.width for x in thumbs) + 22
    cell_h = max(x.height for x in thumbs) + 32
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w + 18, rows * cell_h + 18), "#e8eef1")
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        x = 9 + (i % cols) * cell_w + 8
        y = 9 + (i // cols) * cell_h + 22
        sheet.paste(thumb, (x, y))
        draw.text((x, y - 17), f"Page {i+1}", fill="#16324f")
    sheet.save(output)
    return len(doc), output.stat().st_size


if __name__ == "__main__":
    qa = ROOT / "analysis" / "qa"
    qa.mkdir(parents=True, exist_ok=True)
    for name in ("meridian_board_report.pdf", "meridian_board_presentation.pdf"):
        count, size = contact(ROOT / "deliverables" / name, qa / (name.replace(".pdf", "_contact.png")), cols=2)
        print(name, "pages", count, "contact_sheet_bytes", size)
