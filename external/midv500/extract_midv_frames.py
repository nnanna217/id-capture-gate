"""Sample frames from the MIDV-500 videos (augmentation set; the primary set is the user's own captures).

6 evenly spaced frames from the middle 80% of each video (avoids the start/end where the document is
being placed or removed). Clutter (CA/CS) goes to `heldout_clutter/` from the start: it is the
generalisation check and is never trained on. Output is gitignored (local/midv-500/).
Run with `python -I` — the videos are untrusted third-party data.
"""
import csv
import glob
import os

import cv2

PER_VIDEO = 6
CONDITION = {"T": "table", "K": "keyboard", "H": "hand", "P": "partial", "C": "clutter"}
PHONE = {"A": "phoneA", "S": "phoneS"}
OUT = "local/midv-500/frames"


def main() -> None:
    rows = []
    for path in sorted(glob.glob("local/midv-500/videos/*")):
        stem = os.path.splitext(os.path.basename(path))[0]  # e.g. TA01
        cond, phone = CONDITION[stem[0]], PHONE[stem[1]]
        split = "heldout_clutter" if cond == "clutter" else cond
        os.makedirs(f"{OUT}/{split}", exist_ok=True)
        cap = cv2.VideoCapture(path)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        lo, hi = int(n * 0.1), int(n * 0.9)
        idxs = [lo + round(i * (hi - lo) / (PER_VIDEO - 1)) for i in range(PER_VIDEO)]
        for i in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, frame = cap.read()
            if not ok:
                print("read failed", stem, i)
                continue
            f = f"{OUT}/{split}/midv-{stem}-f{i:03d}.jpg"
            cv2.imwrite(f, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            rows.append([f, "midv-500", cond, phone, i, frame.shape[1], frame.shape[0], split])
        cap.release()
    with open(f"{OUT}/manifest.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "source", "condition", "phone", "frame_index", "width", "height", "split"])
        w.writerows(rows)
    print(len(rows), "frames")


if __name__ == "__main__":
    main()
