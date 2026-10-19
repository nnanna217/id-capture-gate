"""What would `damage` AP be if the class covered fewer damage types? An ESTIMATE from the existing model, with no retraining.

usage (from the repo root): python -I pipeline/4_train_eval/damage_scope_test.py --model capture-gate/3 --export local/exports/v3/x --keep fold_corner,stain,tear
Runs the model once on every valid and test photo, then scores `damage` (COCO mask AP, AP50 and AP50:95) under three definitions:
  all types              the ground truth as it is
  scoped, drop others    only the kept types count, and photos whose damage is an excluded type are left out of the scoring entirely
                         (what the number would look like if the excluded types were simply never shown to the gate)
  scoped, others = none  only the kept types count, but photos with an excluded type stay in with NO ground truth, so any damage the model
                         finds on them is a false positive (the harshest reading)
A model RETRAINED on the narrower definition would behave differently from this one (no confusion from the excluded types, but fewer examples);
these numbers bound the question, they do not answer it.
"""
import argparse
import csv
import io
import contextlib
import json
import os
import re
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from pycocotools import mask as mu
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

import importlib.util
spec = importlib.util.spec_from_file_location("diag", Path(__file__).with_name("damage_diagnosis.py"))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


def rle(m):
    r = mu.encode(np.asfortranarray(m.astype(np.uint8)))
    r["counts"] = r["counts"].decode()
    return r


def ap(images, gts, preds):
    """images: [id]; gts: [(image_id, mask)]; preds: [(image_id, conf, mask)] -> (AP50, AP50:95, n_gt)"""
    if not gts:
        return float("nan"), float("nan"), 0
    d = {"images": [{"id": i, "height": 1, "width": 1} for i in images], "categories": [{"id": 1, "name": "damage"}], "annotations": []}
    for k, (i, m) in enumerate(gts):
        s = rle(m)
        d["annotations"].append({"id": k + 1, "image_id": i, "category_id": 1, "segmentation": s, "area": float(mu.area(s)), "bbox": list(mu.toBbox(s)), "iscrowd": 0})
    with contextlib.redirect_stdout(io.StringIO()):
        g = COCO()
        g.dataset = d
        g.createIndex()
        res = [{"image_id": i, "category_id": 1, "segmentation": rle(m), "score": c} for i, c, m in preds]
        if not res:
            return 0.0, 0.0, len(gts)
        dt = g.loadRes(res)
        e = COCOeval(g, dt, "segm")
        e.evaluate(); e.accumulate(); e.summarize()
    return float(e.stats[1]), float(e.stats[0]), len(gts)


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--model", required=True)
    ap_.add_argument("--export", required=True)
    ap_.add_argument("--keep", required=True, help="comma list of defect types that stay in the class")
    a = ap_.parse_args()
    keep = set(a.keep.split(","))
    load_dotenv(".env")
    from inference import get_model
    model = get_model(a.model, api_key=os.environ["ROBOFLOW_API_KEY"])
    man = {r["file"].rsplit("/", 1)[1]: r for r in csv.DictReader(open("local/captures/damage-manifest.csv"))}
    data = {}                                    # split -> list of (id, defect or None, gtmask, preds)
    n = 0
    for sp in ("valid", "test"):
        c = json.load(open(Path(a.export) / sp / "_annotations.coco.json"))
        cats = {x["id"]: x["name"] for x in c["categories"]}
        by = {}
        for x in c["annotations"]:
            by.setdefault(x["image_id"], []).append(x)
        rows = []
        for im in c["images"]:
            orig = re.sub(r"_jpg\.rf\..*$", ".jpg", im["file_name"])
            img = cv2.imread(str(Path(a.export) / sp / im["file_name"]))
            h, w = img.shape[:2]
            r = model.infer(img, confidence=0.01)
            r = r[0] if isinstance(r, list) else r
            gt = [diag.coco_mask(x["segmentation"], h, w) for x in by.get(im["id"], []) if cats[x["category_id"]] == "damage"]
            n += 1
            rows.append((n, man[orig]["defect"] if gt and orig in man else None, np.any(gt, axis=0) if gt else None, [(n, cf, m) for cf, m in diag.pred_masks(r, h, w)]))
        data[sp] = rows

    def score(rows, mode):
        ids, gts, preds = [], [], []
        for i, d, g, p in rows:
            out = d is not None and d not in keep
            if mode == "drop" and out:
                continue
            ids.append(i)
            if g is not None and (mode == "all" or d in keep):
                gts.append((i, g))
            preds += p
        return ap(ids, gts, preds)

    print(f"kept types: {sorted(keep)}\n")
    print(f"{'definition':28}{'split':>12}{'damage GT':>10}{'AP50':>8}{'AP50:95':>9}")
    for label, mode in (("all types (as trained)", "all"), ("scoped, drop others", "drop"), ("scoped, others = none", "none")):
        for sp, rows in (("valid", data["valid"]), ("test", data["test"]), ("valid + test", data["valid"] + data["test"])):
            a50, a95, ng = score(rows, mode)
            print(f"{label:28}{sp:>12}{ng:10d}{a50:8.3f}{a95:9.3f}")
        print()


if __name__ == "__main__":
    main()
