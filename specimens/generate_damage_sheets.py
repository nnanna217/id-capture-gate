"""Print sheets of mock specimen cards for the damaged-card shoot (D-15, route b): 8 cards per US-Letter page at true size
(85.6 x 54 mm), one layout per page, 3 pages per layout = 24 cards each, 6 pages in all.

The card faces are exactly the ones in generate_mock_cards_pdf.py (imported, not copied), so a damaged copy and a clean copy differ
only by the damage. Nothing is printed on a card face that is not on the clean card. Each card has a copy number (ID-01..ID-24,
BANK-01..BANK-24) printed OUTSIDE it, in the margin under its bottom-left corner: write it on the back after cutting, so the clean
shot and the damaged shot of one physical card can be paired.

Print at 100% / "actual size" (no fit-to-page), on 160-200 gsm paper if you can: plain paper does not fold or tear like a card.
usage (from the repo root): python -I specimens/generate_damage_sheets.py        -> specimens/cards/damage-sheets-letter.pdf
Needs `reportlab`.
"""
import importlib.util
from pathlib import Path

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

spec = importlib.util.spec_from_file_location("faces", Path(__file__).with_name("generate_mock_cards_pdf.py"))
faces = importlib.util.module_from_spec(spec)
spec.loader.exec_module(faces)

CARD_W, CARD_H = faces.CARD_W, faces.CARD_H
COLS, ROWS, PER_LAYOUT = 2, 4, 24
GAP_X, GAP_Y = 10 * mm, 9 * mm
LAYOUTS = (("ID", "ID layout", faces.id_card), ("BANK", "Bank layout", faces.bank_card))
GREY = Color(0.4, 0.4, 0.4)


def page(c, tag, title, draw, number, pages):
    pw, ph = letter
    grid_w, grid_h = COLS * CARD_W + (COLS - 1) * GAP_X, ROWS * CARD_H + (ROWS - 1) * GAP_Y
    x0, top = (pw - grid_w) / 2, (ph + grid_h) / 2          # grid centred on the page
    c.setFillColor(GREY)
    c.setFont("Helvetica", 7.5)
    c.drawString(x0, ph - 11 * mm, f"{title}, page {number} of {pages}: {COLS * ROWS} cards at actual size 85.6 x 54 mm. "
                 f"Print at 100%, no fit-to-page. Cut on the grey guide.")
    c.drawString(x0, 9 * mm, "Specimen cards, invented data only. Write the copy number on the back of each card after cutting.")
    for k in range(COLS * ROWS):
        r, col = divmod(k, COLS)
        x, y = x0 + col * (CARD_W + GAP_X), top - (r + 1) * CARD_H - r * GAP_Y
        draw(c, x, y)
        c.setStrokeColor(Color(0.63, 0.63, 0.63))
        c.setLineWidth(0.3)
        c.rect(x - 3, y - 3, CARD_W + 6, CARD_H + 6, stroke=1, fill=0)   # cut guide, outside the card
        c.setFillColor(GREY)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x, y - 9.5, f"{tag}-{(number - 1) * COLS * ROWS + k + 1:02d}")
    c.showPage()


def main():
    out = Path("specimens/cards")
    out.mkdir(exist_ok=True)
    c = canvas.Canvas(str(out / "damage-sheets-letter.pdf"), pagesize=letter)
    c.setTitle("Mock specimen cards for the damaged-card shoot - print at 100%")
    pages = PER_LAYOUT // (COLS * ROWS)
    for tag, title, draw in LAYOUTS:
        for n in range(1, pages + 1):
            page(c, tag, title, draw, n, pages)
    c.save()
    print("wrote", out / "damage-sheets-letter.pdf", f"({2 * pages} pages, {2 * PER_LAYOUT} cards)")


if __name__ == "__main__":
    main()
