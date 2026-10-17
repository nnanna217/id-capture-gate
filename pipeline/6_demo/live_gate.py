"""Live capture-quality gate: camera in, ONE instruction out, and a small session report when you quit.

Runs the published workflow (model + custom CaptureVerdict block) in-process through the Inference library, on every frame the
camera delivers (as fast as inference allows). The screen shows the camera feed, the model's outlines (toggle), a banner with the
single guidance sentence, and a footer with the measured latency. When the frame has stayed usable for 1 s it is captured
automatically (into local/demo/), and the verdict has to turn not-usable again before it can capture again.

After every capture the screen freezes on the captured frame and asks: ACCEPT or RETAKE (D-15). Accepting ends the session
(--continue-after-accept keeps it going); retaking returns to live guidance.

Nobody gets stuck (D-16): after 3 consecutive rejections, or 120 s with no capture, whichever comes first, SPACE takes the photo
anyway. That frame is saved like any other capture but marked bypassed, with the reasons that were blocking at that moment, and the
screen says it is going to MANUAL REVIEW. The session report leads with the bypass rate (bypassed captures / all captures).
Both are app-layer rules: the published block is unchanged.

The banner is debounced in this app (not in the block): it changes only after 3 consecutive judgements agree on the reason list,
so the sentence does not flicker. The block's own answer for each frame is unchanged and is what the report counts.

On quit it writes local/demo/session-<time>.json and .html: how long each blocker held the capture up, the time to the first
capture, latency (with the hardware), and the one blocker worth fixing. It never shows or stores a numeric quality score.

usage (from the repo root):
    python -I pipeline/6_demo/live_gate.py --list              which cameras OpenCV can open
    python -I pipeline/6_demo/live_gate.py --source 1          live camera 1 (Continuity Camera is usually 0 or 1)
    python -I pipeline/6_demo/live_gate.py --source local/upload/own --hold-frames 14 --headless    test without a camera
keys: q / Esc quit - m outlines on/off - r rotate 90 degrees - n next camera - h footer on/off
      SPACE take the photo anyway (only once the gate has offered it)
      on the review screen: a / Enter accept - r / t / Backspace retake
Raw captures and reports stay under local/ (gitignored). Use a mock card, never a real identity document.
"""
import argparse
import base64
import html
import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

OUT = Path("local/demo")
DEBOUNCE = 3          # consecutive agreeing judgements before the banner changes
HOLD_S = 1.0          # usable for this long -> capture
ACCEPT_SPLASH_S = 1.2
REJECTIONS_TO_OFFER = 3   # D-16: consecutive rejections before the manual-capture option appears
STUCK_S = 120.0           # D-16: seconds with no capture before it appears regardless
REJECT_HOLD_S = 3.0       # D-16: a rejection = card in view and not usable for this long, continuously
KEY_ACCEPT, KEY_RETAKE, KEY_BYPASS = (ord("a"), 13, 10), (ord("r"), ord("t"), 8, 127), ord(" ")
MIN_CONF = 0.4        # the block's own cut-off: draw only the outlines the block used
LABELS = {"too_dark": "too dark", "no_document": "no card in view", "incomplete_document": "card cut off",
          "obstructed": "text covered", "glare_over_data_zone": "glare on the text", "blurred": "blurred",
          "usable": "usable"}
OUTLINE = {"document": (255, 255, 255), "data_zone": (255, 200, 0), "glare": (0, 230, 255), "obstruction": (60, 60, 255)}  # BGR
BLOCKER_COLOR = {"usable": "#2e9e4f", "too_dark": "#5b5b8f", "no_document": "#8a8a8a", "incomplete_document": "#c9803a",
                 "obstructed": "#d1453b", "glare_over_data_zone": "#d9b300", "blurred": "#8a5bb5"}
ROT = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


# ---------------------------------------------------------------- session state (app layer, no camera or model needed)
class Escape:
    """The nobody-gets-stuck rule (D-16). Offers a manual capture when EITHER trigger fires, whichever is first:
    `rejections` consecutive rejections, or `seconds` since the last capture (or the start) with none.

    A live camera judges ~12 times a second, so a rejection cannot be one judgement. Here it is: the card is in view (the shown
    reasons do not include no_document) and the shown verdict stays not-usable for `hold_s` continuously; a block that lasts keeps
    counting once per `hold_s`. A rejection streak is broken only by a capture. The clock is unconditional (it also runs while no
    card is detected, because a document type the model does not recognise is exactly the user who would otherwise be stuck)."""

    def __init__(self, rejections=REJECTIONS_TO_OFFER, seconds=STUCK_S, hold_s=REJECT_HOLD_S):
        self.rejections, self.seconds, self.hold_s = rejections, seconds, hold_s
        self.total_rejections = 0
        self.reset(0.0)

    def reset(self, now):
        self.since, self.streak, self.run_start, self.trigger = now, 0, None, None

    def update(self, now, usable, card_in_view):
        if not usable and card_in_view:
            if self.run_start is None:
                self.run_start = now
            elif now - self.run_start >= self.hold_s:
                self.streak, self.total_rejections, self.run_start = self.streak + 1, self.total_rejections + 1, now
        else:
            self.run_start = None
        if self.trigger is None:
            if self.streak >= self.rejections:
                self.trigger = "rejections"
            elif now - self.since >= self.seconds:
                self.trigger = "timeout"
        return self.trigger


class Session:
    """Captures, the review step after each one, and the escape hatch. Owns no camera and no model: main() feeds it."""

    def __init__(self, out_dir, stamp, escape=None, end_on_accept=True, save=None):
        self.out, self.stamp, self.escape = Path(out_dir), stamp, escape or Escape()
        self.end_on_accept, self.save = end_on_accept, save or (lambda path, frame: cv2.imwrite(str(path), frame))
        self.captures, self.review, self.review_frame, self.done = [], None, None, False

    @property
    def offered(self):
        return self.escape.trigger

    def _take(self, now, frame, **extra):
        path = self.out / f"capture-{self.stamp}-{len(self.captures) + 1:02d}.jpg"
        self.save(path, frame)
        entry = {"t": round(now, 2), "file": str(path), "bypassed": False, "status": "pending", **extra}
        self.captures.append(entry)
        self.escape.reset(now)
        return entry

    def auto_capture(self, now, frame, review=True):
        entry = self._take(now, frame)
        if review:
            self.review = entry
        else:
            entry["status"] = "auto_accepted"     # headless: nobody to ask
        return entry

    def bypass(self, now, frame, blocking_reasons):
        """SPACE: take the photo anyway. Only once the gate has offered it; returns None before that."""
        if self.escape.trigger is None:
            return None
        entry = self._take(now, frame, bypassed=True, trigger=self.escape.trigger, blocking_reasons=list(blocking_reasons),
                           manual_review=True)
        self.review = entry
        return entry

    def accept(self):
        if self.review is not None:
            self.review["status"] = "accepted"
            self.review = None
            self.done = self.end_on_accept
        return self.done

    def retake(self):
        if self.review is not None:
            self.review["status"] = "retaken"
            self.review = None


# ---------------------------------------------------------------- sources
class Camera:
    """Keeps only the newest frame, so a slow inference never works through a queue of old ones."""

    def __init__(self, index):
        self.index = index
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise SystemExit(f"Camera {index} did not open. Try --list, and check macOS camera permission for the Terminal app.")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.frame, self.seq, self.seen, self.alive = None, 0, 0, True
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.alive:
            ok, f = self.cap.read()
            if ok:
                with self.lock:
                    self.frame, self.seq = f, self.seq + 1
            else:
                time.sleep(0.01)

    def read(self):
        for _ in range(400):
            with self.lock:
                if self.seq != self.seen and self.frame is not None:
                    self.seen = self.seq
                    return self.frame.copy()
            time.sleep(0.005)
        return None

    def close(self):
        self.alive = False
        time.sleep(0.05)
        self.cap.release()


class Images:
    """A folder or list of stills, each repeated `hold` times: for testing the whole app without a camera."""

    def __init__(self, paths, hold):
        self.paths, self.hold, self.i, self.cache = paths, hold, 0, {}

    def read(self):
        if self.i >= len(self.paths) * self.hold:
            return None
        p = self.paths[self.i // self.hold]
        self.i += 1
        if p not in self.cache:
            self.cache[p] = cv2.imread(str(p))
        return self.cache[p].copy()

    def close(self):
        pass


def probe_cameras(limit=5):
    found = []
    for i in range(limit):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ok, f = cap.read()
            found.append((i, f.shape[1], f.shape[0]) if ok else (i, 0, 0))
        cap.release()
    return found


def list_cameras():
    try:
        names = subprocess.run(["system_profiler", "SPCameraDataType"], capture_output=True, text=True, timeout=20).stdout
        print("Cameras macOS knows about:")
        print("\n".join("  " + l.strip() for l in names.splitlines() if l.strip().endswith(":") and not l.startswith("Camera")))
    except Exception:
        pass
    print("Indexes OpenCV can open (index, width x height):")
    for i, w, h in probe_cameras():
        print(f"  --source {i}: {w} x {h}")
    print("OpenCV's index order is not guaranteed to match the names above: if the picture is the wrong camera, press n or try another index.")


# ---------------------------------------------------------------- workflow
def make_engine(spec_path):
    load_dotenv(".env")
    from inference.core.managers.base import ModelManager
    from inference.core.registries.roboflow import RoboflowModelRegistry
    from inference.core.workflows.core_steps.common.entities import StepExecutionMode
    from inference.core.workflows.execution_engine.core import ExecutionEngine
    from inference.models.utils import ROBOFLOW_MODEL_TYPES
    spec = json.load(open(spec_path))
    return ExecutionEngine.init(workflow_definition=spec, init_parameters={
        "workflows_core.model_manager": ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES)),
        "workflows_core.api_key": os.environ["ROBOFLOW_API_KEY"], "workflows_core.step_execution_mode": StepExecutionMode.LOCAL})


def chip():
    try:
        return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip() or platform.machine()
    except Exception:
        return platform.machine()


# ---------------------------------------------------------------- drawing
def fit_lines(text, width, font=cv2.FONT_HERSHEY_DUPLEX, thick=2):
    scale = 1.0
    while cv2.getTextSize(text, font, scale, thick)[0][0] > width and scale > 0.5:
        scale -= 0.05
    if cv2.getTextSize(text, font, scale, thick)[0][0] <= width:
        return [text], scale
    words = text.split()
    best = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
    lines = [" ".join(words[:best]), " ".join(words[best:])]
    scale = 0.9
    while max(cv2.getTextSize(l, font, scale, thick)[0][0] for l in lines) > width and scale > 0.4:
        scale -= 0.05
    return lines, scale


def draw(frame, out, shown, ms, offer, show_masks, show_footer, captures, rot, streak=0, need=REJECTIONS_TO_OFFER):
    h, w = frame.shape[:2]
    s = min(1.0, 900.0 / max(h, w))
    view = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else frame.copy()
    vh, vw = view.shape[:2]
    det = out.get("predictions")
    if show_masks and det is not None and len(det) and det.mask is not None:
        names = det.data.get("class_name", [])
        for i in range(len(det)):
            if float(det.confidence[i]) < MIN_CONF:
                continue
            m = cv2.resize(det.mask[i].astype(np.uint8), (vw, vh), interpolation=cv2.INTER_NEAREST)
            cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(view, cs, -1, OUTLINE.get(str(names[i]), (200, 200, 200)), 2)
    ok = shown[0] == "usable"
    colour = (70, 160, 60) if ok else (45, 45, 200)
    text = shown[2]
    lines, scale = fit_lines(text, vw - 30)
    lh = int(46 * scale) + 8
    bh = lh * len(lines) + 18
    cv2.rectangle(view, (0, 0), (vw, bh), colour, -1)
    for k, l in enumerate(lines):
        cv2.putText(view, l, (15, 14 + lh * (k + 1) - 8), cv2.FONT_HERSHEY_DUPLEX, scale, (255, 255, 255), 2, cv2.LINE_AA)
    if len(shown[1]) > 1:
        also = "also: " + ", ".join(LABELS[r] for r in shown[1][1:])
        cv2.putText(view, also, (15, bh + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    if offer:
        lines2, sc2 = fit_lines("Not working? Press SPACE to take the photo anyway. It will be sent for manual review.", vw - 30)
        lh2 = int(46 * sc2) + 8
        bh2 = lh2 * len(lines2) + 18
        top = vh - (28 if show_footer else 0) - bh2
        cv2.rectangle(view, (0, top), (vw, top + bh2), (20, 130, 235), -1)
        for k, l in enumerate(lines2):
            cv2.putText(view, l, (15, top + 14 + lh2 * (k + 1) - 8), cv2.FONT_HERSHEY_DUPLEX, sc2, (255, 255, 255), 2, cv2.LINE_AA)
    if show_footer:
        foot = (f"{ms:.0f} ms/frame   captures {captures}   rejections in a row {streak}/{need}   rot {rot}   "
                f"[m] outlines [r] rotate [n] camera [q] quit")
        cv2.rectangle(view, (0, vh - 28), (vw, vh), (30, 30, 30), -1)
        cv2.putText(view, foot, (10, vh - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
    return view


def draw_review(frame, entry, splash=False):
    """The frozen captured frame with two unmistakable choices (D-15). `splash`: the closing 'accepted' screen."""
    h, w = frame.shape[:2]
    s = min(1.0, 900.0 / max(h, w))
    view = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else frame.copy()
    vh, vw = view.shape[:2]
    bypass = entry.get("bypassed")
    if splash:
        head, colour = ("Sent for manual review. Thank you." if bypass else "Accepted. Thank you."), (70, 160, 60)
    elif bypass:
        head, colour = "Taken anyway. This photo is going to MANUAL REVIEW.", (20, 130, 235)
    else:
        head, colour = "Captured. Is this photo OK?", (70, 160, 60)
    lines, scale = fit_lines(head, vw - 30)
    lh = int(46 * scale) + 8
    bh = lh * len(lines) + 18
    cv2.rectangle(view, (0, 0), (vw, bh), colour, -1)
    for k, l in enumerate(lines):
        cv2.putText(view, l, (15, 14 + lh * (k + 1) - 8), cv2.FONT_HERSHEY_DUPLEX, scale, (255, 255, 255), 2, cv2.LINE_AA)
    if bypass and entry.get("blocking_reasons"):
        why = "It did not pass: " + ", ".join(LABELS[r] for r in entry["blocking_reasons"])
        cv2.putText(view, why, (15, bh + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    if not splash:
        bw, bth = (vw - 45) // 2, 78
        y0 = vh - bth - 15
        for x0, col, key, label in ((15, (70, 160, 60), "A", "SUBMIT FOR REVIEW" if bypass else "ACCEPT"), (30 + bw, (20, 130, 235), "R", "RETAKE")):
            cv2.rectangle(view, (x0, y0), (x0 + bw, y0 + bth), col, -1)
            cv2.rectangle(view, (x0, y0), (x0 + bw, y0 + bth), (255, 255, 255), 3)
            txt = f"[{key}]  {label}"
            sc = 1.1
            while cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, sc, 2)[0][0] > bw - 20 and sc > 0.5:
                sc -= 0.05
            tw, th = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, sc, 2)[0]
            cv2.putText(view, txt, (x0 + (bw - tw) // 2, y0 + (bth + th) // 2), cv2.FONT_HERSHEY_DUPLEX, sc, (255, 255, 255), 2, cv2.LINE_AA)
    return view


# ---------------------------------------------------------------- report
def thumb(path, h=150):
    im = cv2.imread(str(path))
    if im is None:
        return ""
    s = h / im.shape[0]
    im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def summarise(samples, captures, hardware, guidance_of, total_rejections=0):
    if not samples:
        return None
    dts = [samples[i + 1]["t"] - samples[i]["t"] for i in range(len(samples) - 1)]
    last = float(np.median(dts)) if dts else 0.0
    for i, smp in enumerate(samples):
        smp["dt"] = dts[i] if i < len(dts) else last
        smp["blocker"] = smp["shown"][0] if smp["shown"] else "usable"
    total = sum(s["dt"] for s in samples)
    by = {}
    for s in samples:
        by[s["blocker"]] = by.get(s["blocker"], 0.0) + s["dt"]
    usable_s = by.get("usable", 0.0)
    blocked_s = total - usable_s
    first_cap = captures[0]["t"] if captures else None
    before = {}
    for s in samples:
        if first_cap is not None and s["t"] >= first_cap:
            break
        if s["blocker"] != "usable":
            before[s["blocker"]] = before.get(s["blocker"], 0.0) + s["dt"]
    ms = sorted(s["ms"] for s in samples)
    blockers = {k: v for k, v in by.items() if k != "usable"}
    top = max(blockers, key=blockers.get) if blockers else None
    two = sum(1 for s in samples if len(s["shown"]) > 1)
    if top:
        insight = (f"{LABELS[top].capitalize()} held the capture up for {blockers[top]:.0f} s of {blocked_s:.0f} s not usable "
                   f"({100 * blockers[top] / blocked_s:.0f}%). The instruction that fixes it: \"{guidance_of.get(top, '')}\"")
    else:
        insight = "Nothing blocked the capture in this session."
    attempts = len(captures)
    bypassed = [c for c in captures if c.get("bypassed")]
    triggers = {}
    for c in bypassed:
        triggers[c["trigger"]] = triggers.get(c["trigger"], 0) + 1
    blocking = {}
    for c in bypassed:
        for r in c.get("blocking_reasons") or ["none_at_that_moment"]:
            blocking[r] = blocking.get(r, 0) + 1
    status = {k: sum(1 for c in captures if c.get("status") == k) for k in ("accepted", "retaken", "auto_accepted", "pending")}
    return {"seconds": round(total, 1), "judgements": len(samples), "usable_seconds": round(usable_s, 1),
            # first-class: the share of capture attempts taken past the gate (D-16). A rising rate means the gate is too strict.
            "attempts": attempts, "bypassed": len(bypassed), "bypass_rate": round(len(bypassed) / attempts, 3) if attempts else None,
            "bypass_triggers": triggers, "bypass_blocking_reasons": dict(sorted(blocking.items(), key=lambda kv: -kv[1])),
            "capture_status": status, "rejections": total_rejections,
            "blocked_seconds": round(blocked_s, 1), "seconds_by_blocker": {k: round(v, 1) for k, v in sorted(by.items(), key=lambda kv: -kv[1])},
            "captures": len(captures), "first_capture_after_s": round(first_cap, 1) if first_cap is not None else None,
            "blocked_before_first_capture_s": {k: round(v, 1) for k, v in sorted(before.items(), key=lambda kv: -kv[1])},
            "judgements_with_two_or_more_reasons": two, "latency_ms_median": round(ms[len(ms) // 2]),
            "latency_ms_p95": round(ms[min(len(ms) - 1, int(0.95 * len(ms)))]), "latency_scope": "model + custom block, in-process, per frame; excludes camera and drawing",
            "hardware": hardware, "insight": insight, "top_blocker": top}


def write_report(stamp, summ, samples, captures, source_desc):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"session-{stamp}.json").write_text(json.dumps({"summary": summ, "source": source_desc, "captures": captures,
                                                         "judgements": [{k: s[k] for k in ("t", "raw", "shown", "ms")} for s in samples]}))
    T = max(summ["seconds"], 0.1)
    rects, x = [], 0.0
    for s in samples:
        wd = 1000 * s["dt"] / T
        rects.append(f'<rect x="{x:.2f}" y="0" width="{max(wd, 0.4):.2f}" height="34" fill="{BLOCKER_COLOR.get(s["blocker"], "#999")}"/>')
        x += wd
    ticks = "".join(f'<rect x="{1000 * c["t"] / T:.1f}" y="-6" width="3" height="46" fill="{"#e8820c" if c.get("bypassed") else "#111"}"/>'
                    for c in captures)
    rows = "".join(f'<tr><td><span style="background:{BLOCKER_COLOR.get(k, "#999")}" class="sw"></span>{html.escape(LABELS[k])}</td>'
                   f'<td>{v:.1f} s</td><td>{100 * v / T:.0f}%</td></tr>' for k, v in summ["seconds_by_blocker"].items())
    thumbs = "".join(f'<figure><img src="{thumb(c["file"])}"><figcaption>capture {i + 1} at {c["t"]:.1f} s - '
                     + (f'<b class="bp">BYPASSED</b> ({html.escape(c["trigger"])}; blocked by '
                        f'{html.escape(", ".join(LABELS[r] for r in c.get("blocking_reasons") or []) or "nothing at that moment")})'
                        if c.get("bypassed") else "passed the gate")
                     + f", {html.escape(c.get('status', ''))}</figcaption></figure>" for i, c in enumerate(captures))
    if summ["bypass_rate"] is None:
        bypass_box = '<div class="bypass"><b>Bypass rate: n/a</b><br>No captures in this session.</div>'
    else:
        bypass_box = (f'<div class="bypass"><b>Bypass rate: {100 * summ["bypass_rate"]:.0f}%</b> - {summ["bypassed"]} of {summ["attempts"]} '
                      f'capture(s) were taken past the gate and flagged for manual review.<br><span class="mut">{summ["rejections"]} rejection(s) '
                      f'in the session. A rising bypass rate across sessions is the signal that the gate has become too strict; the bypassed '
                      f'frames are the next model version\'s training data.</span></div>')
    before = ", ".join(f"{LABELS[k]} {v:.1f} s" for k, v in summ["blocked_before_first_capture_s"].items()) or "nothing"
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Capture session report</title><style>
:root{{--bg:#fafaf8;--fg:#1c1c1a;--mut:#666;--line:#ddd}}@media(prefers-color-scheme:dark){{:root{{--bg:#161614;--fg:#eee;--mut:#aaa;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:24px 16px}}
h1{{font-size:22px;margin:0 0 4px}}.mut{{color:var(--mut);font-size:14px}}.insight{{font-size:19px;border-left:5px solid #d1453b;padding:8px 14px;margin:18px 0}}
table{{border-collapse:collapse;width:100%}}td{{padding:6px 8px;border-bottom:1px solid var(--line)}}.sw{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:8px}}
svg{{width:100%;height:60px;margin:8px 0}}figure{{display:inline-block;margin:0 12px 12px 0}}img{{height:150px;border-radius:6px}}figcaption{{font-size:13px;color:var(--mut);max-width:260px}}
.bypass{{font-size:19px;border-left:5px solid #e8820c;padding:8px 14px;margin:18px 0}}.bp{{color:#e8820c}}
</style></head><body><h1>Capture session report</h1>
<div class="mut">{summ['seconds']} s, {summ['judgements']} judgements - {html.escape(source_desc)}</div>
{bypass_box}
<div class="insight">{html.escape(summ['insight'])}</div>
<p>{summ['captures']} capture(s). First capture after {summ['first_capture_after_s'] if summ['first_capture_after_s'] is not None else 'n/a'} s;
before that the time was lost to: {html.escape(before)}.</p>
<svg viewBox="0 -8 1000 48" preserveAspectRatio="none">{''.join(rects)}{ticks}</svg>
<div class="mut">Timeline of the session, left to right. Ticks are captures (orange: taken past the gate). Colours are the blocker shown on screen.</div>
<table><tr><td><b>Blocker</b></td><td><b>Time</b></td><td><b>Share</b></td></tr>{rows}</table>
<p class="mut">{summ['judgements_with_two_or_more_reasons']} judgements had two or more reasons; the banner showed the first one (precedence order in DECISIONS.md D-13).</p>
{thumbs}
<p class="mut">Latency per frame (model + custom block, in-process): median {summ['latency_ms_median']} ms, 95th percentile {summ['latency_ms_p95']} ms on {html.escape(summ['hardware'])}.
Excludes camera capture and drawing. No numeric quality score is produced or stored.</p></body></html>"""
    (OUT / f"session-{stamp}.html").write_text(page)
    return OUT / f"session-{stamp}.html"


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--source", default="0", help="camera index, a folder of images, or an image/video file")
    ap.add_argument("--spec", default="workflows/capture-gate-verdict-published.json")
    ap.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270])
    ap.add_argument("--hold-frames", type=int, default=10, help="stills only: judgements per image")
    ap.add_argument("--headless", action="store_true", help="no window (for testing with stills)")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--continue-after-accept", action="store_true", help="accepting a capture keeps the session going (default: it ends)")
    ap.add_argument("--bypass-rejections", type=int, default=REJECTIONS_TO_OFFER, help="consecutive rejections before SPACE is offered")
    ap.add_argument("--bypass-seconds", type=float, default=STUCK_S, help="seconds with no capture before SPACE is offered")
    a = ap.parse_args()
    if a.list:
        list_cameras()
        return
    cams = []
    if a.source.isdigit():
        cams = [i for i, _, _ in probe_cameras()] or [int(a.source)]
        src, desc = Camera(int(a.source)), f"camera {a.source}"
    else:
        p = Path(a.source)
        paths = sorted(p.glob("*.jpg")) if p.is_dir() else [p]
        if not paths:
            raise SystemExit("no images found in " + a.source)
        src, desc = Images(paths, a.hold_frames), f"{len(paths)} still image(s) from {a.source}"
    print("loading the published workflow (first load takes a few seconds)...")
    engine = make_engine(a.spec)
    engine.run(runtime_parameters={"image": np.zeros((480, 640, 3), np.uint8)})
    hardware = chip()
    print(f"ready on {hardware}. q to quit.")
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    rot, show_masks, show_footer = a.rotate, True, True
    samples, guidance_of = [], {}
    shown, cand, cand_n = None, None, 0
    usable_since, armed = None, True
    sess = Session(OUT, stamp, Escape(a.bypass_rejections, a.bypass_seconds), end_on_accept=not a.continue_after_accept)
    review_on = not a.headless          # headless has nobody to ask: captures are auto-accepted and SPACE does not exist
    paused, review_t0 = 0.0, None       # time spent on the review screen is not session time (it would distort the timeline)
    t0 = time.perf_counter()
    try:
        while True:
            if sess.review is not None:
                cv2.imshow("capture gate", draw_review(sess.review_frame, sess.review))
                k = cv2.waitKey(30) & 0xFF
                done = None
                if k in KEY_ACCEPT:
                    done = sess.accept()
                elif k in KEY_RETAKE:
                    sess.retake()
                elif k in (ord("q"), 27):
                    break
                if k in KEY_ACCEPT or k in KEY_RETAKE:
                    paused += time.perf_counter() - review_t0
                    usable_since, armed = None, True
                    if done:
                        cv2.imshow("capture gate", draw_review(sess.review_frame, sess.captures[-1], splash=True))
                        cv2.waitKey(int(ACCEPT_SPLASH_S * 1000))
                        break
                continue
            frame = src.read()
            if frame is None:
                break
            if rot:
                frame = cv2.rotate(frame, ROT[rot])
            t1 = time.perf_counter()
            out = engine.run(runtime_parameters={"image": frame})[0]
            ms = (time.perf_counter() - t1) * 1000
            now = time.perf_counter() - t0 - paused
            raw = (out["verdict"], tuple(out["reasons"]), out["guidance"])
            if out["reasons"]:
                guidance_of.setdefault(out["reasons"][0], out["guidance"])
            if shown is None or raw[1] == shown[1]:
                shown, cand, cand_n = (raw if shown is None else shown), None, 0
            else:
                cand_n = cand_n + 1 if cand == raw[1] else 1
                cand = raw[1]
                if cand_n >= DEBOUNCE:
                    shown, cand, cand_n = raw, None, 0
            samples.append({"t": now, "raw": list(raw[1]), "shown": list(shown[1]), "ms": ms})
            sess.escape.update(now, shown[0] == "usable", "no_document" not in shown[1])
            if shown[0] == "usable":
                usable_since = now if usable_since is None else usable_since
                if armed and now - usable_since >= HOLD_S and raw[0] == "usable":
                    entry = sess.auto_capture(now, frame, review=review_on)
                    armed = False
                    print(f"captured #{len(sess.captures)} at {now:.1f} s -> {entry['file']}")
            else:
                usable_since, armed = None, True
            if sess.review is not None:
                sess.review_frame, review_t0 = frame, time.perf_counter()
            if not a.headless:
                cv2.imshow("capture gate", draw(frame, out, shown, ms, sess.offered, show_masks, show_footer, len(sess.captures), rot,
                                                sess.escape.streak, sess.escape.rejections))
                k = cv2.waitKey(1) & 0xFF
                if k in (ord("q"), 27):
                    break
                elif k == KEY_BYPASS:
                    entry = sess.bypass(now, frame, raw[1] or shown[1])
                    if entry is not None:
                        sess.review_frame, review_t0 = frame, time.perf_counter()
                        print(f"BYPASS #{len(sess.captures)} at {now:.1f} s ({entry['trigger']}; blocked by {entry['blocking_reasons']}) -> {entry['file']}")
                elif k == ord("m"):
                    show_masks = not show_masks
                elif k == ord("h"):
                    show_footer = not show_footer
                elif k == ord("r"):
                    rot = (rot + 90) % 360
                elif k == ord("n") and isinstance(src, Camera) and len(cams) > 1:
                    nxt = cams[(cams.index(src.index) + 1) % len(cams)] if src.index in cams else cams[0]
                    src.close()
                    src, desc = Camera(nxt), f"camera {nxt}"
                    print("switched to camera", nxt)
    finally:
        src.close()
        cv2.destroyAllWindows()
    captures = sess.captures
    summ = summarise(samples, captures, hardware, guidance_of, sess.escape.total_rejections)
    if summ is None:
        print("no frames were judged")
        return
    path = write_report(stamp, summ, samples, captures, desc)
    print(f"\n{summ['insight']}")
    rate = "n/a" if summ["bypass_rate"] is None else f"{100 * summ['bypass_rate']:.0f}% ({summ['bypassed']} of {summ['attempts']})"
    print(f"bypass rate: {rate}; rejections: {summ['rejections']}")
    print(f"{summ['captures']} capture(s); first after {summ['first_capture_after_s']} s; "
          f"latency median {summ['latency_ms_median']} ms, p95 {summ['latency_ms_p95']} ms on {hardware}")
    print("report:", path)
    if not a.no_open and not a.headless:
        subprocess.run(["open", str(path)])


if __name__ == "__main__":
    main()
