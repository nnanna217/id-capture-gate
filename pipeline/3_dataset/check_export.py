"""Sanity-check a downloaded Roboflow COCO-segmentation export (exports/<v>/x/{train,valid,test}).

usage: python -I pipeline/3_dataset/check_export.py exports/v1/x
Reports, per split: glare / obstruction instance counts, the share of each shape lying on the document, and (glare) the
share of shapes brighter than their surround; for train, how stable the on-card share is across the 3 augmented copies of a
source image; and any glare shape lying mostly off the card. Run with `python -I` (the export is downloaded data).
"""
import collections
import json
import re
import statistics as st
import sys
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mu


def decode(seg, H, W):
    if isinstance(seg, dict):
        rle = mu.frPyObjects(seg, *seg["size"]) if isinstance(seg["counts"], list) else seg
        m = mu.decode(rle).astype(np.uint8)
        return m if m.shape == (H, W) else cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
    m = np.zeros((H, W), np.uint8)
    for poly in seg:
        if len(poly) >= 6:
            cv2.fillPoly(m, [np.round(np.array(poly, float).reshape(-1, 2)).astype(np.int32)], 1)
    return m


def main(base: Path) -> None:
    stats = collections.defaultdict(lambda: collections.defaultdict(list))
    copies = collections.defaultdict(list)
    off = collections.defaultdict(set)
    for split in ("train", "valid", "test"):
        j = json.load(open(base / split / "_annotations.coco.json"))
        cat = {c["id"]: c["name"] for c in j["categories"]}
        imgs = {i["id"]: i for i in j["images"]}
        by = collections.defaultdict(list)
        for a in j["annotations"]:
            by[a["image_id"]].append(a)
        for iid, anns in by.items():
            info = imgs[iid]
            W, H = info["width"], info["height"]
            src = re.sub(r"_jpg\.rf\..*", "", info["file_name"])
            g = cv2.cvtColor(cv2.imread(str(base / split / info["file_name"])), cv2.COLOR_BGR2GRAY).astype(float)
            doc = np.zeros((H, W), np.uint8)
            for a in anns:
                if cat[a["category_id"]] == "document":
                    doc |= decode(a["segmentation"], H, W)
            for a in anns:
                c = cat[a["category_id"]]
                if c not in ("glare", "obstruction"):
                    continue
                m = decode(a["segmentation"], H, W)
                if not m.sum():
                    stats[(split, c)]["empty"].append(1)
                    continue
                share = float((m & doc).sum() / m.sum())
                stats[(split, c)]["on_card"].append(share)
                copies[(src, c, info["file_name"])].append(share)
                if c == "glare":
                    ring = (cv2.dilate(m, np.ones((9, 9), np.uint8)) - m) & doc
                    if ring.sum() > 10:
                        stats[(split, c)]["delta"].append(float(g[m > 0].mean() - g[ring > 0].mean()))
                    if share < 0.5:
                        off[src].add(split)
    print(f"{'split':6s} {'class':12s} {'n':>4s} {'median on-card share':>22s} {'glare >15 grey levels brighter':>32s} {'empty':>6s}")
    for (split, c), d in sorted(stats.items()):
        n = len(d["on_card"])
        if not n:
            continue
        br = f"{100 * sum(x > 15 for x in d['delta']) / len(d['delta']):.0f}% of {len(d['delta'])}" if d["delta"] else "-"
        print(f"{split:6s} {c:12s} {n:4d} {st.median(d['on_card']):22.2f} {br:>32s} {len(d['empty']):6d}")
    for c in ("glare", "obstruction"):
        per_src = collections.defaultdict(list)
        for (src, cl, fn), v in copies.items():
            if cl == c and fn.startswith(src + "_jpg.rf."):
                per_src[(src, fn)].append(v)
        # one value per (source, copy): mean over that copy's instances; spread across copies of the same source
        by_src = collections.defaultdict(list)
        for (src, fn), v in per_src.items():
            by_src[src].append(st.mean(x for vv in v for x in vv))
        sp = [max(v) - min(v) for v in by_src.values() if len(v) >= 3]
        if sp:
            print(f"{c}: {len(sp)} source images with 3 copies; spread of mean on-card share across copies: median {st.median(sp):.2f}, max {max(sp):.2f}")
    print("glare shapes lying mostly off the card (source: splits):", {k: sorted(v) for k, v in off.items()})


if __name__ == "__main__":
    main(Path(sys.argv[1]))
