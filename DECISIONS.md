# Decisions

## D-01 · Capture with the phone, not the laptop webcam
**Decision:** the dataset is shot on the iPhone, and the iPhone is the camera for the live demo (via Continuity Camera).
**Why:** the training camera and the demo camera should be the same device, and MIDV-500 (the augmentation set) was itself shot on smartphones.
**Rejected:** the MacBook webcam, because it is the simpler setup but makes both a different camera from the one the business case is about and a lower-quality one than a real capture flow would see.
**Evidence:** MIDV-500 is phone video at 1080 × 1920; own test photos are 3024 × 4032, downsized to 1440 × 1920 on ingest. Not yet measured: the resolution the live Continuity Camera path delivers.

## D-02 · Four positive classes, no `bad_capture` or `blurry` class
**Decision:** the detector finds `document`, `glare`, `obstruction` and `data_zone`; usability is derived from those boxes plus geometry and a Laplacian-variance blur check.
**Why:** absence is not an object, so a class for "bad" teaches the model a shape instead of a condition, and nothing it outputs can be reasoned over.
**Rejected:** a `bad_capture` or `blurry` class (and `no_glare`-style absence classes), because no confidence threshold can fix a class that was never detectable.
**Evidence:** PPE build — one frame carried `vest` 0.54 and `no vest` 0.63 on the same torso, kitchen chairs and counter stools were tagged `no vest`, and SAM 3 auto-label ignored "without" in the prompts.

## D-03 · `data_zone` is the printed text block, not the whole card
**Decision:** `data_zone` is one rectangle tightly enclosing the printed fields that carry data (names, numbers, dates); it excludes the portrait photo, signature, logos, security patterns and the card edge.
**Why:** the question a person can act on is "can the data be read", and glare or a thumb elsewhere on the card does not stop that.
**Rejected:** the whole document as the zone, because glare on the border or a thumb on the photo would fail a good capture; and per-field boxes, because they cost far more labelling and the card layouts differ.
**Evidence:** MIDV-500's own ground truth separates 11 text fields from the `photo` and `signature` entries; on the printed render the text box is 310 × 400 px on the ID card and 872 × 193 px on the bank card (1012 × 638 template), and my first ID zone was 653 px wide, over twice the text, until I measured it.

## D-04 · `obstruction` is labelled only where it covers the printed card surface
**Decision:** a finger or object counts as `obstruction` only if it covers the printed area of the card, the text block or anywhere else on the printed surface; fingers behind the card or on the laminate margin are not labelled.
**Why:** hand-held capture is the normal case, and most real captures have fingers on the card edge, which should not be reported as a defect.
**Rejected:** labelling any finger contact, because it flags the ordinary way people hold a card and teaches the model that a hand means a problem.
**Evidence:** the shoot deliberately pairs frames with a thumb over the text and frames with fingers at the edge only (about 6 of each among the 13 obstruction frames, by eye); whether the model separates them is untested.

## D-05 · `too_dark` is its own reason, from a classical brightness check
**Decision:** a classical brightness measurement on the capture produces a `too_dark` reason, and it is evaluated before the blur check.
**Why:** darkness lowers the sharpness measure, so without its own reason a dark frame is reported as blurred and the user is told to hold still when the problem is light.
**Rejected:** treating legible dark frames as usable with no reason, because the sharpness check would still misread them and the user gets no guidance.
**Evidence:** whole-frame mean grey for the four `lowlight` frames is 33.3–41.7 against 78.1 for the darkest other frame; their whole-frame Laplacian variance (median 46.8) sits below the blur batch (59.8–86.6). Not yet tested: the check on the `data_zone` alone, and any threshold.

## D-06 · Instance segmentation with polygon labels, not box detection
**Decision:** an Instance Segmentation project, polygon labels for all four classes, RF-DETR Seg Nano as the first model.
**Why:** the glare test depends on shape, and the box around a thin diagonal streak covers far more than the streak.
**Rejected:** object detection with boxes, because a box-overlap test would flag captures whose text is actually clear; polygons convert to boxes on the platform, so the choice can be reversed without relabelling.
**Evidence:** on the M3, Nano detection ran at 37 ms p50 and Seg Nano at 56 ms (about 18 fps), measured without masks in the output; two oblique-glare frames keep their streaks at 312 × 312. Not yet tested: Seg Nano training on this account, and latency with real masks.

## D-07 · Train at the model's native input size, not 640
**Decision:** the dataset version is resized to 312 × 312 (stretch), the Seg Nano default, with no larger intermediate size.
**Why:** a larger version means a double resize and more pixels per frame for no gain the model was designed to use.
**Rejected:** 640 × 640, which the PPE build used against the platform's own 384 warning.
**Evidence:** the PPE model ran at 2.22 fps at 640 against a native 384; the cause was not isolated, so this is a precaution and not a measured effect.

## D-08 · No public dataset goes into the Roboflow project
**Decision:** only my own frames are uploaded; MIDV-500 stays local as the held-out test set, and two Universe ID-card sets were considered and not used.
**Why:** the project is public, so the licence and provenance of anything uploaded must be clean, and images labelled for only some classes teach the model that the others are absent.
**Rejected:** uploading MIDV-500 (CC BY-SA 2.5, no compatible ShareAlike option found) and the Universe sets `cccd` (134 images) and `cv` (110 images), whose pages have no description or source and whose class names point at national ID cards.
**Evidence:** `license.txt` on the MIDV server; both Universe pages read on 2026-10-09 (instance segmentation, CC BY 4.0, classes `id-card`/`tlu-card` and `car`/`back`/`addres`/`drive`/`iraq id card`); I did not open their images.

## D-09 · Split by capture group, not at random
**Decision:** train, valid and test are assigned a whole capture group at a time, where a group is a run of back-to-back shots from one set-up.
**Why:** near-duplicate shots on both sides of a split make the validation score look better than the model is.
**Rejected:** Roboflow's default random 70/20/10 split, because with this many same-set-up shots it puts copies of one shot in train and validation.
**Evidence:** nearest-training-frame distance for held-out frames has a median of 0.566 with the group split against 0.292 for random splits (20 seeds); the group split still has leakage through shared backgrounds, which only the MIDV held-out set tests.

## D-10 · `document` and `data_zone` come from the printed template; `glare` and `obstruction` are labelled by hand
**Decision:** the card outline and its text block are computed by matching each frame to the card's known layout; only the two classes that need judgement are drawn by hand.
**Why:** both mock cards have a fixed, known layout, so these two classes can be located exactly, and labelling time goes where a person is actually needed.
**Rejected:** SAM 3 for `data_zone`, which annotated none on the trial frames (a text region is not a nameable object), and hand-drawing all four classes on all 131 frames.
**Evidence:** the template labelled 120 of 131 frames with both polygons, missing only blurred or very dark ones; I checked overlays on 56 distinct frames (the 30 lowest alignment scores, 24 random others, 4 I doubted) and all were correct bar two slightly rotated outlines; 11 frames still need hand-drawn labels.

## D-11 · Augment with rotation, not flips, and no cutout
**Decision:** train-split augmentation uses 90° rotations, ±15° rotation, mild brightness and blur, and no horizontal or vertical flips, hue or saturation shifts, or cutout.
**Why:** a handheld card turns however the person holds it and the demo orientation is undecided, while a flip makes mirrored text that never occurs and a cutout paints blocks that look like an obstruction but carry no label.
**Rejected:** the PPE build's recipe, which left rotation out because its cameras were fixed here that reasoning does not hold, and flips, which were the one thing the recipe did allow.
**Evidence:** from the template homographies, only 45 of 120 cards are upright (60 sideways, 7 upside down, 8 in between); the staged set is 79 portrait and 52 landscape. On the exported version, 90% of augmented glare shapes (n = 126) are brighter than the card around them against 91% of untouched validation shapes (n = 11), and a source image's on-card share moves by at most 0.07 across its three copies.

## D-12 · Stay with Seg Nano after the first run
**Decision:** the model for the demo is RF-DETR Seg Nano at 312 × 312, from one training run on v2, with no move up a size.
**Why:** both minority classes learned on the first run, and Nano is the smallest and fastest size, which is the point of the on-device argument.
**Rejected:** starting at Seg Small (384 × 384), because nothing in the per-class numbers asks for a larger model and it measured about 80 ms against about 56 ms on the pretrained checkpoints.
**Evidence:** validation AP50 glare 0.904 (11 instances), obstruction 0.837 (17); test glare 1.000 (5), obstruction 0.965 (11); the run cost 0.34 credits and took 10 min 33 s. Seg Small was not trained, so the comparison is on latency only.

## D-13 · One instruction at a time: dark, no card, cut off, covered, glare, blur
**Decision:** every reason that fires is kept in the reason list, but the single guidance string follows this order: `too_dark`, `no_document`, `incomplete_document`, `obstructed`, `glare_over_data_zone`, `blurred`.
**Why:** each check only means something once the ones above it hold (no light means no reliable detection, no card in frame means no text zone, a covered or glared zone cannot be judged for sharpness), and a person can act on one instruction at a time.
**Rejected:** reading every reason out at once, a severity-weighted ranking (a score by another name), and blur first because it is the cheapest fix, since blur misfires on dark, covered and glared frames.
**Evidence:** inside the rectified text zone, dark frames (ID 36–116, bank 26–42), bank frames with an obstruction (down to 30.6) or glare (down to 55.8) fall in the range of the heavily blurred ID frames (46–65), against sharp frames at 501 and above (ID) and 167 and above (bank); 0 of 152 frames carry both glare and obstruction, so the order of those two, and of the top three, rests on dependency and not on data.
