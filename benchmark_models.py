"""Latency of COCO-pretrained RF-DETR checkpoints on this machine (speed only; the weights are irrelevant to timing).

Same architecture and input size as the models that would be trained, so this is a fair preview of the demo's frame rate
for detection vs segmentation. usage: python benchmark_models.py <image> [alias ...]
Times include Inference's pre/post-processing (model.infer), not camera or drawing. One image, repeated.
"""
import statistics as st
import sys
import time

import cv2

DEFAULT = ["rfdetr-nano", "rfdetr-seg-nano", "rfdetr-seg-small"]


def main() -> None:
    img = cv2.imread(sys.argv[1])
    aliases = sys.argv[2:] or DEFAULT
    from inference import get_model
    import onnxruntime as ort
    print("onnxruntime providers available:", ort.get_available_providers())
    print(f"image {img.shape[1]}x{img.shape[0]}")
    for a in aliases:
        try:
            t0 = time.time()
            m = get_model(a)
            load = time.time() - t0
            m.infer(img)  # first call (warm-up, includes provider compile)
            for _ in range(2):
                m.infer(img)
            ts = []
            for _ in range(20):
                t = time.perf_counter()
                r = m.infer(img)
                ts.append((time.perf_counter() - t) * 1000)
            ts.sort()
            n = len(r[0].predictions) if isinstance(r, list) else len(r.predictions)
            print(f"{a}: load {load:.1f}s | 20 runs ms: p50 {st.median(ts):.0f}  p95 {ts[18]:.0f}  min {ts[0]:.0f}  max {ts[-1]:.0f}"
                  f" | {1000 / st.median(ts):.2f} fps at p50 | detections on this image: {n}")
        except Exception as e:  # keep going: report what failed
            print(f"{a}: FAILED {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
