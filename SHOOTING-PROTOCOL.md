# Shooting protocol — mock specimen cards

Target: **112 frames**, split evenly across the two printed mock cards (`id` and `bank`). Specimen cards only: no real document, no other card, and no mail or personal items in the background. Keep your face out of frame. Raw photos stay out of git (`captures/` is ignored).

## Per card

| Condition | Per card | Total | What the frame must show |
|---|---|---|---|
| `good` | 15 | 30 | All four corners in frame, sharp, no glare, text readable |
| `glare_direct` | 7 | 14 | A bright patch from a light or window, ON the text block |
| `glare_oblique` | 7 | 14 | A streak or band across the card from a low side angle |
| `obstruction` | 13 | 26 | A thumb, finger or object covering part of the card |
| `partial` | 5 | 10 | The card cut off by the frame edge |
| `blur` | 5 | 10 | Motion or focus blur |
| `lowlight` | 4 | 8 | A dim room; card still visible |

## Phone settings

Photo mode. **Live Photo off** (AirDrop sends an extra `.MOV` per photo otherwise). Portrait mode off, flash off, no edits or crops. Tap to focus unless the condition says otherwise.

Orientation: shoot mostly **landscape**, with about a quarter in portrait. I don't yet know whether the Continuity Camera feed is landscape, so this is a hedge, not a measured choice.

## Condition notes

**good.** Vary rotation (about −30° to +30°), distance (card fills roughly a third to two thirds of the width), background (desk, wood table, kitchen counter, a dark keyboard-like surface) and light (daylight, lamp). The point is variety in everything except the condition.

**glare_direct.** Tilt the card toward a window or lamp until a bright patch lands on the text block. Vary the size, from a small spot to most of the block. **About 3 of 7 per card should have the glare on the photo, border or blank area but not on the text.** Those are the negatives for the intersection test.

**glare_oblique.** Hold the card at a shallow angle to the light so the glare is a band across the card. Vary the angle and which part of the card it crosses.

**obstruction.** Mostly a thumb or fingers, since that's the real-world case. Cover the text block fully, half, and only a corner. **About 5 of 13 per card should have fingers on the edge but not over the text.** Add one or two with a pen or paper edge.

**partial.** One corner out, one edge out, about a third of the card out. Include some where the card is cut but the text block is still fully visible. That checks the corners test separately from the text.

**blur.** Move the phone or the card during the shot (motion blur), or tap to focus on the background so the card goes soft (defocus). Aim for mild, medium and heavy, because the blur threshold needs a gradient to be tuned against.

**lowlight.** A dim room, with the lamp off or far away. Keep the card visible.

## Optional, only if time allows (not counted above)

About 6 frames with two problems at once (for example glare plus a corner cut off). They test the reason-code precedence later. The target is 112; with these, 118, still under 120.

## How to bring them in

One batch per condition and card, in its own folder, then ingest. Example:

```bash
cd /Users/nnannaeze/Personal/capture-gate && ./.venv/bin/python ingest_phone_photos.py --src ~/Downloads/glare-direct-id --condition glare_direct --card id
```

Conditions: `good`, `glare_direct`, `glare_oblique`, `obstruction`, `partial`, `blur`, `lowlight`. Cards: `id`, `bank`.
