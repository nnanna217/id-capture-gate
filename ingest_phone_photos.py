"""Bring phone photos into the dataset: convert, normalise, strip metadata, record condition and card.

usage: python ingest_phone_photos.py --src ~/Downloads/airdrop-batch --condition glare_direct --card id

- reads HEIC/JPG/PNG from --src (originals are copied from, never moved or deleted)
- applies EXIF orientation, resizes so the long edge is <= --max-edge (default 1920)
- re-encodes as JPEG, which drops EXIF — including GPS location
- writes captures/<condition>/<card>-<condition>-NNN.jpg and appends to captures/manifest.csv
Raw captures stay gitignored (captures/).
"""
import argparse
import csv
import subprocess
import tempfile
import time
from pathlib import Path

import cv2

CONDITIONS = ["good", "glare_direct", "glare_oblique", "obstruction", "partial", "blur", "lowlight"]
EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png"}
ROOT = Path("captures")
MANIFEST = ROOT / "manifest.csv"


def load(path: Path):
    """cv2 cannot read HEIC; let macOS `sips` convert it. cv2.imread applies EXIF orientation itself."""
    if path.suffix.lower() in {".heic", ".heif"}:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "x.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", str(path), "--out", str(out)],
                           check=True, capture_output=True)
            return cv2.imread(str(out))
    return cv2.imread(str(path))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    ap.add_argument("--card", required=True, choices=["id", "bank"])
    ap.add_argument("--max-edge", type=int, default=1920)
    a = ap.parse_args()

    files = sorted(p for p in Path(a.src).expanduser().iterdir() if p.suffix.lower() in EXTS)
    if not files:
        raise SystemExit(f"no photos found in {a.src}")
    dest = ROOT / a.condition
    dest.mkdir(parents=True, exist_ok=True)
    # next number = highest existing + 1 (counting files would overwrite after any deletion)
    nums = [int(f.stem.rsplit("-", 1)[1]) for f in dest.glob(f"{a.card}-{a.condition}-*.jpg")]
    n = max(nums, default=0)
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["file", "condition", "width", "height", "timestamp", "card", "source"])
        for p in files:
            im = load(p)
            if im is None:
                print("skipped (unreadable):", p.name)
                continue
            h, wd = im.shape[:2]
            s = a.max_edge / max(h, wd)
            if s < 1:
                im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            n += 1
            out = dest / f"{a.card}-{a.condition}-{n:03d}.jpg"
            cv2.imwrite(str(out), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
            w.writerow([str(out), a.condition, im.shape[1], im.shape[0], time.strftime("%Y-%m-%dT%H:%M:%S"),
                        a.card, "phone"])
            print(f"{p.name} ({wd}x{h}) -> {out} ({im.shape[1]}x{im.shape[0]})")


if __name__ == "__main__":
    main()
