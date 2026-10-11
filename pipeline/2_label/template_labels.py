"""Locate each mock card in each frame by matching its printed design (SIFT + RANSAC homography), then derive:
  document  = the template card rectangle projected into the frame, clipped to the image
  data_zone = the template's text-block rectangle (see specimens/generate_mock_cards.py) projected into the frame, clipped
No hand labelling: the cards have a fixed, known layout. glare / obstruction are NOT derivable and stay manual.

usage: python -I pipeline/2_label/template_labels.py [--list upload/own-set.csv] [--images upload/own] [--out labels/template-labels.json]
Writes labels/template-labels.json (gitignored) and prints success rate by card and condition.
A frame "fails" when too few good matches survive RANSAC; failures are listed, never guessed.
"""
import argparse
import collections
import csv
import json
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon, box

TEMPLATES = {"id": "specimens/cards/print-id.png", "bank": "specimens/cards/print-bank.png"}  # the PDF as printed, rendered at 300 dpi
# tight text-block rectangles in template pixels: measured text bbox of the printed render + 10 px margin
# (ID text bbox 329,102-639,502; bank 36,246-908,439). The first version used the whole right panel and was ~2x too wide.
ZONES = {"id": (319, 92, 649, 512), "bank": (26, 236, 918, 449)}
MIN_INLIERS = 20
MAX_EDGE = 1280


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', default='upload/own-set.csv')
    ap.add_argument('--images', default='upload/own')
    ap.add_argument('--out', default='labels/template-labels.json')
    args = ap.parse_args()
    sift = cv2.SIFT_create(nfeatures=4000)
    bf = cv2.BFMatcher()
    tmpl, tmpl_gray = {}, {}
    for card, path in TEMPLATES.items():
        im = cv2.imread(path)
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        kp, ds = sift.detectAndCompute(g, None)
        tmpl[card] = (im.shape[1], im.shape[0], kp, ds)
        tmpl_gray[card] = g
        print(f"template {card}: {im.shape[1]}x{im.shape[0]}, {len(kp)} keypoints")

    rows = list(csv.DictReader(open(args.list)))
    out, stats, fails = {}, collections.defaultdict(lambda: [0, 0]), []
    for r in rows:
        f = r["file"]
        w_t, h_t, kp_t, ds_t = tmpl[r["card"]]
        im = cv2.imread(args.images + "/" + f)
        h0, w0 = im.shape[:2]
        s = min(1.0, MAX_EDGE / max(h0, w0))
        small = cv2.resize(im, None, fx=s, fy=s) if s < 1 else im
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        kp, ds = sift.detectAndCompute(g, None)
        ok, n_in, ecc = False, 0, None
        if ds is not None and len(kp) >= 8:
            m = bf.knnMatch(ds_t, ds, k=2)
            good = [a for a, b in (x for x in m if len(x) == 2) if a.distance < 0.75 * b.distance]
            if len(good) >= 8:
                src = np.float32([kp_t[a.queryIdx].pt for a in good]).reshape(-1, 1, 2)
                dst = np.float32([kp[a.trainIdx].pt for a in good]).reshape(-1, 1, 2)
                H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
                if H is not None:
                    # refine by direct image alignment (ECC); its correlation is the quality score
                    try:
                        tg = cv2.GaussianBlur(tmpl_gray[r["card"]], (0, 0), 1.5)
                        ig = cv2.GaussianBlur(g, (0, 0), 1.5)
                        W = H.astype(np.float32)
                        cc, W = cv2.findTransformECC(tg, ig, W, cv2.MOTION_HOMOGRAPHY,
                                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
                        H, ecc = W.astype(np.float64), float(cc)
                    except cv2.error:
                        ecc = None
                if H is not None:
                    n_in = int(mask.sum())
                    ok = n_in >= MIN_INLIERS
                    H_full = np.diag([1 / s, 1 / s, 1.0]) @ H if ok else None
        stats[(r["card"], r["condition"])][1] += 1
        if not ok:
            fails.append((f, n_in))
            continue
        stats[(r["card"], r["condition"])][0] += 1

        def proj(rect):
            x0, y0, x1, y1 = rect
            pts = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]).reshape(-1, 1, 2)
            return cv2.perspectiveTransform(pts, H).reshape(4, 2) / s

        doc_q, zone_q = proj((0, 0, w_t, h_t)), proj(ZONES[r["card"]])
        frame = box(0, 0, w0, h0)
        objs = []
        for cls, q in (("document", doc_q), ("data_zone", zone_q)):
            p = Polygon(q)
            if not p.is_valid:
                p = p.buffer(0)
            c = p.intersection(frame)
            if not c.is_empty and c.geom_type == "Polygon" and c.area > 50:
                objs.append({"class": cls, "polygon": [list(map(float, x)) for x in c.exterior.coords][:-1],
                             "clipped": bool(c.area < p.area - 1)})
        out[f] = {"width": w0, "height": h0, "card": r["card"], "condition": r["condition"],
                  "inliers": n_in, "ecc": ecc, "H": H_full.tolist(), "objects": objs}

    Path("labels").mkdir(exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    tot_ok = sum(v[0] for v in stats.values())
    print(f"\nmatched {tot_ok} of {len(rows)} frames (min {MIN_INLIERS} inliers)")
    for k in sorted(stats):
        print(f"  {k[0]:5s} {k[1]:14s} {stats[k][0]:2d} / {stats[k][1]:2d}")
    print("failed:", sorted(fails))


if __name__ == "__main__":
    main()
