"""Phase 0 spike: can the in-process Inference library run a Dynamic Python block?

No API key, no personal images. A synthetic sharp image and a blurred copy go through
a workflow whose only step is a custom block returning the variance of the Laplacian.
Pass condition: the block executes and sharp > blurred.
"""
import json
import sys

import cv2
import numpy as np

from inference.core.managers.base import ModelManager
from inference.core.registries.roboflow import RoboflowModelRegistry
from inference.core.workflows.core_steps.common.entities import StepExecutionMode
from inference.core.workflows.execution_engine.core import ExecutionEngine
from inference.models.utils import ROBOFLOW_MODEL_TYPES

RUN_CODE = """
def run(self, image: WorkflowImageData) -> BlockResult:
    gray = cv2.cvtColor(image.numpy_image, cv2.COLOR_BGR2GRAY)
    return {"laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var())}
"""

SPEC = {
    "version": "1.0",
    "inputs": [{"type": "WorkflowImage", "name": "image"}],
    "dynamic_blocks_definitions": [
        {
            "type": "DynamicBlockDefinition",
            "manifest": {
                "type": "ManifestDescription",
                "block_type": "LaplacianVariance",
                "inputs": {
                    "image": {
                        "type": "DynamicInputDefinition",
                        "selector_types": ["input_image"],
                    }
                },
                "outputs": {
                    "laplacian_variance": {"type": "DynamicOutputDefinition", "kind": ["float"]}
                },
            },
            "code": {"type": "PythonCode", "run_function_code": RUN_CODE},
        }
    ],
    "steps": [{"type": "LaplacianVariance", "name": "blur", "image": "$inputs.image"}],
    "outputs": [{"type": "JsonField", "name": "laplacian_variance", "selector": "$steps.blur.laplacian_variance"}],
}


def main() -> int:
    rng = np.random.default_rng(0)
    sharp = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(sharp, (0, 0), 5)

    mm = ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES))
    engine = ExecutionEngine.init(
        workflow_definition=SPEC,
        init_parameters={
            "workflows_core.model_manager": mm,
            "workflows_core.api_key": None,
            "workflows_core.step_execution_mode": StepExecutionMode.LOCAL,
        },
    )
    results = {}
    for name, img in (("sharp", sharp), ("blurred", blurred)):
        out = engine.run(runtime_parameters={"image": img})
        results[name] = out[0]["laplacian_variance"]
        print(f"{name}: {json.dumps(out[0])}")
    ok = results["sharp"] > results["blurred"]
    print("SPIKE PASS" if ok else "SPIKE FAIL: block ran but ordering is wrong")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
