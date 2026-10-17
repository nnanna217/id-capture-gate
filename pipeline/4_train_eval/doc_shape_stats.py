"""Shape of the model's `document` mask per frame: solidity, extent and quad-fill. The evidence behind D-15 (can a folded or torn card be
caught from the mask we already have, with no retraining?).

usage (from the repo root): python -I pipeline/4_train_eval/doc_shape_stats.py <out.csv> [--demo "local/demo/capture-*.jpg"]
Default: the 152 project frames (data/split*.csv). --demo: a glob of live-app captures instead (no condition labels; judge them by eye).
  solidity = mask area / convex-hull area         (1.0 for any convex shape, so it only sees concavities: a bite, a notch)
  extent   = mask area / minAreaRect area         (1.0 only for an upright rectangle; ALSO falls with perspective, so a tilted clean card reads low)
  quadfill = mask area / area of a 4-corner hull  (not used in the decision; kept for completeness)
Runs the published workflow in-process; the key is read from .env and never printed.
"""
import csv
import glob
import json
import os
import sys

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv(".env")
from inference.core.managers.base import ModelManager
from inference.core.registries.roboflow import RoboflowModelRegistry
from inference.core.workflows.core_steps.common.entities import StepExecutionMode
from inference.core.workflows.execution_engine.core import ExecutionEngine
from inference.models.utils import ROBOFLOW_MODEL_TYPES

MIN_CONF = 0.4     # the block's own cut-off


def shape(o):
    p = o["predictions"]
    n = len(p)
    names = list(p.data.get("class_name", [])) if n else []
    idx = [i for i in range(n) if names[i] == "document" and p.confidence[i] >= MIN_CONF]
    if not idx:
        return {}
    i = max(idx, key=lambda i: p.confidence[i])
    m = p.mask[i].astype(np.uint8)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cs, key=cv2.contourArea)
    a, hull = cv2.contourArea(c), cv2.convexHull(c)
    (_, _), (w, h), _ = cv2.minAreaRect(c)
    quad = cv2.convexHull(cv2.approxPolyDP(hull, 0.05 * cv2.arcLength(hull, True), True))
    return {"solidity": a / cv2.contourArea(hull), "extent": a / (w * h), "quadfill": a / cv2.contourArea(quad),
            "area_frac": a / m.size, "conf": float(p.confidence[i])}


def main():
    out, demo = sys.argv[1], (sys.argv[sys.argv.index("--demo") + 1] if "--demo" in sys.argv else None)
    spec = json.load(open("workflows/capture-gate-verdict-published.json"))
    eng = ExecutionEngine.init(workflow_definition=spec, init_parameters={
        "workflows_core.model_manager": ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES)),
        "workflows_core.api_key": os.environ["ROBOFLOW_API_KEY"], "workflows_core.step_execution_mode": StepExecutionMode.LOCAL})
    rows = []
    if demo:
        items = [(f, "?", "demo") for f in sorted(glob.glob(demo))]
    else:
        plan = {}
        for p in ("data/split.csv", "data/split-additions.csv"):
            for r in csv.DictReader(open(p)):
                plan[r["file"]] = r
        items = [(("local/upload/new/" if os.path.exists("local/upload/new/" + n) else "local/upload/own/") + n, plan[n]["card"], plan[n]["condition"])
                 for n in sorted(plan)]
    for path, card, cond in items:
        o = eng.run(runtime_parameters={"image": cv2.imread(path)})[0]
        rows.append({"file": os.path.basename(path), "card": card, "condition": cond, "verdict": o["verdict"], "reasons": "|".join(o["reasons"]), **shape(o)})
    keys = ["file", "card", "condition", "verdict", "reasons", "solidity", "extent", "quadfill", "area_frac", "conf"]
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} frames -> {out}")


if __name__ == "__main__":
    main()
