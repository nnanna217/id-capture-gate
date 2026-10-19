"""Audit the damage labels on the platform against D-18 (read-only on Roboflow's side; reads local/labels/damage-platform-readback2.json).

usage (from the repo root): python -I pipeline/3_dataset/audit_damage_labels.py
Checks, per kept photo (roles damage, clean, negative in local/captures/damage-manifest.csv):
  every damaged photo has >= 1 `damage` label; no clean or undamaged photo has one; exactly one `document`; at most one `data_zone`,
  a 4-point rectangle (D-03); only the five known classes; `damage` regions that are tiny, huge, outside the card, stacked on each other,
  or far bigger than the usual for their type; `obstruction` labels sitting on damaged photos (allowed, listed). Raster (mask-type) labels are decoded exactly.
"""
import base64
import collections
import csv
import json
import zlib

import cv2
import numpy as np
from pycocotools import mask as mu

CLASSES = {"document", "data_zone", "glare", "obstruction", "damage"}


def shape(b, w, h):
    """A label's pixels. Polygons are filled; raster `mask` labels are COCO run-length data for the WHOLE image (base64 + zlib), decoded exactly
    (checked: the decoded area equals the stored `area`); the bounding box is only the fallback if decoding fails."""
    m = np.zeros((h, w), np.uint8)
    if b.get("type") == "polygon" and b.get("points"):
        cv2.fillPoly(m, [np.array(b["points"], np.int32)], 1)
        return m.astype(bool)
    try:
        return mu.decode({"size": [h, w], "counts": zlib.decompress(base64.b64decode(b["mask"]))}).astype(bool)
    except Exception:
        bw, bh = int(float(b["width"])), int(float(b["height"]))
        x0, y0 = int(float(b["x"]) - bw / 2), int(float(b["y"]) - bh / 2)
        m[max(0, y0):max(0, y0) + bh, max(0, x0):max(0, x0) + bw] = 1
        return m.astype(bool)


def main():
    D = json.load(open("local/labels/damage-platform-readback2.json"))
    man = {r["file"].rsplit("/", 1)[1]: r for r in csv.DictReader(open("local/captures/damage-manifest.csv"))}
    split = {r["group"]: r["split"] for r in csv.DictReader(open("data/damage-split.csv"))}
    issues, rows = collections.defaultdict(list), []
    for n, d in D.items():
        a = d.get("annotation") or {}
        bx, w, h = a.get("boxes", []), a.get("width"), a.get("height")
        m = man[n]
        role, defect = m["role"], m["defect"]
        lab = collections.Counter(b["label"] for b in bx)
        for c in lab:
            if c not in CLASSES:
                issues["unknown class"].append((n, c))
        if role == "damage" and lab["damage"] == 0:
            issues["damaged photo with NO damage label"].append(n)
        if role != "damage" and lab["damage"]:
            issues["undamaged photo WITH a damage label"].append((n, lab["damage"]))
        if lab["document"] != 1:
            issues["not exactly one document"].append((n, lab["document"]))
        if lab["data_zone"] > 1:
            issues["more than one data_zone"].append((n, lab["data_zone"]))
        for b in bx:
            if b["label"] == "data_zone" and b.get("type") == "polygon" and len(b.get("points", [])) != 4:
                issues["data_zone not a 4-point rectangle"].append((n, len(b["points"])))
        doc = [b for b in bx if b["label"] == "document"]
        zon = [b for b in bx if b["label"] == "data_zone"]
        dm = [b for b in bx if b["label"] == "damage"]
        if dm and doc and w and h:
            D_ = shape(doc[0], w, h)
            masks = [shape(b, w, h) for b in dm]
            U = np.any(masks, axis=0)
            frac = U.sum() / max(1, D_.sum())
            outside = (U & ~D_).sum() / max(1, U.sum())
            cov = (U & shape(zon[0], w, h)).sum() / max(1, shape(zon[0], w, h).sum()) if zon else None
            # damage polygons lying on top of each other (a label drawn twice)
            for i in range(len(masks)):
                for j in range(i + 1, len(masks)):
                    inter = (masks[i] & masks[j]).sum()
                    if inter / max(1, min(masks[i].sum(), masks[j].sum())) > 0.8:
                        issues["two damage labels on top of each other"].append(n)
            rows.append(dict(n=n, defect=defect, split=split[m["group"]], k=len(dm), frac=float(frac), outside=float(outside), cov=cov,
                             mask=any(b.get("type") == "mask" for b in dm), obs=lab["obstruction"]))
        if len(dm) > 3:
            issues["more than 3 damage labels"].append((n, len(dm)))
    print(f"photos audited: {len(D)} | damaged {sum(1 for n in D if man[n]['role'] == 'damage')} | clean {sum(1 for n in D if man[n]['role'] == 'clean')} | undamaged/fingers/bow {sum(1 for n in D if man[n]['role'] == 'negative')}")
    print(f"\n{'type':12}{'photos':>7}{'labels':>7}{'per photo':>10}{'% of card (median)':>20}{'% of text zone (median)':>25}{'mask-type':>10}")
    by = collections.defaultdict(list)
    for r in rows:
        by[r["defect"]].append(r)
    for t, v in sorted(by.items()):
        cv = [x["cov"] for x in v if x["cov"] is not None]
        print(f"{t:12}{len(v):7d}{sum(x['k'] for x in v):7d}{np.mean([x['k'] for x in v]):10.1f}{100 * np.median([x['frac'] for x in v]):19.1f}%{100 * (np.median(cv) if cv else 0):24.0f}%{sum(x['mask'] for x in v):10d}")
        med = np.median([x["frac"] for x in v])
        for x in v:
            if x["frac"] < 0.002:
                issues["damage region tiny (<0.2% of the card)"].append((x["n"], round(100 * x["frac"], 2)))
            if x["outside"] > 0.25:
                issues["damage region mostly outside the card outline (>25%)"].append((x["n"], round(100 * x["outside"])))
            if len(v) >= 4 and x["frac"] > max(4 * med, 0.15) and t != "stain":
                issues[f"damage region unusually large for a {t}"].append((x["n"], round(100 * x["frac"], 1)))
    print("\nlabels by split (damage):", {s: sum(r["k"] for r in rows if r["split"] == s) for s in ("train", "valid", "test")},
          "| photos:", {s: sum(1 for r in rows if r["split"] == s) for s in ("train", "valid", "test")})
    obs_on_neg = sum(1 for n, d in D.items() if man[n]["defect"] == "fingers" and any(b["label"] == "obstruction" for b in (d.get("annotation") or {}).get("boxes", [])))
    print("fingers photos carrying an obstruction label:", obs_on_neg, "of", sum(1 for n in D if man[n]["defect"] == "fingers"))
    print("\nISSUES" if issues else "\nNO ISSUES")
    for k, v in issues.items():
        print(f"  {k}: {len(v)}  {v[:6]}")


if __name__ == "__main__":
    main()
