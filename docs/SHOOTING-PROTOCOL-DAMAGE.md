# Shooting protocol: damaged specimen cards (D-15, route b, step 2)

**Start with the illustrated guide: open [`damage-shoot-guide.html`](damage-shoot-guide.html) in a browser.** It draws every scenario on your real
card faces (the pictures are illustrations, not photographs). This file is the same protocol in text. Tick cards off in
[`damage-shoot-log.csv`](damage-shoot-log.csv). Regenerate both with `python -I docs/build_damage_guide.py`.

Goal: teach the gate a fifth class, `damage`, from printed specimen cards damaged by hand, added to the 152 photos already in the dataset. About
**152 new photos**: 32 damaged cards x 4 photos (1 clean before + 3 damaged) and 24 hard-negative photos. Specimen cards only: no real document, no
business card, no other card or personal items in frame, no face. Raw photos stay out of git (`local/` is ignored).

## Why it is built this way

- **A clean BARE photo of every damaged card, taken first.** Most of the 152 existing photos show the card inside the clear pouch. If every
  undamaged example is pouched and every damaged one is bare, the model learns "no pouch = damaged". The clean-before photo gives it bare cards that
  are fine, and it pairs each damaged card with its own undamaged self.
- **One problem per photo.** No glare on the text, no finger over the text, no blur, all four corners in frame. Otherwise the label is wrong.
- **Mild and severe.** MILD: the damage stays away from the text zone and the text is fully readable. SEVERE: the damage crosses the text zone,
  text still legible. The later block decision (block or only flag) depends on this split.
- **Hard negatives.** A gently bowed card and a steeply tilted clean card are NOT damage. Without them the model learns
  "anything curved or squashed is damaged", which is the trap the mask-shape test fell into.
- **Split by physical card.** Each numbered card is one capture group (D-09), so no card appears in both train and test.

## Per layout (do ID, then bank)

| Cards | Plan | Photos each |
|---|---|---|
| 01-04 | Fold: 01, 02 mild; 03, 04 severe | 4 |
| 05-08 | Crease: mild, mild, severe, severe | 4 |
| 09-12 | Tear: mild, mild, severe, severe | 4 |
| 13-16 | Curl / bow: mild, mild, severe, severe | 4 |
| 17, 18 | Hard negative: gentle bow | 3 |
| 19, 20 | Hard negative: steep tilt (clean card at about 45 degrees) | 3 |
| 21-24 | Spares (only if a card is ruined or a shot missed) | 0 |

76 new photos per layout, 152 in all.

## Before you start

Printed cards cut out with the copy number on the back. A pen or pencil (curling), scissors, a flat desk, two different surfaces. Phone: Photo
mode, **Live Photo off**, flash off, no filters, portrait mode off, tap to focus. Light from the side (it shows creases) but keep it off the text.

## The four photos of every damaged card

1. **CLEAN BEFORE.** Bare card, undamaged, flat and square on the desk. Before you touch it.

(Then damage it, recipes below, and shoot at once.)

2. **Flat and square** again, same pose.
3. **Turned 20-30 degrees, on the other surface.**
4. **In your hand, different light,** fingers on the edges only, never over the damage or the text zone.

Landscape mostly, some portrait. The card fills a third to two thirds of the frame width, all four corners visible. Shoot curls and bows
immediately: they relax within a minute.

## The eight recipes

| Scenario | Make it | The photo must show |
|---|---|---|
| **Fold, mild** | Fold the bottom-left corner over, about 12 mm each way. Press flat, let go. | Flap and fold line visible, away from the text zone. |
| **Fold, severe** | Fold the card in half down the middle, press hard, open to about a right angle, lay it down bent. | A hard centre fold through the text zone, halves at different angles. |
| **Crease, mild** | One crease line below the text zone, pressed with a fingernail, then flatten. | One clear light/dark line in a blank area. |
| **Crease, severe** | Two hard creases crossing each other over the text zone (one down the middle, one across). Flatten. | Two crossing lines through the text zone with bright and dark edges. |
| **Tear, mild** | A ragged notch about 5 mm wide in the top edge, away from the text. | A small bite out of the edge, desk showing through. |
| **Tear, severe** | Tear the bottom-right corner off (about 25 mm, ragged) and a 40-100 mm slit in from the right edge toward (bank: into) the text zone. | Missing corner and slit, ragged edges, text still legible. |
| **Curl, mild** | Roll the bottom-right corner over a pen for a few seconds, lay flat. | Corner lifted about 10 mm, back of the paper and a shadow. |
| **Bow, severe** | Roll the whole card around a pen for 15 s, release, lay down so it bows. | Visibly bowed: shaded bands, curved edges, shadow under the middle. |

Tears: rip them, do not cut with scissors; the edge should be ragged and show pale paper fibre. A damaged card is never damaged twice.

## Hard negatives (3 photos each, no clean-before)

- **Gentle bow:** flex slightly, lay down a little curved. No crease anywhere. (cards 17, 18)
- **Steep tilt:** a clean flat card at about 45 degrees. (cards 19, 20)

## Retake if

A finger covers the damage; there is glare on the text; the card is cut off by the frame; it is blurred; the damage cannot be seen on the phone
screen; a curl has relaxed flat.

## Getting the photos in

One folder per physical card, named with the copy number and plan, photos in the order taken (photo 1 is always the clean BEFORE), for example
`~/Downloads/damage/ID-03-fold-severe/` and `~/Downloads/damage/BANK-17-hardneg-bow/`. Do not rename the photos. The ingest script does not
know these folders yet; that is the next step, so just keep them as they are.

## Out of this iteration

Cards in a clear sleeve or pouch. The model outlines the sleeve instead of the card (BUILD-LOG, 14 Oct); that is a separate problem and is not
mixed into the damage data. **Keep every card out of a sleeve for this shoot.** This leaves the existing set (mostly pouched cards) and the new
damaged set (bare cards) different in more than damage, which is why the clean-before photos are not optional.

## Limits, said plainly

Printed paper does not fold or tear like plastic ID. This set is a seed that teaches the idea of damage; it does not prove the gate catches worn
real documents. Those frames come later from the bypass queue (D-17).
