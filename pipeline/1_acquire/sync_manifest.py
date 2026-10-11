"""Drop local/captures/manifest.csv rows whose image file no longer exists (after you delete frames by hand).
Prints what it removed. Never touches image files."""
import csv
from pathlib import Path

M = Path("local/captures/manifest.csv")
rows = list(csv.DictReader(M.open()))
keep = [r for r in rows if Path(r["file"]).exists()]
gone = [r["file"] for r in rows if not Path(r["file"]).exists()]
with M.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(keep)
print(f"{len(keep)} rows kept, {len(gone)} removed:", *gone, sep="\n  ")
