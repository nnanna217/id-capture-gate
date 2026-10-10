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
**Evidence:** MIDV-500's own ground truth separates 11 text fields from the `photo` and `signature` entries; both mock cards have one contiguous text block. Not yet tested: how consistently I label it by hand.

## D-04 · `obstruction` is labelled only where it covers the printed card surface
**Decision:** a finger or object counts as `obstruction` only if it covers the printed area of the card; fingers behind the card or on the laminate margin are not labelled.
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
