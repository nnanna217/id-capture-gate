# Shooting list, round 2 (D-19): corner folds, tears, stains and peeled corners, one folder per card

Half-folds, rolls and creases are out. This round targets the weak spots, and every damaged card is its own capture group so the split can keep whole
cards apart. **102 photos, 30 cards, about 1.5 hours** (a guess, not timed). Pictures of how each defect should look: `damage-shoot-guide.html`
(fold corner, tear, curl) and `damage-labelling-guide.png`. Specimen cards only, bare (no sleeve), no real document, no face.

## What to shoot (full list with card numbers: `damage-shoot-log-r2.csv`)

| What | Cards | Photos each | How to make it |
|---|---|---|---|
| **Tear** | 8 (4 ID, 4 bank) | 3 | RIP a clear bite 10-20 mm deep from an edge or a corner (vary which: top, side, corner). Not scissors: the edge should be ragged. A nick is too small. |
| **Peeled / curled corner** | 8 (4 ID, 4 bank) | 3 | Roll a corner over a pen for a few seconds so it stays about 10 mm off the desk, or peel the corner up. Shoot at once, it relaxes. |
| **Corner fold** | 4 (2 ID, 2 bank) | 3 | Fold a corner over about 12 mm, press, let go. |
| **Stain** | 4 (2 ID, 2 bank) | 3 | A small mark on the card (food, ink, oil). Varied size. |
| **Undamaged, fingers on the card** | 4 (2 ID, 2 bank) | 5 | Bare, undamaged card held with fingers at the edges or one finger lightly over the card. These cut the false alarms. |
| **Undamaged, bare** | 2 (1 ID, 1 bank) | 5 | Flat on a surface, in a hand, on a different surface. |

Print the sheets again (`specimens/cards/damage-sheets-letter.pdf`, 24 cards per layout, 8 per page) if you do not have 36 fresh cards left.
Write the copy number on the back as before.

## The three photos of every damaged card
Shoot straight after you make the damage: (1) flat and square on the desk; (2) turned 20-30 degrees on a different surface; (3) in your hand, other
light, fingers on the edges only, never over the damage. One problem per photo: no glare on the text, no blur, all four corners in frame.
Retake if the damage cannot be seen on the phone screen.

## Folders: name them, and the ingest does the rest
One folder per physical card, named `R2-<ID or BANK>-<card number>-<what>`, photos in the order taken, for example
`R2-ID-03-tear`, `R2-BANK-11-curl`, `R2-ID-26-fingers`, `R2-BANK-29-clean` (`what` is one of tear, curl, fold_corner, stain, fingers, clean).
Put them all under one parent folder and send me the path. No batch table is needed: the folder name gives the type, the card layout and the
group, and every card becomes its own capture group.

## Why 4 cards per type and card layout
The split rule (D-19) wants, for each type and layout, 4 distinct cards: 2 for training, 1 for valid, 1 for test, so the numbers are measured on
cards the model never saw. Today most types have 0 to 3. After this round `build_damage_upload_set.py` prints what is still short.

## If time is short, in this order
1. Tears (8 cards), the most realistic damage and the weakest result. 2. Fingers on the card (4 cards). 3. Peeled corners (8).
4. Corner folds and stains (they already work).
