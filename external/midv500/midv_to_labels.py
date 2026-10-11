"""MIDV-500 TIFF frames -> `document` and `data_zone` labels from the dataset's own ground truth.

Takes 6 of the 30 annotated frames per video (indices below), converts them to JPEG, and writes
polygon labels (neutral format: the detection-vs-segmentation decision is not made yet):
  document   = the frame's ground-truth quad, clipped to the image (clipped=True when it was cut)
  data_zone  = the template-space bounding RECTANGLE of all text fields (field*, NOT photo/signature; matches
               D-03: one rectangle), projected into the frame with a homography from the template rectangle
               to the frame quad
glare / obstruction are NOT in the ground truth and are labelled by hand.

Clutter (CA/CS) goes to `heldout_clutter/` and is never trained on.
The zip is untrusted third-party data: members are read as bytes and written to paths chosen here.
Run with `python -I`. Output is gitignored (local/midv-500/).
"""
import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon, box

ZIP = "local/midv-500/archives/01_alb_id.zip"
OUT = Path("local/midv-500/tiff")
IDX = [1, 7, 12, 18, 24, 30]
VIDEOS = ["TA", "TS", "KA", "KS", "HA", "HS", "PA", "PS", "CA", "CS"]
COND = {"T": "table", "K": "keyboard", "H": "hand", "P": "partial", "C": "clutter"}


def read_json(z, name):
    return json.loads(z.read(name).decode("utf-8"))


def read_img(z, name):
    return cv2.imdecode(np.frombuffer(z.read(name), np.uint8), cv2.IMREAD_COLOR)


def main() -> None:
    z = zipfile.ZipFile(ZIP)
    tmpl = read_img(z, "01_alb_id/images/01_alb_id.tif")
    th, tw = tmpl.shape[:2]
    tgt = read_json(z, "01_alb_id/ground_truth/01_alb_id.json")
    fields = [np.float32(v["quad"]) for k, v in tgt.items() if k.startswith("field")]
    allpts = np.vstack(fields)
    x0, y0 = allpts.min(axis=0)
    x1, y1 = allpts.max(axis=0)
    zone_rect = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    print(f"template data_zone rectangle: x {x0:.0f}-{x1:.0f}, y {y0:.0f}-{y1:.0f}")
    tmpl_rect = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]])
    print(f"template {tw}x{th}, {len(fields)} text fields (photo/signature excluded)")

    labels = {}
    for vid in VIDEOS:
        cond = COND[vid[0]]
        split = "heldout_clutter" if cond == "clutter" else cond
        (OUT / split).mkdir(parents=True, exist_ok=True)
        for i in IDX:
            stem = f"{vid}01_{i:02d}"
            img = read_img(z, f"01_alb_id/images/{vid}/{stem}.tif")
            gt = read_json(z, f"01_alb_id/ground_truth/{vid}/{stem}.json")
            h, w = img.shape[:2]
            quad = np.float32(gt["quad"])
            H = cv2.getPerspectiveTransform(tmpl_rect, quad)
            pts = cv2.perspectiveTransform(zone_rect.reshape(1, 4, 2), H).reshape(4, 2)
            frame_box = box(0, 0, w, h)
            doc_full = Polygon(quad)
            doc = doc_full.intersection(frame_box)
            zone_full = Polygon(pts)
            zone = zone_full.intersection(frame_box)
            fname = f"midv-{stem}.jpg"
            cv2.imwrite(str(OUT / split / fname), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            objs = []
            if not doc.is_empty:
                objs.append({"class": "document", "polygon": [list(map(float, p)) for p in doc.exterior.coords][:-1],
                             "clipped": bool(doc.area < doc_full.area - 1)})
            if not zone.is_empty and zone.geom_type == "Polygon":
                objs.append({"class": "data_zone", "polygon": [list(map(float, p)) for p in zone.exterior.coords][:-1],
                             "clipped": bool(zone.area < zone_full.area - 1)})
            labels[f"{split}/{fname}"] = {"width": w, "height": h, "split": split, "condition": cond,
                                          "source": "midv-gt", "objects": objs}
    (OUT / "labels.json").write_text(json.dumps(labels, indent=1))
    n_doc = sum(1 for v in labels.values() for o in v["objects"] if o["class"] == "document")
    n_zone = sum(1 for v in labels.values() for o in v["objects"] if o["class"] == "data_zone")
    n_clip = sum(1 for v in labels.values() for o in v["objects"] if o["clipped"])
    print(f"{len(labels)} frames, {n_doc} document, {n_zone} data_zone polygons, {n_clip} clipped")


if __name__ == "__main__":
    main()
