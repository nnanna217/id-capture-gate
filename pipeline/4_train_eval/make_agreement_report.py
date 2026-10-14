"""Build local/report/agreement-report.html: held-out agreement, the D-13 precedence
findings and the by-design negatives, each with its frames and measurements.

usage: python pipeline/4_train_eval/make_agreement_report.py
Reads local/labels/verdict-run-v5.csv and local/captures/<condition>/<file>.
Images are referenced relative to the report file, so it works wherever it is opened.
"""
import csv, os, html, collections

CSV = "local/labels/verdict-run-v5.csv"
OUT = "local/report/agreement-report.html"
PREC = ["too_dark", "no_document", "incomplete_document", "obstructed",
        "glare_over_data_zone", "blurred"]
GUIDE = {"too_dark": "Move to better light", "no_document": "Hold the card in view",
         "incomplete_document": "Move back", "obstructed": "Finger off the text",
         "glare_over_data_zone": "Tilt the card", "blurred": "Hold steady",
         "usable": "(none)"}
EXPECT = {"good": "usable", "glare_direct": "glare_over_data_zone",
          "glare_oblique": "glare_over_data_zone", "obstruction": "obstructed",
          "partial": "incomplete_document", "blur": "blurred", "lowlight": "too_dark"}

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def primary(r):
    if r["verdict"] == "usable": return "usable"
    fired = [x for x in r["reasons"].split("|") if x]
    for p in PREC:
        if p in fired: return p
    return fired[0] if fired else "?"

def classify(r):
    """exact | by-design | under-cutoff | disagree"""
    c, p = r["condition"], primary(r)
    if p == EXPECT[c]: return "exact"
    cov = num(r["glare_cov"]) if c.startswith("glare") else (num(r["obs_cov"]) if c == "obstruction" else None)
    if p == "usable" and cov == 0: return "by-design"
    if p == "usable" and cov is not None and cov > 0: return "under-cutoff"
    return "disagree"

rows = list(csv.DictReader(open(CSV)))
for r in rows:
    r["_p"] = primary(r); r["_k"] = classify(r)
    r["_img"] = os.path.join("local/captures", r["condition"], r["file"])

BADGE = {"exact": ("#1D9E75", "#04342C", "reason matched"),
         "by-design": ("#9FE1CB", "#04342C", "usable, defect off the text zone"),
         "under-cutoff": ("#FAC775", "#412402", "usable, under the cut-off"),
         "disagree": ("#EF9F27", "#412402", "disagreement")}

def pct(x, y): return f"{x/y:.1%}" if y else "n/a"

def stats(sub):
    k = collections.Counter(r["_k"] for r in sub)
    ok = k["exact"] + k["by-design"]
    return len(sub), k, ok

def card(r, show=()):
    col, txt, lab = BADGE[r["_k"]]
    bits = []
    for f, name in (("sharp", "sharpness"), ("glare_cov", "glare of zone"),
                    ("obs_cov", "obstruction of zone"), ("p95", "p95 grey")):
        if f in show:
            v = num(r[f])
            if f in ("glare_cov", "obs_cov"):
                s = f"{v*100:.2f}%" if v is not None else "&mdash;"
            elif f == "sharp":
                s = f"{v:.3f}" if v is not None else "<em>not measured</em>"
            else:
                s = f"{v:.0f}" if v is not None else "&mdash;"
            bits.append(f'<div class="m"><span>{name}</span><b>{s}</b></div>')
    reasons = html.escape(r["reasons"]) or "&mdash;"
    return f"""<figure class="card">
  <img src="../../{html.escape(r['_img'])}" alt="{html.escape(r['file'])}" loading="lazy">
  <figcaption>
    <div class="fn">{html.escape(r['file'].replace('.jpg',''))}</div>
    <div class="row"><span class="tag">{html.escape(r['condition'])}</span><span class="tag sp">{html.escape(r['split'])}</span></div>
    <div class="bar" style="background:{col};color:{txt}">{lab}</div>
    <div class="m"><span>expected</span><b>{EXPECT[r['condition']]}</b></div>
    <div class="m"><span>gate said</span><b>{html.escape(r['_p'])}</b></div>
    <div class="m"><span>all reasons</span><b>{reasons}</b></div>
    <div class="m"><span>guidance</span><b>{html.escape(r['guidance']) or '&mdash;'}</b></div>
    {''.join(bits)}
  </figcaption></figure>"""

def grid(sub, show=()):
    return '<div class="grid">' + "".join(card(r, show) for r in sub) + "</div>"

test = [r for r in rows if r["split"] == "test"]
vt = [r for r in rows if r["split"] in ("valid", "test")]
incomplete_other = [r for r in rows
                    if r["_p"] == "incomplete_document" and r["condition"] != "partial"]
bydesign = [r for r in rows if r["_k"] == "by-design"]
undercut = [r for r in rows if r["_k"] == "under-cutoff"]
disagree_vt = [r for r in vt if r["_k"] in ("disagree", "under-cutoff")]
blur_masked = [r for r in rows if r["condition"] == "blur" and r["_p"] == "incomplete_document"]

def summary_row(label, sub):
    n, k, ok = stats(sub)
    return (f"<tr><td>{label}</td><td>{n}</td><td>{k['exact']} ({pct(k['exact'],n)})</td>"
            f"<td>{k['by-design']}</td><td>{k['under-cutoff']+k['disagree']}</td>"
            f"<td class=hi>{pct(ok,n)}</td></tr>")

ladder = "".join(
    f'<li><span class="r">{i+1}</span><code>{p}</code><span class="g">{GUIDE[p]}</span>'
    + (f'<span class="note">catches {len(incomplete_other)} frames from other conditions first</span>' if p=="incomplete_document" else "")
    + (f'<span class="note">only {len([r for r in rows if num(r["sharp"]) is not None])} frames reached it</span>' if p=="blurred" else "")
    + "</li>" for i, p in enumerate(PREC))

doc = f"""<!DOCTYPE html><html lang=en><meta charset=utf-8>
<title>Capture gate &middot; agreement report</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{{--fg:#1a1a19;--mut:#6b6a65;--bd:#e1e0d9;--bg:#fcfcfb;--card:#fff}}
*{{box-sizing:border-box}}
body{{font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--fg);background:var(--bg);margin:0;padding:2rem 1.5rem 4rem;max-width:1280px;margin:0 auto}}
h1{{font-size:23px;font-weight:500;margin:0 0 .25rem}}
h2{{font-size:18px;font-weight:500;margin:2.5rem 0 .25rem;padding-top:1.5rem;border-top:1px solid var(--bd)}}
h3{{font-size:15px;font-weight:500;margin:1.5rem 0 .5rem}}
p.sub{{color:var(--mut);margin:0 0 1.5rem;font-size:14px}}
p{{max-width:76ch}}
table{{border-collapse:collapse;font-size:14px;margin:1rem 0}}
th,td{{text-align:left;padding:7px 14px 7px 0;border-bottom:1px solid var(--bd)}}
th{{font-weight:500;color:var(--mut);font-size:13px}}
td.hi{{font-weight:500}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(228px,1fr));gap:14px;margin:1rem 0 2rem}}
.card{{margin:0;background:var(--card);border:1px solid var(--bd);border-radius:10px;overflow:hidden}}
.card img{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#f1efe8}}
figcaption{{padding:9px 11px 11px}}
.fn{{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut);margin-bottom:5px;word-break:break-all}}
.row{{display:flex;gap:5px;margin-bottom:7px;flex-wrap:wrap}}
.tag{{font-size:11px;background:#f1efe8;color:#44443f;padding:2px 7px;border-radius:3px}}
.tag.sp{{background:#E6F1FB;color:#0C447C}}
.bar{{font-size:11px;padding:3px 8px;border-radius:3px;margin-bottom:7px;display:inline-block}}
.m{{display:flex;justify-content:space-between;gap:10px;font-size:12px;padding:2px 0;border-top:1px solid #f1efe8}}
.m span{{color:var(--mut);flex-shrink:0}}
.m b{{font-weight:400;text-align:right;word-break:break-word}}
ol.lad{{list-style:none;padding:0;margin:1rem 0 2rem;max-width:760px}}
ol.lad li{{display:flex;align-items:center;gap:11px;padding:7px 0;border-bottom:1px solid var(--bd);flex-wrap:wrap}}
.r{{width:19px;color:var(--mut);font-size:13px}}
ol.lad code{{font:12px ui-monospace,Menlo,monospace;background:#f1efe8;padding:3px 8px;border-radius:3px;min-width:178px}}
.g{{font-size:13px;color:var(--mut)}}
.note{{font-size:12px;color:#854F0B;background:#FAEEDA;padding:2px 8px;border-radius:3px}}
.cap{{color:var(--mut);font-size:13px;max-width:76ch;margin:.25rem 0 0}}
@media (prefers-color-scheme:dark){{
 :root{{--fg:#f0efec;--mut:#9c9a92;--bd:#2c2c2a;--bg:#161615;--card:#1e1e1c}}
 .tag{{background:#2c2c2a;color:#c3c2b7}} .tag.sp{{background:#0C447C;color:#B5D4F4}}
 .m{{border-color:#252523}} ol.lad code{{background:#2c2c2a}}
 .note{{background:#412402;color:#FAC775}} .card img{{background:#2c2c2a}}}}
</style>
<h1>Capture gate &middot; reason-code agreement</h1>
<p class=sub>Does the gate's reason match what is actually wrong with the frame? Compared against the condition each frame was shot under. Generated from <code>{CSV}</code>.</p>

<h2>1 &middot; Agreement, by split</h2>
<table><tr><th>Set</th><th>n</th><th>exact match</th><th>by design</th><th>disagree</th><th>agreement</th></tr>
{summary_row("<b>Test</b>", test)}
{summary_row("<b>Valid + test</b>", vt)}
{summary_row("All 152 <em>(structural only)</em>", rows)}
</table>
<p class=cap><b>Lead with the held-out rows.</b> The model trained on 276 images derived from the 92 train-split sources, so its detections on train frames are contaminated and the all-152 figure is not an accuracy claim. It is kept because two findings below need the volume &mdash; the test split contains one blur frame.</p>
<p class=cap>The condition label is <b>shooting intent</b>, not a blind third-party judgement. &ldquo;By design&rdquo; means the defect was deliberately placed <em>off</em> the text block, so <code>usable</code> is the correct answer.</p>

<h2>2 &middot; The held-out frames &mdash; test split ({len(test)})</h2>
<p class=cap>Every test frame, its expected reason, what the gate said, and the measurements behind it. Note the composition: {collections.Counter(r['condition'] for r in test)['obstruction']} of {len(test)} are obstruction, which is why this is indicative rather than settled.</p>
{grid(test, ("sharp","glare_cov","obs_cov"))}

<h2>3 &middot; Disagreements across valid + test ({len(disagree_vt)})</h2>
<p class=cap>The frames behind the 90% figure that did not match. Most are threshold calls rather than errors.</p>
{grid(disagree_vt, ("sharp","glare_cov","obs_cov"))}

<h2>4 &middot; D-13 precedence &mdash; one instruction at a time</h2>
<p class=cap>The reason list keeps every reason that fired. Only the single guidance string follows this order.</p>
<ol class=lad>{ladder}</ol>

<h3>The {len(incomplete_other)} frames that returned <code>incomplete_document</code> from another condition</h3>
<p class=cap>These are rank 3 firing before ranks 4, 5 and 6. Read the <b>all reasons</b> line on each card: where it shows only <code>incomplete_document</code>, nothing below it was ever evaluated. &ldquo;Move back&rdquo; is the right single instruction, because moving back usually fixes the other defect too.</p>
{grid(incomplete_other, ("sharp","glare_cov","obs_cov"))}

<h3>Of those, the {len(blur_masked)} blur frames that never reached the sharpness check</h3>
<p class=cap><code>sharpness</code> reads <em>not measured</em> on every one. Combined with the 4 bank blur frames that had no template match, only {len([r for r in rows if num(r['sharp']) is not None])} frames in 152 ever reached the blur measurement &mdash; the sharpest available statement of this project's weakest class.</p>
{grid(blur_masked, ("sharp","p95"))}

<h2>5 &middot; By-design negatives ({len(bydesign)})</h2>
<p class=cap>Defect present on the card, deliberately <b>off</b> the text block, coverage of the text zone measured at exactly <b>0.00%</b>. The gate called every one <code>usable</code>, which is correct: the question is whether the data can be read, not whether the card has glare or a finger on it somewhere. These are the proof the intersection test discriminates rather than firing on any glare or any finger.</p>
{grid(bydesign, ("glare_cov","obs_cov","sharp"))}

<h3>Near the line &mdash; defect on the zone but under the cut-off ({len(undercut)})</h3>
<p class=cap>Coverage above zero but below the threshold, so still <code>usable</code>. These are threshold calls and the honest place to say the cut-off is a judgement, not a measurement.</p>
{grid(undercut, ("glare_cov","obs_cov","sharp"))}
</html>"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w").write(doc)
n, k, ok = stats(test)
print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
print(f"test n={n} agreement {pct(ok,n)} | valid+test {pct(stats(vt)[2], stats(vt)[0])}")
print(f"sections: test {len(test)} | disagree(v+t) {len(disagree_vt)} | incomplete-from-other {len(incomplete_other)} | blur masked {len(blur_masked)} | by-design {len(bydesign)} | under-cutoff {len(undercut)}")
