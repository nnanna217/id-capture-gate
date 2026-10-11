"""Per-class mask AP for a trained Roboflow segmentation model, run locally through Inference.

The platform's results card shows only a headline mAP; this reports AP per class with the number of ground-truth instances
beside it, because with few instances a per-class AP is anecdotal.

usage:
  python -I pipeline/4_train_eval/evaluate_model.py --model capture-gate/2 --coco local/exports/v2/x/valid           # valid split of the v2 export
  python -I pipeline/4_train_eval/evaluate_model.py --model capture-gate/2 --coco local/exports/v2/x/test
  python -I pipeline/4_train_eval/evaluate_model.py --model capture-gate/2 --midv                               # held-out MIDV Clutter (document, data_zone only)
  python -I pipeline/4_train_eval/evaluate_model.py --selftest --coco local/exports/v2/x/valid                        # ground truth as predictions: every AP must be 1.0

Metric: COCO mask AP (pycocotools), AP = mean over IoU 0.50:0.95 and 101 recall points, AP50 = IoU 0.50. The model is run at
confidence 0.01 so the precision-recall curve is complete. Run with `python -I`; the key is read from .env, never printed.
"""
import argparse
import collections
import contextlib
import io
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mu
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

CLASSES = ["document", "data_zone", "glare", "obstruction"]


def poly_mask(points, h, w):
    m = np.zeros((h, w), np.uint8)
    pts = np.round(np.array(points, float)).astype(np.int32).reshape(-1, 2)
    if len(pts) >= 3:
        cv2.fillPoly(m, [pts], 1)
    return m


def to_rle(seg, h, w):
    """Polygon list or run-length dict -> compressed RLE with a str 'counts' (what COCOeval needs for results)."""
    if isinstance(seg, dict):
        rle = mu.frPyObjects(seg, *seg["size"]) if isinstance(seg["counts"], list) else dict(seg)
    else:
        polys = [p for p in seg if len(p) >= 6]
        rle = mu.merge(mu.frPyObjects(polys, h, w)) if polys else mu.encode(np.asfortranarray(np.zeros((h, w), np.uint8)))
    if isinstance(rle["counts"], bytes):
        rle["counts"] = rle["counts"].decode()
    return rle


def gt_from_midv(split_dir="local/midv-500/tiff/heldout_clutter", labels="local/midv-500/tiff/labels.json"):
    """COCO-style ground truth for the held-out Clutter frames: document and data_zone polygons only."""
    L = json.load(open(labels))
    images, anns, aid = [], [], 1
    cats = [{"id": i + 1, "name": c} for i, c in enumerate(CLASSES)]
    for iid, (key, v) in enumerate((k, v) for k, v in sorted(L.items()) if v["split"] == "heldout_clutter"):
        images.append({"id": iid + 1, "file_name": Path(key).name, "width": v["width"], "height": v["height"]})
        for o in v["objects"]:
            m = poly_mask(o["polygon"], v["height"], v["width"])
            rle = mu.encode(np.asfortranarray(m))
            rle["counts"] = rle["counts"].decode()
            anns.append({"id": aid, "image_id": iid + 1, "category_id": CLASSES.index(o["class"]) + 1,
                         "segmentation": rle, "area": float(m.sum()), "bbox": list(map(float, mu.toBbox(rle))), "iscrowd": 0})
            aid += 1
    return {"images": images, "annotations": anns, "categories": cats}, Path(split_dir)


def evaluate(gt_dict, preds, label):
    quiet = io.StringIO()
    gt = COCO()
    gt.dataset = gt_dict
    with contextlib.redirect_stdout(quiet):
        gt.createIndex()
    if not preds:
        print(f"{label}: the model returned no predictions at all")
        return
    with contextlib.redirect_stdout(quiet):
        dt = gt.loadRes(preds)
    out = []
    for cat in gt_dict["categories"]:
        n = sum(1 for a in gt_dict["annotations"] if a["category_id"] == cat["id"])
        if n == 0:
            continue
        ev = COCOeval(gt, dt, "segm")
        ev.params.catIds = [cat["id"]]
        with contextlib.redirect_stdout(quiet):
            ev.evaluate(); ev.accumulate()
        p = ev.eval["precision"][:, :, 0, 0, 2]          # [iou, recall] for area=all, maxDets=100
        ap = float(np.mean(p[p > -1])) if (p > -1).any() else float("nan")
        p50 = ev.eval["precision"][0, :, 0, 0, 2]
        ap50 = float(np.mean(p50[p50 > -1])) if (p50 > -1).any() else float("nan")
        out.append((cat["name"], n, ap50, ap))
    print(f"\n{label}")
    print(f"{'class':12s} {'GT instances':>13s} {'AP50':>7s} {'AP50:95':>8s}")
    for name, n, ap50, ap in out:
        print(f"{name:12s} {n:13d} {ap50:7.3f} {ap:8.3f}")
    print("(per-class numbers on fewer than about 20 instances are anecdotal)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--coco", help="export split folder containing _annotations.coco.json and the images")
    ap.add_argument("--midv", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--conf", type=float, default=0.01)
    a = ap.parse_args()

    if a.midv:
        gt_dict, img_dir = gt_from_midv()
    else:
        img_dir = Path(a.coco)
        gt_dict = json.load(open(img_dir / "_annotations.coco.json"))
        names = {c["id"]: c["name"] for c in gt_dict["categories"]}
        # keep the four project classes; drop the platform's placeholder category
        keep = {i: n for i, n in names.items() if n in CLASSES}
        gt_dict["categories"] = [{"id": i, "name": n} for i, n in keep.items()]
        gt_dict["annotations"] = [x for x in gt_dict["annotations"] if x["category_id"] in keep]
    cat_by_name = {c["name"]: c["id"] for c in gt_dict["categories"]}

    preds = []
    if a.selftest:
        size = {im["id"]: (im["height"], im["width"]) for im in gt_dict["images"]}
        for x in gt_dict["annotations"]:
            h, w = size[x["image_id"]]
            preds.append({"image_id": x["image_id"], "category_id": x["category_id"], "segmentation": to_rle(x["segmentation"], h, w), "score": 1.0})
        evaluate(gt_dict, preds, f"SELFTEST (ground truth as predictions) on {img_dir}")
        return

    from dotenv import load_dotenv
    from inference import get_model
    load_dotenv(".env")
    key = os.environ.get("ROBOFLOW_API_KEY", "")
    if not key:
        sys.exit("ROBOFLOW_API_KEY missing in .env")
    model = get_model(a.model, api_key=key)
    counts = collections.Counter()
    for im in gt_dict["images"]:
        img = cv2.imread(str(img_dir / im["file_name"]))
        h, w = img.shape[:2]
        r = model.infer(img, confidence=a.conf)
        r = r[0] if isinstance(r, list) else r
        for p in r.predictions:
            if p.class_name not in cat_by_name:
                continue
            m = poly_mask([(q.x, q.y) for q in p.points], h, w)
            if m.sum() == 0:
                continue
            rle = mu.encode(np.asfortranarray(m))
            rle["counts"] = rle["counts"].decode()
            preds.append({"image_id": im["id"], "category_id": cat_by_name[p.class_name], "segmentation": rle, "score": float(p.confidence)})
            counts[p.class_name] += 1
    print("predictions kept per class:", dict(counts))
    evaluate(gt_dict, preds, f"{a.model} on {'MIDV held-out Clutter' if a.midv else img_dir}")


if __name__ == "__main__":
    main()
