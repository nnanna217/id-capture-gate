"""Print-ready mock specimen cards: one US-Letter page, two layouts at true size (85.6 x 54 mm, 300 dpi).

Everything on the cards is invented. No real name, number, face, or brand logo. The text block on each
card is the intended `data_zone`; SPECIMEN sits in a strip outside it.
Print at 100% / "actual size" (no fit-to-page), then laminate or sleeve in gloss — glare is a labelled class.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DPI = 300
MM = DPI / 25.4
CARD_W, CARD_H = round(85.6 * MM), round(54.0 * MM)
PAGE_W, PAGE_H = round(8.5 * DPI), round(11 * DPI)

BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
MONO = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
SANS = "/System/Library/Fonts/Helvetica.ttc"


def font(path, size):
    return ImageFont.truetype(path, size)


def silhouette(d, box):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=(200, 205, 212), outline=(120, 125, 135), width=3)
    cx, w, h = (x0 + x1) // 2, x1 - x0, y1 - y0
    r = int(w * 0.2)
    d.ellipse((cx - r, y0 + int(h * 0.2), cx + r, y0 + int(h * 0.2) + 2 * r), fill=(130, 135, 145))
    d.ellipse((cx - int(w * 0.38), y0 + int(h * 0.58), cx + int(w * 0.38), y1 + int(h * 0.55)), fill=(130, 135, 145))
    d.rectangle((x0, y1, x1, y1 + 200), fill="white")  # hide the part of the shoulders below the frame


def id_card():
    im = Image.new("RGB", (CARD_W, CARD_H), (232, 240, 247))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, CARD_W, 70), fill=(30, 70, 120))
    d.text((24, 16), "SPECIMEN IDENTITY CARD", font=font(BOLD, 36), fill="white")
    silhouette(d, (28, 100, 28 + 270, 100 + 340))
    d.rectangle((28, 440, 298, 600), fill=(232, 240, 247))
    # data zone: text block, right of the photo
    zx0, zy0, zx1, zy1 = 330, 100, CARD_W - 28, 520
    rows = [("SURNAME", "SPECIMEN"), ("GIVEN NAME", "ALEX"), ("DATE OF BIRTH", "01-01-1990"),
            ("ID NUMBER", "SP-0000000"), ("EXPIRES", "01-01-2099")]
    y = zy0
    for label, value in rows:
        d.text((zx0, y), label, font=font(SANS, 24), fill=(70, 80, 95))
        d.text((zx0, y + 26), value, font=font(MONO, 46), fill=(10, 10, 10))
        y += 84
    d.rectangle((0, CARD_H - 40, CARD_W, CARD_H), fill=(30, 70, 120))
    d.text((24, CARD_H - 34), "NOT A REAL DOCUMENT · FOR VISION TESTING ONLY", font=font(SANS, 24), fill="white")
    d.rectangle((0, 0, CARD_W - 1, CARD_H - 1), outline=(60, 60, 60), width=3)
    return im, (zx0, zy0, zx1, zy1)


def bank_card():
    im = Image.new("RGB", (CARD_W, CARD_H), (45, 52, 70))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((36, 60, 36 + 150, 60 + 115), radius=14, fill=(212, 175, 90))  # chip
    d.text((CARD_W - 36 - 380, 40), "SPECIMEN BANK", font=font(BOLD, 40), fill="white")
    zx0, zy0, zx1, zy1 = 36, 235, CARD_W - 36, 470
    d.text((zx0, zy0), "0000 0000 0000 0000", font=font(MONO, 74), fill=(245, 245, 245))
    d.text((zx0, zy0 + 110), "VALID THRU 01/99", font=font(MONO, 40), fill=(245, 245, 245))
    d.text((zx0, zy0 + 170), "ALEX SPECIMEN", font=font(MONO, 46), fill=(245, 245, 245))
    d.text((36, CARD_H - 70), "NOT A REAL CARD · FOR VISION TESTING ONLY", font=font(SANS, 26), fill=(200, 205, 215))
    d.rectangle((0, 0, CARD_W - 1, CARD_H - 1), outline=(20, 20, 20), width=3)
    return im, (zx0, zy0, zx1, zy1)


def main():
    out = Path("cards")
    out.mkdir(exist_ok=True)
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(page)
    cards = {"id": id_card(), "bank": bank_card()}
    x = (PAGE_W - CARD_W) // 2
    for i, (name, (im, zone)) in enumerate(cards.items()):
        y = 300 + i * (CARD_H + 300)
        page.paste(im, (x, y))
        # cut guide, outside the card edge
        d.rectangle((x - 12, y - 12, x + CARD_W + 12, y + CARD_H + 12), outline=(160, 160, 160), width=1)
        d.text((x, y - 60), f"{name} layout, actual size 85.6 x 54 mm — print at 100%", font=font(SANS, 28), fill=(90, 90, 90))
        im.save(out / f"mock-{name}.png", dpi=(DPI, DPI))
        print(f"{name}: card {im.size}px, intended data_zone {zone}")
    page.save(out / "mock-cards-letter.pdf", resolution=DPI)
    page.resize((PAGE_W // 3, PAGE_H // 3)).save(out / "mock-cards-preview.png")
    print("wrote", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
