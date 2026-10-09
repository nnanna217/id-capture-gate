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
