"""Render every PDF page locally for visual inspection and make contact sheets."""
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'verification/rendered';DEST.mkdir(parents=True,exist_ok=True)
for filename,prefix in [('Meridian_executive_report.pdf','report'),('Meridian_board_presentation.pdf','deck')]:
    doc=pdfium.PdfDocument(ROOT/'deliverables'/filename)
    thumbs=[]
    for i in range(len(doc)):
        page=doc[i];bitmap=page.render(scale=1.4 if prefix=='report' else 1.25);im=bitmap.to_pil().convert('RGB')
        im.save(DEST/f'{prefix}_{i+1:02}.png')
        thumb=ImageOps.contain(im,(310,439) if prefix=='report' else (400,225))
        tile=Image.new('RGB',(330,470) if prefix=='report' else (420,255),'#dde5e8');tile.paste(thumb,((tile.width-thumb.width)//2,21))
        ImageDraw.Draw(tile).text((10,5),f'{prefix.upper()} {i+1}',fill='#122c43');thumbs.append(tile)
        bitmap.close();page.close()
    columns=3 if prefix=='report' else 2;tw,th=thumbs[0].size
    contact=Image.new('RGB',(columns*tw,((len(thumbs)+columns-1)//columns)*th),'#dde5e8')
    for i,tile in enumerate(thumbs):contact.paste(tile,((i%columns)*tw,(i//columns)*th))
    contact.save(DEST/f'{prefix}_contact.png');doc.close()
    print(f'Rendered {len(thumbs)} {prefix} pages')
