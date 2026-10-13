"""Run every project frame through a workflow spec, in-process, and write one row per frame to a CSV.

usage (from the repo root): python -I pipeline/5_workflow/run_all_frames.py <spec.json> <out.csv>
e.g. python -I pipeline/5_workflow/run_all_frames.py workflows/capture-gate-verdict.json local/labels/verdict-run-v3.csv
Columns: file, card, condition, split, verdict, reasons (| separated), guidance, plus the raw measurements.
The key is read from .env and never printed.
"""
import csv
import json
import os
import sys
import time

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv(".env")
spec = json.load(open(sys.argv[1]))
out_path = sys.argv[2]
from inference.core.managers.base import ModelManager
from inference.core.registries.roboflow import RoboflowModelRegistry
from inference.core.workflows.core_steps.common.entities import StepExecutionMode
from inference.core.workflows.execution_engine.core import ExecutionEngine
from inference.models.utils import ROBOFLOW_MODEL_TYPES

engine = ExecutionEngine.init(workflow_definition=spec, init_parameters={
    "workflows_core.model_manager": ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES)),
    "workflows_core.api_key": os.environ["ROBOFLOW_API_KEY"], "workflows_core.step_execution_mode": StepExecutionMode.LOCAL})
plan = {}
for p in ("data/split.csv", "data/split-additions.csv"):
    for r in csv.DictReader(open(p)):
        plan[r["file"]] = r
rows, times = [], []
for n in sorted(plan):
    folder = "local/upload/new/" if os.path.exists("local/upload/new/" + n) else "local/upload/own/"
    t = time.perf_counter()
    o = engine.run(runtime_parameters={"image": cv2.imread(folder + n)})[0]
    times.append((time.perf_counter() - t) * 1000)
    d = o["details"]
    rows.append({"file": n, "card": plan[n]["card"], "condition": plan[n]["condition"], "split": plan[n]["split"],
                 "verdict": o["verdict"], "reasons": "|".join(o["reasons"]), "guidance": o["guidance"],
                 "sharp": d.get("zone_sharpness"), "p95": d.get("brightness_p95"), "obs_cov": d.get("obstruction_zone_coverage"),
                 "glare_cov": d.get("glare_zone_coverage"), "covered": d.get("card_mostly_covered")})
with open(out_path, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} frames -> {out_path} | per-frame median {np.median(times[1:]):.0f} ms (first call excluded)")
