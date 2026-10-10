"""Take frames from a phone video into the dataset (same naming/manifest as ingest_phone_photos.py).

usage: python extract_video_frames.py --src ~/Downloads/glare-video.MOV --condition glare_direct --card bank \
           [--start 0] [--end 3] [--n 4] [--window 4] [--max-edge 1920]

- picks --n evenly spaced moments between --start and --end seconds
- for each, looks +---window frames around it and keeps the sharpest (whole-frame Laplacian variance; only
  used to avoid motion-blurred picks, not as a quality measure)
- applies the video's rotation (OpenCV does this by default), resizes to --max-edge, re-encodes as JPEG
  (drops metadata), writes captures/<condition>/<card>-<condition>-NNN.jpg, appends captures/manifest.csv
  with source=video and the timestamp-in-video in the note of the printed output
Consecutive video frames are near-duplicates: keep --n small and review what you get.
"""
import argparse
import csv
import time
from pathlib import Path

import cv2

CONDITIONS = ["good", "glare_direct", "glare_oblique", "obstruction", "partial", "blur", "lowlight"]
ROOT = Path("captures")
MANIFEST = ROOT / "manifest.csv"


def sharpness(frame) -> float:
    return float(cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    ap.add_argument("--card", required=True, choices=["id", "bank"])
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=3.0)
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--window", type=int, default=4)
    ap.add_argument("--max-edge", type=int, default=1920)
    a = ap.parse_args()

    cap = cv2.VideoCapture(str(Path(a.src).expanduser()))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {a.src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"{a.src}: {total} frames, {fps:.2f} fps, {total / fps:.2f} s")
    last = min(int(a.end * fps), total - 1)
    first = min(int(a.start * fps), last)
    targets = [first + round(i * (last - first) / max(a.n - 1, 1)) for i in range(a.n)] if a.n > 1 else [first]

    dest = ROOT / a.condition
    dest.mkdir(parents=True, exist_ok=True)
    nums = [int(f.stem.rsplit("-", 1)[1]) for f in dest.glob(f"{a.card}-{a.condition}-*.jpg")]
    n = max(nums, default=0)
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["file", "condition", "width", "height", "timestamp", "card", "source"])
        for t in targets:
            best, best_s, best_i = None, -1.0, t
            for i in range(max(t - a.window, 0), min(t + a.window, total - 1) + 1):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ok, fr = cap.read()
                if ok:
                    s = sharpness(fr)
                    if s > best_s:
                        best, best_s, best_i = fr, s, i
            if best is None:
                print("could not read around frame", t)
                continue
            h, wd = best.shape[:2]
            sc = a.max_edge / max(h, wd)
            if sc < 1:
                best = cv2.resize(best, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
            n += 1
            out = dest / f"{a.card}-{a.condition}-{n:03d}.jpg"
            cv2.imwrite(str(out), best, [cv2.IMWRITE_JPEG_QUALITY, 95])
            w.writerow([str(out), a.condition, best.shape[1], best.shape[0], time.strftime("%Y-%m-%dT%H:%M:%S"),
                        a.card, "video"])
            print(f"t={best_i / fps:.2f}s (frame {best_i}, {wd}x{h}) -> {out} ({best.shape[1]}x{best.shape[0]})")
    cap.release()


if __name__ == "__main__":
    main()
