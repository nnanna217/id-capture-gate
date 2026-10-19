"""Stage the damaged-card photos for Roboflow and pre-label what the model can (D-15, route b; D-18 says what gets labelled by hand).

usage (from the repo root): python -I pipeline/3_dataset/build_damage_upload_set.py
Reads local/captures/damage-manifest.csv (written by ingest_damage_photos.py). Takes roles damage, clean and negative; the 4 `other` photos
(single-pass obstruction / glare / partial / blur) are not staged: they need glare or obstruction labels and add nothing to this class.

1. SPLIT (D-09). The unit is the capture group, not the photo. Group -> split is stored in data/damage-split.csv and is NEVER changed once a
   group is in it (images already uploaded must not move split); only groups that are not in the file yet are assigned, by a seeded search that
   aims for 70/20/10 of the photos and wants every damage type in train and, where there is more than one group, in valid. Add photos later,
   re-run, and only the new groups are placed.
2. STAGE. Copies into local/upload/damage/{train,valid,test}/ (gitignored). Upload each folder to the project with its split.
3. PRE-LABEL. Runs the published workflow on every staged photo and writes the model's `document` and `data_zone` outlines as polygons to
   local/labels/damage-prelabels.json (same format import_template_labels.py reads). They are PROPOSALS: the model has never seen a damaged
   card, so on exactly these photos its outlines are the least trustworthy; the labelling order file marks the ones to check first.
   `damage` polygons are drawn by hand; nothing here writes them.
Writes data/damage-split.csv (tracked: filenames only) and data/damage-labelling-order.csv.
"""
import csv
import json
import os
import random
import shutil
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

MANIFEST = Path("local/captures/damage-manifest.csv")
SPLIT = Path("data/damage-split.csv")
ORDER = Path("data/damage-labelling-order.csv")
STAGE = Path("local/upload/damage")
PRELABELS = Path("local/labels/damage-prelabels.json")
PRELABELS_NEW = Path("local/labels/damage-prelabels-new.json")     # only photos that were not in the previous prelabels file
ROLES = {"damage", "clean", "negative"}
TARGET = {"train": 0.70, "valid": 0.20, "test": 0.10}
RULE = "per (defect, card): 4+ groups so that train has 2, valid 1 and test 1"   # round 2 aims every kept damage type at this
SEED = 7
MIN_CONF = 0.4          # the block's own cut-off


def assign(groups, frozen):
    """groups: {group: (n_photos, defect, card, role)}. frozen: {group: split}. Returns the full group -> split map."""
    out = {g: sp for g, sp in frozen.items() if g in groups}        # a group that left the set (parked) stops counting
    todo = [g for g in sorted(groups) if g not in out]
    if not todo:
        return out
    rng = random.Random(SEED)
    best, best_score = None, 1e18
    for _ in range(20000):
        cand = {g: rng.choices(list(TARGET), weights=[.7, .2, .1])[0] for g in todo}
        full = {**out, **cand}
        tot = {s: 0 for s in TARGET}
        for g, s in full.items():
            tot[s] += groups[g][0]
        n = sum(tot.values())
        score = sum(abs(tot[s] / n - TARGET[s]) for s in TARGET) * 10
        for key in {(groups[g][3], groups[g][1], groups[g][2]) for g in full}:      # per (role, defect, card): see RULE
            gs = [g for g in full if (groups[g][3], groups[g][1], groups[g][2]) == key]
            tr, va, te = (sum(full[g] == x for g in gs) for x in ("train", "valid", "test"))
            n = len(gs)
            score += 50 * max(0, min(2, n - 1 if n < 4 else 2) - tr)               # train: 2 groups when there are 4+, else at least 1
            if n >= 2:
                score += 10 * (va == 0)                                             # valid: at least 1
            if n >= 3:
                score += 4 * (te == 0)                                              # test: at least 1 once there are 3+
        for sp in ("valid", "test"):                                   # both card types on each side where possible
            cards = {groups[g][2] for g in full if full[g] == sp and groups[g][3] == "damage"}
            score += 1.5 * (2 - len(cards))
        if score < best_score:
            best, best_score = cand, score
    out.update(best)
    return out


def poly(mask):
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 0.004 * cv2.arcLength(c, True), True)
    return [[float(x), float(y)] for x, y in c[:, 0, :]] if len(c) >= 3 else None


def rect(mask):
    """D-03: data_zone is ONE rectangle. The model's mask is a loose blob, so propose its rotated bounding rectangle instead."""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return None
    box = cv2.boxPoints(cv2.minAreaRect(max(cs, key=cv2.contourArea)))
    return [[float(x), float(y)] for x, y in box]


def prelabel(files):
    load_dotenv(".env")
    from inference.core.managers.base import ModelManager
    from inference.core.registries.roboflow import RoboflowModelRegistry
    from inference.core.workflows.core_steps.common.entities import StepExecutionMode
    from inference.core.workflows.execution_engine.core import ExecutionEngine
    from inference.models.utils import ROBOFLOW_MODEL_TYPES
    spec = json.load(open("workflows/capture-gate-verdict-published.json"))
    eng = ExecutionEngine.init(workflow_definition=spec, init_parameters={
        "workflows_core.model_manager": ModelManager(model_registry=RoboflowModelRegistry(ROBOFLOW_MODEL_TYPES)),
        "workflows_core.api_key": os.environ["ROBOFLOW_API_KEY"], "workflows_core.step_execution_mode": StepExecutionMode.LOCAL})
    labels, conf = {}, {}
    for f in files:
        im = cv2.imread(str(f))
        h, w = im.shape[:2]
        p = eng.run(runtime_parameters={"image": im})[0]["predictions"]
        n = len(p)
        names = list(p.data.get("class_name", [])) if n else []
        objs, c = [], {}
        for cls in ("document", "data_zone"):
            idx = [i for i in range(n) if names[i] == cls and p.confidence[i] >= MIN_CONF]
            if idx:
                i = max(idx, key=lambda i: p.confidence[i])
                pg = rect(p.mask[i]) if cls == "data_zone" else poly(p.mask[i])
                if pg:
                    objs.append({"class": cls, "polygon": pg})
                    c[cls] = float(p.confidence[i])
        labels[f.name], conf[f.name] = {"width": w, "height": h, "objects": objs}, c
    return labels, conf


def main():
    rows = [r for r in csv.DictReader(MANIFEST.open()) if r["role"] in ROLES]
    groups = {}
    for r in rows:
        n, *_ = groups.get(r["group"], (0,))
        groups[r["group"]] = (n + 1, r["defect"], r["card"], r["role"])
    frozen = {r["group"]: r["split"] for r in csv.DictReader(SPLIT.open())} if SPLIT.exists() else {}
    full = assign(groups, frozen)
    new = [g for g in full if g not in frozen]
    with SPLIT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "split", "role", "defect", "card", "photos"])
        for g in sorted(full):
            w.writerow([g, full[g], groups[g][3], groups[g][1], groups[g][2], groups[g][0]])
    print(f"{len(groups)} groups, {len(new)} newly assigned, {len(frozen)} kept as they were")
    for role in ("damage", "clean", "negative"):
        t = {s: sum(groups[g][0] for g in full if full[g] == s and groups[g][3] == role) for s in TARGET}
        print(f"  {role:9} photos  train {t['train']:3d}  valid {t['valid']:3d}  test {t['test']:3d}")

    for s in TARGET:
        (STAGE / s).mkdir(parents=True, exist_ok=True)
    keep = {Path(r["file"]).name for r in rows}
    for sp in TARGET:                                   # drop staged copies of photos that left the set (parked) or moved split
        for old in (STAGE / sp).glob("*.jpg"):
            if old.name not in keep or full.get(next((r["group"] for r in rows if Path(r["file"]).name == old.name), ""), sp) != sp:
                old.unlink()
    staged = []
    for r in rows:
        dst = STAGE / full[r["group"]] / Path(r["file"]).name
        if not dst.exists():
            shutil.copy2(r["file"], dst)
        staged.append((r, dst))
    print(f"staged {len(staged)} photos under {STAGE}/<split>/")
    print(f"\nrule check, {RULE}:")
    print(f"  {'defect':13}{'card':6}{'train':>6}{'valid':>6}{'test':>5}   short by")
    for key in sorted({(groups[g][1], groups[g][2]) for g in full if groups[g][3] == "damage"}):
        gs = [g for g in full if groups[g][3] == "damage" and (groups[g][1], groups[g][2]) == key]
        tr, va, te = (sum(full[g] == x for g in gs) for x in ("train", "valid", "test"))
        short = [f"{need - have} {nm}" for nm, have, need in (("train", tr, 2), ("valid", va, 1), ("test", te, 1)) if have < need]
        print(f"  {key[0]:13}{key[1]:6}{tr:6d}{va:6d}{te:5d}   {', '.join(short) or 'ok'}")

    before = set(json.loads(PRELABELS.read_text())) if PRELABELS.exists() else set()
    labels, conf = prelabel([d for _, d in staged])
    PRELABELS.parent.mkdir(parents=True, exist_ok=True)
    PRELABELS.write_text(json.dumps(labels))
    PRELABELS_NEW.write_text(json.dumps({k: v for k, v in labels.items() if k not in before}))
    ordr = []
    for r, d in staged:
        c, o = conf[d.name], labels[d.name]["objects"]
        check = []
        if "document" not in c:
            check.append("no document outline: draw it")
        elif c["document"] < 0.8:
            check.append(f"document conf {c['document']:.2f}")
        if "data_zone" not in c:
            check.append("no data_zone outline: draw it")
        elif c["data_zone"] < 0.6:
            check.append(f"data_zone conf {c['data_zone']:.2f}")
        ordr.append([d.name, full[r["group"]], r["role"], r["card"], r["defect"], r["severity"], r["baseline_verdict"],
                     f"{c.get('document', 0):.2f}", f"{c.get('data_zone', 0):.2f}", "; ".join(check), "yes" if r["role"] == "damage" else "no"])
    ordr.sort(key=lambda x: (x[10] != "yes", x[9] == "", x[1] != "train", x[0]))      # damage first, frames to check first, then train
    with ORDER.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "split", "role", "card", "defect", "severity", "gate_says_now", "document_conf", "data_zone_conf",
                    "check_outlines", "draw_damage_polygon"])
        w.writerows(ordr)
    chk = sum(1 for x in ordr if x[9])
    print(f"pre-labels: {sum(1 for l in labels.values() if l['objects'])} photos with outlines; {chk} flagged for an outline check")
    print(f"wrote {SPLIT}, {ORDER}, {PRELABELS} and {PRELABELS_NEW} ({len(labels) - len(before & set(labels))} new photos: import THIS file for them, not the full one)")


if __name__ == "__main__":
    main()
