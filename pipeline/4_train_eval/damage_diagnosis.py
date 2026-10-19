"""Where does the `damage` class fail? Per photo and per defect type, on the valid and test splits (photos the model never trained on),
plus false alarms on photos with no damage.

usage (from the repo root): python -I pipeline/4_train_eval/damage_diagnosis.py --model capture-gate/3 --export local/exports/v3/x
For every valid/test photo with a ground-truth damage region (from the export, defect type from local/captures/damage-manifest.csv):
  best_conf   the highest `damage` confidence the model gives that photo (model run at confidence 0.01)
  found@t     a damage mask at confidence >= t that overlaps the ground-truth region with IoU >= 0.5 (t = 0.4 is the block's own cut-off)
  hit@t       any damage mask at all at confidence >= t (looser: right place not required)
False alarms: photos with NO damage label (the 152 older photos plus the clean and bow/tilt photos), any `damage` mask at confidence >= t,
reported separately for photos the model trained on (optimistic) and photos it did not.
The key is read from .env and never printed.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from pycocotools import mask as mu


def coco_mask(seg, h, w):
    if isinstance(seg, dict):
        rle = mu.frPyObjects(seg, h, w) if isinstance(seg["counts"], list) else seg
        return mu.decode(rle).astype(bool)
    rles = mu.frPyObjects(seg, h, w)
    return mu.decode(mu.merge(rles)).astype(bool)


def pred_masks(r, h, w):
    out = []
    for p in r.predictions:
        if p.class_name != "damage":
            continue
        m = np.zeros((h, w), np.uint8)
        pts = np.array([[q.x, q.y] for q in p.points], np.int32)
        if len(pts) >= 3:
            cv2.fillPoly(m, [pts], 1)
        out.append((float(p.confidence), m.astype(bool)))
    return out


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--export", required=True)
    a = ap.parse_args()
    load_dotenv(".env")
    from inference import get_model
    model = get_model(a.model, api_key=os.environ["ROBOFLOW_API_KEY"])
    man = {r["file"].rsplit("/", 1)[1]: r for r in csv.DictReader(open("local/captures/damage-manifest.csv"))}
    split = {r["group"]: r["split"] for r in csv.DictReader(open("data/damage-split.csv"))}
    ths = (0.4, 0.25, 0.1)

    rows = []
    for sp in ("valid", "test"):
        c = json.load(open(Path(a.export) / sp / "_annotations.coco.json"))
        cats = {x["id"]: x["name"] for x in c["categories"]}
        by = defaultdict(list)
        for x in c["annotations"]:
            by[x["image_id"]].append(x)
        for im in c["images"]:
            orig = re.sub(r"_jpg\.rf\..*$", ".jpg", im["file_name"])
            img = cv2.imread(str(Path(a.export) / sp / im["file_name"]))
            h, w = img.shape[:2]
            r = model.infer(img, confidence=0.01)
            r = r[0] if isinstance(r, list) else r
            preds = pred_masks(r, h, w)
            gt = [coco_mask(x["segmentation"], h, w) for x in by[im["id"]] if cats[x["category_id"]] == "damage"]
            gtu = np.any(gt, axis=0) if gt else None
            best = max((p[0] for p in preds), default=0.0)
            found = {t: any(c >= t and gtu is not None and iou(m, gtu) >= 0.5 for c, m in preds) for t in ths}
            hit = {t: any(c >= t for c, _ in preds) for t in ths}
            mi = man.get(orig)
            rows.append(dict(split=sp, file=orig, defect=(mi["defect"] if mi and gt else ("none" if not gt else "?")), has_gt=bool(gt),
                             gt_frac=float(gtu.mean()) if gtu is not None else 0.0, best=best, found=found, hit=hit))

    print(f"\n== photos WITH damage in valid/test: did the model find it? (never trained on these)")
    print(f"{'defect':13}{'split':>6}{'photos':>7}{'best conf (median)':>20}{'found@0.4':>11}{'found@0.25':>12}{'found@0.1':>11}{'hit@0.25':>10}")
    g = defaultdict(list)
    for x in rows:
        if x["has_gt"]:
            g[(x["defect"], x["split"])].append(x)
    for (d, sp), v in sorted(g.items()):
        print(f"{d:13}{sp:>6}{len(v):7d}{np.median([x['best'] for x in v]):20.2f}"
              + "".join(f"{sum(x['found'][t] for x in v):8d}/{len(v):<2d}" if i < 3 else f"{sum(x['hit'][0.25] for x in v):7d}/{len(v):<2d}" for i, t in enumerate(ths + (0.25,))))
    allv = [x for x in rows if x["has_gt"]]
    print(f"{'ALL':13}{'':>6}{len(allv):7d}{np.median([x['best'] for x in allv]):20.2f}"
          + "".join(f"{sum(x['found'][t] for x in allv):8d}/{len(allv):<2d}" for t in ths))
    print("\nper photo (valid/test, with damage):")
    for x in sorted(allv, key=lambda x: (x["split"], x["defect"], x["file"])):
        print(f"  {x['split']:5} {x['defect']:13} {x['file']:24} gt {100 * x['gt_frac']:4.1f}% of image  best conf {x['best']:.2f}  found@0.25 {x['found'][0.25]}")

    # false alarms on photos with no damage label: valid/test negatives from the export, and the older/staged photos
    neg = [x for x in rows if not x["has_gt"]]
    print(f"\n== photos with NO damage in valid/test (never trained on): {len(neg)}")
    for t in ths:
        print(f"   damage mask at conf >= {t}: {sum(x['hit'][t] for x in neg)} of {len(neg)}")
    print("   worst:", sorted(((round(x['best'], 2), x['file']) for x in neg), reverse=True)[:5])


if __name__ == "__main__":
    main()
