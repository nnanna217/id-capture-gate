"""Capture-quality verdict: the custom Workflow block's code.

THIS FILE IS THE SOURCE OF TRUTH. build_workflow.py embeds its text, unchanged, as the Dynamic Python block's code, and the
tests execute the same text. Only numpy and cv2 are used (both available inside Workflow code).

Input : the camera image and the segmentation model's detections (document, data_zone, glare, obstruction masks).
Output: verdict ("usable" / "not_usable"), reasons (every reason that applies, in precedence order), ONE guidance string
        (for the first reason), and details (the raw measurements, for the session report and tuning; never shown to the person).
There is deliberately no numeric quality score in the output contract (DECISIONS.md D-02, D-13).

Precedence (D-13): too_dark, no_document, incomplete_document, obstructed, glare_over_data_zone, blurred.
`blurred` is only judged when nothing above it applies: sharpness inside a dark, covered or glared text zone is not meaningful
(measured: those frames fall in the same sharpness range as genuinely blurred ones).

Defaults come from measurements on this project's 152 frames and are provisional where noted (BUILD-LOG.md, 2026-10-11):
  dark_p95      110   95th-percentile grey over the card; 11 lowlight frames <= 103, 141 others >= 116 (margin 13 on the bank card)
  blur_min_*    0.35 / 0.70  zone sharpness (Laplacian variance / pixel variance, zone warped to 320 px), one cut-off per text-zone
                      layout because the scales differ: block-shaped zone (aspect < 2.5, the ID card) 0.35: blur <= 0.093, sharp >= 0.526;
                      wide strip (aspect >= 2.5, the bank card) 0.70: blur <= 0.505, sharp >= 0.959. PROVISIONAL: no mildly blurred
                      frames exist, and two ID frames at 0.406 / 0.462 are undecided (to be judged by a person)
  overlap_min   0.02  share of the text zone covered; slivers under 2% are not counted
  min_confidence 0.4  the model's score cut-off (provisional: not yet tuned on held-out frames)
  edge_margin_px 2    the card mask touching the frame edge within this many pixels means a corner is out of frame
  covered_card  0.9   an obstruction over this share of the card mask makes the card-based checks (light, edges) untrustworthy
                      (evidence: ONE frame, bank-obstruction-003, where the model's 'card' mask is the strap itself)
"""
import cv2
import numpy as np

ORDER = ["too_dark", "no_document", "incomplete_document", "obstructed", "glare_over_data_zone", "blurred"]
GUIDANCE = {
    "too_dark": "Move to better light.",
    "no_document": "Hold the card in front of the camera.",
    "incomplete_document": "Move back so all four corners are in view.",
    "obstructed": "Move your finger or anything else off the text.",
    "glare_over_data_zone": "Tilt the card to move the glare off the text.",
    "blurred": "Hold steady.",
}
USABLE_GUIDANCE = "Looks good. Capture it."


def _picks(names, conf, name, min_conf):
    idx = [i for i in range(len(names)) if names[i] == name and conf[i] >= min_conf]
    return sorted(idx, key=lambda i: -conf[i])


def _union(masks, idx, shape):
    out = np.zeros(shape, bool)
    for i in idx:
        out |= masks[i].astype(bool)
    return out


def _zone_sharpness(gray, zone, long_side=320):
    """Laplacian variance / pixel variance of the text zone warped to a fixed 320 px long side (contrast-normalised).
    NOT scale-invariant: a zone smaller than 320 px is upsampled and reads softer than it is (the project's ID zone is about 420 px
    and the bank zone about 880 px, so both are downsampled). A card held far from the camera would therefore look blurrier."""
    cnts, _ = cv2.findContours(zone.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, None
    box = cv2.boxPoints(cv2.minAreaRect(max(cnts, key=cv2.contourArea))).astype(np.float32)
    s, d = box.sum(1), np.diff(box, axis=1).ravel()
    box = np.array([box[np.argmin(s)], box[np.argmin(d)], box[np.argmax(s)], box[np.argmax(d)]], np.float32)  # tl tr br bl
    w, h = np.linalg.norm(box[1] - box[0]), np.linalg.norm(box[3] - box[0])
    if w < h:
        box, w, h = np.array([box[3], box[0], box[1], box[2]], np.float32), h, w
    if w < 8 or h < 4:
        return None, None
    sc = long_side / w
    W, H = long_side, max(int(round(h * sc)), 8)
    M = cv2.getPerspectiveTransform(box, np.float32([[0, 0], [W, 0], [W, H], [0, H]]))
    patch = cv2.warpPerspective(gray, M, (W, H), flags=cv2.INTER_AREA)
    var = float(patch.astype(np.float64).var())
    aspect = float(w / h)
    if var < 1e-6:
        return 0.0, aspect
    return float(cv2.Laplacian(patch, cv2.CV_64F).var()) / var, aspect


def run(self, image, predictions, min_confidence=0.4, dark_p95=110.0, blur_min_block=0.35, blur_min_wide=0.70, wide_aspect=2.5,
        overlap_min=0.02, edge_margin_px=2, covered_card=0.9):
    img = image.numpy_image
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    H, W = gray.shape[:2]
    n = len(predictions) if predictions is not None else 0
    names = list(predictions.data.get("class_name", [])) if n else []
    conf = list(predictions.confidence) if n and predictions.confidence is not None else [1.0] * n
    masks = predictions.mask if n and predictions.mask is not None else None

    def pick(name):
        return _picks(names, conf, name, min_confidence) if masks is not None else []

    doc_i, zone_i = pick("document"), pick("data_zone")
    doc = masks[doc_i[0]].astype(bool) if doc_i else None
    zone = masks[zone_i[0]].astype(bool) if zone_i else None
    details = {"document_found": doc is not None, "data_zone_found": zone is not None}
    reasons = []

    obs = _union(masks, pick("obstruction"), (H, W)) if masks is not None else np.zeros((H, W), bool)
    gla = _union(masks, pick("glare"), (H, W)) if masks is not None else np.zeros((H, W), bool)
    # an obstruction over (almost) the whole card mask means the card mask is not trustworthy for light or edge checks
    covered = bool(doc is not None and doc.any() and (obs & doc).sum() / float(doc.sum()) >= covered_card)
    details["card_mostly_covered"] = covered

    # 1. light: on the card when it is found, on the whole frame when it is not (so a dark scene is not reported as "no card")
    use_card = doc is not None and doc.any() and not covered
    region = gray[doc] if use_card else gray.ravel()
    p95 = float(np.percentile(region, 95))
    details["brightness_p95"] = p95
    details["brightness_region"] = "card" if use_card else "frame"
    if p95 < dark_p95:
        reasons.append("too_dark")

    # 2-3. the card
    if doc is None:
        reasons.append("no_document")
    elif not covered:
        m = int(edge_margin_px)
        touches = bool(doc[: m + 1, :].any() or doc[-(m + 1):, :].any() or doc[:, : m + 1].any() or doc[:, -(m + 1):].any())
        details["card_touches_frame_edge"] = touches
        if touches:
            reasons.append("incomplete_document")

    # 4-5. covered or glared text zone (falls back to the whole card if the text zone was not found)
    target = zone if zone is not None else doc
    details["zone_fallback_to_card"] = zone is None and doc is not None
    if target is not None and target.any():
        area = float(target.sum())
        o_cov, g_cov = float((obs & target).sum() / area), float((gla & target).sum() / area)
        details["obstruction_zone_coverage"], details["glare_zone_coverage"] = o_cov, g_cov
        if o_cov >= overlap_min:
            reasons.append("obstructed")
        if g_cov >= overlap_min:
            reasons.append("glare_over_data_zone")
        # 6. sharpness, only when nothing above applies
        if not reasons and zone is not None:
            sharp, aspect = _zone_sharpness(gray, zone)
            limit = blur_min_wide if (aspect is not None and aspect >= wide_aspect) else blur_min_block
            details["zone_sharpness"], details["zone_aspect"], details["blur_threshold_used"] = sharp, aspect, limit
            if sharp is not None and sharp < limit:
                reasons.append("blurred")

    reasons = [r for r in ORDER if r in reasons]
    details["thresholds"] = {"min_confidence": min_confidence, "dark_p95": dark_p95, "blur_min_block": blur_min_block,
                             "blur_min_wide": blur_min_wide, "wide_aspect": wide_aspect, "overlap_min": overlap_min,
                             "edge_margin_px": edge_margin_px, "covered_card": covered_card}
    return {
        "verdict": "not_usable" if reasons else "usable",
        "reasons": reasons,
        "guidance": GUIDANCE[reasons[0]] if reasons else USABLE_GUIDANCE,
        "details": details,
    }
