# Demo script: the three follow-up changes (about 6 minutes, on a call)

Setup: Continuity Camera on, a printed specimen card, a second sheet of paper to hide the card with, and the app started with the
hatch shortened so you are not waiting two minutes. From the repo root:

    python -I pipeline/6_demo/live_gate.py --source 0 --bypass-rejections 2 --bypass-seconds 30 --continue-after-accept

(`--bypass-seconds 30` is for the call only; the real default is 120 s, and 3 rejections. Say so out loud.)

## 1. Review step (D-16): "what did it just capture?" (1 min)
1. Show the card cleanly. Banner goes green: "Looks good. Capture it." One second later the screen **freezes on the captured frame**
   with two big buttons: green `[A] ACCEPT`, orange `[R] RETAKE`.
2. Press **R**: back to live guidance. Say: the invisible capture is gone, a person confirms every photo.
3. Press **A** once to show accept (with `--continue-after-accept` the session carries on; without it, it ends).

## 2. Nobody gets stuck (D-17): the part to land (3 min)
1. Hold the second sheet of paper over the text, or tilt the card into glare, and **leave it there**. The banner keeps giving one
   instruction ("Move your finger or anything else off the text").
2. Watch the footer: `rejections in a row 1/2`, then `2/2`. (Real defaults: 3, or 120 s, whichever comes first.)
3. When the **orange bar** appears, "Not working? Press SPACE to take the photo anyway. It will be sent for manual review.", press **SPACE**.
4. The screen freezes on that frame, orange banner "Taken anyway. This photo is going to MANUAL REVIEW.", and a line naming what blocked
   it. Same two choices. Say: it did not silently accept it, it flagged it, and it kept the reason that was blocking.
5. Say the line: a user whose photo is fine but keeps being rejected can no longer be trapped. A false reject now costs one extra
   key press, not the onboarding.

## 3. The bypass rate is the metric (1 min)
1. Press **q**; the report opens. Point at the top: **"Bypass rate: 50% - 1 of 2 captures were taken past the gate"**, and at the
   orange tick on the timeline and the **BYPASSED** badge on the thumbnail with its blocking reason.
2. Say: the escape hatch is also the instrument. A rising bypass rate means the gate has become too strict; the flagged frames are
   exactly the labelled failures the next model version needs. Nothing auto-deploys; the retrained model is validated against the
   accumulated bypass frames first.

## 4. Damaged cards (D-15): say it, do not demo it (1 min)
Do **not** fold a card live as proof of a fix: it still passes, and that is the honest answer. Say: I measured whether the mask we
already have can catch a fold. It cannot (solidity: damaged 0.972-0.981 against clean 0.959-0.990; flagging all four damaged frames
would flag 51 of the 152 project frames), so the fix is a fifth class and a retrain, which is Phase 2, and the review
step you just saw is what catches it in the meantime.

## Say honestly if asked
- "Sent for manual review" is a message on the screen and a flag in the report. There is no review queue behind it yet.
- The 3 s per rejection, 3 rejections and 120 s are my numbers, not tuned on real users.
- The block did not change: still 30 of 30 tests, 152 of 152 identical to the platform. These rules live in the app.
- Not tried on a live camera by me; the tests and a scripted run on stills are what back it.
