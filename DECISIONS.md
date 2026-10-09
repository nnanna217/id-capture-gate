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
