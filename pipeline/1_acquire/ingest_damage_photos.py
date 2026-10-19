"""Bring the damaged-card shoot into the dataset (D-15, route b): convert, normalise, strip metadata, and record what each photo is.

usage (from the repo root):
    python -I pipeline/1_acquire/ingest_damage_photos.py --src ~/Downloads/damaged-id-dataset                # DRY RUN: prints the plan, writes nothing
    python -I pipeline/1_acquire/ingest_damage_photos.py --src ~/Downloads/damaged-id-dataset --apply        # writes images + manifest

The photos were not shot in folders per type, so what each photo IS comes from data/damage-batches.csv: capture-number ranges (IMG_nnnn),
one row per run of photos, read off the contact sheets and editable. The optional `set` column forces a new capture group (use it for
separate surface or location runs that were shot within a minute of each other). Per photo this script also records
  card            id or bank, guessed from the model's `document` mask (mean grey: ID cards are pale, the bank card is navy). Override with --card-map.
  group           a capture group for the train/valid/test split (D-09): photos of the same role, card and defect taken within --gap seconds
                  of each other (recomputed over the whole manifest on every --apply).
                  This is an approximation of "one physical card"; two cards can share a group when photographed back to back.
  baseline_*      what the CURRENT published gate says about the photo (verdict and reasons). On damaged photos, `usable` is the false pass.
Output: local/captures/damage/<role>/<card>-<defect>-NNN.jpg (JPEG, long edge <= 1920, EXIF and GPS dropped) and
        local/captures/damage-manifest.csv. The existing local/captures/manifest.csv is NOT touched. Originals are copied from, never moved.
The key is read from .env and never printed. Already-ingested photos (by original IMG number) are skipped, so it is safe to re-run.
--reclassify re-applies data/damage-batches.csv to photos already ingested (used to park a defect type).
Round 2 onwards, photos in a folder named <R2>-<ID|BANK>-<copy no>-<tear|crease|curl|fold_corner|stain|clean|fingers|bow_tilt> need no batch row.
"""
import argparse
import csv
import datetime as dt
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

ROOT = Path("local/captures/damage")
MANIFEST = Path("local/captures/damage-manifest.csv")
BATCHES = Path("data/damage-batches.csv")
FIELDS = ["file", "orig", "role", "defect", "severity", "set", "card", "card_source", "group", "timestamp", "width", "height",
          "baseline_verdict", "baseline_reasons", "note"]
BANK_BELOW = 113            # mean grey inside the document mask: bank 53-101 on the 113 photos, ID 127-175 (one ID in glare at 127)

spec = importlib.util.spec_from_file_location("ingest_phone_photos", Path(__file__).with_name("ingest_phone_photos.py"))
phone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phone)


def captured_at(path):
    out = subprocess.run(["mdls", "-raw", "-name", "kMDItemContentCreationDate", str(path)], capture_output=True, text=True).stdout.strip()
    try:
        return dt.datetime.strptime(out, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)


def read_batches():
    rows = []
    for r in csv.DictReader(BATCHES.open()):
        rows.append((int(r["first"]), int(r["last"]), r))
    return rows


FOLDER = __import__("re").compile(r"^(?:(R\d+)-)?(ID|BANK)-(\d+)-([a-z_]+)$", __import__("re").I)
ROLE_OF = {"tear": "damage", "crease": "parked", "curl": "damage", "fold_corner": "damage", "stain": "damage",
           "clean": "clean", "fingers": "negative", "bow_tilt": "negative"}


def from_folder(path):
    """Round 2 onwards: one folder per physical card, named <round>-<LAYOUT>-<copy number>-<what>, e.g. R2-ID-05-tear or R2-BANK-17-fingers.
    The folder name gives role, defect and a `set` (= the physical card), so no entry in damage-batches.csv is needed and every card is its
    own capture group. Returns a batch-like dict, or None when the parent folder is not named that way."""
    m = FOLDER.match(path.parent.name)
    if not m or m.group(4).lower() not in ROLE_OF:
        return None
    rnd, layout, num, what = m.group(1) or "R1", m.group(2).upper(), m.group(3), m.group(4).lower()
    return {"role": ROLE_OF[what], "defect": "none" if what == "clean" else what, "severity": "", "set": f"{rnd}-{layout}{num}".lower(),
            "note": f"folder {path.parent.name}", "card_hint": layout.lower()}


def batch_of(n, rows):
    for a, b, r in rows:
        if a <= n <= b:
            return r
    return None


def make_engine():
    load_dotenv(".env")
    from inference.core.managers.base import ModelManager
    from inference.core.registries.roboflow import RoboflowModelRegistry
    from inference.core.workflows.core_steps.common.entities import StepExecutionMode
    from inference.core.workflows.execution_engine.core import ExecutionEngine
    from inference.models.utils import ROBOFLOW_MODEL_TYPES
    spec_json = json.load(open("workflows/capture-gate-verdict-published.json"))
    return ExecutionEngine.init(workflow_definition=spec_json, init_parameters={
        "workflows_core.model_manager": ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES)),
        "workflows_core.api_key": os.environ["ROBOFLOW_API_KEY"], "workflows_core.step_execution_mode": StepExecutionMode.LOCAL})


def judge(engine, im):
    o = engine.run(runtime_parameters={"image": im})[0]
    p = o["predictions"]
    n = len(p)
    names = list(p.data.get("class_name", [])) if n else []
    idx = [i for i in range(n) if names[i] == "document" and p.confidence[i] >= 0.4]
    grey = None
    if idx:
        i = max(idx, key=lambda i: p.confidence[i])
        grey = float(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)[p.mask[i].astype(bool)].mean())
    return o["verdict"], "|".join(o["reasons"]), grey


def migrate_manifest():
    """A manifest written with an older column set is rewritten with the current FIELDS BEFORE new rows are appended; appending rows with
    more columns under an old header shifts every column of the new rows (this happened once, when `set` was added)."""
    if not MANIFEST.exists():
        return
    raw = list(csv.reader(MANIFEST.open()))
    if not raw or raw[0] == FIELDS:
        return
    rows = [dict(zip(raw[0], r)) for r in raw[1:]]
    with MANIFEST.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, restval="")
        w.writeheader()
        w.writerows(rows)


def reclassify(gap):
    """Apply the current data/damage-batches.csv to photos already ingested (e.g. park a defect type). Files move to the new role folder but KEEP their names (the platform knows the photos by name)."""
    rows = list(csv.DictReader(MANIFEST.open()))
    batches = read_batches()
    changed = 0
    for r in rows:
        b = batch_of(int(r["orig"]), batches)
        if b is None or (b["role"], b["defect"], b.get("set", "")) == (r["role"], r["defect"], r.get("set", "")):
            continue
        old = Path(r["file"])
        dst_dir = ROOT / b["role"]
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / old.name                         # never rename: the file name is what Roboflow knows the photo by
        if dst != old:
            old.rename(dst)
        r.update(file=str(dst), role=b["role"], defect=b["defect"], severity=b["severity"], set=b.get("set", ""), note=b["note"])
        changed += 1
    with MANIFEST.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, restval="")
        w.writeheader()
        w.writerows(rows)
    print(f"reclassified {changed} photos; {regroup(gap)} capture groups")


def regroup(gap):
    """Capture groups over the whole manifest: photos of the same role, card and defect taken within `gap` seconds of the previous one
    (D-09: the unit of the train/valid/test split is a group, not a photo). An approximation of one physical card."""
    rows = list(csv.DictReader(MANIFEST.open()))
    prev, k = {}, {}
    for r in sorted(rows, key=lambda r: r["timestamp"]):
        t = dt.datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        key = (r["role"], r["card"], r["defect"], r.get("set", ""))
        if key not in prev or (t - prev[key]).total_seconds() > gap:
            k[key] = k.get(key, 0) + 1
        prev[key] = t
        r["group"] = f"{r['role']}-{r['card']}-{r['defect']}" + (f"-{r['set']}" if r.get("set") else "") + f"-g{k[key]:02d}"
    with MANIFEST.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return len({r["group"] for r in rows})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--apply", action="store_true", help="write images and the manifest (default: dry run)")
    ap.add_argument("--gap", type=float, default=60.0, help="seconds between photos that starts a new capture group")
    ap.add_argument("--max-edge", type=int, default=1920)
    ap.add_argument("--reclassify", action="store_true", help="re-read data/damage-batches.csv and update role/defect/set of photos ALREADY ingested (moves files); no model run")
    ap.add_argument("--card-map", help="optional CSV orig,card to override the guessed card type (orig = IMG number, e.g. 3611)")
    a = ap.parse_args()

    if a.reclassify:
        reclassify(a.gap)
        return
    src = Path(a.src).expanduser()
    files = sorted(src.rglob("*.HEIC")) + sorted(src.rglob("*.heic"))
    files = sorted({f for f in files}, key=lambda p: int(p.stem.split("_")[-1]))
    if not files:
        raise SystemExit(f"no HEIC photos under {a.src}")
    rows = read_batches()
    override = {int(r["orig"]): r["card"] for r in csv.DictReader(open(a.card_map))} if a.card_map else {}
    done = {int(r["orig"]) for r in csv.DictReader(MANIFEST.open())} if MANIFEST.exists() else set()
    engine = make_engine()
    engine.run(runtime_parameters={"image": np.zeros((480, 640, 3), np.uint8)})

    plan, unknown = [], []
    for f in files:
        n = int(f.stem.split("_")[-1])
        if n in done:
            continue
        b = from_folder(f) or batch_of(n, rows)
        if b is None:
            unknown.append(f.name)
            continue
        im = phone.load(f)
        if im is None:
            print("skipped (unreadable):", f.name)
            continue
        s = a.max_edge / max(im.shape[:2])
        if s < 1:
            im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        verdict, reasons, grey = judge(engine, im)
        if n in override:
            card, how = override[n], "card-map"
        elif b.get("card_hint"):
            card, how = b["card_hint"], "folder name"
        elif grey is None:
            card, how = "unknown", "no document found"
        else:
            card, how = ("bank" if grey < BANK_BELOW else "id"), f"mask grey {grey:.0f}"
        plan.append(dict(f=f, n=n, im=im, b=b, card=card, how=how, t=captured_at(f), verdict=verdict, reasons=reasons))
    if unknown:
        print("NOT in data/damage-batches.csv and not in a card folder (skipped):", ", ".join(unknown))

    for p in plan:
        p["group"] = ""                             # assigned over the WHOLE manifest at write time (see regroup)

    summ = {}
    for p in plan:
        s = summ.setdefault((p["b"]["role"], p["b"]["defect"], p["card"]), [0, 0])
        s[0] += 1
        s[1] += p["verdict"] == "usable"
    print(f"{'role':9} {'defect':13} {'card':8} {'photos':>6} {'gate says usable':>17}")
    for (role, defect, card), (nn, u) in sorted(summ.items()):
        print(f"{role:9} {defect:13} {card:8} {nn:6d} {u:17d}")
    dmg = [p for p in plan if p["b"]["role"] == "damage"]
    if dmg:
        print(f"\nDAMAGED photos the current gate passes as usable: {sum(p['verdict'] == 'usable' for p in dmg)} of {len(dmg)}")
    print(f"{len(plan)} photo(s) to ingest, {len(done)} already ingested")

    if not a.apply:
        print("\nDRY RUN: nothing written. Re-run with --apply.")
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    migrate_manifest()
    new = not MANIFEST.exists()
    count = {}
    for d in ROOT.glob("*/*.jpg"):
        stem, num = d.stem.rsplit("-", 1)
        count[(d.parent.name, stem)] = max(count.get((d.parent.name, stem), 0), int(num))
    with MANIFEST.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for p in plan:
            stem = f"{p['card']}-{p['b']['defect']}"
            key = (p["b"]["role"], stem)
            count[key] = count.get(key, 0) + 1
            out = ROOT / p["b"]["role"] / f"{stem}-{count[key]:03d}.jpg"
            out.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out), p["im"], [cv2.IMWRITE_JPEG_QUALITY, 95])
            w.writerow(dict(file=str(out), orig=p["n"], role=p["b"]["role"], defect=p["b"]["defect"], severity=p["b"]["severity"], set=p["b"].get("set", ""), card=p["card"],
                            card_source=p["how"], group=p["group"], timestamp=p["t"].strftime("%Y-%m-%dT%H:%M:%S%z"), width=p["im"].shape[1],
                            height=p["im"].shape[0], baseline_verdict=p["verdict"], baseline_reasons=p["reasons"], note=p["b"]["note"]))
    print(f"wrote {len(plan)} images under {ROOT} and rows to {MANIFEST}; {regroup(a.gap)} capture groups in total")


if __name__ == "__main__":
    main()
