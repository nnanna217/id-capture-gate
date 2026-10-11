"""Capture-group train/valid/test split for the 131 staged own frames.

Frames shot back to back in one set-up are near-duplicates; a random split puts copies of the same shot on both
sides and inflates validation scores. So the unit of assignment is a GROUP, not a frame.

Group = a run of consecutively numbered frames (ingest order = shot order) within one (card, condition) whose
neighbouring frames are similar (HSV colour histogram, Bhattacharyya distance <= TAU). Groups are then assigned to train/valid/test by a seeded
random search that scores closeness to 70/20/10 per family and penalises any key class (glare, obstruction) or card
missing from valid or test, and any card/family missing from train.

Writes upload/split.csv and stages upload/train, upload/valid, upload/test (copies; gitignored).
Then reports leakage: nearest-train-frame distance of valid/test frames, group split vs random split.
"""
import collections
import csv
import random
import shutil
from pathlib import Path

import cv2
import numpy as np

TAU = 0.4
RATIO = {"train": 0.70, "valid": 0.20, "test": 0.10}
FAMILY = {"good": "good", "glare_direct": "glare", "glare_oblique": "glare", "obstruction": "obstruction",
          "partial": "partial", "blur": "blur", "lowlight": "lowlight"}
SEED = 7


def num(f):
    return int(f.rsplit("-", 1)[1][:3])


def hist(f):
    im = cv2.resize(cv2.imread("upload/own/" + f), (160, 213), interpolation=cv2.INTER_AREA)
    h = cv2.calcHist([cv2.cvtColor(im, cv2.COLOR_BGR2HSV)], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
    return cv2.normalize(h, h).flatten()


def dist(a, b):
    return cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA)


def main() -> None:
    rows = list(csv.DictReader(open("upload/own-set.csv")))
    H = {r["file"]: hist(r["file"]) for r in rows}
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["card"], r["condition"])].append(r["file"])

    groups = []  # (card, family, condition, [files])
    for (card, cond), fs in by.items():
        fs = sorted(fs, key=num)
        cur = [fs[0]]
        for a, b in zip(fs, fs[1:]):
            if dist(H[a], H[b]) <= TAU:
                cur.append(b)
            else:
                groups.append((card, FAMILY[cond], cond, cur))
                cur = [b]
        groups.append((card, FAMILY[cond], cond, cur))

    # search for the assignment of whole groups that best matches 70/20/10 per family and keeps every key class,
    # and both cards, represented in valid and test
    rng = random.Random(SEED)
    splits = list(RATIO)
    N = len(rows)

    def score(asg):
        cnt = collections.Counter()
        for g, sp in zip(groups, asg):
            cnt[("all", sp)] += len(g[3])
            cnt[(g[1], sp)] += len(g[3])
            cnt[(g[0] + "/" + g[1], sp)] += len(g[3])
        sc = 0.0
        for sp in splits:
            sc += 20 * (cnt[("all", sp)] / N - RATIO[sp]) ** 2
        for fam in set(g[1] for g in groups):
            tot = sum(cnt[(fam, sp)] for sp in splits)
            for sp in splits:
                sc += 4 * ((cnt[(fam, sp)] / tot - RATIO[sp]) ** 2) * (tot / N) * 10
            if cnt[(fam, "valid")] == 0 or cnt[(fam, "test")] == 0:
                sc += 5
        for key in set(g[0] + "/" + g[1] for g in groups):  # no card/family may be missing from train
            if cnt[(key, "train")] == 0:
                sc += 6
        for card in ("id", "bank"):
            for fam in ("glare", "obstruction"):
                for sp in ("valid", "test"):
                    if cnt[(card + "/" + fam, sp)] == 0:
                        sc += 3
        return sc

    best, best_sc = None, 1e9
    for restart in range(60):
        asg = [rng.choices(splits, weights=[RATIO[x] for x in splits])[0] for _ in groups]
        cur = score(asg)
        for _ in range(4000):
            i = rng.randrange(len(groups))
            old = asg[i]
            asg[i] = rng.choice(splits)
            new_sc = score(asg)
            if new_sc <= cur:
                cur = new_sc
            else:
                asg[i] = old
        if cur < best_sc:
            best, best_sc = list(asg), cur
    assign = {id(g): sp for g, sp in zip(groups, best)}
    print(f"search score {best_sc:.4f} (lower is better)")

    out = collections.defaultdict(list)
    for g in groups:
        for f in g[3]:
            out[assign[id(g)]].append((f, g))
    for s in RATIO:
        d = Path("upload") / s
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for f, _ in out[s]:
            shutil.copy2("upload/own/" + f, d / f)
    gid = {id(g): i for i, g in enumerate(groups)}
    with open("upload/split.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "card", "condition", "family", "group", "split"])
        for s in RATIO:
            for f, g in out[s]:
                w.writerow([f, g[0], g[2], g[1], gid[id(g)], s])

    print(f"{len(groups)} groups from {len(rows)} frames (TAU={TAU})")
    print("frames per split:", {s: len(out[s]) for s in RATIO})
    fam = collections.defaultdict(lambda: collections.Counter())
    for s in RATIO:
        for f, g in out[s]:
            fam[(g[0], g[1])][s] += 1
    print(f"{'card/family':18s} train valid test")
    for k in sorted(fam):
        print(f"{k[0]+'/'+k[1]:18s} {fam[k]['train']:5d} {fam[k]['valid']:5d} {fam[k]['test']:4d}")

    # leakage: for each valid/test frame, distance to its nearest train frame in the same (card, condition)
    def leak(split_of):
        ds = []
        for r in rows:
            if split_of[r["file"]] == "train":
                continue
            tr = [dist(H[r["file"]], H[x["file"]]) for x in rows
                  if split_of[x["file"]] == "train" and (x["card"], x["condition"]) == (r["card"], r["condition"])]
            if tr:
                ds.append(min(tr))
        return ds
    grp_split = {f: s for s in RATIO for f, _ in out[s]}
    gd = leak(grp_split)
    rd = []
    for seed in range(20):
        r2 = random.Random(seed)
        files = [r["file"] for r in rows]
        r2.shuffle(files)
        n_tr, n_va = round(0.7 * len(files)), round(0.2 * len(files))
        sp = {f: ("train" if i < n_tr else "valid" if i < n_tr + n_va else "test") for i, f in enumerate(files)}
        rd.extend(leak(sp))
    print(f"nearest-train distance (higher = less leakage): group split median {np.median(gd):.3f} mean {np.mean(gd):.3f}"
          f" (n={len(gd)}) | random split median {np.median(rd):.3f} mean {np.mean(rd):.3f} (20 seeds, n={len(rd)})")


if __name__ == "__main__":
    main()
