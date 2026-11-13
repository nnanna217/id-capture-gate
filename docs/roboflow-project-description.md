# Roboflow project description (paste into the project's public description)

Every number below comes from `BUILD-LOG.md` (v6 entries, 2026-10-19) or from the live Universe page read on 2026-11-13.
Check anything you change against those. Claims to re-confirm before publishing are marked **[confirm]**.

## 1. One-line summary (search results and link previews)

Capture-quality gate for identity-card photos: segments the card, its text block, glare, anything covering it and physical damage, so an app can tell the person how to retake.

## 2. About text (the long description)

Capture-quality gate for identity-card photos. Before a photo is taken or uploaded it asks one question: can the text on this card be read? If not, it says what to fix.

This is the segmentation model and dataset behind a small gate. Five classes mark the card (`document`), its printed text block (`data_zone`), `glare`, anything covering the card (`obstruction`) and physical `damage` (corner folds, tears, creases, stains, peeled corners). A custom Roboflow Workflow block reads those masks and returns usable or not usable, the reasons, and ONE instruction for the person, for example "Tilt the card to move the glare off the text." There is no quality score.

**Data**
- 340 images, shot by me on a phone of printed specimen ID cards and bank-style cards I designed for this project. No real identity document and no personal data appears on any card. **[confirm]** The images show my desk and hands because the project is public.
- Conditions: good, glare (direct and oblique), a finger, pen, cable or glasses over the text, the card partly out of frame, low light, blur, and damage.
- Split by capture set-up, not at random, so near-identical frames never sit in both train and test.
- `document` and `data_zone` outlines come from the printed card layout (feature matching and a homography); `glare`, `obstruction` and `damage` are hand-labelled polygons.

**Model**: RF-DETR Seg Nano, instance segmentation, 312 x 312 input (version 6).

**Results (version 6)**
- Roboflow's validation-set headline: mAP@50 93.1%, precision 93.6%, recall 91.4%.
- My own scoring on the held-out test split, AP50 (instances in brackets): document 1.000, data_zone 0.985, glare 0.967 (5), obstruction 0.868 (18), damage 0.568 (27).
- Damage is the hardest class. On 41 damaged photos the model never trained on, it found the damage on 35 (confidence 0.4 or higher, overlap with my outline 0.5 or higher).

**Limits, stated plainly**
- Small dataset from one person, one phone and two card designs. The test split is small (glare has 5 test instances), and damage scores far lower on test than on validation.
- The text-block class depends on this card layout. On an unfamiliar card type the model can lose the text block.
- Not for verifying real identity documents. Out of scope: reading text, authenticity or tamper checks, face matching.

**Use it**: `eze-nnanna-chijioke/capture-gate-6-rfdetr-seg-nano-t1` through Roboflow Inference or the Try this model box above.
**Code and decision log**: https://github.com/nnanna217/id-capture-gate
**Licence**: CC BY 4.0. Credit "Nnanna Eze".

## 3. Where it goes (from memory of the Roboflow UI, not verified)

On the Universe page the section "About capture-gate Model" currently reads "A description for this project has not been published yet." The description field is normally in the project's Settings, in the public/Universe section.
If you cannot find it, send me a screenshot of the Settings page.

## 4. Share link

Share `https://universe.roboflow.com/eze-nnanna-chijioke/capture-gate`. The `app.roboflow.com/.../overview` link is your logged-in dashboard, so other people cannot open it.
