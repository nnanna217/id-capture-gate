# Decisions

## D-01 · Capture with the phone, not the laptop webcam
**Decision:** the dataset is shot on the iPhone, and the iPhone is the camera for the live demo (via Continuity Camera).
**Why:** the training camera and the demo camera should be the same device, and MIDV-500 (the augmentation set) was itself shot on smartphones.
**Rejected:** the MacBook webcam, because it is the simpler setup but makes both a different camera from the one the business case is about and a lower-quality one than a real capture flow would see.
**Evidence:** MIDV-500 is phone video at 1080 × 1920; own test photos are 3024 × 4032, downsized to 1440 × 1920 on ingest. Not yet measured: the resolution the live Continuity Camera path delivers.
