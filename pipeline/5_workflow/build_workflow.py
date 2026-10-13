"""Build the capture-gate verdict Workflow spec: trained segmentation model -> custom verdict block.

The custom block's code is the text published on the platform (workflows/verdict_block_editor.py, generated from verdict_block.py).
Writes workflows/capture-gate-verdict.json. Run from the repo root:
    python -I pipeline/5_workflow/build_workflow.py
"""
import json
from pathlib import Path

MODEL_ID = "eze-nnanna-chijioke/capture-gate-2-rfdetr-seg-nano-t1"   # the trained model, as the platform names it
SRC, EDITOR = Path("pipeline/5_workflow/verdict_block.py"), Path("workflows/verdict_block_editor.py")
if not EDITOR.exists() or EDITOR.stat().st_mtime < SRC.stat().st_mtime:
    raise SystemExit("workflows/verdict_block_editor.py is missing or older than verdict_block.py: run make_editor_block.py first")
CODE = EDITOR.read_text()   # the exact text published on the platform (single-function form), not the module-level source


def num_input(default):
    return {"type": "DynamicInputDefinition", "value_types": ["float"], "has_default_value": True, "default_value": default}


SPEC = {
    "version": "1.0",
    "inputs": [{"type": "WorkflowImage", "name": "image"}],
    "dynamic_blocks_definitions": [{
        "type": "DynamicBlockDefinition",
        "manifest": {
            "type": "ManifestDescription",
            "block_type": "CaptureVerdict",
            "inputs": {
                "image": {"type": "DynamicInputDefinition", "selector_types": ["input_image"]},
                "predictions": {"type": "DynamicInputDefinition", "selector_types": ["step_output"],
                                "selector_data_kind": {"step_output": ["instance_segmentation_prediction"]}},
                "min_confidence": num_input(0.4),
                "dark_p95": num_input(110.0),
                "blur_min_block": num_input(0.43),
                "blur_min_wide": num_input(0.70),
                "wide_aspect": num_input(2.5),
                "overlap_min": num_input(0.02),
                "edge_margin_px": num_input(2.0),
                "covered_card": num_input(0.9),
            },
            "outputs": {
                "verdict": {"type": "DynamicOutputDefinition", "kind": ["string"]},
                "reasons": {"type": "DynamicOutputDefinition", "kind": ["list_of_values"]},
                "guidance": {"type": "DynamicOutputDefinition", "kind": ["string"]},
                "details": {"type": "DynamicOutputDefinition", "kind": ["dictionary"]},
            },
        },
        "code": {"type": "PythonCode", "run_function_code": CODE, "run_function_name": "run"},
    }],
    "steps": [
        {"type": "roboflow_core/roboflow_instance_segmentation_model@v4", "name": "model", "model_id": MODEL_ID,
         "confidence_mode": "custom", "custom_confidence": 0.25, "images": "$inputs.image"},
        {"type": "CaptureVerdict", "name": "capture_verdict", "image": "$inputs.image", "predictions": "$steps.model.predictions"},
    ],
    "outputs": [
        {"type": "JsonField", "name": "verdict", "selector": "$steps.capture_verdict.verdict"},
        {"type": "JsonField", "name": "reasons", "selector": "$steps.capture_verdict.reasons"},
        {"type": "JsonField", "name": "guidance", "selector": "$steps.capture_verdict.guidance"},
        {"type": "JsonField", "name": "details", "selector": "$steps.capture_verdict.details"},
        {"type": "JsonField", "name": "predictions", "selector": "$steps.model.predictions"},
    ],
}

if __name__ == "__main__":
    out = Path("workflows/capture-gate-verdict.json")
    out.write_text(json.dumps(SPEC, indent=2))
    print(f"wrote {out} ({out.stat().st_size} bytes); block code {len(CODE)} characters; model {MODEL_ID}")
