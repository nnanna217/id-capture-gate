"""Shoot the primary dataset. Keys 1-7 pick the condition, SPACE saves, Q quits.

Frames go to local/captures/<condition>/ (gitignored: raw frames are shot at home and unredacted)
and every save is appended to local/captures/manifest.csv with the condition and actual resolution,
so nothing about a frame has to be remembered later.
"""
import csv
import time
from pathlib import Path

import cv2

CONDITIONS = {
    "1": ("good", 30),
    "2": ("glare_direct", 14),
    "3": ("glare_oblique", 14),
    "4": ("obstruction", 22),
    "5": ("partial", 10),
    "6": ("blur", 10),
    "7": ("lowlight", 8),
}
ROOT = Path("local/captures")
MANIFEST = ROOT / "manifest.csv"


def counts() -> dict:
    return {name: len(list((ROOT / name).glob("*.jpg"))) for name, _ in CONDITIONS.values()}


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    for name, _ in CONDITIONS.values():
        (ROOT / name).mkdir(exist_ok=True)
    new = not MANIFEST.exists()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise SystemExit("Webcam not opened — check macOS camera permission for Terminal.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    for _ in range(15):  # let auto-exposure settle
        cap.read()
    cur = "1"
    have = counts()
    print("keys: 1 good · 2 glare_direct · 3 glare_oblique · 4 obstruction · 5 partial · 6 blur · 7 lowlight")
    print("SPACE = save · Q = quit")
    with MANIFEST.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["file", "condition", "width", "height", "timestamp"])
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            name, target = CONDITIONS[cur]
            view = frame.copy()
            cv2.putText(view, f"{name}: {have[name]}/{target}  (total {sum(have.values())})", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            cv2.imshow("capture", cv2.resize(view, None, fx=0.5, fy=0.5))
            k = cv2.waitKey(1) & 0xFF
            if chr(k) in CONDITIONS:
                cur = chr(k)
            elif k == ord(" "):
                have[name] += 1
                path = ROOT / name / f"{name}-{have[name]:03d}.jpg"
                cv2.imwrite(str(path), frame)
                w.writerow([str(path), name, frame.shape[1], frame.shape[0], time.strftime("%Y-%m-%dT%H:%M:%S")])
                fh.flush()
                print("saved", path, f"{frame.shape[1]}x{frame.shape[0]}")
            elif k == ord("q"):
                break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
