"""Tests for the app-layer rules in live_gate.py: the nobody-gets-stuck escape hatch (D-16), the review step (D-15) and the bypass
rate in the report. No camera, no model, no network. Run from the repo root:
    python -I pipeline/6_demo/test_live_gate.py
These rules are deliberately NOT in the Workflow block (the published block is verified 152 of 152 against the platform); the block's
own tests are pipeline/5_workflow/test_verdict_block.py and are unaffected.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("live_gate", "pipeline/6_demo/live_gate.py")
lg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lg)

FRAME = np.zeros((90, 120, 3), np.uint8)
PASSED, FAILED = 0, []


def check(name, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name} {detail}")


def blocked(esc, t0, t1, step=0.1, card=True, usable=False):
    """Feed the escape rule one judgement every `step` seconds from t0 to t1."""
    t = t0
    while t <= t1 + 1e-9:
        esc.update(t, usable, card)
        t = round(t + step, 6)


def fake_save(log):
    return lambda path, frame: log.append(str(path))


# ---------------------------------------------------------------- Escape: the two triggers
e = lg.Escape()
blocked(e, 0.0, 8.9)
check("2 rejections is not enough", e.trigger is None and e.streak == 2, (e.trigger, e.streak))
blocked(e, 9.0, 9.2)
check("3 consecutive rejections offer the hatch", e.trigger == "rejections" and e.streak == 3, (e.trigger, e.streak))

e = lg.Escape()
blocked(e, 0.0, 119.9, usable=True, card=False)             # camera idle, nothing in view, no rejections
check("not offered at 119.9 s", e.trigger is None)
e.update(120.0, False, False)
check("offered at 120 s with no capture, even with no card in view", e.trigger == "timeout")

e = lg.Escape()
blocked(e, 0.0, 9.1)
e.update(120.0, False, True)
check("whichever comes first: the trigger recorded stays the first", e.trigger == "rejections")

e = lg.Escape()
blocked(e, 0.0, 100.0, card=False)                          # no_document for a long time: not a rejection
check("no card in view never counts as a rejection", e.streak == 0 and e.total_rejections == 0 and e.trigger is None)

e = lg.Escape()
for k in range(10):                                         # blocked for 2 s, then usable for 1 s, over and over
    blocked(e, k * 3.0, k * 3.0 + 1.9)
    e.update(k * 3.0 + 2.0, True, True)
check("a block shorter than the hold is not a rejection", e.streak == 0 and e.trigger is None, e.streak)

e = lg.Escape()
blocked(e, 0.0, 6.1)
e.update(6.2, True, True)
blocked(e, 6.3, 9.5)
check("a usable moment does not erase the streak (only a capture does)", e.streak == 3 and e.trigger == "rejections", (e.streak, e.trigger))

e = lg.Escape()
blocked(e, 0.0, 6.1)
e.reset(6.2)
check("a capture resets the streak", e.streak == 0 and e.trigger is None)
blocked(e, 6.2, 6.2 + 8.9)
check("and the count starts again from zero", e.trigger is None and e.streak == 2)

e = lg.Escape()
e.reset(50.0)
e.update(169.9, False, False)
check("a capture restarts the 120 s clock", e.trigger is None)
e.update(170.0, False, False)
check("...and it fires 120 s after the capture", e.trigger == "timeout")

e = lg.Escape(rejections=1, seconds=10, hold_s=1.0)
blocked(e, 0.0, 1.1)
check("thresholds are parameters (demo flags)", e.trigger == "rejections")
e = lg.Escape(rejections=99, seconds=10, hold_s=1.0)
e.update(10.0, False, False)
check("timeout is a parameter", e.trigger == "timeout")

e = lg.Escape()
blocked(e, 0.0, 120.0, step=0.5)
check("a long single block keeps counting: 3 rejections well before 120 s", e.trigger == "rejections")
check("the session total counts every rejection", e.total_rejections >= 3)

# ---------------------------------------------------------------- Session: bypass
log = []
s = lg.Session("out", "S", save=fake_save(log))
check("bypass is refused before it is offered", s.bypass(5.0, FRAME, ["blurred"]) is None and not s.captures and not log)
blocked(s.escape, 0.0, 9.2)
ent = s.bypass(9.3, FRAME, ["blurred", "glare_over_data_zone"])
check("bypass saves the frame like any capture", len(log) == 1 and log[0].endswith("capture-S-01.jpg") and ent["file"] == log[0])
check("bypass is marked, with trigger and the reasons blocking at that moment",
      ent["bypassed"] is True and ent["trigger"] == "rejections" and ent["blocking_reasons"] == ["blurred", "glare_over_data_zone"], ent)
check("bypass is flagged for manual review, not silently accepted", ent["manual_review"] is True and ent["status"] == "pending")
check("bypass opens the review screen", s.review is ent)
check("bypass resets the escape rule", s.escape.trigger is None and s.escape.streak == 0)
check("a second bypass is refused until offered again", s.bypass(9.4, FRAME, ["blurred"]) is None)

s = lg.Session("out", "T", save=fake_save([]))
s.escape.update(120.0, False, False)
ent = s.bypass(120.1, FRAME, [])
check("the 120 s trigger is recorded as its own trigger", ent["trigger"] == "timeout" and ent["blocking_reasons"] == [])

# ---------------------------------------------------------------- Session: review (accept / retake)
s = lg.Session("out", "U", save=fake_save([]))
ent = s.auto_capture(3.0, FRAME)
check("auto-capture freezes on the captured frame for review", s.review is ent and ent["status"] == "pending" and not ent["bypassed"])
check("accept ends the session by default", s.accept() is True and ent["status"] == "accepted" and s.review is None and s.done)

s = lg.Session("out", "V", end_on_accept=False, save=fake_save([]))
s.auto_capture(3.0, FRAME)
check("accept can advance instead of ending", s.accept() is False and not s.done)

s = lg.Session("out", "W", save=fake_save([]))
first = s.auto_capture(3.0, FRAME)
s.retake()
check("retake clears the review and keeps the file as an attempt", s.review is None and first["status"] == "retaken" and len(s.captures) == 1)
second = s.auto_capture(9.0, FRAME)
check("after a retake the next capture is a new numbered attempt", second["file"].endswith("capture-W-02.jpg") and len(s.captures) == 2)

s = lg.Session("out", "X", save=fake_save([]))
ent = s.auto_capture(1.0, FRAME, review=False)
check("headless captures are auto-accepted, no review screen", s.review is None and ent["status"] == "auto_accepted")
check("accept/retake with nothing under review is harmless", s.accept() is False and (s.retake() is None))

# ---------------------------------------------------------------- summary: the bypass rate is first-class
def samples(n=20):
    return [{"t": i * 0.1, "raw": [], "shown": [], "ms": 80.0} for i in range(n)]


def caps(flags):
    out = []
    for i, f in enumerate(flags):
        c = {"t": float(i), "file": f"x{i}.jpg", "bypassed": f, "status": "accepted"}
        if f:
            c.update(trigger="timeout", blocking_reasons=["blurred"], manual_review=True)
        out.append(c)
    return out


sm = lg.summarise(samples(), caps([False, True, False, True, False]), "chip", {}, total_rejections=7)
check("bypass rate = bypassed / total attempts", sm["attempts"] == 5 and sm["bypassed"] == 2 and sm["bypass_rate"] == 0.4, sm["bypass_rate"])
check("rejections are reported", sm["rejections"] == 7)
check("blocking reasons of the bypassed frames are tallied", sm["bypass_blocking_reasons"] == {"blurred": 2} and sm["bypass_triggers"] == {"timeout": 2})
sm0 = lg.summarise(samples(), [], "chip", {})
check("no captures: the rate is None, not 0", sm0["bypass_rate"] is None and sm0["attempts"] == 0)
sm1 = lg.summarise(samples(), caps([True]), "chip", {})
check("a session that was all bypass reads 100%", sm1["bypass_rate"] == 1.0)
sm2 = lg.summarise(samples(), caps([False, False]), "chip", {})
check("no bypass reads 0.0", sm2["bypass_rate"] == 0.0 and sm2["bypassed"] == 0)

with tempfile.TemporaryDirectory() as d:
    lg.OUT = Path(d)
    captures = caps([False, True, False, True, False])
    sl = samples()                                      # summarise() annotates the samples it is given; write_report reads that
    smx = lg.summarise(sl, captures, "chip", {"blurred": "Hold steady."}, 7)
    page = lg.write_report("Z", smx, sl, captures, "test").read_text()
    data = json.loads((Path(d) / "session-Z.json").read_text())
    check("the report page leads with the bypass rate", "Bypass rate: 40%" in page and "2 of 5" in page)
    check("the report page flags bypassed frames", page.count("BYPASSED") == 2)
    check("the raw JSON carries per-capture bypass fields", data["captures"][1]["bypassed"] and data["captures"][1]["blocking_reasons"] == ["blurred"])
    check("the JSON summary carries the rate", data["summary"]["bypass_rate"] == 0.4)
    sl = samples()
    smn = lg.summarise(sl, [], "chip", {}, 0)
    page0 = lg.write_report("Y", smn, sl, [], "test").read_text()
    check("an empty session reports n/a, not 0%", "Bypass rate: n/a" in page0)

# ---------------------------------------------------------------- screens: both choices are drawn and unmistakable
big = np.full((1080, 1920, 3), 90, np.uint8)
auto = {"bypassed": False, "status": "pending"}
byp = {"bypassed": True, "status": "pending", "blocking_reasons": ["blurred"], "trigger": "timeout"}
v1, v2, v3 = lg.draw_review(big, auto), lg.draw_review(big, byp), lg.draw_review(big, auto, splash=True)
h, w = v1.shape[:2]
GREEN, ORANGE = (70, 160, 60), (20, 130, 235)
px = lambda v, x, y: tuple(int(c) for c in v[y, x])
check("review screen shows an accept button (green, left) and a retake button (orange, right)",
      px(v1, 30, h - 40) == GREEN and px(v1, w - 30, h - 40) == ORANGE, (px(v1, 30, h - 40), px(v1, w - 30, h - 40)))
check("the bypass review screen has the same two choices", px(v2, 30, h - 40) == GREEN and px(v2, w - 30, h - 40) == ORANGE)
check("the bypass banner is orange (different from a normal capture's green)", px(v2, 5, 5) == ORANGE and px(v1, 5, 5) == GREEN)
check("the closing splash has no buttons", px(v3, 30, h - 40) != GREEN and px(v3, w - 30, h - 40) != ORANGE)
live = lg.draw(big, {"predictions": None}, ("not_usable", ("blurred",), "Hold steady."), 80.0, "rejections", False, True, 0, 0, 3, 3)
base = lg.draw(big, {"predictions": None}, ("not_usable", ("blurred",), "Hold steady."), 80.0, None, False, True, 0, 0, 3, 3)
check("the live screen shows the take-it-anyway bar only once offered", not np.array_equal(live, base))
check("key sets do not collide: accept, retake and bypass are distinct", not set(lg.KEY_ACCEPT) & set(lg.KEY_RETAKE) and lg.KEY_BYPASS not in lg.KEY_ACCEPT + lg.KEY_RETAKE)

print(f"{PASSED} passed, {len(FAILED)} failed")
for f in FAILED:
    print("FAIL:", f)
sys.exit(1 if FAILED else 0)
