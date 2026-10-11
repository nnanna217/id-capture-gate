"""Attach the template-derived `document` / `data_zone` polygons to the images already uploaded to Roboflow.

Format: Darknet/YOLO text with polygon rows (`class x1 y1 x2 y2 ...`, normalised), wrapped in JSON with a labelmap, sent to
POST /dataset/{project}/annotate/{image_id}. WHETHER THIS FORMAT IMPORTS AS POLYGONS IN AN INSTANCE SEGMENTATION PROJECT IS
NOT DOCUMENTED, so this script has three modes and the default writes nothing:

  python import_template_labels.py                      dry run: reads image ids (read-only), writes labels/yolo/*.txt, shows a sample
  python import_template_labels.py --only FILE.jpg      WRITES one image's annotation
  python import_template_labels.py --all                WRITES every frame in labels/template-labels.json

A 409 means the image already has an annotation; it is reported and skipped, never overwritten.
The API key is read from .env and never printed.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(".env")
KEY = os.environ.get("ROBOFLOW_API_KEY", "")
WS, PROJECT = "eze-nnanna-chijioke", "capture-gate"
CLASSES = ["document", "data_zone", "glare", "obstruction"]
LABELMAP = {str(i): c for i, c in enumerate(CLASSES)}


def image_ids() -> dict:
    """All image name -> id pairs. Offset paging can skip an image if the result order shifts between pages (seen once:
    one of 131 went missing), so keep fetching until the unique count equals the reported total."""
    for attempt in range(6):
        ids, off, total = {}, 0, None
        while True:
            r = requests.post(f"https://api.roboflow.com/{WS}/{PROJECT}/search", params={"api_key": KEY},
                              json={"offset": off, "limit": 100, "fields": ["id", "name"]}, timeout=60)
            if r.status_code != 200:
                sys.exit(f"search failed: HTTP {r.status_code}")
            d = r.json()
            total = d.get("total", 0)
            for it in d.get("results", []):
                ids[it["name"]] = it["id"]
            off += len(d.get("results", []))
            if not d.get("results") or off >= total:
                break
        if len(ids) == total:
            return ids
        print(f"attempt {attempt + 1}: got {len(ids)} unique names but the project reports {total}; retrying")
    sys.exit(f"could not fetch all {total} image ids after 6 attempts (got {len(ids)})")


def yolo_poly(label: dict) -> str:
    w, h = label["width"], label["height"]
    rows = []
    for o in label["objects"]:
        pts = o["polygon"]
        if len(pts) < 3:
            continue
        flat = []
        for x, y in pts:
            flat += [min(max(x / w, 0.0), 1.0), min(max(y / h, 0.0), 1.0)]
        rows.append(f"{CLASSES.index(o['class'])} " + " ".join(f"{v:.6f}" for v in flat))
    return "\n".join(rows) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--labels", default="labels/template-labels.json")
    a = ap.parse_args()
    if not KEY:
        sys.exit("ROBOFLOW_API_KEY missing in .env")
    labels = json.load(open(a.labels))
    ids = image_ids()
    out = Path("labels/yolo")
    out.mkdir(parents=True, exist_ok=True)
    files = [a.only] if a.only else sorted(k for k, v in labels.items() if v["objects"])  # skip frames with no polygons
    missing = [f for f in files if f not in ids or f not in labels]
    if missing:
        sys.exit(f"not found on the platform or in the label file: {missing[:5]}")
    for f in files:
        (out / (Path(f).stem + ".txt")).write_text(yolo_poly(labels[f]))
    print(f"read {len(ids)} image ids; wrote {len(files)} YOLO polygon files to labels/yolo/")
    sample = files[0]
    print(f"\nsample ({sample}, id {ids[sample]}):\n{(out / (Path(sample).stem + '.txt')).read_text()[:400]}")
    if not (a.only or a.all):
        print("DRY RUN: nothing was sent to Roboflow.")
        return
    ok = skipped = failed = 0
    for f in files:
        body = {"annotationFile": (out / (Path(f).stem + ".txt")).read_text(), "labelmap": LABELMAP}
        r = requests.post(f"https://api.roboflow.com/dataset/{PROJECT}/annotate/{ids[f]}",
                          params={"api_key": KEY, "name": Path(f).stem + ".txt"}, json=body, timeout=60)
        if r.status_code == 200:
            ok += 1
        elif r.status_code == 409:
            skipped += 1
            print(f"{f}: already annotated, skipped")
        else:
            failed += 1
            print(f"{f}: HTTP {r.status_code} {r.text[:200]!r}")
        if a.only:
            print("response:", r.status_code, r.text[:300])
    print(f"sent: {ok} ok, {skipped} skipped (already annotated), {failed} failed")


if __name__ == "__main__":
    main()
