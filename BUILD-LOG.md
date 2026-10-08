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
