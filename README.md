# capture-gate

A capture quality gate for identity-document photos. It decides whether a capture is usable *before* it is submitted, and tells the
person why not: a verdict (`usable` / `not_usable`), reason codes, and one guidance string. Never a numeric score.

Built for the Roboflow Field Engineering tech challenge. **Start with [`DECISIONS.md`](DECISIONS.md)** (the choices, each with the
alternative that was rejected) and [`BUILD-LOG.md`](BUILD-LOG.md) (what actually happened, failures included, unrounded numbers).

## Layout

The folders follow the brief's stages. Run every script **from the repo root**, as `python -I <path>`: scripts use paths
relative to it (`captures/`, `upload/`, `labels/`, ...). The API key is read from `.env` (see `.env.example`) and never printed.

| Folder | What it holds |
|---|---|
| `specimens/` | Generators for the two mock specimen cards (invented data only) and their print files. |
| `pipeline/1_acquire/` | Capture and ingest frames: webcam capture, phone-photo ingest, video-frame extraction, manifest sync. |
| `pipeline/2_label/` | `document` and `data_zone` labels derived from the printed template; import them into Roboflow. |
| `pipeline/3_dataset/` | Stage the upload set, the capture-group train/valid/test split, checks on a downloaded version export. |
| `pipeline/4_train_eval/` | Per-class mask AP for the trained model, and latency benchmarks. |
| `pipeline/5_workflow/` | The Workflow work: custom-block spike, fetch-and-run the published workflow. |
| `external/midv500/` | MIDV-500 (CC BY-SA 2.5): kept local, used only as the held-out test set. Never uploaded. |
| `workflows/`, `data/` | Tracked workflow specs and small CSVs (splits, labelling order). |
| `docs/` | The shooting protocol. |

## Not in the repo, on purpose

Raw captures, uploads, labels, exports, MIDV and the venv are gitignored: the frames are shot at home and the project's
Roboflow workspace is public. Only redacted stills and filenames-only CSVs are committed.

## Where the old root scripts went

`capture_frames`, `ingest_phone_photos`, `extract_video_frames`, `sync_manifest` → `pipeline/1_acquire/` ·
`template_labels`, `import_template_labels` → `pipeline/2_label/` · `build_upload_set`, `make_split`, `check_export` →
`pipeline/3_dataset/` · `evaluate_model`, `benchmark_models` → `pipeline/4_train_eval/` · `spike_block`,
`fetch_and_run_workflow` → `pipeline/5_workflow/` · `extract_midv_frames`, `midv_to_labels` → `external/midv500/` ·
`generate_mock_cards`, `generate_mock_cards_pdf` → `specimens/` (and `cards/` → `specimens/cards/`) ·
`SHOOTING-PROTOCOL.md` → `docs/`. `BUILD-LOG.md` still uses the old root names: it is a record of what was run at the time.
The commit before the move is tagged `pre-reorg`.
