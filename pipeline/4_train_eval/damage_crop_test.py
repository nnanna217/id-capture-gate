"""Does cropping to the card help the `damage` class? A cheap test with NO retraining (the idea from the crop-then-classify advice).

usage (from the repo root): python -I pipeline/4_train_eval/damage_crop_test.py --model capture-gate/3 --export local/exports/v3/x
For each valid/test photo: run the model on the full 1920 px photo (as the diagnosis does), then crop to the card (the model's own `document`
mask, bounding box plus a 6% margin) and run the SAME model on the crop, so the card fills the 312 px input. Compare against the ground-truth
damage region (export masks scaled to the full photo and cropped the same way). The model was NOT trained on crops, so a gain here means the
crop idea has legs; a retrain on crops would do better still. Also counts false alarms on valid/test photos with no damage.
"""
import argparse
import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

import importlib.util
spec = importlib.util.spec_from_file_location("diag", Path(__file__).with_name("damage_diagnosis.py"))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

ORIGINALS = ["local/upload/damage/train", "local/upload/damage/valid", "local/upload/damage/test", "local/upload/own", "local/upload/new"]


def find(name):
    for d in ORIGINALS:
        if (Path(d) / name).exists():
            return Path(d) / name
    return None


def doc_box(r, h, w, margin=0.06):
    best = None
    for p in r.predictions:
        if p.class_name == "document" and (best is None or p.confidence > best.confidence):
            best = p
    if best is None:
        return None
    xs = [q.x for q in best.points]
    ys = [q.y for q in best.points]
    bw, bh = max(xs) - min(xs), max(ys) - min(ys)
    x0, x1 = int(max(0, min(xs) - margin * bw)), int(min(w, max(xs) + margin * bw))
    y0, y1 = int(max(0, min(ys) - margin * bh)), int(min(h, max(ys) + margin * bh))
    return (x0, y0, x1, y1) if x1 - x0 > 20 and y1 - y0 > 20 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--export", required=True)
    a = ap.parse_args()
    load_dotenv(".env")
    from inference import get_model
    model = get_model(a.model, api_key=os.environ["ROBOFLOW_API_KEY"])
    man = {r["file"].rsplit("/", 1)[1]: r for r in csv.DictReader(open("local/captures/damage-manifest.csv"))}
    ths = (0.4, 0.25)
    pos = defaultdict(lambda: [0, 0, 0, 0])      # defect -> [n, full@0.4, crop@0.4, crop@0.25]
    neg = [0, 0, 0]                              # n, full@0.4 alarms, crop@0.4 alarms
    skipped = 0
    for sp in ("valid", "test"):
        c = json.load(open(Path(a.export) / sp / "_annotations.coco.json"))
        cats = {x["id"]: x["name"] for x in c["categories"]}
        by = defaultdict(list)
        for x in c["annotations"]:
            by[x["image_id"]].append(x)
        for im in c["images"]:
            orig = re.sub(r"_jpg\.rf\..*$", ".jpg", im["file_name"])
            p = find(orig)
            if p is None:
                skipped += 1
                continue
            img = cv2.imread(str(p))
            H, W = img.shape[:2]
            gts = [diag.coco_mask(x["segmentation"], im["height"], im["width"]) for x in by[im["id"]] if cats[x["category_id"]] == "damage"]
            gt = cv2.resize(np.any(gts, axis=0).astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST).astype(bool) if gts else None
            r = model.infer(img, confidence=0.01)
            r = r[0] if isinstance(r, list) else r
            full = diag.pred_masks(r, H, W)
            box = doc_box(r, H, W)
            crop = []
            if box:
                x0, y0, x1, y1 = box
                rc = model.infer(img[y0:y1, x0:x1], confidence=0.01)
                rc = rc[0] if isinstance(rc, list) else rc
                crop = diag.pred_masks(rc, y1 - y0, x1 - x0)
                gtc = gt[y0:y1, x0:x1] if gt is not None else None
            if gt is not None:
                d = man[orig]["defect"]
                s = pos[d]
                s[0] += 1
                s[1] += any(cf >= 0.4 and diag.iou(m, gt) >= 0.5 for cf, m in full)
                if box:
                    s[2] += any(cf >= 0.4 and diag.iou(m, gtc) >= 0.5 for cf, m in crop)
                    s[3] += any(cf >= 0.25 and diag.iou(m, gtc) >= 0.5 for cf, m in crop)
            else:
                neg[0] += 1
                neg[1] += any(cf >= 0.4 for cf, _ in full)
                neg[2] += any(cf >= 0.4 for cf, _ in crop)
    print(f"{'defect':13}{'photos':>7}{'full photo @0.4':>17}{'card crop @0.4':>16}{'card crop @0.25':>17}")
    tot = [0, 0, 0, 0]
    for d, s in sorted(pos.items()):
        print(f"{d:13}{s[0]:7d}{s[1]:12d}/{s[0]:<3d}{s[2]:11d}/{s[0]:<3d}{s[3]:12d}/{s[0]:<3d}")
        tot = [x + y for x, y in zip(tot, s)]
    print(f"{'ALL':13}{tot[0]:7d}{tot[1]:12d}/{tot[0]:<3d}{tot[2]:11d}/{tot[0]:<3d}{tot[3]:12d}/{tot[0]:<3d}")
    print(f"\nno-damage photos (valid/test): {neg[0]} | false alarms at 0.4: full photo {neg[1]}, card crop {neg[2]} | skipped (original not found): {skipped}")


if __name__ == "__main__":
    main()
