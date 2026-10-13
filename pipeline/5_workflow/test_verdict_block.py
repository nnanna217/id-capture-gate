"""Unit tests for the verdict block, on synthetic images and detections. Run from the repo root:
    python -I pipeline/5_workflow/test_verdict_block.py
The block's source text is executed exactly as the Workflow will execute it (build_workflow.py embeds the same file).
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import supervision as sv

SRC = Path(os.environ.get("VERDICT_SRC", "pipeline/5_workflow/verdict_block.py")).read_text()
NS = {}
exec(compile(SRC, "verdict_block.py", "exec"), NS)
run = NS["run"]
HAVE_INTERNALS = "GUIDANCE" in NS      # false for the editor-safe variant, whose helpers are nested inside run

H, W = 480, 640
DOC = (80, 400, 100, 540)      # rows r0..r1, cols c0..c1
ZONE = (150, 330, 200, 480)
rng = np.random.default_rng(0)


def rect(r0, r1, c0, c1):
    m = np.zeros((H, W), bool)
    m[r0:r1, c0:c1] = True
    return m


def scene(brightness=1.0, blur=False):
    img = np.full((H, W, 3), 120, np.uint8)
    img[DOC[0]:DOC[1], DOC[2]:DOC[3]] = 205
    z = rng.integers(110, 245, (ZONE[1] - ZONE[0], ZONE[3] - ZONE[2]), dtype=np.uint8)
    if blur:
        z = cv2.GaussianBlur(z, (0, 0), 4)
    img[ZONE[0]:ZONE[1], ZONE[2]:ZONE[3]] = z[:, :, None]
    return np.clip(img.astype(float) * brightness, 0, 255).astype(np.uint8)


def dets(items):
    """items: list of (class_name, mask, confidence)."""
    if not items:
        return sv.Detections.empty()
    masks = np.stack([m for _, m, _ in items])
    xyxy = np.array([[0, 0, 1, 1]] * len(items), float)
    return sv.Detections(xyxy=xyxy, mask=masks, confidence=np.array([c for _, _, c in items], float),
                         class_id=np.arange(len(items)), data={"class_name": np.array([n for n, _, _ in items])})


def call(img, items, **kw):
    return run(None, SimpleNamespace(numpy_image=img), dets(items), **kw)


EXPECTED = {
    "too_dark": "Move to better light.",
    "no_document": "Hold the card in front of the camera.",
    "incomplete_document": "Move back so all four corners are in view.",
    "obstructed": "Move your finger or anything else off the text.",
    "glare_over_data_zone": "Tilt the card to move the glare off the text.",
    "blurred": "Hold steady.",
}
USABLE_TEXT = "Looks good. Capture it."
DOC_M, ZONE_M = rect(*DOC), rect(*ZONE)
card = [("document", DOC_M, 0.95), ("data_zone", ZONE_M, 0.93)]
results = []


def check(name, cond, got):
    results.append(cond)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   got {got}"))


r = call(scene(), card)
check("clean capture is usable, with the 'usable' guidance", r["verdict"] == "usable" and r["reasons"] == [] and r["guidance"] == USABLE_TEXT, r)
check("output contract: exactly verdict, reasons, guidance, details; no score", set(r) == {"verdict", "reasons", "guidance", "details"}
      and isinstance(r["guidance"], str) and r["verdict"] in ("usable", "not_usable"), sorted(r))

r = call(scene(), [])
check("no detections, bright frame -> no_document", r["reasons"] == ["no_document"] and r["guidance"] == EXPECTED["no_document"], r)
r = call(scene(0.25), [])
check("no detections, dark frame -> too_dark first, then no_document (frame brightness fallback)", r["reasons"] == ["too_dark", "no_document"]
      and r["guidance"] == EXPECTED["too_dark"] and r["details"]["brightness_region"] == "frame", r)
r = call(scene(0.25), card)
check("dark card -> too_dark only (blur is not judged in the dark)", r["reasons"] == ["too_dark"] and r["details"]["brightness_region"] == "card", r)

r = call(scene(), [("document", rect(0, 300, 100, 540), 0.9), ("data_zone", ZONE_M, 0.9)])
check("card touching the frame edge -> incomplete_document", r["reasons"] == ["incomplete_document"], r)

obs_cover = rect(150, 250, 200, 480)          # covers 100/180 = 56% of the zone
check("finger over the text -> obstructed", call(scene(), card + [("obstruction", obs_cover, 0.8)])["reasons"] == ["obstructed"], None)
gla_cover = rect(150, 330, 200, 300)          # 100/280 = 36% of the zone
r = call(scene(), card + [("glare", gla_cover, 0.8)])
check("glare over the text -> glare_over_data_zone", r["reasons"] == ["glare_over_data_zone"] and r["guidance"] == EXPECTED["glare_over_data_zone"], r)
r = call(scene(), card + [("obstruction", obs_cover, 0.8), ("glare", gla_cover, 0.8)])
check("obstruction and glare together: both listed, obstruction guidance first", r["reasons"] == ["obstructed", "glare_over_data_zone"]
      and r["guidance"] == EXPECTED["obstructed"], r)

off = rect(300, 330, 480, 540)                # glare beside the zone, on the card
check("glare on the card but off the text -> usable", call(scene(), card + [("glare", off, 0.8)])["verdict"] == "usable", None)
sliver = rect(150, 152, 200, 480)             # 2 of 180 rows = about 1.1% of the zone
check("a sliver under 2% of the zone is not counted", call(scene(), card + [("obstruction", sliver, 0.8)])["verdict"] == "usable", None)
check("a low-confidence obstruction is ignored", call(scene(), card + [("obstruction", obs_cover, 0.2)])["verdict"] == "usable", None)
check("the confidence cut-off is a parameter", call(scene(), card + [("obstruction", obs_cover, 0.2)], min_confidence=0.1)["reasons"] == ["obstructed"], None)

r = call(scene(blur=True), card)
check("blurred zone alone -> blurred", r["reasons"] == ["blurred"] and r["guidance"] == EXPECTED["blurred"], r)
r = call(scene(blur=True), card + [("glare", gla_cover, 0.8)])
check("blur is not judged when glare covers the zone", r["reasons"] == ["glare_over_data_zone"] and "zone_sharpness" not in r["details"], r)

r = call(scene(0.25), [("document", rect(0, 300, 100, 540), 0.9), ("data_zone", ZONE_M, 0.9), ("obstruction", obs_cover, 0.8)])
check("dark + cut off + covered -> precedence too_dark, incomplete_document, obstructed", r["reasons"] == ["too_dark", "incomplete_document", "obstructed"]
      and r["guidance"] == EXPECTED["too_dark"], r)

r = call(scene(), [("document", DOC_M, 0.9), ("obstruction", rect(150, 250, 200, 480), 0.8)])
check("no text zone found: falls back to the whole card, and says so", r["details"]["zone_fallback_to_card"] is True, r)
r = call(scene(), [("document", DOC_M, 0.9), ("obstruction", rect(80, 400, 100, 400), 0.8)])
check("fallback still catches a large obstruction", r["reasons"] == ["obstructed"], r)
r = call(scene(), [("document", DOC_M, 0.9)])
check("card found, nothing else wrong, no text zone -> blurred (the text cannot be read), and says why",
      r["reasons"] == ["blurred"] and r["details"].get("blurred_because_no_text_zone") is True and r["guidance"] == EXPECTED["blurred"], r)

r = call(scene(), card + [("document", rect(10, 20, 10, 20), 0.5)])
check("the highest-confidence document is the one used", r["verdict"] == "usable", r)
check("thresholds are reported in the details", r["details"]["thresholds"]["dark_p95"] == 110.0, r)

# --- brightness must be judged on the card, not the frame (a mutation test showed this was untested)
def small_card_scene(bg, card_val):
    img = np.full((H, W, 3), bg, np.uint8)
    img[200:240, 300:360] = card_val                 # 40 x 60 card = 0.8% of the frame
    img[210:230, 310:350] = np.where(rng.random((20, 40)) > 0.5, card_val, card_val * 0.6)[:, :, None].astype(np.uint8)
    return img
sm_doc, sm_zone = rect(200, 240, 300, 360), rect(210, 230, 310, 350)
sm = [("document", sm_doc, 0.9), ("data_zone", sm_zone, 0.9)]
r = call(small_card_scene(30, 210), sm)
check("bright card on a dark background is NOT too_dark (judged on the card)", "too_dark" not in r["reasons"] and r["details"]["brightness_region"] == "card", r)
r = call(small_card_scene(200, 60), sm)
check("dim card on a bright background IS too_dark", r["reasons"][:1] == ["too_dark"], r)

# --- the guidance strings are product decisions (D-13): pin them as literals, not as the block's own constants
if HAVE_INTERNALS:
  check("guidance strings and precedence order match the decision, as literals", NS["GUIDANCE"] == EXPECTED
      and NS["ORDER"] == ["too_dark", "no_document", "incomplete_document", "obstructed", "glare_over_data_zone", "blurred"]
      and NS["USABLE_GUIDANCE"] == "Looks good. Capture it.", (NS["GUIDANCE"], NS["ORDER"]))

# --- a card that is (almost) entirely covered: the card mask is not trustworthy for light or edge checks
full_cover = rect(80, 400, 100, 540)
edge_doc = rect(0, 300, 100, 540)
r = call(scene(), [("document", edge_doc, 0.9), ("data_zone", ZONE_M, 0.9), ("obstruction", edge_doc, 0.9)])
check("card mask fully covered: obstructed only, no edge or light claim from the covered card", r["reasons"] == ["obstructed"]
      and r["details"]["card_mostly_covered"] is True, r)
r = call(scene(0.25), [("document", DOC_M, 0.9), ("data_zone", ZONE_M, 0.9), ("obstruction", full_cover, 0.9)])
check("covered card in a dark scene: still too_dark, judged on the whole frame", r["reasons"][:1] == ["too_dark"] and r["details"]["brightness_region"] == "frame", r)

if HAVE_INTERNALS:   # needs to replace the block's sharpness helper, which is nested (not reachable) in the editor-safe variant
    # --- the blur cut-off depends on the text-zone layout. The sharpness VALUE is stubbed so the test isolates the selection
    # logic (the measure itself depends on how the zone is resampled, so the same blur gives different values in different shapes).
    def with_stub(sharp, aspect, items):
        real = NS["_zone_sharpness"]
        NS["_zone_sharpness"] = lambda gray, zone, long_side=320: (sharp, aspect)
        try:
            return call(scene(), items)
        finally:
            NS["_zone_sharpness"] = real
    rb = with_stub(0.50, 1.3, card)      # block-shaped zone (ID-like): 0.50 is above its 0.43 cut-off
    rw = with_stub(0.50, 4.2, card)      # wide strip (bank-like): 0.50 is below its 0.70 cut-off
    check("sharpness 0.50: usable in a block-shaped zone (cut-off 0.43), blurred in a wide strip (cut-off 0.70)",
          rb["verdict"] == "usable" and rb["details"]["blur_threshold_used"] == 0.43
          and rw["reasons"] == ["blurred"] and rw["details"]["blur_threshold_used"] == 0.70, (rb["details"], rw["details"]))
    check("a very soft block-shaped zone is still blurred", with_stub(0.08, 1.3, card)["reasons"] == ["blurred"], None)
    check("a sharp wide strip is usable", with_stub(1.2, 4.2, card)["verdict"] == "usable", None)

# --- the default thresholds are decisions with evidence behind them (BUILD-LOG 2026-10-11): pin them
th = call(scene(), card)["details"]["thresholds"]
check("default thresholds are pinned", th == {"min_confidence": 0.4, "dark_p95": 110.0, "blur_min_block": 0.43, "blur_min_wide": 0.70,
      "wide_aspect": 2.5, "overlap_min": 0.02, "edge_margin_px": 2, "covered_card": 0.9}, th)

print(f"\n{sum(results)} of {len(results)} passed" + ("" if HAVE_INTERNALS else "  (3 tests that need the block's internals were skipped for this variant)"))
sys.exit(0 if all(results) else 1)
