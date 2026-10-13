"""Fetch a PUBLISHED Roboflow workflow, run every project frame through it locally, and compare with a reference run.

What it answers: "does the workflow published on the platform give exactly the same answers as the JSON version I tested here?"

usage (from the repo root):
    python -I pipeline/5_workflow/compare_published_workflow.py [workflow-slug] [reference.csv]
defaults: capture-gate-verdict, local/labels/verdict-run-v2.csv (made from workflows/capture-gate-verdict.json)

Writes workflows/<slug>-published.json (the published spec) and local/report/published-run.json (every frame's result and the
model's mask outlines, which make_report.py draws). The API key is read from .env and never printed.
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv(".env")
KEY, WS = os.environ["ROBOFLOW_API_KEY"], "eze-nnanna-chijioke"
slug = sys.argv[1] if len(sys.argv) > 1 else "capture-gate-verdict"
ref_path = sys.argv[2] if len(sys.argv) > 2 else "local/labels/verdict-run-v2.csv"

r = requests.get(f"https://api.roboflow.com/{WS}/workflows/{slug}", params={"api_key": KEY}, timeout=60)
if r.status_code != 200:
    sys.exit(f"HTTP {r.status_code} fetching workflow '{slug}'")
wf = r.json().get("workflow", r.json())
cfg = wf.get("config")
spec = json.loads(cfg) if isinstance(cfg, str) else cfg
spec = spec.get("specification", spec) if spec else {}
steps = spec.get("steps", [])
print(f"published steps: {len(steps)} -> {[(s.get('type'), s.get('name')) for s in steps]}")
print("published outputs:", [o["name"] for o in spec.get("outputs", [])])
print("custom block inside the published workflow:", [d["manifest"]["block_type"] for d in spec.get("dynamic_blocks_definitions", [])])
if not steps:
    sys.exit("the published spec has no steps: saved but not published?")
Path(f"workflows/{slug}-published.json").write_text(json.dumps(spec, indent=2))

from inference.core.managers.base import ModelManager
from inference.core.registries.roboflow import RoboflowModelRegistry
from inference.core.workflows.core_steps.common.entities import StepExecutionMode
from inference.core.workflows.execution_engine.core import ExecutionEngine
from inference.models.utils import ROBOFLOW_MODEL_TYPES

engine = ExecutionEngine.init(workflow_definition=spec, init_parameters={
    "workflows_core.model_manager": ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES)),
    "workflows_core.api_key": KEY, "workflows_core.step_execution_mode": StepExecutionMode.LOCAL})


def outlines(det, h, w):
    """Mask outlines (simplified polygons, as fractions of the frame) per detection, for drawing."""
    out = []
    if det is None or len(det) == 0 or det.mask is None:
        return out
    names = det.data.get("class_name", [])
    for i in range(len(det)):
        cs, _ = cv2.findContours(det.mask[i].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cs:
            continue
        c = max(cs, key=cv2.contourArea)
        c = cv2.approxPolyDP(c, 0.004 * cv2.arcLength(c, True), True).reshape(-1, 2)
        out.append({"class": str(names[i]), "confidence": round(float(det.confidence[i]), 3),
                    "points": [[round(x / w, 4), round(y / h, 4)] for x, y in c.tolist()]})
    return out


ref = {x["file"]: x for x in csv.DictReader(open(ref_path))}
records, diffs, times = [], [], []
for f in sorted(ref):
    folder = "local/upload/new/" if os.path.exists("local/upload/new/" + f) else "local/upload/own/"
    img = cv2.imread(folder + f)
    t = time.perf_counter()
    o = engine.run(runtime_parameters={"image": img})[0]
    times.append((time.perf_counter() - t) * 1000)
    reasons = "|".join(o["reasons"])
    same = (reasons, o["verdict"], o["guidance"]) == (ref[f]["reasons"], ref[f]["verdict"], ref[f]["guidance"])
    if not same:
        diffs.append((f, (ref[f]["reasons"], ref[f]["verdict"], ref[f]["guidance"]), (reasons, o["verdict"], o["guidance"])))
    d = o["details"]
    records.append({"file": f, "card": ref[f]["card"], "condition": ref[f]["condition"], "split": ref[f]["split"],
                    "verdict": o["verdict"], "reasons": o["reasons"], "guidance": o["guidance"], "same_as_reference": same,
                    "details": {k: d.get(k) for k in ("brightness_p95", "brightness_region", "zone_sharpness", "zone_aspect",
                                                       "obstruction_zone_coverage", "glare_zone_coverage",
                                                       "card_touches_frame_edge", "card_mostly_covered", "blur_threshold_used")},
                    "outlines": outlines(o.get("predictions"), *img.shape[:2])})
Path("local/report").mkdir(parents=True, exist_ok=True)
Path("local/report/published-run.json").write_text(json.dumps({"slug": slug, "frames": records}))

n = len(records)
print(f"\nframes compared: {n}")
print(f"  identical to the reference (verdict, reasons and guidance): {n - len(diffs)}")
print(f"  different: {len(diffs)}")
for f, w, g in diffs[:15]:
    print(f"    {f}\n      reference: {w}\n      published: {g}")
print(f"per-frame time, model + block: median {np.median(times[1:]):.0f} ms (first call excluded)")
