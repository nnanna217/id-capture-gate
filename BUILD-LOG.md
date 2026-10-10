# Build log — Capture quality gate

Chronological, verbose, failures included. Numbers are as measured, unrounded. Times are UTC unless stated. Decisions with a rejected alternative go in `DECISIONS.md`, not here.

**Hardware:** MacBook, Apple M3, 16 GB, macOS (Darwin 25.6), no NVIDIA GPU.

---

## 2026-10-08 — Phase 0

### 0.1 Environment

- Interpreter for the new venv: `/opt/anaconda3/bin/python3.11` (3.11.7), found by following `roboflow-build/.venv/bin/python` → `python3` → `/opt/anaconda3/bin/python3`. Absolute path used so the `~/.zshrc` `python`/`pip` aliases cannot interfere.
- Venv at `capture-gate/.venv`, **2.0 GB**. Installed `inference==1.7.3` (PyPI's latest when checked; `requires_python <3.14,>=3.10`). Previous build used 1.6.2.
- Resolved versions: `inference` 1.7.3 · `inference-models` 0.39.1 · `supervision` 0.30.9 · `onnxruntime` 1.21.1 · `shapely` 2.0.7 · `numpy` 2.2.6 · `torch` 2.14.1.
- **Disk:** 18 GiB free (96% used) before the venv; 12 GiB after the venv and before the MIDV download; 11 GiB after one MIDV archive. Docker Inference Server (wants 20 GB) is not viable on this disk.

### 0.2 Custom Workflow Block — docs

- Mechanism: **Dynamic Python block**. Defined inside the workflow definition under `dynamic_blocks_definitions` (a `manifest` plus `code`), compiled into a block by the Execution Engine at runtime.
- Docs say it runs on self-hosted/local `inference`, Dedicated Deployments, and (per an August 2025 changelog entry) the Serverless Hosted API v2, where code runs in isolated containers.
- Docs say `ALLOW_CUSTOM_PYTHON_EXECUTION_IN_WORKFLOWS=False` disables local execution; the default is not stated outright (implied on).
- Docs list `cv2`, `numpy`, `supervision`, `shapely` as available without extra imports.
- Docs do **not** say which plan is required.

### 0.3 Custom Workflow Block — local spike (PASS)

`spike_block.py`: in-process `ExecutionEngine`, no API key, no personal images. One dynamic block returns the variance of the Laplacian. Synthetic 480×640 noise image (seed 0) vs the same image Gaussian-blurred (sigma 5):

| image | laplacian_variance |
|---|---|
| sharp | 48694.38381979841 |
| blurred | 2.4104720049434243 |

Passed first run. **Self-correction:** I first declared the block's output kind as `float_zero_to_one`, which is wrong for an unbounded variance. The engine did not enforce it, so it ran anyway. Changed to `float` and re-ran; same numbers.

### 0.4 Custom Workflow Block — platform authoring (UNRESOLVED, failing)

Workspace `eze-nnanna-chijioke`, workflow `capture-gate-spike`, evening of 8 Oct (local time, UTC-6).

1. Block editor → Run Test with the block's code in the editor: **`Failed to connect to Modal endpoint: HTTPSConnectionPool(host='roboflow--webexec-roboflow-platform-executor-execute-block.modal.run', port=443): Read timed out. (read timeout=30)`**. Same on first run and on retry after waiting.
2. Same test with a trivial no-input block (`def run(self) -> BlockResult: return {"ok": 1}`): **same error**. So not the code and not the image payload.
3. Workflow editor: **`SERVER ERROR — The dynamic block service timed out while loading output types. Please retry.`** The editor also showed an "Unsaved" banner.

- status.roboflow.com showed "All Systems Operational" including Serverless Hosted API V2; it has no component for the block executor.
- No other report of this exact error found in docs or forum search.
- Not established: whether this is an outage, a cold service, or an account/plan limit. **Do not record it as a plan limitation.**
- Fallback if it persists: author the workflow as a JSON spec in this repo with the block inline, run locally (proven in 0.3).

### 0.5 Data path — MIDV-500 (PASS)

- `ftp://smartengines.com/midv-500/` listing returned in 2.2 s. Entries seen: `2024833545.html`, `Photo.scr`, `dataset`, `documents.pdf`, `extra`, `info.zip`, `license.txt`, `md5.txt`, `readme.txt`, `test_write_perm_8860`. **`Photo.scr` (a Windows screensaver executable) and `test_write_perm_8860` were not downloaded or opened.**
- `dataset/` holds 50 archives, each roughly 600–700 MB, dated 27 Jun 2018.
- Throughput probe: 26,214,400 bytes in 4.942 s = 5.30 MB/s (range request).
- Full archive `01_alb_id.zip`: **656,880,207 bytes in 42.76 s = 15.4 MB/s**; MD5 `0e18ba8c816b6c3bcd7af609e4b70af6` matches `md5.txt`.
- Archive contents (listed with `unzip -l`, not fully extracted): 636 entries; 10 videos (conditions TA, KA, HA, PA, CA × two phones, `A` = `.MOV`, `S` = `.mp4`); 301 `.tif` frames; 301 ground-truth JSONs; 1,017,004,502 bytes uncompressed.
- One frame extracted for inspection: `CA01_01.tif`, shape **(1920, 1080, 3)** (portrait). Mock Albanian ID with a synthetic face, public-domain source, on a cluttered desk. Ground truth gives the document quad per frame (`[[97, 672], [904, 643], [931, 1142], [122, 1185]]`) and per-field quads on the template. Possible use: seed labels for `document` and `data_zone`. Not yet tested.
- Data lives in `midv-500/` (gitignored). **Caveat on MIDV:** it covers 50 document types; the project uses one-document-type framing, so only a few archives are likely needed. Disk is the limit (11 GiB free).

### 0.6 Scaffold

- `git init`, `.gitignore` from `build-artifacts.md` plus `.DS_Store` and `.pip-install.log`. Verified with `git check-ignore -v` before the first commit that `.env`, `prompts.md`, `.venv`, `midv-500/` contents and the install log are ignored.
- `.env` created **empty** (ignored); `.env.example` committed with the variable name only. The API key is for the user to add.

### 0.4b Platform authoring — recovered (later the same evening)

- Retrying the block save returned **"A block with this type already exists"**: the earlier Save had in fact gone through despite the "Unsaved" banner. Renamed the Block Type to `LaplacianVarianceV2` to avoid the collision (the docs do not say where saved blocks are listed or how to edit one).
- Block editor Run Test on `LaplacianVarianceV2` then **succeeded**: output `laplacian_variance`, Data Type float, **1015.3089239358211**. Test image not recorded (not comparable with the 0.3 synthetic numbers).
- The earlier timeouts (0.4) resolved with no change to the block. **Cause unknown**; consistent with a transient service problem, not demonstrated to be one. Not a plan limitation, since the same account runs it now.
- Still to prove: block added to a workflow → Save → **Publish** → published spec fetched and run locally with the dynamic block inside it.

### 0.4c Gate 1 closed — published workflow with the custom block runs locally (2026-10-08)

- In the editor: block added to `capture-gate-spike`, workflow Test returned `{"custom_python_block_output": 1015.3089239358211}` on `CA01_01_preview.jpg` (768×432). Saved **and Published**.
- `fetch_and_run_workflow.py` fetched the published spec: published steps 1, draft steps 1 (so Save-vs-Publish trap avoided). Spec saved to `workflows/capture-gate-spike.json` (2,225 bytes; checked it holds no API key). It contains `dynamic_blocks_definitions: ['LaplacianVarianceV2']`, one step, output `custom_python_block_output`.
- Ran that published spec **in-process on this laptop** on the same file: **1018.3152326527953**. My direct `cv2.Laplacian(gray, CV_64F).var()` on the file gave **1018.3152326527953** — identical.
- **Discrepancy:** hosted run 1015.3089239358211 vs local 1018.3152326527953, a difference of 3.0063 (~0.3%). The block logic is not the cause (local run of the same spec matches the direct computation). Cause not established; suspect image handling in the hosted path (e.g. re-encoding in transit), untested. **Consequence:** tune blur thresholds on the local path, since the demo runs locally, and do not mix hosted and local numbers.
- Quirk: the editor named the step `custom_python_block` and the workflow output `custom_python_block_output`; names are editor defaults, rename before the real build.
- Renamed in the editor and re-published: step `blur_variance`, workflow output `capture_verdict` (an interim name — it currently carries a float, not a verdict; the real verdict block replaces it). Re-fetched the published spec; names confirmed; local run on `CA01_01_preview.jpg` still 1018.3152326527953. (An intermediate name, `compute_variance_score`, was dropped because "score" clashes with the no-numeric-quality-score rule.)

## 2026-10-08 — Phase 1 start

### 1.1 Specimen card

- The user's own cards (expired debit card, loyalty card, Costco card) all carry the real name and PAN, some a signature. **Rejected as capture subjects**: real personal data, the demo is live on a video call, and redacted stills are meant to be committed. (The reasoning is a candidate for `DECISIONS.md` only if it turns into a choice between real alternatives — it is a constraint, not yet a decision.)
- No printer, glossy paper or laminating pouch at home. Plan: print at a Staples (Regina) and laminate or sleeve in gloss, because glare is a labelled class and matte paper barely produces it.
- `generate_mock_cards.py` → `cards/mock-cards-letter.pdf` (US Letter, two layouts at true size 85.6 × 54 mm, 300 dpi): an ID-style card (photo silhouette, text block) and a bank-style card (chip, 16 zeros, name). All invented data; SPECIMEN text sits outside the data zone. First render had the bank number nearly touching the card edge; font reduced 84 → 74.
- `capture_frames.py` written (condition keys 1–7, manifest CSV, resolution recorded per frame). **Not yet run:** camera permission belongs to the user's Terminal; a probe from the build shell returned `isOpened() == False` for indices 0–2, which is expected, not a camera fault.
- The raster PDF (239,708 bytes) was too large to attach to an email by hand (319,613 base64 chars), so `generate_mock_cards_pdf.py` now builds the printable page as a **vector PDF with reportlab 5.0.1: 2,897 bytes**, same layout, sharper at actual size. The raster script no longer writes the PDF (it still writes the PNGs). Rendered the PDF to check it before sending. Emailed to the user's own address with the Staples checklist.
- User decision: shoot **both** cards, split across conditions.

### 1.2 MIDV-500 subset (augmentation)

- Extracted only the 10 videos from `01_alb_id.zip` (≈ 110 MB, not the 301 TIFFs). Each 130–213 frames (1,607 total), ≈ 30 fps, **1080 × 1920 portrait**. Conditions TA/TS table, KA/KS keyboard, HA/HS hand, PA/PS partial, CA/CS clutter (A = `.MOV`, S = `.mp4`, two phones).
- `extract_midv_frames.py`: 6 evenly spaced frames from the middle 80% of each video → **60 frames, 25 MB** in `midv-500/frames/` (gitignored), with `manifest.csv`. **Clutter (CA, CS; 12 frames) went to `heldout_clutter/` from the start** — the plan's generalisation check; never trained on.
- Looked at a contact sheet of 20 of them. Observed, not measured: some keyboard-condition frames show specular highlights on the card; the hand condition has fingers at the card edge/corner; some partial-condition frames cut the card at the frame edge. So MIDV is not glare-free, contrary to the plan's expectation; none of this is labelled yet and no counts are claimed.
- **Mismatches to remember:** MIDV is portrait 1080×1920, the webcam is landscape; and all 60 frames are **one document design** (an Albanian ID), so the model could learn that one card's appearance. Both are reasons MIDV stays augmentation.
- Free disk after this step: 14 GiB (it had read 11 GiB earlier; not investigated).

### 1.3 Capture UX — viewfinder on the phone, not the Mac

- User launched `capture_frames.py` (no frames saved, so no test frames exist): macOS **Continuity Camera** exposed the iPhone as the webcam (OpenCV index 0) and the live preview opened on the Mac (in the VS Code terminal window), while the user was holding the card in front of the phone — hard to frame and centre. The Continuity Camera resolution was **not** measured.
- Change: shoot with the phone's native Camera app (live viewfinder and shutter on the phone), AirDrop each batch to the Mac, then `ingest_phone_photos.py --src <dir> --condition <c> --card id|bank` converts HEIC with `sips`, applies EXIF orientation, downsizes to a 1920 px long edge, re-encodes JPEG (drops EXIF incl. GPS) and appends `captures/manifest.csv` (file, condition, width, height, timestamp, card, source).
- Tested on one JPG and one HEIC made with `sips` from a MIDV frame: both converted, manifest correct. **Untested:** EXIF rotation and the downscale from a real phone photo.
- Open question this raises (not decided): training on phone **stills** vs the demo's live path. If the demo uses the iPhone via Continuity Camera or the MacBook webcam, the training photos came from a different pipeline (photo mode, HEIC/HDR, higher resolution). Candidate `DECISIONS.md` entry once decided.
- `capture_frames.py` (webcam path) is kept for checking the live path; its manifest has 5 columns, the ingest manifest 7 — no test frames were saved, so there is nothing to clear; if the webcam script is ever used for real frames, keep its 5-column manifest separate from the ingest one.

### 1.4 Phone ingest tested on real photos; camera choice

- Test batch of 3 iPhone HEIC photos (`IMG_3272–3274.HEIC`, 3024 × 4032) ingested as `--condition good --card id` → `captures/good/id-good-001..003.jpg`, **1440 × 1920** each (long edge 1920, ratio 0.476). Downscale and portrait orientation confirmed from the printed sizes; **visual orientation not yet confirmed by the user**.
- The printed mock cards do not exist yet (no printer; Staples visit pending), so the subject of these three frames is something else. **To check with the user: if it was a real card, delete the three frames.**
- User will use the **phone on Thursday** → `DECISIONS.md` D-01.
- **Risk to test on Tuesday (not yet tried):** Zoom and the OpenCV/Inference pipeline both using the Continuity Camera feed during the demo; whether macOS allows both to open it at once is unverified.
- User raised building a simple mobile app to show the guidance on-device. Declined as out of scope (mobile app is on the freeze list); recorded as a "what I'd do next" item.

### 1.5 Taxonomy and data_zone drafted (2026-10-08)

- `DECISIONS.md` D-02 (no `bad_capture`/`blurry` class) and D-03 (`data_zone` = printed text block). Both drafts are mine from the existing evidence; the user has not yet reviewed or changed them.
- Checked MIDV's template ground truth (`01_alb_id.json`): `field01`–`field11` are text; `photo` and `signature` are separate keys. The text fields span two columns (template coordinates x 333–904, y 122–496; the template image size was not checked), so a single enclosing rectangle includes a gap between the columns. Accepted for now.
- **Untested:** using MIDV ground truth to pre-label `data_zone`. The per-frame quads exist for the dataset's 301 annotated TIFF frames, not for the arbitrary video frames I sampled, so seeding labels would need either those TIFFs (≈ 900 MB to extract) or a homography from the template.
- **Consequence of D-03 worth stating once:** the portrait photo is not gated by this design, because face matching is out of scope. A real deployment that feeds face matching would need its own photo-zone check.
- Fallback already in the plan if the logic overruns: drop `data_zone` and test glare against the whole document box.

### 1.6 MIDV-500 readme facts that change earlier statements (2026-10-09)

- Videos were shot on **two devices: `A` = Apple iPhone 5, `S` = Samsung Galaxy S3 (GT-I9300)** (not just "two smartphones"). Each document image was **printed on photo paper with a laser colour printer and laminated with glossy film** — the same recipe as the Staples plan for the mock cards; this is the likely source of the specular highlights seen in the keyboard frames.
- The 301 TIFFs = one template image + **30 frames per video from the first 3 seconds only, split at 10 fps** (`ffmpeg -r 10 -q:v 1`). Consecutive frames 0.1 s apart. My 60 video frames were sampled from the middle 80% of the full 4–7 s videos, so they overlap with the TIFF time window only partly.
- Per-frame ground truth is **only the document quad** `{"quad": [[x,y]×4]}` (top-left, top-right, bottom-right, bottom-left). Field quads exist only on the template image. Deriving `data_zone` per frame would need a homography from the template rectangle to each frame's quad: **not tried**.
- TIFF counts from the archive listing: 30 × 10 videos = 300 frames + 1 template, 907,479,464 bytes in total (≈ 3 MB each).
- User review of D-02 and D-03 parked for later.

### 1.7 MIDV TIFF subset with ground-truth labels (2026-10-09)

- User chose the 6-per-video TIFF plan. `midv_to_labels.py` reads the zip with `zipfile` (members read as bytes, written to paths chosen by the script), takes TIFF frames 1, 7, 12, 18, 24, 30 of each of the 10 videos → **60 frames**, converted to JPEG q95, in `midv-500/tiff/<condition>/` (24 MB). Clutter (CA, CS; 12 frames) is in `heldout_clutter/`. Labels in neutral polygon JSON (`midv-500/tiff/labels.json`), not a training format yet: the detection-vs-segmentation decision is open.
- **Output: 60 `document` polygons, 58 `data_zone` polygons, 17 clipped by the frame edge.** Two frames (`partial/midv-PS01_01`, `PS01_07`) have a `document` but no `data_zone` inside the frame: the card is almost entirely out of view.
- Template is 1040 × 653 with 11 text fields; the text-field bounding rectangle is x 333–904, y 122–496 in template coordinates.
- **First version was wrong, found by drawing the labels on the frames:** `data_zone` was a convex hull of the field boxes, which gives a sloping trapezoid (its top edge cut diagonally from the short first field to the right column) — it contradicted D-03 ("one rectangle"). Replaced with the projected bounding rectangle. Re-checked on 12 overlaid frames across keyboard, hand, clutter and partial: document polygon hugs the card, rectangle sits on the text block, alignment holds under rotation. **Only those 12 of 60 were looked at.**
- Observed, not counted: several frames show strong specular glare across the card (e.g. a white band in the partial condition); the hand condition has fingers at the card edge. Neither is labelled. `glare` and `obstruction` are not in MIDV's ground truth and will be labelled by hand.
- Caveat on D-03 evidence: the rectangle includes an empty area in the top-right of the text block (the right column starts lower than the left), so it is "all text fields", not "tight to every character".
- The 60 video frames from 1.2 (`midv-500/frames/`) are now unused, kept on disk, not deleted.

### 1.8 Shooting protocol (2026-10-09)

- `SHOOTING-PROTOCOL.md` written: **112 frames** split evenly across the `id` and `bank` mock cards — good 30, glare_direct 14, glare_oblique 14, obstruction 26, partial 10, blur 10, lowlight 8. Obstruction raised from 22 to 26 because the Gate 3 floor is ≥ 20 instances and 22 leaves no margin if some frames do not label cleanly.
- Orientation: mostly landscape, about a quarter portrait — a hedge, since whether the Continuity Camera feed is landscape is **unverified**.
- Deliberate negatives built in: about 3 of 7 glare frames per card have glare off the text block; about 5 of 13 obstruction frames per card have fingers on the edge but not over the text. These test that the intersection logic does not fire on every glare or finger.
- The printed cards still do not exist (Staples visit pending); no frames shot yet beyond the 3 test frames.

## 2026-10-09 — Shoot, session 1 (ID card)

- Batch `good`, card `id`: 16 new frames ingested (`IMG_3275–3281`, `3284–3292`; `3282–3283` not ingested) → `id-good-004..019`. Frames `001–003` are the earlier test frames from before the cards were printed; **their subject was never confirmed** (open question to the user). Orientation of all 19: 10 portrait, 9 landscape. 4032×3024 → 1920×1440; 3024×4032 → 1440×1920.
- Batch `glare_direct`, card `id`: 11 frames (`IMG_3306–3312`, `3322–3325`) → `id-glare_direct-001..011`; 7 portrait, 4 landscape. Over the per-card target of 7 by 4.
- **Whole-frame Laplacian variance, measured:** `good` (19 frames) min 189.5 / median 528.6 / max 1602.4; `glare_direct` (11) min 166.0 / median 221.6 / max 398.8. Whether every `good` frame is sharp was not checked by eye, but if so, the whole-frame value spans about 8.5× (1602.4 / 189.5) from scene texture alone → the blur check probably has to be computed **inside the `data_zone` (or `document`) crop, not on the whole frame.** Candidate `DECISIONS.md` entry once tested on the labelled crops. No inference drawn from glare frames being lower (backgrounds differ).
- Shoot-session set-ups were not yet written down by the user (requested).

### Session 1 review (visual, 2026-10-09)

- User confirmed the earlier test frames were **Costco cards** (real) and deleted them. Manifest checked after deletion: 27 rows, 27 files, none stale. The originals may still sit in the phone's Photos / Recently Deleted and the Mac's Downloads (user to clear).
- **Bug found and fixed in `ingest_phone_photos.py`:** the next number was the *count* of existing files, so after deleting 001–003 a new `good` batch would have started at 017 and overwritten `id-good-017.jpg`. Now highest existing number + 1. Tested in a scratch folder with files 004, 005, 017 → next is 018.
- Viewed thumbnails of all 27 frames and a larger view of six `glare_direct` frames (my eyeball judgement, not measured): `good` varied and legible; `id-good-004` contains the bank mock card at the bottom edge (recommend delete); card in a clear pouch → `document` follows the printed edge. **`glare_direct`: the card is fairly matte; most bright patches are on the counter. About 3 of 11 show a patch on the card (005, 006, 010); none clearly on the text block** (006: just below it; 010: on the photo area; 007: faint haze). Gate 3 needs ≥ 25 glare instances, so more of the same would not meet it.
- Protocol amended: flash or a second phone's torch allowed for glare frames; card to fill about half the frame width; check on the phone that a patch is visible.
- `sync_manifest.py` added: removes manifest rows for deleted frames. Run at this point: 26 rows, 26 files (good 15, glare_direct 11), 0 removed. (`id-good-004` is already gone from disk and the manifest.)
- Advice given on the 11 `glare_direct` frames (from thumbnails, not measured): keep 005, 006, 007, 010 (patch on card or borderline) and a few clean-card frames as negatives; delete one of the near-identical 008/009 and 001 (small card, no distinct content). Final pruning to be decided after labelling, when it is clear which frames carry a `glare` label.

### Session 1 — glare reshoot review (2026-10-09)

- Deletions checked: `glare_direct-001` deleted (manifest was 41 rows vs 40 files) → `sync_manifest.py` removed the row → 40 rows, 40 files, nothing orphaned either way. `id-good-004` already gone. `008` and `009` (near-duplicates) both still present; user to decide.
- New batch `IMG_3348–3368` (15 frames, all 3024×4032 → 1440×1920) → `id-glare_direct-012..026`. Counts now: `good` 15, `glare_direct` 25, all card `id`.
- Visual review (thumbnails, eyeball, not measured): **017–026 (10 frames) show a large saturated flash blob over the text block, text beneath washed out** — the clear `glare_over_data_zone` positives. 013–015 small spots near the text; 016 a sheen along the edge; 012 clean. **Problems:** (1) blobs are all round, saturated and similar in size and position — flash glare only; streaks/bands needed (`glare_oblique`); (2) about 11 of 15 new frames are hand-held vs about 2 of 15 `good` → "hand ⇒ glare" confound; (3) only about 3 set-ups across the 10 clear frames (017–020, 021–024, 025–026) → near-duplicates; (4) no glare-off-text frames yet.
- Gate 3 estimate (eyeball, not a count): about 14–18 usable glare instances so far vs ≥ 25 needed across both cards.

### Session 1 — third check (2026-10-09)

- Ingested: `good` +4 (`IMG_3376, 3378–3380` → `id-good-020..023`, hand-held, 4032×3024 → 1920×1440), `glare_direct` +10 (`IMG_3369–3373, 3375, 3377, 3381–3383` → `027..036`), `blur` 7 (`IMG_3336–3339, 3341–3343` → `id-blur-001..007`; two files had a lowercase `.heic` extension and were handled). **Manifest: 61 rows = 61 files, no duplicates, nothing orphaned.** Counts (all card `id`): good 19, glare_direct 35, blur 7.
- **Whole-frame Laplacian variance, measured:** blur 59.8–86.6 (001 68.7, 002 86.6, 003 75.9, 004 70.5, 005 59.8, 006 61.8, 007 61.8); good min 189.5 / median 488.7 / max 1602.4; glare_direct min 88.1 / median 305.0 / max 790.3. Blur max (86.6) < good min (189.5) in this set. **But six glare frames fall below the good minimum — 035 (88.1), 023 (149.2), 005 (166.0), 008 (173.1), 036 (173.3), 034 (188.3) — and 035 sits within 1.5 of the blur maximum.** A whole-frame threshold anywhere between ~87 and ~189 would flag glare frames as blurry. Supports computing blur inside the `data_zone`, and suggests glare haze lowers the measure (untested on crops).
- Visual (eyeball): blur gradient looks real — 001–004 mild/medium (text legible but soft), 005–007 heavy (text unreadable). All look like defocus; no motion blur. 002–004 appear to extend to the frame edges (possible partial-capture confound). New `good` frames sharp, hand-held, legible → hand confound reduced (about 6 of 19 `good` hand-held). `glare_direct` 027–032 soft sheens/bands on a dark carpet (more varied, fuzzy edges); 033 glare on the title band, text clear (good negative); 034 whole-card haze; **035 and 036 show dark smudged marks over the text — look like reflections, not bright glare → ambiguous, recommend not labelling as glare (candidate hard cases for the limitations slide).**
- **Budget arithmetic:** `id` has 61 frames so far against a per-card plan of 56 for all seven conditions, with `glare_oblique` (7), `obstruction` (13), `partial` (5), `lowlight` (4) still to shoot (29 more → 90 for `id`). Same counts for `bank` would pass the brief-era cap of 120 own frames. Labelling time is the constraint (plan assumed 120–150 frames in about 2.5 h, plus 60 MIDV frames needing glare/obstruction by hand).

### Session 1 — fourth check, ID card complete (2026-10-09)

- Manifest **96 rows = 96 files**, no duplicates, nothing orphaned. All card `id`. Counts: good 19, glare_direct 35, glare_oblique 12, obstruction 13, partial 6, blur 7, lowlight 4. Per-card plan was 56 total → 40 over, mostly `glare_direct` (+28).
- **Orientation, counted from the manifest: 69 portrait / 27 landscape (about 72% portrait)** — the reverse of the protocol's "mostly landscape". `glare_oblique` 12/12 portrait, `glare_direct` 30 of 35 portrait. Demo feed orientation still unverified.
- Whole-frame Laplacian variance (measured): glare_oblique min 597.4 / median 1071.5 / max 1793.9; obstruction 128.6 / 261.6 / 804.3; partial 128.7 / 803.7 / 2065.6; **lowlight 18.0 / 46.8 / 192.4 — below the blur batch's 59.8–86.6 range although the lowlight text is legible by eye** → a whole-frame blur check would flag legible dark frames as blurry.
- Visual (eyeball, thumbnails): `glare_oblique` varied — soft bands on wood (001–005), curved arcs across the photo area on a keyboard (006–010), streaks on carpet (011–012); most arcs sit on the photo/top-left, i.e. glare-off-text negatives; 002, 003 cross the lower text. `obstruction`: about 6 clearly over the text (002, 006, 007, 011, 013, maybe 012), about 6 at the edge only (001, 003, 004, 005, 009, 010), 008 ambiguous — a good over/not-over mix. **Four obstruction frames (001, 002, 003, 011) show a laptop screen with readable text/notifications in the background** (privacy). `partial` 001, 002, 005: mostly out of frame (a sliver); 003: left side cut but text block fully visible (the wanted case); 004: right side cut; **006 looks like a full card in frame — possibly mis-filed (to be confirmed by the user)**. `lowlight`: all four dim but legible.
- **Gaps found in the design, not yet decided:** (1) no rule yet for when a finger counts as `obstruction` (fingers hold the card in about 25+ frames across conditions); (2) `lowlight` has no class and no reason code — legible dark frames should probably be `usable`, which the whole-frame blur check would contradict.

### Privacy crops (2026-10-09)

- User agreed the numbers and chose to **crop** (not skip) the four obstruction frames showing a laptop screen. Cut from the top: `id-obstruction-001`, `002`, `011` at 37% (1440×1920 → 1440×1210), `003` at 30% (→ 1440×1344; keeps the thumb over the card's top edge). `011` removed a dock and a notification/status bar that included the user's username.
- Originals copied to `private-backup/` (new, gitignored) before cropping; manifest width/height updated.
- Checked the leftover strips at full resolution: the remaining screen in 001/002/003 is out-of-focus lines with no readable words (my reading); 011 shows keyboard only. Obstruction count therefore stays 13 (not 9).
- Agreed plan (user): label ID card about 81 frames (good 19, glare_direct 20 of 35, glare_oblique 12, obstruction 13, partial 5–6, blur 7, lowlight 4); bank card about 34 frames, mostly landscape (good 8, glare 8, obstruction 10 with at least 6 over the text, partial 3, blur 3, lowlight 2) → about 115 own frames, under the 120 ceiling. `glare_direct` picks: 003, 005, 006, 007, 010, 011, 013, 014, 016, 017, 019, 021, 023, 025, 027, 029, 031, 032, 033, 034; exclude 035 and 036 (dark reflections; hard cases).
- **Still open (user has not answered):** finger-as-obstruction rule; lowlight handling; whether `partial-006` is a full-card frame; Thursday demo-feed orientation.

### Decisions taken by the user, 2026-10-09

1. Finger rule agreed → `DECISIONS.md` D-04.
2. User chose to **add a `too_dark` reason** (not treat legible dark frames as usable) → D-05, drafted by me from measured evidence; the user has not yet reviewed the wording. Reason codes are now: `glare_over_data_zone`, `incomplete_document`, `obstructed`, `blurred`, `too_dark`, `no_document`. It is a thresholded measurement, not a score, and is within scope before the Monday freeze.
3. `partial-006` is **not** a full-card frame (not all four corners in view) → stays `partial`.
4. Demo-feed orientation **undecided** by the user, hence both portrait and landscape in the set.
- **Whole-frame mean grey, measured:** lowlight 33.3 / 33.7 / 37.2 / 41.7 (001, 003, 002, 004); darkest non-lowlight frames are the dark-carpet glare frames `glare_direct` 027 (78.1), 028 (81.0), 031 (82.5), 030 (88.3), 029 (90.2); good min 127.4. Per condition (min / median / max): blur 145.0 / 157.7 / 165.3; glare_direct 78.1 / 131.0 / 161.6; glare_oblique 109.6 / 129.1 / 134.3; good 127.4 / 143.0 / 169.2; obstruction 109.4 / 139.3 / 153.7; partial 140.2 / 147.6 / 160.7.
- Consequences noted: (a) a whole-frame brightness threshold would be confused by dark *backgrounds* with a bright card (the carpet frames), so brightness, like blur, belongs on the card region; (b) all four lowlight frames are at one narrow dark level (33–42), so a threshold cannot be tuned from them — a gradient of mildly dim frames is missing; (c) brightness must run before blur in the precedence order.
