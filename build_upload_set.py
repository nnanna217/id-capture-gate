"""Stage the agreed own-frame label set into upload/own/ (copies; gitignored) and write upload/own-set.csv.

Selection (agreed with the user, 2026-10-09):
  ID card   : all good, glare_oblique, obstruction, partial, blur, lowlight; glare_direct picks below
  bank card : all good, obstruction, partial, blur, lowlight; glare picks below
MIDV is deliberately NOT included: it is CC BY-SA 2.5 and the Roboflow project is public.
"""
import csv
import shutil
from pathlib import Path

ID_DIRECT = [3, 5, 6, 7, 10, 11, 13, 14, 16, 17, 19, 21, 23, 25, 27, 29, 31, 32, 33, 34]
BANK_DIRECT = [1, 4, 5, 10, 12, 13, 15]
BANK_OBLIQUE = [1, 2, 3, 6, 7, 9, 11]
PICKS = {("id", "glare_direct"): ID_DIRECT, ("bank", "glare_direct"): BANK_DIRECT, ("bank", "glare_oblique"): BANK_OBLIQUE}

rows = list(csv.DictReader(open("captures/manifest.csv")))
out = Path("upload/own")
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
chosen = []
for r in rows:
    card, cond = r["card"], r["condition"]
    num = int(r["file"].rsplit("-", 1)[1][:3])
    if (card, cond) in PICKS and num not in PICKS[(card, cond)]:
        continue
    shutil.copy2(r["file"], out / Path(r["file"]).name)
    chosen.append([Path(r["file"]).name, card, cond, r["width"], r["height"], r["source"]])
with open("upload/own-set.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["file", "card", "condition", "width", "height", "source"])
    w.writerows(chosen)
import collections
print(len(chosen), "frames staged")
print(dict(collections.Counter((c[1], c[2]) for c in chosen)))
