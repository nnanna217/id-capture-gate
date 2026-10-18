"""Builds the illustrated damaged-card shooting guide and the shoot log (D-15, route b, Step 2).

usage (from the repo root): python -I docs/build_damage_guide.py
writes  docs/damage-shoot-guide.html   (open in a browser; prints cleanly)
        docs/damage-shoot-log.csv      (one row per physical card, prefilled with the plan)
The pictures are ILLUSTRATIONS drawn on the real mock-card faces, not photographs: they show what each defect should look like and
where it sits against the text zone. The text zones drawn are the template's approximate extents (D-03), not labels.
"""
import base64
import csv
import html
import io
from pathlib import Path

from PIL import Image

CARDS = Path("specimens/cards")
W, H = 1011, 638
ZONE = {"id": (330, 100, 640, 520), "bank": (36, 240, 908, 450)}       # x0, y0, x1, y1: approximate text zone, design pixels
NAME = {"id": "ID card", "bank": "Bank card"}
DESK = "#cdb99a"


def data_uri(path):
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def defs():
    out = ['<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>']
    for k in ("id", "bank"):
        out.append(f'<image id="face-{k}" width="{W}" height="{H}" href="{data_uri(CARDS / f"mock-{k}.png")}"/>')
    out.append('<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="9"/></filter>')
    out.append('<filter id="soft3" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3"/></filter>')
    out.append('<filter id="blur6"><feGaussianBlur stdDeviation="7"/></filter>')
    out.append('</defs></svg>')
    return "".join(out)


def frame(inner, extra_defs="", w=H * 0 + 1111, h=738):
    return (f'<svg viewBox="-50 -50 {w} {h}" role="img" xmlns="http://www.w3.org/2000/svg">'
            f'<defs>{extra_defs}</defs><rect x="-50" y="-50" width="{w}" height="{h}" fill="{DESK}"/>'
            f'<g opacity=".10">' + "".join(f'<rect x="-50" y="{y}" width="{w}" height="2" fill="#000"/>' for y in range(-50, 700, 37)) + '</g>'
            f'{inner}</svg>')


def zone_outline(k):
    x0, y0, x1, y1 = ZONE[k]
    return (f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="#7c3aed" stroke-width="5" '
            f'stroke-dasharray="16 10"/><text x="{x0 + 8}" y="{y0 - 12}" font-size="30" font-family="sans-serif" fill="#5b21b6" '
            f'font-weight="700">text zone</text>')


def card(k, clip=None, tf=""):
    c = f' clip-path="url(#{clip})"' if clip else ""
    t = f' transform="{tf}"' if tf else ""
    return f'<g{t}><g{c}><use href="#face-{k}"/></g></g>'


def shadow(path_d, dx=10, dy=14, op=.45):
    return f'<path d="{path_d}" transform="translate({dx} {dy})" fill="#000" opacity="{op}" filter="url(#soft)"/>'


def crease(pts, strength=1.0):
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    return (f'<path d="{d}" fill="none" stroke="#000" stroke-opacity="{.07 * strength:.2f}" stroke-width="26" stroke-linecap="round" filter="url(#soft3)"/>'
            f'<path d="{d}" transform="translate(3 3)" fill="none" stroke="#000" stroke-opacity="{.38 * strength:.2f}" stroke-width="3.5"/>'
            f'<path d="{d}" transform="translate(-2 -2)" fill="none" stroke="#fff" stroke-opacity="{.75 * strength:.2f}" stroke-width="3.5"/>')


RECT = f"M0,0 H{W} V{H} H0 Z"


def s_fold_mild(k, zone):
    clip = f'<clipPath id="fm{k}"><path d="M0,0 H{W} V{H} H130 L0,508 Z"/></clipPath>'
    flap = '<path d="M0,508 L130,638 L130,508 Z" fill="#ecebe5" stroke="#b9b7ae" stroke-width="2"/>'
    flap += '<path d="M0,508 L130,638 L130,508 Z" fill="url(#fg)" />'
    d = '<linearGradient id="fg" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity=".18"/><stop offset="1" stop-color="#fff" stop-opacity=".0"/></linearGradient>'
    inner = shadow(RECT) + card(k, f"fm{k}") + '<path d="M0,508 L130,638" stroke="#000" stroke-opacity=".35" stroke-width="3"/>' + shadow("M0,508 L130,638 L130,508 Z", 6, 8, .35) + flap
    return frame(inner + (zone_outline(k) if zone else ""), clip + d)


def s_fold_severe(k, zone):
    x = 520
    clip_l = f'<clipPath id="fsl{k}"><rect x="0" y="0" width="{x}" height="{H}"/></clipPath>'
    clip_r = f'<clipPath id="fsr{k}"><rect x="{x}" y="0" width="{W - x}" height="{H}"/></clipPath>'
    d = '<linearGradient id="fsg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity=".32"/><stop offset="1" stop-color="#000" stop-opacity=".05"/></linearGradient>'
    right_tf = f"translate({x} 0) matrix(0.80 -0.07 0 1 0 22) translate({-x} 0)"
    inner = (shadow(f"M0,0 H{x} V{H} H0 Z") + shadow(f"M{x},22 H{x + 400} V{H + 10} H{x} Z", 14, 16, .5) + card(k, f"fsl{k}")
             + f'<g transform="{right_tf}"><g clip-path="url(#fsr{k})"><use href="#face-{k}"/></g>'
             + f'<rect x="{x}" y="0" width="{W - x}" height="{H}" fill="url(#fsg)"/></g>'
             + f'<path d="M{x},0 V{H}" stroke="#fff" stroke-opacity=".7" stroke-width="3"/>'
             + f'<path d="M{x + 3},0 V{H}" stroke="#000" stroke-opacity=".35" stroke-width="3"/>')
    return frame(inner + (zone_outline(k) if zone else ""), clip_l + clip_r + d)


def s_crease_mild(k, zone):
    pts = [(0, 548), (250, 545), (520, 550), (780, 546), (W, 549)]
    return frame(shadow(RECT) + card(k) + crease(pts, .9) + (zone_outline(k) if zone else ""))


def s_crease_severe(k, zone):
    a = [(478, 0), (486, 160), (494, 330), (500, 480), (506, H)]
    b = [(0, 318), (260, 326), (520, 312), (780, 322), (W, 308)]
    return frame(shadow(RECT) + card(k) + crease(a, 1.15) + crease(b, 1.0) + (zone_outline(k) if zone else ""))


def s_tear_mild(k, zone):
    notch = "M668,0 L684,26 L694,14 L704,50 L718,22 L736,0 Z"
    clip = f'<clipPath id="tm{k}"><path clip-rule="evenodd" d="{RECT} {notch}"/></clipPath>'
    inner = (shadow(RECT) + card(k, f"tm{k}") + f'<path d="{notch}" fill="none" stroke="#fff" stroke-width="3" stroke-opacity=".9"/>')
    return frame(inner + (zone_outline(k) if zone else ""), clip)


def s_tear_severe(k, zone):
    end = 600 if k == "id" else 780
    corner = f"M{W},{H} L{W},470 L985,500 L968,486 L940,540 L912,552 L890,604 L846,612 L812,{H} Z"
    slit = f"M{W},296 L{end + 40},302 L{end},306 L{end + 36},311 L{W},322 Z"
    clip = f'<clipPath id="ts{k}"><path clip-rule="evenodd" d="{RECT} {corner} {slit}"/></clipPath>'
    inner = (shadow(RECT) + card(k, f"ts{k}") + f'<path d="{corner}" fill="none" stroke="#fff" stroke-width="3" stroke-opacity=".9"/>'
             + f'<path d="{slit}" fill="none" stroke="#fff" stroke-width="3" stroke-opacity=".9"/>')
    return frame(inner + (zone_outline(k) if zone else ""), clip)


def s_curl_mild(k, zone):
    clip = f'<clipPath id="cm{k}"><path d="M0,0 H{W} V{H - 100} Q{W - 40},{H - 30} {W - 100},{H} H0 Z"/></clipPath>'
    d = '<linearGradient id="cg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#cfcdc4"/></linearGradient>'
    flap = f'M{W},{H - 100} Q{W - 40},{H - 30} {W - 100},{H} Q{W - 100},{H - 70} {W - 30},{H - 80} Z'
    inner = (shadow(f"M0,0 H{W} V{H - 100} Q{W - 40},{H - 30} {W - 100},{H} H0 Z") + card(k, f"cm{k}")
             + shadow(flap, 8, 16, .5) + f'<path d="{flap}" fill="url(#cg)" stroke="#b9b7ae" stroke-width="2"/>')
    return frame(inner + (zone_outline(k) if zone else ""), clip + d)


def bowed(k, zone, amt, prof=True):
    top = f"M0,{amt} Q{W / 2},{-amt} {W},{amt}"
    bot = f"L{W},{H - amt} Q{W / 2},{H + amt} 0,{H - amt} Z"
    clip = f'<clipPath id="bw{k}{amt}"><path d="{top} {bot}"/></clipPath>'
    g = (f'<linearGradient id="bg{amt}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity="{.04 * amt / 8:.2f}"/>'
         f'<stop offset=".5" stop-color="#fff" stop-opacity="{.18 * amt / 8:.2f}"/><stop offset="1" stop-color="#000" stop-opacity="{.10 * amt / 8:.2f}"/></linearGradient>')
    inner = (shadow(f"{top} {bot}", 8, 18, .5) + card(k, f"bw{k}{amt}")
             + f'<g clip-path="url(#bw{k}{amt})"><rect width="{W}" height="{H}" fill="url(#bg{amt})"/></g>')
    if prof:
        inner += (f'<g transform="translate(40 660)"><text x="0" y="-8" font-size="26" font-family="sans-serif" fill="#2b2b2b">side view</text>'
                  f'<path d="M0,40 Q150,{40 - amt * 3} 300,40" fill="none" stroke="#222" stroke-width="6"/>'
                  f'<path d="M-20,46 H320" stroke="#6b5b3e" stroke-width="3"/></g>')
    return frame(inner + (zone_outline(k) if zone else ""), clip + g, h=790)


def s_curl_severe(k, zone):
    return bowed(k, zone, 30)


def s_bow_gentle(k, zone):
    return bowed(k, zone, 8)


def s_steep(k, zone):
    tf = "translate(150 60) matrix(0.78 0.0 -0.22 0.62 0 0)"
    inner = shadow("M0,0 H1011 V638 H0 Z", 10, 12, .4).replace("<path", f'<path transform="translate(150 60) matrix(0.78 0 -0.22 0.62 12 14)"') if False else ""
    inner = (f'<g transform="{tf}">' + f'<path d="{RECT}" transform="translate(14 18)" fill="#000" opacity=".4" filter="url(#soft)"/>'
             + '<use href="#face-%s"/>' % k + '</g>')
    return frame(inner)


SCEN = [
    ("fold-mild", "Fold, mild", "fold", "mild", s_fold_mild),
    ("fold-severe", "Fold, severe", "fold", "severe", s_fold_severe),
    ("crease-mild", "Crease, mild", "crease", "mild", s_crease_mild),
    ("crease-severe", "Crease, severe", "crease", "severe", s_crease_severe),
    ("tear-mild", "Tear, mild", "tear", "mild", s_tear_mild),
    ("tear-severe", "Tear, severe", "tear", "severe", s_tear_severe),
    ("curl-mild", "Curl / peel, mild", "curl", "mild", s_curl_mild),
    ("curl-severe", "Curl / bow, severe", "curl", "severe", s_curl_severe),
]

RECIPE = {
    "fold-mild": dict(make="Fold one corner over, about 12 mm each way (the bottom-left corner, as drawn). Press the fold flat with a fingernail, then let go.",
                      show="The folded flap and its fold line are visible. The corner is NOT touching the text zone.",
                      mistake="Folding it so far that the flap covers printed text. That is no longer 'mild'."),
    "fold-severe": dict(make="Fold the card in half down the middle (short edges together), press hard, then open it back to roughly a right angle and lay it down so it stays bent.",
                        show="A hard centre fold line running through the text zone, with the two halves at different angles to the camera (one half looks narrower and darker).",
                        mistake="Shooting while the card is folded flat shut (you see half a card), or fully flattened out again (the fold has relaxed, shoot it bent)."),
    "crease-mild": dict(make="Bend the card gently across its width below the text zone, press one crease line with a fingernail, and flatten it back. One line only.",
                        show="One clear light/dark crease line crossing the card in a blank area, away from the text.",
                        mistake="A crease so faint it cannot be seen in the photo. If you cannot see it on the phone screen, press harder and retake."),
    "crease-severe": dict(make="Make two hard creases that cross each other, one down the middle and one across, so the text zone sits on top of the crossing. Flatten the card back out.",
                          show="Two crossing crease lines through the text zone, each with a visible bright edge and dark edge.",
                          mistake="Creases that stop before the text zone. Both lines must cross it."),
    "tear-mild": dict(make="Nick the edge with scissors or tear a small notch, about 5 mm wide, in the top edge, away from the text zone.",
                      show="A small bite out of the edge with the desk showing through it, text zone untouched.",
                      mistake="Cutting it with a clean straight scissor line. Tear it so the edge is ragged and shows pale paper fibre."),
    "tear-severe": dict(make="Tear the bottom-right corner off (about 25 mm, ragged) AND tear a 40 to 100 mm slit in from the right edge so it runs toward, and for the bank card into, the text zone.",
                        show="A missing corner and a slit, both with ragged edges, the slit reaching the text zone.",
                        mistake="Tearing right through the text, so it cannot be read at all. The aim is damage over legible text, not destroyed text."),
    "curl-mild": dict(make="Lift the bottom-right corner by rolling it over a pen for a few seconds, then lay the card flat. The corner should stay up about 10 mm off the desk.",
                      show="A lifted corner showing the paper's back side and a small shadow, text zone flat and untouched.",
                      mistake="Shooting after the corner has settled flat again. Curl and shoot straight away."),
    "curl-severe": dict(make="Roll the whole card around a pen along its length for 15 seconds, release, and lay it down so it bows up in the middle and rocks on the desk.",
                        show="The whole card visibly bowed: shaded bands across the face, curved edges, a shadow under the lifted middle.",
                        mistake="A card that has relaxed flat. If it lies flat, roll it again. Shoot within a minute, the bow relaxes."),
}

NEG = [
    ("bow", "Gentle bow (NOT damage)", s_bow_gentle, "Flex the card slightly between your fingers and lay it down so it sits a little curved. No crease anywhere.",
     "Label: no damage. This teaches the model that slightly curved is normal."),
    ("steep", "Steep tilt (NOT damage)", s_steep, "A clean flat card photographed at a steep angle (about 45 degrees), so the shape looks squashed.",
     "Label: no damage. A tilted clean card is not a damaged one; this is the exact trap the mask-shape test fell into."),
]


def fig(svg, cap, cls=""):
    return f'<figure class="{cls}">{svg}<figcaption>{cap}</figcaption></figure>'


def pose_svgs():
    def desk(inner):
        return frame(inner)
    cardrect = '<rect x="150" y="150" width="811" height="512" rx="24" fill="#e8f0f7" stroke="#334" stroke-width="5"/>'
    flat = desk(f'<rect x="150" y="150" width="811" height="512" rx="24" fill="#000" opacity=".25" transform="translate(12 16)" filter="url(#soft)"/>{cardrect}'
                '<text x="555" y="430" font-size="64" text-anchor="middle" font-family="sans-serif" fill="#456">card flat, square</text>')
    rot = desk('<g transform="rotate(-24 555 320)"><rect x="150" y="150" width="811" height="512" rx="24" fill="#000" opacity=".25" transform="translate(12 16)" filter="url(#soft)"/>'
               + cardrect + '</g><text x="555" y="660" font-size="54" text-anchor="middle" font-family="sans-serif" fill="#222">turned 20 to 30 degrees, other surface</text>')
    hand = desk(cardrect + ''.join(f'<ellipse cx="{x}" cy="{y}" rx="46" ry="62" fill="#a66a4c" stroke="#6b402b" stroke-width="4"/>'
                                   for x, y in ((130, 270), (130, 420), (980, 270), (980, 420)))
                + '<rect x="360" y="230" width="400" height="300" fill="none" stroke="#7c3aed" stroke-width="5" stroke-dasharray="16 10"/>'
                  '<text x="555" y="395" font-size="46" text-anchor="middle" font-family="sans-serif" fill="#5b21b6">fingers on the EDGES only</text>')
    return flat, rot, hand


def bad_svgs():
    face = '<use href="#face-id"/>'
    base = lambda inner: frame(inner)
    finger = base(shadow(RECT) + face + '<ellipse cx="200" cy="560" rx="120" ry="200" fill="#a66a4c" stroke="#6b402b" stroke-width="5" transform="rotate(-20 200 560)"/>' + crease([(0, 548), (W, 549)], .9))
    glare = base(shadow(RECT) + face + '<ellipse cx="480" cy="300" rx="150" ry="95" fill="#fff" opacity=".9" filter="url(#soft3)"/>' + crease([(0, 548), (W, 549)], .9))
    cut = base(f'<g transform="translate(-260 -40)">{shadow(RECT)}{face}</g>' + '<rect x="-50" y="-50" width="1111" height="738" fill="none"/>')
    blur = base(f'<g filter="url(#blur6)">{shadow(RECT)}{face}{crease([(0, 548), (W, 549)], .9)}</g>')
    return finger, glare, cut, blur


CSS = """
:root{--bg:#fafaf8;--fg:#1c1c1a;--mut:#5f5f5a;--line:#dcdcd6;--acc:#7c3aed;--ok:#1d7a3f;--bad:#b3261e;--card:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--fg:#eee;--mut:#aaa;--line:#333;--card:#1f1f1c;--acc:#a78bfa;--ok:#5ec27f;--bad:#ff8a80}}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px 80px}
main{max-width:1040px;margin:0 auto}h1{font-size:28px;margin:0 0 4px}h2{font-size:22px;margin:44px 0 6px;border-top:2px solid var(--line);padding-top:18px}
h3{font-size:17px;margin:0 0 4px}.mut{color:var(--mut);font-size:14px}.lead{font-size:17px}
.grid{display:grid;gap:16px;grid-template-columns:1fr}
.scen{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:6px 20px}.scen h3{grid-column:1/-1}
@media(max-width:760px){.scen{grid-template-columns:1fr}}
.scen{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;break-inside:avoid}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0}figure{margin:0}figure svg{width:100%;height:auto;display:block;border-radius:6px}
figcaption{font-size:12.5px;color:var(--mut);margin-top:3px}
.tag{display:inline-block;font-size:12px;font-weight:700;border-radius:999px;padding:1px 9px;color:#fff;background:var(--acc)}.tag.sev{background:#c2410c}.tag.neg{background:#475569}
dl{margin:8px 0 0}dt{font-weight:700;font-size:13px;margin-top:6px;text-transform:uppercase;letter-spacing:.03em;color:var(--mut)}dd{margin:1px 0 0}
.ok{color:var(--ok);font-weight:700}.no{color:var(--bad);font-weight:700}
table{border-collapse:collapse;width:100%;font-size:14.5px}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{font-size:13px;color:var(--mut)}
.callout{border-left:5px solid var(--acc);background:var(--card);padding:10px 14px;margin:14px 0;border-radius:0 8px 8px 0}
.callout.warn{border-color:#c2410c}ol.steps li,ul.chk li{margin:4px 0}code{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:13.5px}
.bad{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
@media print{body{background:#fff;color:#000}.scen,.callout{break-inside:avoid}h2{break-after:avoid}}
"""


def plan_rows():
    rows = []
    for layout in ("id", "bank"):
        tag = layout.upper()
        n = 0
        for typ in ("fold", "crease", "tear", "curl"):
            for sev in ("mild", "mild", "severe", "severe"):
                n += 1
                rows.append((f"{tag}-{n:02d}", layout, typ, sev, 4, "1 clean BEFORE + 3 damaged"))
        for kind in ("bow", "bow", "steep", "steep"):
            n += 1
            rows.append((f"{tag}-{n:02d}", layout, "hardneg-" + kind, "none", 3, "3 shots, no damage"))
        for _ in range(4):
            n += 1
            rows.append((f"{tag}-{n:02d}", layout, "spare", "", 0, "only if a card is ruined or a shot is missed"))
    return rows


def build():
    d, s = defs(), []
    s.append("<h1>Damaged-card shoot: illustrated guide</h1>")
    s.append('<p class="lead">Teach the gate what a damaged card looks like. You damage printed specimen cards by hand and photograph each one '
             'and add them to the 152 photos you already have. About <b>152 new photos</b> across the two card layouts. The pictures below are <b>drawings on your real card faces</b>, '
             'not photos: they show what each defect should look like and where it sits against the text zone (purple dashed box).</p>')
    s.append('<div class="callout"><b>Why every damaged card gets one clean photo first:</b> most of your existing 152 photos show the card inside the clear '
             'pouch. If every undamaged example is pouched and every damaged one is bare, the model learns "no pouch = damaged". One <b>bare, undamaged</b> '
             'photo of each card, taken before you damage it, gives the model bare cards that are fine. This is the one photo that must not be skipped.</div>')

    s.append("<h2>1. The numbers</h2><table><tr><th></th><th>Per layout (ID, then bank)</th><th>Both layouts</th></tr>"
             "<tr><td>Cards that get damaged</td><td>16 (4 types x 2 mild + 2 severe)</td><td>32</td></tr>"
             "<tr><td>Photos per damaged card</td><td>1 clean BEFORE + 3 damaged</td><td>128 photos</td></tr>"
             "<tr><td>Hard negatives (not damage)</td><td>4 cards x 3 photos</td><td>24 photos</td></tr>"
             "<tr><td>Spare cards</td><td>4 (only if one is ruined)</td><td>8</td></tr>"
             "<tr><td><b>Total new photos</b></td><td>76 photos</td><td><b>152 photos</b></td></tr></table>"
             '<p class="mut">Time is an estimate: about 2 hours for everything, including damaging the cards. You can do one layout one day and the other the next. '
             "If you run short, do all the SEVERE cards first, they matter most to the next step.</p>")

    s.append("<h2>2. Before you start</h2><ul class='chk'>"
             "<li>Printed cards cut out, <b>copy number written on the back</b> of each (ID-01 ... ID-24, BANK-01 ... BANK-24).</li>"
             "<li>A pen or pencil (for curling), scissors, a flat desk, and two different surfaces (for example a wood table and a dark keyboard or mat).</li>"
             "<li>Phone: Photo mode, <b>Live Photo off</b>, flash off, no filters, portrait mode off. Tap to focus on the card.</li>"
             "<li>Light: daylight or a lamp from the side. <b>Side light makes creases show up</b>, but keep it off the text so there is no glare patch on it.</li>"
             "<li><b>No sleeve or pouch.</b> Keep every card bare for this shoot (sleeves are a separate problem, out of this iteration).</li>"
             "<li>Specimen cards only. No real document, no other card, no business card, no personal mail in the background. Keep your face out of frame.</li></ul>")

    s.append("<h2>3. Golden rules</h2><ol class='steps'>"
             "<li><b>Clean photo FIRST.</b> Photograph the card bare and undamaged, then damage it. Then shoot it at once: curls and bows relax within a minute.</li>"
             "<li><b>One problem per photo.</b> No glare on the text, no finger over the text, no blur, all four corners in frame. Only the damage is wrong.</li>"
             "<li><b>Damage must be visible on the phone screen.</b> If you cannot see it, press harder and retake.</li>"
             "<li><b>Text stays legible</b> in MILD cards and is crossed (but not destroyed) in SEVERE ones.</li>"
             "<li><b>One card, one damage.</b> Never damage a card twice. Use the next numbered card.</li></ol>")

    s.append("<h2>4. Where the text zone is</h2><p>MILD means the damage stays <b>away from</b> the purple box. SEVERE means it <b>crosses</b> it.</p><div class='pair'>")
    for k in ("id", "bank"):
        s.append(fig(frame(card(k) + zone_outline(k)), f"{NAME[k]}: approximate text zone"))
    s.append("</div>")

    s.append("<h2>5. The eight damage scenarios</h2>"
             '<p class="mut">Left picture: the ID card. Right picture: the bank card. Same defect, same recipe. Purple dashed box = text zone.</p><div class="grid">')
    for key, title, typ, sev, fn in SCEN:
        r = RECIPE[key]
        s.append(f'<div class="scen"><h3>{title} <span class="tag {"sev" if sev == "severe" else ""}">{sev}</span></h3><div class="pair">'
                 + fig(fn("id", True), "ID card") + fig(fn("bank", True), "Bank card") + "</div><dl>"
                 f"<dt>How to make it</dt><dd>{html.escape(r['make'])}</dd>"
                 f"<dt>The photo must show</dt><dd><span class='ok'>Yes:</span> {html.escape(r['show'])}</dd>"
                 f"<dt>Common mistake</dt><dd><span class='no'>No:</span> {html.escape(r['mistake'])}</dd></dl></div>")
    s.append("</div>")

    s.append("<h2>6. Hard negatives: cards that look odd but are NOT damaged</h2>"
             "<p>These stop the model from flagging every curved or tilted card. Shoot 3 photos of each card, no clean-before needed. (Bow: two cards. Steep tilt: two cards.)</p><div class='grid'>")
    for key, title, fn, make, note in NEG:
        s.append(f'<div class="scen"><h3>{title} <span class="tag neg">no damage</span></h3><div class="pair">'
                 + fig(fn("id", False), "ID card") + fig(fn("bank", False), "Bank card") + f"</div><dl><dt>How to make it</dt><dd>{html.escape(make)}</dd>"
                 f"<dt>Why</dt><dd>{html.escape(note)}</dd></dl></div>")
    s.append("</div>")

    flat, rot, hand = pose_svgs()
    s.append("<h2>7. The shot sequence for every damaged card (4 photos)</h2><ol class='steps'>"
             "<li><b>Photo 1, CLEAN BEFORE.</b> Bare card, undamaged, flat and square on the desk (A). Before you touch it.</li>"
             "<li>Damage the card with the recipe above.</li>"
             "<li><b>Photo 2:</b> flat and square again (A).</li>"
             "<li><b>Photo 3:</b> turn it 20 to 30 degrees and move it to the other surface (B).</li>"
             "<li><b>Photo 4:</b> hold it in your hand in different light (C), fingers on the edges only, never over the damage or the text zone.</li></ol>"
             "<div class='pair' style='grid-template-columns:repeat(3,1fr)'>" + fig(flat, "A. flat, square (photos 1 and 2)") + fig(rot, "B. turned, other surface (photo 3)")
             + fig(hand, "C. in hand (photo 4)") + "</div>"
             '<p class="mut">Landscape for most photos, a few in portrait. The card should fill about a third to two thirds of the frame width, all four corners visible.</p>')

    fi, gl, cu, bl = bad_svgs()
    s.append("<h2>8. Retake these</h2><p>Each of these ruins a photo. Retake it.</p><div class='bad'>"
             + fig(fi, "Finger over the card face hides the damage") + fig(gl, "Glare patch on the text (a different problem, not this shoot)")
             + fig(cu, "Card cut off by the frame edge") + fig(bl, "Blurred: the crease cannot be seen") + "</div>")

    s.append("<h2>9. Which card is which</h2><p>The plan is prefilled in <code>docs/damage-shoot-log.csv</code>, one row per physical card.</p>"
             "<table><tr><th>ID cards</th><th>Bank cards</th><th>Plan</th></tr>"
             "<tr><td>ID-01 to ID-04</td><td>BANK-01 to BANK-04</td><td>Fold: 01 02 mild, 03 04 severe</td></tr>"
             "<tr><td>ID-05 to ID-08</td><td>BANK-05 to BANK-08</td><td>Crease: mild, mild, severe, severe</td></tr>"
             "<tr><td>ID-09 to ID-12</td><td>BANK-09 to BANK-12</td><td>Tear: mild, mild, severe, severe</td></tr>"
             "<tr><td>ID-13 to ID-16</td><td>BANK-13 to BANK-16</td><td>Curl: mild, mild, severe, severe</td></tr>"
             "<tr><td>ID-17, ID-18</td><td>BANK-17, BANK-18</td><td>Hard negative: gentle bow</td></tr>"
             "<tr><td>ID-19, ID-20</td><td>BANK-19, BANK-20</td><td>Hard negative: steep tilt (clean card at about 45 degrees)</td></tr>"
             "<tr><td>ID-21 to ID-24</td><td>BANK-21 to BANK-24</td><td>Spares</td></tr></table>")

    s.append("<h2>10. Getting the photos in</h2><p><b>One folder per physical card</b>, named with the copy number and the plan, with the photos in the order you took them (photo 1 is always the clean BEFORE). "
             "AirDrop each card's photos to a folder like:</p>"
             "<p><code>~/Downloads/damage/ID-03-fold-severe/</code> &nbsp; <code>~/Downloads/damage/BANK-17-hardneg-bow/</code></p>"
             "<p>Do not rename the photos. Tick the card off in the log as you go. Raw photos stay out of git (<code>local/</code> is ignored). "
             "The next step teaches the ingest script about these folders; until then just keep them as they are.</p>"
             '<div class="callout warn"><b>One honest limit:</b> printed paper does not fold or tear like real plastic ID. This set teaches the idea of damage on '
             "paper specimens; it is a seed, not proof the gate catches worn real documents. Real-world damage frames come later, from the bypass queue.</div>")
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Damaged-card shoot guide</title><style>{CSS}</style></head><body>{d}<main>{''.join(s)}</main></body></html>")
    Path("docs/damage-shoot-guide.html").write_text(page)

    rows = plan_rows()
    with open("docs/damage-shoot-log.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["copy", "layout", "plan", "severity", "photos_expected", "what", "clean_before_done", "damaged_done", "folder_name", "notes"])
        for copy, layout, typ, sev, n, what in rows:
            folder = f"{copy}-{typ}" + (f"-{sev}" if sev not in ("", "none") else "") if typ != "spare" else ""
            w.writerow([copy, layout, typ, sev, n, what, "", "", folder, ""])
    print("wrote docs/damage-shoot-guide.html and docs/damage-shoot-log.csv", len(rows), "rows")


if __name__ == "__main__":
    build()
