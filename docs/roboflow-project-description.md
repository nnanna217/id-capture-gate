# Roboflow project description (paste into the project's public description)

Project display name (chosen 2026-11-13): **Real-time ID Photo Check**. Public page: https://universe.roboflow.com/eze-nnanna-chijioke/real-time-id-photo-check
The rename changed the project id to `real-time-id-photo-check`. The trained models keep their old ids (`capture-gate-6-rfdetr-seg-nano-t1` and so on); the Universe page still shows that model id, and it works.

Every number below comes from `BUILD-LOG.md` (v6 entries, 2026-10-19; live sessions, 2026-10-13) or from the live Universe page.
Check anything you change against those. Claims to re-confirm before publishing are marked **[confirm]**.

## 1. Subtitle / one-line summary (search results and link previews)

Tells you what to fix before you photograph your ID card.

## 2. About text (the long description; plain text, so nothing shows as stray symbols)

Real-time ID Photo Check tells you what to fix before you photograph your ID card.

It answers one question: can the text on this card be read? If not, it gives one short instruction, such as "Tilt the card to move the glare off the text." There is no quality score.

This project is the dataset and segmentation model behind it. Five classes mark the card (document), its printed text block (data_zone), glare, anything covering the card (obstruction) and physical damage (damage: corner folds, tears, creases, stains, peeled corners). A custom Roboflow Workflow block reads those masks and returns usable or not usable, the reasons, and the one instruction.

REAL-TIME
In my live demo the check runs on a laptop camera feed. Across three live sessions the median time per frame was 72 to 96 ms (model plus decision logic, Apple M3, run locally with Roboflow Inference). The live demo uses an earlier model version (v2); version 6, listed here, adds the damage class and is not in the live check yet. The Try this model box on this page checks one uploaded image at a time.

DATA
- 340 images, shot by me on a phone, of printed specimen ID cards and bank-style cards I designed for this project. No real identity document and no personal data appears on any card. [confirm] The images show my desk and hands because the project is public.
- Conditions: good, glare (direct and oblique), a finger, pen, cable or glasses over the text, the card partly out of frame, low light, blur, and damage.
- Split by capture set-up, not at random, so near-identical frames never sit in both train and test.
- Document and data_zone outlines come from the printed card layout (feature matching and a homography). Glare, obstruction and damage are hand-labelled polygons.

MODEL
RF-DETR Seg Nano, instance segmentation, 312 x 312 input (version 6).

RESULTS (version 6)
- Roboflow's validation-set headline: mAP@50 93.1%, precision 93.6%, recall 91.4%.
- My own scoring on the held-out test split, AP50 (instances in brackets): document 1.000, data_zone 0.985, glare 0.967 (5), obstruction 0.868 (18), damage 0.568 (27).
- Damage is the hardest class. On 41 damaged photos the model never trained on, it found the damage on 35 (confidence 0.4 or higher, overlap with my outline 0.5 or higher).

LIMITS
- Small dataset from one person, one phone and two card designs. The test split is small (glare has only 5 test instances), and damage scores far lower on test than on validation.
- The text-block class depends on this card layout. On an unfamiliar card type the model can lose the text block.
- Not for verifying real identity documents. Out of scope: reading the text, authenticity or tamper checks, face matching.

USE IT
Model: eze-nnanna-chijioke/capture-gate-6-rfdetr-seg-nano-t1 (the model id keeps the project's old name), through Roboflow Inference or the Try this model box above.
Code and decision log: https://github.com/nnanna217/id-capture-gate
Licence: CC BY 4.0. Please credit Nnanna Eze.

## 3. Where it goes (from memory of the Roboflow UI, not verified)

On the Universe page the section "About Real-time ID Photo Check Model" currently reads "A description for this project has not been published yet." The description field is normally in the project's Settings, in the public/Universe section.
If you cannot find it, send me a screenshot of the Settings page.

## 4. Share link

Share `https://universe.roboflow.com/eze-nnanna-chijioke/real-time-id-photo-check`. The dashboard link (`app.roboflow.com/eze-nnanna-chijioke/real-time-id-photo-check/overview`) is your login view, so other people cannot open it. Links you shared before the rename (`.../capture-gate`) still loaded at the time I checked, but the API no longer knows that id, so replace them.
