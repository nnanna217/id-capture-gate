"""Fetch a PUBLISHED workflow from Roboflow, save its spec, and run it in-process on a local image.

Checks the Save-vs-Publish trap: the published `config` must have steps; the draft lives in
`lastVersionConfig`. Never prints the API key or any URL containing it.

usage: python fetch_and_run_workflow.py <workflow-url-slug> <image> [<image> ...]
"""
import json
import os
import sys
from pathlib import Path

import cv2
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ.get("ROBOFLOW_API_KEY", "")
WS = "eze-nnanna-chijioke"


def fetch(slug: str) -> dict:
    try:
        r = requests.get(f"https://api.roboflow.com/{WS}/workflows/{slug}", params={"api_key": KEY}, timeout=30)
    except requests.RequestException as e:
        sys.exit(f"request failed: {type(e).__name__}")
    if r.status_code != 200:
        sys.exit(f"HTTP {r.status_code} fetching workflow '{slug}' (body: {r.text[:200]!r})")
    return r.json()


def as_spec(cfg):
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    return cfg.get("specification", cfg) if cfg else {}


def main() -> int:
    if not KEY:
        sys.exit("ROBOFLOW_API_KEY missing in .env")
    slug, images = sys.argv[1], sys.argv[2:]
    body = fetch(slug)
    wf = body.get("workflow", body)
    published = as_spec(wf.get("config"))
    draft = as_spec(wf.get("lastVersionConfig"))
    print(f"published steps: {len(published.get('steps', []))} | draft steps: {len(draft.get('steps', []))}")
    if not published.get("steps"):
        sys.exit("published spec has no steps — saved but not published?")

    out = Path("workflows") / f"{slug}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(published, indent=2))
    print(f"saved published spec -> {out}")
    print("inputs :", [i.get("name") for i in published.get("inputs", [])])
    print("steps  :", [(s.get("type"), s.get("name")) for s in published.get("steps", [])])
    print("outputs:", [(o.get("name"), o.get("selector")) for o in published.get("outputs", [])])
    dyn = published.get("dynamic_blocks_definitions", [])
    print("dynamic_blocks_definitions:", [d["manifest"]["block_type"] for d in dyn])

    from inference.core.managers.base import ModelManager
    from inference.core.registries.roboflow import RoboflowModelRegistry
    from inference.core.workflows.core_steps.common.entities import StepExecutionMode
    from inference.core.workflows.execution_engine.core import ExecutionEngine
    from inference.models.utils import ROBOFLOW_MODEL_TYPES

    engine = ExecutionEngine.init(
        workflow_definition=published,
        init_parameters={
            "workflows_core.model_manager": ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES)),
            "workflows_core.api_key": KEY,
            "workflows_core.step_execution_mode": StepExecutionMode.LOCAL,
        },
    )
    input_name = published["inputs"][0]["name"]
    for path in images:
        img = cv2.imread(path)
        res = engine.run(runtime_parameters={input_name: img})[0]
        print(f"{path}: {json.dumps(res, default=str)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
