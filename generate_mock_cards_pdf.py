"""Vector version of the printable mock-card page (US Letter, two cards at true size 85.6 x 54 mm).

Same layout and invented data as generate_mock_cards.py (which makes the raster PNGs); this one is the file
to print: a few KB, sharp at any scale. Print at 100% / actual size. Needs `reportlab`.
"""
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

CARD_W, CARD_H = 85.6 * mm, 54.0 * mm
PX = 1 / (300 / 25.4)  # PNG design pixels -> mm


def px(v):
    return v * PX * mm


def rgb(r, g, b):
    return Color(r / 255, g / 255, b / 255)


def id_card(c, x, y):
    """(x, y) = bottom-left of the card. Design coordinates come from the PNG (origin top-left)."""
    def top(v):  # PNG y (from top) -> PDF y
        return y + CARD_H - px(v)

    c.setFillColor(rgb(232, 240, 247)); c.rect(x, y, CARD_W, CARD_H, stroke=0, fill=1)
    c.setFillColor(rgb(30, 70, 120)); c.rect(x, top(70), CARD_W, px(70), stroke=0, fill=1)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 10.5)
    c.drawString(x + px(24), top(52), "SPECIMEN IDENTITY CARD")
    # photo placeholder: generic silhouette, clipped to its frame
    px0, py0, pw, ph = x + px(28), top(440), px(270), px(340)
    c.setFillColor(rgb(200, 205, 212)); c.setStrokeColor(rgb(120, 125, 135)); c.setLineWidth(0.8)
    c.rect(px0, py0, pw, ph, stroke=1, fill=1)
    c.saveState()
    p = c.beginPath(); p.rect(px0, py0, pw, ph); c.clipPath(p, stroke=0, fill=0)
    c.setFillColor(rgb(130, 135, 145))
    r = pw * 0.2
    c.circle(px0 + pw / 2, py0 + ph * 0.8 - r + r * 0.0, r, stroke=0, fill=1)
    c.ellipse(px0 + pw * 0.12, py0 - ph * 0.55, px0 + pw * 0.88, py0 + ph * 0.42, stroke=0, fill=1)
    c.restoreState()
    # data zone: labelled text block
    rows = [("SURNAME", "SPECIMEN"), ("GIVEN NAME", "ALEX"), ("DATE OF BIRTH", "01-01-1990"),
            ("ID NUMBER", "SP-0000000"), ("EXPIRES", "01-01-2099")]
    yy = 100
    for label, value in rows:
        c.setFillColor(rgb(70, 80, 95)); c.setFont("Helvetica", 6)
        c.drawString(x + px(330), top(yy + 20), label)
        c.setFillColor(rgb(10, 10, 10)); c.setFont("Courier-Bold", 12.5)
        c.drawString(x + px(330), top(yy + 66), value)
        yy += 84
    c.setFillColor(rgb(30, 70, 120)); c.rect(x, y, CARD_W, px(40), stroke=0, fill=1)
    c.setFillColor(white); c.setFont("Helvetica", 6)
    c.drawString(x + px(24), y + px(12), "NOT A REAL DOCUMENT · FOR VISION TESTING ONLY")
    c.setStrokeColor(rgb(60, 60, 60)); c.setLineWidth(0.8); c.rect(x, y, CARD_W, CARD_H, stroke=1, fill=0)


def bank_card(c, x, y):
    def top(v):
        return y + CARD_H - px(v)

    c.setFillColor(rgb(45, 52, 70)); c.rect(x, y, CARD_W, CARD_H, stroke=0, fill=1)
    c.setFillColor(rgb(212, 175, 90)); c.roundRect(x + px(36), top(175), px(150), px(115), px(14), stroke=0, fill=1)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 10)
    c.drawRightString(x + CARD_W - px(36), top(75), "SPECIMEN BANK")
    c.setFillColor(rgb(245, 245, 245))
    c.setFont("Courier-Bold", 18.5); c.drawString(x + px(36), top(295), "0000 0000 0000 0000")
    c.setFont("Courier-Bold", 10); c.drawString(x + px(36), top(380), "VALID THRU 01/99")
    c.setFont("Courier-Bold", 11.5); c.drawString(x + px(36), top(440), "ALEX SPECIMEN")
    c.setFillColor(rgb(200, 205, 215)); c.setFont("Helvetica", 6.5)
    c.drawString(x + px(36), y + px(48), "NOT A REAL CARD · FOR VISION TESTING ONLY")
    c.setStrokeColor(rgb(20, 20, 20)); c.setLineWidth(0.8); c.rect(x, y, CARD_W, CARD_H, stroke=1, fill=0)


def main():
    out = Path("cards"); out.mkdir(exist_ok=True)
    c = canvas.Canvas(str(out / "mock-cards-letter.pdf"), pagesize=letter)
    c.setTitle("Mock specimen cards - print at 100%")
    pw, ph = letter
    x = (pw - CARD_W) / 2
    for i, (name, draw) in enumerate((("ID layout", id_card), ("Bank layout", bank_card))):
        y = ph - 300 / 300 * 72 - (i + 1) * CARD_H - i * 1.0 * 72
        draw(c, x, y)
        c.setStrokeColor(rgb(160, 160, 160)); c.setLineWidth(0.3)
        c.rect(x - 3, y - 3, CARD_W + 6, CARD_H + 6, stroke=1, fill=0)  # cut guide
        c.setFillColor(rgb(90, 90, 90)); c.setFont("Helvetica", 7)
        c.drawString(x, y + CARD_H + 8, f"{name}, actual size 85.6 x 54 mm — print at 100%, no fit-to-page")
    c.showPage(); c.save()
    print("wrote", out / "mock-cards-letter.pdf")


if __name__ == "__main__":
    main()
