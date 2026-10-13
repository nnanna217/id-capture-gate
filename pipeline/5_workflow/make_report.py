"""Build an interactive, self-contained HTML report of the verdict block's tests: local/report/verdict-report.html

Tabs: try the logic yourself, the 30 unit tests as pictures, the deliberate breaks, all 152 real frames with the model's outlines,
and published-vs-local. Everything shown comes from real runs made when this script runs: it executes the unit tests and the
mutation check itself and reads local/report/published-run.json (written by compare_published_workflow.py).
The report contains the project's raw frames (resized, embedded), so it lives under local/ and is never committed.

usage (from the repo root): python -I pipeline/5_workflow/make_report.py
"""
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import cv2

TEST = "pipeline/5_workflow/test_verdict_block.py"
SRC = Path("pipeline/5_workflow/verdict_block.py").read_text()
OUT = Path("local/report/verdict-report.html")

# ---------------------------------------------------------------- 1. unit tests, run for real
def run_tests(src_path=None):
    env = dict(os.environ)
    if src_path:
        env["VERDICT_SRC"] = str(src_path)
    p = subprocess.run([sys.executable, "-I", TEST], capture_output=True, text=True, env=env)
    res = []
    for line in p.stdout.splitlines():
        m = re.match(r"(PASS|FAIL) (.*?)(   got .*)?$", line)
        if m:
            res.append({"name": m.group(2).strip(), "pass": m.group(1) == "PASS"})
    return res

tests = run_tests()
assert len(tests) == 30, f"expected 30 tests, got {len(tests)}"

# plain-English description, expected answer and a scene for each test, in the order the tests run
META = [
 ("A good photo", "usable. 'Looks good. Capture it.'", {}),
 ("The answer has four parts and no score", "verdict, reasons, guidance, details", {}),
 ("No card in view, light is fine", "no_document", {"noCard": 1}),
 ("No card in view, and the room is dark", "too_dark first, then no_document", {"noCard": 1, "dark": 1}),
 ("A card in view, but it is dark", "too_dark only (blur is not judged in the dark)", {"dark": 1}),
 ("Card pushed against the edge of the picture", "incomplete_document", {"cut": 1}),
 ("A finger over the text", "obstructed", {"finger": "on"}),
 ("Glare over the text", "glare_over_data_zone", {"glare": "on"}),
 ("A finger AND glare over the text", "obstructed first, glare listed second", {"finger": "on", "glare": "on"}),
 ("Glare on the card, but beside the text", "usable (it does not touch the text)", {"glare": "off"}),
 ("A sliver of finger, under 2% of the text zone", "usable (too small to count)", {"finger": "sliver"}),
 ("A finger the model is unsure about (score 0.2)", "usable (unsure detections are ignored)", {"finger": "on", "dim": 1}),
 ("Same finger, but we lower the cut-off to 0.1", "obstructed (the cut-off is a setting)", {"finger": "on"}),
 ("Blurry text, nothing else wrong", "blurred", {"blur": 1}),
 ("Blurry text AND glare over it", "glare only: blur is not judged when glare covers the text", {"blur": 1, "glare": "on"}),
 ("Dark, cut off and covered, all at once", "too_dark, incomplete_document, obstructed, in that order", {"dark": 1, "cut": 1, "finger": "on"}),
 ("The model finds the card but not the text zone", "falls back to the whole card, and says so", {"noZone": 1}),
 ("...and a large finger over that card", "obstructed (still caught)", {"noZone": 1, "finger": "big"}),
 ("Card found, no text zone, nothing else wrong", "blurred (the text cannot be read)", {"noZone": 1, "blur": 1}),
 ("Two card detections", "the more confident one is used: usable", {}),
 ("The answer reports the cut-offs it used", "thresholds are listed in the details", {}),
 ("A bright card on a dark table", "NOT too_dark: brightness is judged on the card", {"brightOnDark": 1}),
 ("A dim card on a bright table", "too_dark", {"dimOnBright": 1}),
 ("The six guidance sentences and their order are fixed", "pinned word for word", {"text": 1}),
 ("A finger covers the whole card", "obstructed only: no edge or light claim from a covered card", {"covered": 1, "cut": 1}),
 ("A covered card in a dark room", "too_dark (judged on the whole picture)", {"covered": 1, "dark": 1}),
 ("Medium-soft text in two layouts", "usable on the ID-shaped zone, blurred on the wide strip", {"wide": 1, "blur": 1}),
 ("Very soft text, ID-shaped zone", "blurred", {"blur": 1}),
 ("Sharp text, wide strip", "usable", {"wide": 1}),
 ("The default cut-offs are fixed", "pinned: dark 110, blur 0.43 / 0.70, overlap 2%, and so on", {"text": 1}),
]
for t, m in zip(tests, META):
    t["plain"], t["expect"], t["scene"] = m

# ---------------------------------------------------------------- 2. deliberate breaks, run for real
src = SRC
MUTANTS = [
 ("Put 'blurred' at the top of the order", 'ORDER = ["too_dark", "no_document", "incomplete_document", "obstructed", "glare_over_data_zone", "blurred"]',
  'ORDER = ["blurred", "too_dark", "no_document", "incomplete_document", "obstructed", "glare_over_data_zone"]'),
 ("Swap glare and finger in the order", '"obstructed", "glare_over_data_zone", "blurred"]', '"glare_over_data_zone", "obstructed", "blurred"]'),
 ("Measure blur even when glare covers the text", "if not reasons and zone is not None:", "if zone is not None:"),
 ("Judge brightness on the whole picture, not the card", "use_card = doc is not None and doc.any() and not covered", "use_card = False"),
 ("Count any overlap, however tiny", "if o_cov >= overlap_min:", "if o_cov > 0:"),
 ("Stop ignoring detections the model is unsure about", "if names[i] == name and conf[i] >= min_conf]", "if names[i] == name]"),
 ("Never check if the card touches the picture edge", "if touches:", "if False:"),
 ("Change the 'usable' message", 'USABLE_GUIDANCE = "Looks good. Capture it."', 'USABLE_GUIDANCE = "ok"'),
 ("Remove the rule for a fully covered card", "covered = bool(doc is not None and doc.any() and (obs & doc).sum() / float(doc.sum()) >= covered_card)", "covered = False"),
 ("Use one blur cut-off for both card layouts", "limit = blur_min_wide if (aspect is not None and aspect >= wide_aspect) else blur_min_block", "limit = blur_min_block"),
 ("Lower the darkness cut-off from 110 to 90", "dark_p95=110.0", "dark_p95=90.0"),
 ("Pass a card whose text zone cannot be found", "elif not reasons and zone is None:", "elif False:"),
]
tmp = Path("local/report/mutants"); tmp.mkdir(parents=True, exist_ok=True)
mutants = []
for i, (what, a, b) in enumerate(MUTANTS):
    assert a in src, "mutation target not found: " + what
    p = tmp / f"m{i}.py"; p.write_text(src.replace(a, b))
    r = run_tests(p)
    failed = [x["name"] for x in r if not x["pass"]]
    mutants.append({"what": what, "failed": failed, "caught": bool(failed)})
    print(f"  break {i + 1}/{len(MUTANTS)}: {what} -> {len(failed)} test(s) noticed")

# ---------------------------------------------------------------- 3. real frames
pub = json.load(open("local/report/published-run.json"))
frames = []
for rec in pub["frames"]:
    folder = "local/upload/new/" if os.path.exists("local/upload/new/" + rec["file"]) else "local/upload/own/"
    im = cv2.imread(folder + rec["file"])
    h, w = im.shape[:2]
    s = 380 / max(h, w)
    im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 72])
    rec = dict(rec)
    rec["img"] = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
    rec["w"], rec["h"] = im.shape[1], im.shape[0]
    frames.append(rec)

data = {"tests": tests, "mutants": mutants, "frames": frames, "slug": pub["slug"],
        "same": sum(1 for f in frames if f["same_as_reference"]), "n": len(frames)}
HTML = Path("pipeline/5_workflow/report_template.html").read_text()
OUT.write_text(HTML.replace("__DATA__", json.dumps(data).replace("</", "<\\/")))
print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB): {sum(t['pass'] for t in tests)}/{len(tests)} tests pass, "
      f"{sum(m['caught'] for m in mutants)}/{len(mutants)} breaks caught, {data['same']}/{data['n']} frames identical")
