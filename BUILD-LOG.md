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

## 2026-10-09 — Shoot, session 2 (bank card): check

- Manifest **150 rows = 150 files**, no duplicates, nothing orphaned. Bank: 54 frames — good 10, glare_direct 11, glare_oblique 11, obstruction 10, partial 5, blur 4, lowlight 3 (plan was 34: glare 22 vs 8). Orientation: bank 23 landscape / 31 portrait; **all 150 frames: 54 L / 96 P (64% portrait)**, up from 72% portrait for the ID card alone.
- **Non-camera files:** `bank-glare_direct-007` (1242 × 1566), `010` (887 × 1920), `011` (1242 × 1659). 1242 px is an iPhone screenshot width; `010` visibly contains the Photos app interface (clock, back button, toolbar). So these three are screenshots of photos, not the camera originals. (The four other non-standard sizes are the ID privacy crops.)
- Bank per-condition whole-frame Laplacian variance (min / median / max) and mean grey: blur 19.4 / 61.7 / 1444.0, mean grey 64.4–146.9; glare_direct 83.9 / 321.3 / 1040.2; glare_oblique 357.9 / 714.5 / 1018.4; good 132.2 / 206.5 / 299.8, mean grey 85.5–141.6; lowlight 14.2 / 29.2 / 32.0, mean grey **15.5–18.9** (001 15.5, 003 17.8, 002 18.9); obstruction 122.0 / 288.7 / 922.5; partial 110.6 / 495.4 / 821.9.
- **`bank-blur-004` has whole-frame variance 1444.0** — higher than any ID `good` frame except the maximum (1602.4) — yet it is labelled blur (001 56.2, 002 67.2, 003 19.4). By eye it is only mildly soft, on a high-texture carpet. Second, very direct evidence the blur check cannot use the whole frame.
- Visual (eyeball, thumbnails): `good` varied (marble, dark desk, wood, carpet, keyboard, hand). `blur`: 002 is true **motion blur** (streaks), 003 defocus with keyboard bokeh, 001 heavy and close (card runs off the frame), 004 mild. `lowlight`: all three extremely dark, text barely legible in 001 and unreadable in 003. `glare_direct`: round blobs over the number on 004, 005, 007, 011; small spots on 001, 002. **`glare_oblique` is the standout: curved S-arcs and thin diagonal/vertical streaks crossing the number block** (shape variety achieved) — but nearly all on one wooden desk. `obstruction`: thumbs over text (001, 002, 007–009), a white cable across the number row (004), a black object across the top (003), edge-only fingers (005, 006, 010). `partial`: five, mostly close-ups cut at an edge.
- **Evidence for the detection-vs-segmentation decision (not yet decided):** thin diagonal glare streaks that cross the data zone have axis-aligned bounding boxes covering far more than the streak, so a box-based "glare intersects data_zone" test would over-trigger where a polygon test would not.
- **Gradient still missing for `too_dark`:** darkest non-lowlight frame 78.1 (carpet); ID lowlight 33.3–41.7; bank lowlight 15.5–18.9 → nothing between about 42 and 78.

### Screenshot frames replaced by video extraction (2026-10-09)

- The three screenshot-sized bank glare frames came from paused phone videos. User asked whether to supply the videos instead (best glare happens in the first 3 s). Answer: yes — frames from the original video have no interface and no screenshot scaling. **Deleted `bank-glare_direct-007`, `010`, `011`** and synced the manifest (150 → 147 rows). Remaining bank direct-glare numbers: 001–006, 008, 009 (next ingest gets 010; numbers can be reused after deletion, file names are the key).
- `extract_video_frames.py` added: `--n` evenly spaced moments in `[--start, --end]` (default 0–3 s, 4 frames), each nudged to the sharpest frame within ±4 frames (whole-frame Laplacian variance, used only to avoid motion-blurred picks), JPEG q95, long edge ≤ 1920, manifest `source=video`. Tested in a scratch folder on `CA01.MOV` (iPhone 5, 4.40 s, 29.98 fps): four frames at t = 0.03, 0.97, 2.00, 3.04 s, all 1080 × 1920 portrait, numbering continued 001–005. **Untested:** modern iPhone HEVC or 4K video.
- User: will shoot 4 more `lowlight` frames at moderate dimness; accepted the labelling proposal (about 125 own frames + MIDV capped at about 24 train frames, 12 Clutter held out), and may label more depending on time and on whether SAM 3 speeds labelling up.
- To test, not assume: SAM 3 auto-label on a small sample per class, counting how many drafts needed correcting. From the PPE build: SAM 3 keyed on nouns and ignored negation; nouns like "ID card" or "thumb" may work, "text block" and "bright reflection" are unknowns.
- User correction: the best glare is at about **0.02 s** and the videos are **very short**, so spreading picks over 0–3 s was wrong, and the sharpest-neighbour step could drift away from the glare moment. `extract_video_frames.py` now takes `--times T [T ...]` (exact moments) and `--window 0` disables drift. Tested in a scratch folder: `--times 0.02 0.3 --window 0` on `CA01.MOV` (29.98 fps) gave t = 0.03 s (frame 1) and 0.30 s (frame 9). At about 30 fps one frame is about 33 ms, so 0.02 s falls between frame 0 and frame 1 and rounds to frame 1.

### Video-sourced bank glare frames (2026-10-09)

- Six frames from two short videos → `bank-glare_direct-010..015`, all **1440 × 1920** (the videos are 3:4, so no rotation problem), manifest `source=video`. **Manifest 153 rows = 153 files**, no duplicates, nothing orphaned. Bank counts: good 10, glare_direct 14, glare_oblique 11, obstruction 10, partial 5, blur 4, lowlight 3.
- Measured (whole-frame Laplacian variance / mean grey): 010 330.4 / 189.2; 011 390.7 / 171.5; 012 488.9 / 144.2; 013 **12.4** / 205.4; 014 131.3 / 189.7; 015 645.1 / 151.9. Within each clip sharpness rises and brightness falls from the first frame to the last.
- Visual (eyeball): 010–012 are near-duplicates of one moment — a strong round flash blob over the number row — differing mainly in exposure (010 brightest with a washed-out chip, 012 richer colour). **Likely, unconfirmed:** the camera's auto-exposure is still settling in the first fractions of a second, which is why the glare is strongest at about 0.02 s. 013–015: a close-up with the card cut by the frame, large blob over the number; 013 is overexposed and soft (12.4 is lower than any other frame in the dataset, the blur batch's lowest is 19.4); 015 is readable around a smaller blob.
- **013 is glare + blur + partial in one frame** → a natural test for the reason-code precedence.
- Updated bank glare picks: `direct` 001, 004, 005, 010, 012, 013, 015; `oblique` 001, 002, 003, 006, 007, 009, 011 (skip 011 and 014 of the video set: near-duplicates). Own frames labelled about 127.
- Still to shoot: 4 moderately dim `lowlight` frames (mean grey roughly 50–100 target; a guide, not a guarantee).

### Lowlight gradient added; shoot complete (2026-10-09)

- Four moderately dim bank frames ingested (`bank-lowlight-004..007`, all phone, 1440×1920 or 1920×1440). **Manifest 157 rows = 157 files**, no duplicates, nothing orphaned. Totals: `id` 96, `bank` 61.
- Mean grey / whole-frame Laplacian variance: 004 54.0 / 34.4; 005 52.5 / 40.6; 006 54.1 / 41.7; 007 58.0 / 35.5. Lowlight levels now: very dark 15.5–18.9 (bank 001–003), dark 33.3–41.7 (id 001–004), dim 52.5–58.0 (bank 004–007). Nothing between 58.0 and the darkest non-lowlight frame (78.1).
- Visual (eyeball): 004 smeared (looks motion-blurred, slow shutter), 005 and 006 legible, 007 soft; all four dark-blue card on dark carpet (low contrast), same background. **At nearly equal brightness legibility differs (004 at 54.0 smeared, 006 at 54.1 readable) → whole-frame mean grey does not predict legibility; measure on the `data_zone` and consider its contrast.** Dim light also blurs the image, so `too_dark` and `blurred` can fire together (D-05 puts `too_dark` first); the new frames' whole-frame variance (34–42) sits inside the blur batch's range (19.4–86.6).
- **Own-frame shoot complete: 157 frames.** To label about 127 of them (picks recorded above) plus about 24 MIDV training frames; 12 MIDV Clutter frames held out.

## 2026-10-09 — Detection vs segmentation research

### Platform facts (read from the primary docs; not yet tried in the user's account)
- Training resolutions (docs table): RF-DETR **Nano 384×384**; Seg **Nano 312×312**, Seg Small 384×384, Medium 432, Large 504, XL 624, 2XL 768.
- **Instance Segmentation project required** for RF-DETR Segmentation training ("semantic segmentation is not supported"); launched as a **preview on 2 Oct 2025** (changelog). A Roboflow comparison page (secondary) says the full Nano–2XL family came in Jan 2026. **Whether hosted Train offers Seg Nano/Small on this account: unverified** until the project exists.
- Project type decides accepted annotation formats: detection accepts boxes, polygons and masks (polygons/masks are **converted to boxes automatically**); instance segmentation accepts polygons and masks; boxes in a segmentation project train poorly (Roboflow staff reply). So **polygon labels keep both options open; box labels do not.**
- Runtime: segmentation checkpoints run on the Serverless API and self-hosted Inference; the Workflows "Instance Segmentation Model" block exists (`roboflow_core/roboflow_instance_segmentation_model@v2`). Hosted-training credit cost for segmentation: not found in the docs.
- Custom Python block libraries documented: `cv2`, `numpy`, `supervision`, `shapely` → mask/polygon geometry is available inside the block.

### Measured latency on this machine (Apple M3, 16 GB, ONNX Runtime CoreML EP, `inference` 1.7.3, `benchmark_models.py`)
COCO-pretrained checkpoints (same architecture and input size as what would be trained), image `captures/good/id-good-005.jpg` (1920×1440), model.infer incl. pre/post-processing, 3 warm-ups then 20 timed runs:

| model | input | p50 | p95 | min / max | fps at p50 | CoreML nodes / partitions |
|---|---|---|---|---|---|---|
| rfdetr-nano (detection) | 384 | **37 ms** | 38 | 36 / 41 | 26.84 | 778 of 822 / 13 |
| rfdetr-seg-nano | 312 | **56 ms** | 57 | 54 / 58 | 17.95 | 1077 of 1109 / 12 |
| rfdetr-seg-small | 384 | **80 ms** | 84 | 77 / 84 | 12.57 | 997 of 1060 / 17 |

- **Caveats:** zero detections on this image for all three, so **mask post-processing was not exercised** (seg latency with real masks is probably higher; untested). Excludes camera, drawing and Workflow/custom-block overhead.
- **Not comparable with the PPE build's 1.88–2.22 fps:** that run was at 640 px input, through a pipeline with camera and drawing, on `inference` 1.6.2 where CoreML took 725 of 900 nodes in 104 partitions; this run is 1.7.3 with 12–17 partitions. Not attributing the difference to a cause.

### Does thin glare survive the resize? (looked at two bank oblique frames, 003 and 007, 1440×1920 stretched to 384² and 312²)
Scale factors to 384: x 0.267, y 0.2; to 312: x 0.217, y 0.163 (aspect is stretched, as in the PPE build). The streaks and the number text stay clearly visible at both sizes in these two frames. **Only two frames checked**; the thinnest streaks in the set are not verified.

- User agreed: instance segmentation, start at Seg Nano → `DECISIONS.md` D-06 (project type) and D-07 (native 312 input). Both are my drafts from the measured evidence; not yet reviewed by the user. **`DECISIONS.md` now holds 7 of its 10 entries**; the three left are earmarked for augmentation (rotation included), the reason-code precedence order, and the out-of-scope boundary.
- Before any upload: confirm the Roboflow project is **private**. The raw frames show the user's home and hands, and a public project would publish them. Plan visibility not yet checked.
- **`DECISIONS.md` hard limit raised from 10 to 15 entries** (user, 2026-10-09). Updated in `interview-prep/roboflow/notes/build-artifacts.md`. It now holds 7 of 15. The note "7 of its 10" above is superseded.

### Public project, licensing and the upload set (2026-10-09)

- The Roboflow project `capture-gate` was created as Instance Segmentation. The user cannot make it private without a plan upgrade, so it is **public**; the user chose to upload their own frames anyway (their call, made knowing the frames show their home, hands and desk). Roboflow's docs say the free plan makes data public by default and that copyrighted or personal data should not be published on Universe. Nothing was uploaded before this decision.
- **MIDV-500 licence read from `license.txt`: CC BY-SA 2.5.** Attribution plus ShareAlike. The licence choices I found for public Roboflow projects (third-party guide, unverified): Public Domain, CC BY 4.0, MIT, BY-NC-SA 4.0, ODbL, none — no ShareAlike entry. → **MIDV is not uploaded** (D-08); it is the local held-out evaluation set. MIDV training augmentation (about 24 frames) is dropped from the plan; the 60 TIFF frames and their ground-truth labels stay local, used for evaluation (12 Clutter frames) and optionally the other 48.
- `build_upload_set.py` → **131 own frames staged in `upload/own/`** (gitignored copies; 112 MB) + `upload/own-set.csv`. id 81 (good 19, glare_direct 20, glare_oblique 12, obstruction 13, partial 6, blur 7, lowlight 4), bank 50 (good 10, glare_direct 7, glare_oblique 7, obstruction 10, partial 5, blur 4, lowlight 7). **No EXIF/XMP metadata in any of the 131** (checked with PIL; HEIC conversion and JPEG re-encode dropped it).
- Not decided yet: the project's licence (the user picks it in Roboflow's Make Public flow); how to split train/valid/test (many near-duplicates within a capture set-up, so a random split would inflate validation scores).

### Capture-group split (2026-10-09)

- `make_split.py` → `upload/train` 92, `upload/valid` 26, `upload/test` 13 (**70.2% / 19.8% / 9.9%** of 131), plus `data/split.csv` (filenames, card, condition, family, group id, split; committed, no images).
- Groups: runs of consecutively numbered frames (ingest order = shot order) within a (card, condition) whose neighbours have HSV-histogram Bhattacharyya distance ≤ 0.4 → **64 groups** from 131 frames. Neighbour distances are a continuum, not bimodal, so the cutoff is a judgement call: TAU 0.5 merged too much (e.g. all 8 bank obstruction frames in one group), 0.4 gave workable groups.
- **First attempt, greedy assignment at TAU 0.5: poor** — big groups left bank obstruction and bank glare_oblique with nothing in valid or test; per-card greedy: ID blur all in train. Replaced by a seeded random search (60 restarts × 4000 steps) scoring closeness to 70/20/10 per family and penalising: a key class (glare, obstruction) missing from valid or test for either card; a family missing from valid or test; a card/family missing from train. Second version still left all four ID lowlight frames out of train — fixed with the train-coverage penalty.
- Per family (train / valid / test): blur 8/2/1; glare 32/9/5; good 20/6/3; lowlight 8/2/1; obstruction 16/5/2; partial 8/2/1. Glare: bank 10/1/3, id 22/8/2. Obstruction: bank 7/2/1, id 9/3/1.
- **Leakage, measured:** nearest-train-frame distance for valid/test frames: group split median **0.566**, mean 0.526 (n = 39); random splits median 0.292, mean 0.325 (20 seeds, n = 772). Higher = less leakage. Colour-histogram distance is a crude proxy for "same shot".
- **Limits stated plainly:** test has 13 frames, with only **2 obstruction, 1 lowlight, 1 blur, 1 partial** frames → per-class numbers on the test split are anecdotal; report instance counts alongside any AP. Groups are bursts, not backgrounds: the same desk/carpet/counter appears in train and valid, so valid measures new shots, not new backgrounds — that is what the MIDV Clutter held-out set (local) is for. Bursts of the same set-up in different conditions (e.g. a hand in `good` and in `glare_direct`) are not linked.
- Roboflow mechanics (docs/search, not yet tried here): the web uploader lets a batch be assigned to a split (older blog; the UI may have changed); the SDK/CLI/REST upload take `split=train|valid|test`; **do not use "Rebalance Train/Test Split" afterwards — it re-randomises.**

### Universe augmentation candidates reviewed (2026-10-10)

- User suggested two Roboflow Universe sets. Read both pages in the built-in browser (Universe returns HTTP 403 to the fetch tool); **did not open their images** (avoiding viewing personal ID documents).
- `test-ckwzi/cccd-7dlm5`: Instance Segmentation, **134 images**, CC BY 4.0, classes `id-card`, `tlu-card`, updated 2 years ago (published Aug 2024), no description. `afc-s-workspace/cv-byofn`: Instance Segmentation, **110 images**, CC BY 4.0, classes `car`, `back`, `addres`, `drive`, `iraq id card`, updated 2 months ago, 4 versions, no description. Neither says whether the documents are specimens or real people's cards; the names point at Vietnamese and Iraqi national IDs.
- Not used: provenance unverifiable against the no-real-identity-document rule; class mismatch (no `data_zone`/`glare`/`obstruction`) → partial labels would teach the model those classes are absent; small gain (only `document` outlines). `DECISIONS.md` D-08 widened to "no public dataset goes into the Roboflow project".

## 2026-10-10 — Upload verified

- User uploaded the three batches. **Verified through the Roboflow API (script, key from `.env`, key not printed):** project `eze-nnanna-chijioke/capture-gate`, type `instance-segmentation`, **public**, **license CC BY 4.0** (the user kept the default and did not remember it), 131 images, `unannotated` 131, classes `{}`, versions 0.
- **Per-image split check via the search endpoint: 131 of 131 present; split counts train 92 / valid 26 / test 13; 0 images with a different split from `data/split.csv`; 0 missing; 0 extra.**
- The project-level `images` and `splits` fields read 0 because uploaded images sit in the annotation queue until annotated and added to the dataset; the Dataset page may show 0 until then.
- Next: classes (`document`, `data_zone`, `glare`, `obstruction`) and a SAM 3 auto-label trial on 10 frames before labelling everything.

## 2026-10-10 — Labels from the printed template

- User reported SAM 3 produced **no `data_zone` on any frame** in the mask preview. Consistent with the PPE finding (nouns work, regions don't). Rather than tune prompts, derived `document` and `data_zone` from the cards' known layout: `template_labels.py` (SIFT + RANSAC homography, then ECC alignment refinement) → `labels/template-labels.json` (gitignored).
- **Three bugs found by looking, not by the numbers:**
  1. First version matched against `mock-*.png`, not the PDF as printed. Rendered the PDF (`cards/print-id.png`, `print-bank.png`) and compared text rows: PNG vs print agree within about 5 px (ID rows 101–500 vs 102–502; bank 250–443 vs 246–439) — the layouts match, so this was not the cause, but the print render is now the template.
  2. **`data_zone` was far too wide** (contradicting D-03): the ID zone was the whole right panel, 653 px wide, while the printed text is **310 × 400 px** (x 329–639, y 102–502; bank 872 × 193, x 36–908, y 246–439). Zones now = measured text box + 10 px margin: ID (319, 92, 649, 512), bank (26, 236, 918, 449). A glare patch on blank card would otherwise have counted as "over the data zone".
  3. **≥ 20 SIFT inliers did not guarantee an accurate homography** (`bank-obstruction-007` outline was a lopsided trapezoid on a clean rectangle). Added ECC refinement; its correlation is a quality score, but **occlusion and glare lower it without misaligning the label**, so it cannot be a pass/fail gate by itself.
- Matching: 123 of 131 frames labelled (first version 118). ECC correlation: n = 120, min 0.178, median 0.807, max 0.969; 30 frames below 0.6. **Failures (no label, 8):** `id-blur-005`, `id-blur-006`, `bank-lowlight-002`, `bank-lowlight-003`, `bank-blur-002`, `bank-blur-003`, `bank-blur-004`, `bank-lowlight-004`. **Labelled by SIFT only, ECC failed, unverified (3):** `id-blur-004`, `bank-blur-001`, `bank-lowlight-007`. → **11 frames need hand-drawn `document` and `data_zone`** (`labels/manual-needed.json`).
- **Visual check, 56 distinct frames:** the 30 lowest scores, 24 random frames with score ≥ 0.6, and the 4 I doubted (some overlap). All looked correct (outline on the card edge, red box on the text block) except two slightly rotated outlines: `bank-partial-002`, `id-glare_direct-023`. The other 67 labelled frames were not looked at. Also un-warped 12 frames into template space: card layout and text rows landed where the template says.
- `DECISIONS.md` D-03 evidence corrected (measured text box) and **D-10** added; 10 of 15 entries.

### Labelling order (2026-10-10)

- User has annotated **nothing** (only used the SAM 3 *preview* to avoid spending credits). Advice: import the template labels first — an annotation upload may overwrite hand-drawn labels on the same image (unconfirmed) — then hand-draw `glare` and `obstruction` on top, then the 11 frames the template could not label.
- `data/labelling-order.csv`: 131 frames; priority 1 glare conditions, 2 obstruction, 3 good, 4 partial/blur/lowlight; the 11 hand-draw frames flagged. Every frame still needs a skim for incidental glare or fingers over the printed surface, because an unlabelled instance teaches the model that the class is absent.

### Annotation-import research and dry run (2026-10-10)

- **Docs (read directly):** `POST https://api.roboflow.com/dataset/{dataset}/annotate/{image_id}` attaches an annotation to an image already uploaded; body = the raw annotation file, or JSON `{annotationFile, labelmap}` for Darknet TXT. Formats named: Pascal VOC XML (boxes only) and Darknet/YOLO TXT; "any supported format that references the image file name". **Polygon / instance-segmentation support is not stated.** The Python SDK `save_annotation` has `annotation_overwrite` (default not stated in the REST page; a search summary says a 409 conflict is returned when the image already has an annotation and the flag is false — **unconfirmed**). `prediction=true` stores an annotation as a model prediction awaiting review instead of ground truth.
- `import_template_labels.py`: dry run is the default (reads image ids only; writes `labels/yolo/*.txt`; sends nothing). `--only FILE` writes one image, `--all` writes all. A 409 is reported and skipped, never overwritten. Key read from `.env`, not printed.
- **Correction:** the dry run showed **120 frames have both polygons; 3 of the "matched" frames (`id-blur-004`, `bank-blur-001`, `bank-lowlight-007`, the ones where ECC refinement failed) have no polygons at all** (degenerate outlines). So the template labelled **120 of 131**, not 123; the 11 frames to hand-draw are unchanged (8 unmatched + these 3). D-10's evidence line corrected.
- Validation (local): 240 polygon rows, all with ≥ 3 points, normalised to [0, 1], none malformed. **Untested against the platform:** whether YOLO polygon text imports as polygons in an Instance Segmentation project, and what happens with an already-annotated image.

- **Import test passed (user ran `--only id-good-021.jpg`):** response `200 {"success":true}`. The editor shows both labels (green `document` outline on the card, purple `data_zone` rectangle around the text block). **API read-back of the stored annotation: both stored as `"type": "polygon"` with four points each** (`document` points [[330.182, 1214.892], [1487.155, 1198.256], [1464.609, 506.052], [364.971, 480.948]], `data_zone` [[713.259, 1061.266], [1087.361, 1058.747], [1085.057, 594.981], [723.26, 588.58]]), image 1920 × 1440, split valid. So the YOLO-polygon route imports as polygons in the Instance Segmentation project. Classes `document` and `data_zone` now exist in the project.
- Still unconfirmed: whether a second upload to an already-annotated image conflicts (409) or replaces — the `--all` run will include `id-good-021` again and show which; whether annotation uploads consume credits (not stated in the docs).

- **`--all` import aborted before sending anything** with `not found on the platform or in the label file: ['id-glare_oblique-003.jpg']`. Cause checked: the platform still holds all 131 images (92/26/13) including that one; **my image-id lookup paged with offsets and skipped it** (result order can shift between pages). Fixed `import_template_labels.py`: it now retries until the number of unique names equals the project's reported total (up to 6 attempts). Nothing was written by the failed run; only `id-good-021` carries an annotation.

### Template labels imported and verified (2026-10-10)

- User ran `import_template_labels.py --all`: **119 ok, 1 skipped, 0 failed**. The skipped image was `id-good-021` (already annotated from the one-image test) → **a repeat upload to an annotated image is blocked, not replaced** ("already annotated, skipped").
- **Verified against the platform (API, every annotated image's detail record, not the script's own count):** 131 of 131 images fetched; 120 images with annotations = exactly the 120 expected; 0 annotated but not expected; class counts **document 120, data_zone 120**; shape type **polygon 240**; 0 images whose platform labels differ from `labels/template-labels.json`. (Compared class lists per image, not point coordinates, except the earlier one-image read-back.)
- Remaining unannotated: the 11 frames in `labels/manual-needed.json` (id-blur-004/005/006, bank-blur-001/002/003/004, bank-lowlight-002/003/004/007). Next: those 11 by hand; SAM 3 trial for `glare` / `obstruction` (first on 2 frames to confirm Auto Label keeps the imported labels); then the skim of all 131 frames.

### The 11 hand-drawn frames verified (2026-10-10)

- Analytics page after the user's drawing: **131 images, 262 annotations, document 131, data_zone 131, 0 missing annotations, 0 null examples**; Annotate board still lists the three upload batches (batch pages show every image uploaded in that batch, annotated or not; the Dataset page counts annotated images).
- **API check of all 131 images:** every image has exactly one `document` and one `data_zone`; **262 shapes, all `polygon`**. The 11 hand-drawn frames: all polygons; the `data_zone` lies **entirely inside** the `document` in all 11 (overlap 1.00). Zone area as a share of card area: ID `blur-004/005/006` 0.20, 0.22, 0.22 (template zone: 0.215); bank 0.30–0.38 across the eight bank frames (template zone: 0.294), i.e. the hand-drawn bank zones are looser by up to about 29% (`bank-lowlight-003` at 0.38), on blurred and dark frames where text edges are hard to see. Not corrected.
- The user did not do any extra "approval" beyond approving each frame; Review Mode is locked behind the plan.
- Next: classes `glare` and `obstruction`; SAM 3 trial; skim and label.
- User asked whether fingers on the card but not over the text should be labelled `obstruction`. Answer: yes, if they cover any printed surface (title band, photo area, footer); the verdict only tests overlap with the `data_zone`, so off-text obstruction is harmless and is the needed negative. Not labelled: behind the card, on the pouch margin, outside the card. D-04 wording made explicit.

### Glare and obstruction labelled — platform check (2026-10-10)

- User labelled `glare` and `obstruction`; the Analytics page did not change because it is a **cached snapshot** ("Generated on … 9:42 am", with a Regenerate button), not live.
- **Live counts from the platform (API, every image's record):** 131 of 131 images; `document` 131, `data_zone` 131 (exactly one each per image), **`glare` 58 instances on 45 images, `obstruction` 28 instances on 25 images**. By split: train glare 42 / obstruction 21; valid 11 / 5; test 5 / 2. Both exceed the Gate 3 floors (≥ 25 glare, ≥ 20 obstruction instances). Max instances per image: glare 3, obstruction 2.
- By condition: glare on 27 `glare_direct`, 17 `glare_oblique`, 1 `partial` image; obstruction on 23 `obstruction` and 2 `glare_oblique` images; **none on `good`**. Glare-condition frames with **no glare label: `bank-glare_oblique-003`, `id-glare_oblique-009`** (to check; my recollection is a clear bright streak on the former). Obstruction-condition frames with no obstruction label: 0.
- **Shape types: 286 polygons + 62 masks.** `glare` 37 mask + 21 polygon; `obstruction` 24 mask + 4 polygon; `document` 130 polygon + **1 mask (`id-glare_direct-010`)**; `data_zone` 131 polygon. 53 images carry masks (raster shapes with an `area`, e.g. from SAM-based tools). The docs say instance segmentation accepts polygons or masks; how they are converted at version generation is untested here.
- **Tiny label:** `id-glare_direct-016` has three glare shapes, one only 34 × 26 px (area 725) — possibly a stray click or a legitimate specular speck; not checked by eye.
- Not known: whether the user skimmed the priority 3–4 frames (good, partial, blur, lowlight) for incidental glare and fingers; the counts suggest few or none were found there.

### Five fixes checked; augmentation drafted (2026-10-10)

- Platform re-check after the user's fixes (API): 131 images; `document` 131 (**all polygons now**), `data_zone` 131, `glare` 58, `obstruction` 27 (was 28). `bank-glare_oblique-003` now has 1 glare label; **`id-glare_oblique-009` still has 0 (to confirm whether deliberate)**; `id-glare_direct-016` glare shapes now area 56,469 and 4,101 (the 725 px speck removed). Shape types: glare 36 mask + 22 polygon; obstruction 24 mask + 3 polygon.
- **Card rotation, measured from the 120 template homographies (angle of the card's long axis in the image): upright within 20° = 45; sideways 90/270 = 60; upside down 180 = 7; in between = 8.** Staged set orientation: 79 portrait, 52 landscape.
- Docs (search, not the app): augmentations offered — flip, 90° rotation, random rotation, random crop, shear, blur, exposure, noise, cutout and mosaic (the last two paid-plan only); the docs recommend starting with none; **no page states, per augmentation, whether instance masks and polygons transform correctly** → inspect generated samples before training.
- **D-11 drafted.** Proposed settings (PPE values reused where there is no new evidence): preprocessing Auto-Orient on, Resize **Stretch 312 × 312** (D-07); augmentations **90° rotate: clockwise, counter-clockwise, upside down**; **Rotation −15° to +15°**; **Brightness −15% to +15%**; **Blur up to 1.5 px**; **3 outputs per training example** (92 train → 276 train images; valid 26 and test 13 untouched). Not used: flips, hue/saturation, shear, noise, cutout, mosaic, crop. 11 of 15 DECISIONS entries.

## 2026-10-10 — Version v1 generated and checked

- Version `capture-gate-v1_(10-10-2026)` (id `eze-nnanna-chijioke/capture-gate/1`), created 2026-10-11 03:50 UTC (21:50 local). **315 images: train 276, valid 26, test 13.** Preprocessing: auto-orient on, **Stretch to 312 × 312**. Augmentation: 3 outputs per example, rotate ±15°, 90° clockwise + counter-clockwise + upside-down, brightness ±15%, blur 1.5 px. Exactly the D-07 / D-11 design. (The API's `classes` field for the version returned an empty list; not investigated.)
- **Ordering:** `id-glare_oblique-009` was corrected (lastSet 03:38:11 UTC) 12 minutes before the version was created (03:50:06), and 0 images had labels set after the version was created → the fix is inside v1. Dataset at that point: glare 60, obstruction 25 (was 58 and 28 earlier). By split (instances / images): train glare 44 / 32, obstruction 18 / 16; valid glare 11 / 10, obstruction 5 / 5; test glare 5 / 5, obstruction 2 / 2. **Obstruction evaluation sets are thin (5 valid, 2 test instances).**
- **Export check:** requested a COCO-segmentation export of v1 through the API (HTTP 202 `progress: 0`, ready on the first poll, 4,741,429 bytes), unpacked with a path-safe extractor into `exports/v1/x` (gitignored). Train 276 images / 738 annotations — **exactly 276 × 2 + (44 + 18) × 3 = 738**; valid 26; test 13; all 312 × 312. Categories: a placeholder `capture-gate` (id 0), `data_zone`, `document`, `glare`, `obstruction`. 146 of 524 sampled annotations in train are **run-length-encoded masks** (my first check mis-read these as empty; decoded with `pycocotools`).
- **Mask alignment after augmentation (`check_export.py`):** glare shapes brighter than the card around them by more than 15 grey levels: train 90% of 126, valid 91% of 11, test 100% of 5; median on-card share 1.00 in all splits. Across the 3 augmented copies of one source image the mean on-card share moves by a median of 0.00 (max 0.07) for glare (32 sources) and 0.01 (max 0.03) for obstruction (16 sources). Drew the three copies of one source: card outline, text zone and glare shapes rotate together. **No evidence of misaligned masks.** (Obstruction on-card share differs by split — train 0.27, valid 0.50, test 0.63 — because they are different images; consistent across copies.)
- **Labelling flaw found by the check:** `id-glare_direct-003` and `id-glare_direct-006` each carry one glare label lying **off the card** (a bright reflection on the marble counter), i.e. 2 of 44 train glare instances (6 of 132 after augmentation) teach that bright background spots are glare. Not fixed in v1.
- `check_export.py` saved for re-running on later versions.

## 2026-10-10 — 21 new obstruction frames (for valid and test)

- User shot **21 new obstruction frames** (`Downloads/obstruction2`, `IMG_3461–3483` with gaps, HEIC 4032 × 3024) to add to the **validation and test** batches, because obstruction evaluation was thin (valid 5, test 2 instances). v1 had not been trained, so the evaluation sets are not yet used for any decision.
- Converted in a scratch folder first and looked at all 21 on a contact sheet (eyeball): **9 ID card, 12 bank card**; obstruction by thumbs and fingers over the text, a pen, a cable, a pair of glasses laid across the card (3 frames), an out-of-focus thumb at the lens (2 frames). **Frames 12, 13, 17, 18 show a logo and the name "CoBSMEs" printed on the surface under the card** → `bank-obstruction-018/019`, `id-obstruction-018/019`; asked the user before any upload (public project).
- Ingested by card: `id-obstruction-014..022` (9), `bank-obstruction-011..022` (12). **Manifest 178 rows = 178 files** (157 + 21), no orphans.
- **Split plan (by burst, not at random), proposed to the user, not yet confirmed:** valid 12 = ID 014–017 (desk/laptop, includes the pen) + ID 018 (glasses) + bank 013–016 (white background) + bank 020–022 (grey); test 9 = bank 011–012 (woven mat) + bank 017 + bank 018–019 (glasses) + ID 019 + ID 020–022. By card/split: valid id 5 / bank 7; test id 4 / bank 5. Each split has both cards and a non-hand obstruction. Files: `data/split-additions.csv`, staged copies in `upload/new/{valid,test}` (gitignored).
- **Template matching on the 21 frames: 21 of 21 matched**; ECC correlation min 0.295, median 0.600, max 0.807 (lower than the main set because the frames are occluded by design); every frame has both polygons. **Looked at all 21 overlays: outlines on the card, text zones on the text, in all 21.** `template_labels.py` and `import_template_labels.py` gained `--list/--images/--out` and `--labels` options for this.
- Trade-off noted: putting all 21 into valid/test leaves **train obstruction at 18 instances** (v1). If obstruction AP is low, the next step is moving some of these into train.
- **User decisions:** keep the four "CoBSMEs" logo frames in the public project (no crop, no skip); split plan accepted as proposed (valid 12 / test 9). Upload of `upload/new/valid` and `upload/new/test` is the user's next step; after it I verify the project (expected 152 images: train 92, valid 38, test 22), dry-run the template-label import for the 21 (`--labels labels/template-labels-new.json`), and the user labels obstruction on them.

- **Upload of the 21 verified (API):** 152 of 152 images; **train 92, valid 38, test 22**; 0 missing, 0 unexpected, 0 in a different split from `data/split.csv` + `data/split-additions.csv`. Dry run of `import_template_labels.py --labels labels/template-labels-new.json`: image ids read, 21 YOLO polygon files written, nothing sent.

### Dataset verified before v2 (2026-10-10)

- After the user's import (`--all --labels labels/template-labels-new.json`), labelling of the 21 and deletion of the two off-card glare labels, **API check of all 152 images:** train 92 / valid 38 / test 22; `document` 152 and `data_zone` 152 (exactly one each per image); **glare 58, obstruction 46**. Shape types: glare 34 mask + 24 polygon; obstruction 37 mask + 9 polygon; document and data_zone all polygon.
- **The 21 new frames: 21 of 21 have an obstruction label (21 instances), 0 glare labels.**
- **By split (instances; images):** train glare 42, obstruction 18 (images 32, 16); **valid glare 11, obstruction 17** (10, 17); **test glare 5, obstruction 11** (5, 11). Obstruction evaluation went from 5 / 2 to 17 / 11 instances. Train glare fell from 44 to 42 (the two off-counter labels removed: `id-glare_direct-006` 2 → 1 glare labels; `-003` now 2). **Train obstruction is still 18.**
- No glare-condition frame is without a glare label. No *polygon* glare shape lies mostly off the card; mask shapes cannot be checked through the live API, so the definitive off-card test is `check_export.py` on the v2 export.
- Next: generate v2 with the same settings as v1 (the new-version dialog may not default to them), check the credit estimate first; export v2 and run `check_export.py`; then train once on v2 (Seg Nano, credit cap).

## 2026-10-10 — Version v2 generated and checked

- **v2** `capture-gate-v2_(10-10-2026)`, created 2026-10-11 05:32:39 UTC (23:32 local): **336 images — train 276, valid 38, test 22.** Preprocessing and augmentation identical to v1 (auto-orient; Stretch to 312 × 312; 3 outputs; rotate ±15°; 90° ×3; brightness ±15%; blur 1.5 px). v1 (315 images) was never trained and is superseded.
- **Cost of generating v2: unknown.** The version page did not show a credit figure, and the workspace API returns only `enabled_features, members, name, projects, url` — no plan, usage or credit fields. Only the app's billing/usage view can show it.
- **Export check (`check_export.py exports/v2/x`, export 4,997,647 bytes):** glare train 126 instances (90% of 126 brighter than their surround by > 15 grey levels), valid 11 (91%), test 5 (100%); median on-card share 1.00 in all splits; **glare shapes lying mostly off the card: none** (this check covers mask shapes too — it closes the gap the live API check left). Obstruction: train 54, valid 17, test 11. Across the 3 augmented copies of a source: glare spread median 0.00 / max 0.06 (32 sources), obstruction median 0.01 / max 0.04 (16 sources).

- **`DECISIONS.md` hard limit raised from 15 to 20 entries** (user, 2026-10-11); updated in `interview-prep/roboflow/notes/build-artifacts.md`. It now holds 11 of 20. Open candidates for the remaining entries: the reason-code precedence order, the out-of-scope boundary, blur and brightness measured on the card region (not the frame), `too_dark` threshold, the model-size/training-run result.

## 2026-10-11 — Training dialog (before pressing Start)

- Roboflow Train dialog, read from the user's screenshot: "Train Roboflow RF-DETR on v2 with 336 images"; model label **"Roboflow RF-DETR (Nano)"** (the word "Seg" is not shown; the project is Instance Segmentation and **312 × 312 is the Seg Nano default**, detection Nano is 384 — so very likely Seg Nano, to be confirmed through the API after training); version 2, 336 images, **276 train / 38 valid / 22 test**; **312×312 (Stretch to)**; no resolution-mismatch warning visible.
- **Estimated Roboflow credits 0.80; estimated training time 12–24 minutes** (lower bound assumes typical early stopping, upper bound runs all 100 epochs); **credit cap 2.11** (about 2.6 × the estimate; the dialog says training stops once billed credits reach the cap; minimum for this model 0.13). Hosted Cloud API pricing shown: **0.1875 credits per 1k images** (relevant to the deployment-cost conversation; the local run uses no credits).
- For comparison, the PPE run: estimate 1.96, actual 0.75 (22 min).
- To record after the run: actual credits, duration, number of epochs before stopping, model id, headline metrics, and the model type from the API.

### Local per-class evaluator built while training was pending (2026-10-11)

- Inspected the pretrained `rfdetr-seg-nano` output through Inference 1.7.3: `InstanceSegmentationInferenceResponse`, each prediction has `class_name`, `confidence` and a polygon `points` list (plus `mask_format`). Inference **1.7.4 exists; kept 1.7.3** so evaluation matches the earlier measurements.
- `evaluate_model.py`: COCO mask AP (pycocotools) per class with ground-truth instance counts beside each number; modes `--coco <export split>`, `--midv` (held-out Clutter, `document` and `data_zone` only — MIDV has no glare/obstruction labels) and `--selftest`. Model run at confidence 0.01.
- **Validated before use:** ground truth fed in as predictions scores **1.000 AP50 and AP50:95 for every class** on v2 valid (document 38, data_zone 38, glare 11, obstruction 17 instances), v2 test (22, 22, 5, 11) and the MIDV Clutter frames (12 frames: document 12, data_zone 12). **Shifting every valid mask by 25 px** drops it: data_zone 0.379 / 0.096, document 1.000 / 0.428, glare 0.000 / 0.000, obstruction 0.312 / 0.090 (AP50 / AP50:95); no predictions → reported as such. (A first version failed on the self-test because the export stores some shapes as polygons and `loadRes` needs RLE; fixed by converting.) **Not yet tested against a real trained model** (the model-loading and polygon-to-mask path).

## 2026-10-11 — Training finished; Gate 3 read

- **Run:** Roboflow Train, v2 (336 images: 276/38/22, 312 × 312 stretch). Dialog estimate was 0.80 credits, 12–24 min, cap 2.11. **Actual: 0.34 of 2.11 credits; duration 633.4 s = 10 min 33 s** (start 1791697651459 ms, end 1791698284870 ms, from the API training record: `status finished`, `jobType fine-tune`, **`modelType rfdetr-seg-nano`** — confirms Seg Nano; the dialog only said "Nano"). Model id `eze-nnanna-chijioke/capture-gate-2-rfdetr-seg-nano-t1` (library id `capture-gate/2`). **Epoch count not visible (behind a plan upgrade; the user last saw 16).** Latency "Not Available" on the card. Licence shown: Apache-2.0.
- **Platform headline (valid set): mAP@50 95.2%, precision 98.3%, recall 93.3%, F1 95.7%.** The mean of my four per-class validation AP50 values is 0.9305; the difference was not investigated.
- **Local per-class mask AP (`evaluate_model.py`, confidence 0.01, COCO AP50 / AP50:95, GT instances in brackets):**
  - valid: document 1.000 / 0.980 (38); data_zone 0.981 / 0.776 (38); **glare 0.904 / 0.608 (11); obstruction 0.837 / 0.544 (17)**
  - test: document 0.996 / 0.928 (22); data_zone 0.969 / 0.670 (22); **glare 1.000 / 0.807 (5); obstruction 0.965 / 0.884 (11)**
  - **MIDV held-out Clutter (12 frames, unseen card design, other phones; GT is document and data_zone only):** document **1.000 / 0.923 (12)**; data_zone **0.770 / 0.262 (12)**. Caveat: MIDV's data_zone is my bounding rectangle of all its text fields, a different definition from the printed block the model learned, so the low AP50:95 is not a clean measure of the model.
  - Predictions on MIDV also included glare (387) and obstruction (81) at confidence ≥ 0.01; MIDV has no labels for those classes, so they are unscored (not inspected).
- **Gate 3 (Sunday 11th): PASSED** — glare and obstruction are far from zero. Limits: glare valid n = 11 and test n = 5, obstruction test n = 11 → anecdotal at those sizes; the validation split is used by the platform for checkpoint selection, so valid is not fully independent of training; AP50:95 well below AP50 for glare and obstruction (thin shapes outlined less precisely).
- **Latency with real masks (Apple M3, CoreML EP, Inference 1.7.3, `model.infer` on full-resolution frames, 20 runs after 3 warm-ups):** `id-obstruction-005` (1920×1440) p50 84 ms / p95 89 → 11.9 fps (2 obstruction, 1 document, 1 data_zone); `id-glare_direct-017` (1440×1920) p50 76 / 78 → 13.2 fps; `id-good-015` p50 69 / 71 → 14.4 fps. Earlier 56 ms (18.0 fps) for the pretrained Seg Nano had zero detections, so it excluded mask post-processing. Excludes camera capture and drawing.
- `DECISIONS.md` D-12 added (12 of 20).

## 2026-10-11 — Scripts reorganised

- Tagged the commit before the move `pre-reorg`. Moved the 17 scripts with `git mv` (history follows) into `specimens/`, `pipeline/{1_acquire,2_label,3_dataset,4_train_eval,5_workflow}/` and `external/midv500/`; `cards/` → `specimens/cards/`; `SHOOTING-PROTOCOL.md` → `docs/`. Data folders (`captures/`, `upload/`, `labels/`, `exports/`, `midv-500/`, `private-backup/`) left in place; a `local/` folder for them was **not** done (optional second step). `README.md` added with the layout and an old-name → new-location table. This log keeps the old root script names on purpose (it records what was run at the time).
- Edits needed by the move: the `cards/` path in `generate_mock_cards.py`, `generate_mock_cards_pdf.py` and `template_labels.py` (→ `specimens/cards/`), and the `usage:` lines in docstrings and the command in `docs/SHOOTING-PROTOCOL.md`. No script imports another, so nothing else changed.
- **Verification, all from the repo root:** all 17 compile; `--help` works on the 5 argument-taking scripts; ran `template_labels` on the 21 new frames (matched 21 of 21, uses the moved `specimens/cards/print-*.png`), `import_template_labels` dry run (152 image ids, 120 files), `sync_manifest` (178 rows kept, 0 removed), `check_export exports/v2/x` (same figures as before), `evaluate_model --selftest` (1.000), `spike_block` (48694.38381979841 / 2.4104720049434243 — identical), `fetch_and_run_workflow` (1018.3152326527953 — identical), `benchmark_models` (rfdetr-seg-nano p50 55 ms, was 56). The two card generators wrote to `specimens/cards/`; the PNGs are byte-identical to the committed ones; the PDF differs only by its embedded timestamp (rendered pages identical pixel for pixel) so the committed PDF was restored.
- **Not run** (they overwrite staged data): `build_upload_set`, `make_split`, `extract_midv_frames`, `midv_to_labels`, `capture_frames` (needs the camera). Compile only, plus a check that every input path they read exists. Their first real run after the move is untested.

- **Data folders moved under `local/` (2026-10-11)** — `captures`, `upload`, `labels`, `exports`, `midv-500`, `private-backup` → `local/…` by plain rename on the same disk (no copy). **Before and after counts identical in all six folders: captures 179 files / 151M, upload 307 / 256M, labels 145 / 736K, exports 663 / 20M, midv-500 142 / 781M, private-backup 4 / 2.8M (1,440 files).** Path prefixes rewritten in the scripts, README and shooting protocol (14 files; two literals that only look like paths were deliberately left alone: the `"midv-500"` source label in `extract_midv_frames.py` and `"labels.json"` in `midv_to_labels.py`). **The paths stored inside the manifests were rewritten too:** `local/captures/manifest.csv` (178 rows) and `local/midv-500/frames/manifest.csv` (60 rows).
- `.gitignore` is now one rule, `local/`, plus the old root names kept as a safety net (so an old command that recreates `captures/` at the root is still ignored). Verified: manifest, a raw frame, staged uploads, labels, an export zip, the MIDV archive and the pre-crop originals each match the `local/` rule; `.env` and `prompts.md` still ignored; **0 tracked files under `local/`**.
- Re-ran from the repo root: `sync_manifest` (178 kept, 0 removed), `template_labels` on the 21 new frames (21 of 21) and the main set (123 of 131), `import_template_labels` dry run (152 ids, 120 files into `local/labels/yolo/`), `check_export` and `evaluate_model --selftest` (valid and MIDV; 1.000), `fetch_and_run_workflow` (1018.3152326527953), and `ingest_phone_photos` + `extract_video_frames` into a scratch `local/captures` (manifest rows carry `local/captures/…`). Not run (they overwrite staged data): `build_upload_set`, `make_split`, `extract_midv_frames`, `midv_to_labels`, `capture_frames`.
