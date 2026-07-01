"""Build the Hawk-Eye (enterprise-grade upgrade) evaluation deck INSIDE the
official iDEA 2.0 template.

Template:  C:/Users/dhruv/Downloads/1782805714605-y6pgad.pptx  (PSBs Hackathon Series 2026)
Output:    C:/Users/dhruv/Code/hawk-eye/docs/deliverables/HAWKEYE_iDEA2_DECK.pptx

Content is structured to the NEW 5-pillar rubric (weights in each eyebrow):
  Problem & Business Relevance (20%) · Technology & Engineering (40%) ·
  Security, Scalability & Enterprise Readiness (20%) · Solution Execution & Demo (15%) ·
  Commercialization & Startup Potential (10%).

Run:  python docs/deliverables/_build_hawkeye_deck.py   (from the hawk-eye repo root,
      with a python that has python-pptx installed)
"""

from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

TEMPLATE = Path(r"C:/Users/dhruv/Downloads/1782805714605-y6pgad.pptx")
OUT = Path(r"C:/Users/dhruv/Code/hawk-eye/docs/deliverables/HAWKEYE_iDEA2_DECK.pptx")

# ── Brand palette (matches template: red on white) ──────────────────────────
INK = RGBColor(0x14, 0x18, 0x1F)
RED = RGBColor(0xE9, 0x2A, 0x2D)
DIM = RGBColor(0x5B, 0x64, 0x71)
FAINT = RGBColor(0x8A, 0x92, 0x9E)
PANEL = RGBColor(0xF5, 0xF6, 0xF8)
PANEL2 = RGBColor(0xFB, 0xEC, 0xEC)
LINE = RGBColor(0xDD, 0xE0, 0xE5)
GREEN = RGBColor(0x1E, 0x9E, 0x5A)
AMBER = RGBColor(0xD9, 0x82, 0x0B)
BLUE = RGBColor(0x25, 0x63, 0xEB)
VIOLET = RGBColor(0x7C, 0x3A, 0xED)
CYAN = RGBColor(0x0E, 0x91, 0xA8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

DISP = "League Spartan"
HEAD = "Montserrat"
MONO = "TT Interphases Mono"
BODY = "Calibri"

PW, PH = 20.0, 11.25
ML = 0.7
CW = PW - 2 * ML
TITLE_Y = 2.02

prs = Presentation(str(TEMPLATE))
BLANK = prs.slide_layouts[6]
FRAME = prs.slides[1]

FRAME_ELS = [copy.deepcopy(sh._element) for sh in FRAME.shapes]
FRAME_IMG_RELS = [(rId, rel.reltype, rel._target)
                  for rId, rel in FRAME.part.rels.items()
                  if not rel.is_external and "image" in rel.reltype]


def clone_frame():
    slide = prs.slides.add_slide(BLANK)
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)
    rid_map = {rId: slide.part.relate_to(target, reltype)
               for rId, reltype, target in FRAME_IMG_RELS}
    spTree = slide.shapes._spTree
    for el0 in FRAME_ELS:
        el = copy.deepcopy(el0)
        for e in el.iter():
            for attr in ("embed", "link"):
                v = e.get(qn("r:" + attr))
                if v in rid_map:
                    e.set(qn("r:" + attr), rid_map[v])
        spTree.append(el)
    return slide


def rect(slide, x, y, w, h, *, fill=PANEL, line=LINE, line_w=1.0, rounded=False):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        shp.adjustments[0] = 0.06
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    return shp


def txt(slide, x, y, w, h, text, *, size=14, color=INK, bold=False, italic=False,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=BODY, spacing=1.0):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    r = p.add_run()
    r.text = text
    f = r.font
    f.name = font; f.size = Pt(size); f.bold = bold; f.italic = italic
    f.color.rgb = color
    return tb


def lines(slide, x, y, w, h, items):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = it.get("align", PP_ALIGN.LEFT)
        p.line_spacing = it.get("spacing", 1.02)
        p.space_before = Pt(it.get("before", 5 if i else 0))
        bullet = it.get("bullet")
        prefix = (bullet + "  ") if bullet else ""
        r = p.add_run()
        r.text = prefix + it["t"]
        f = r.font
        f.name = it.get("font", BODY); f.size = Pt(it.get("size", 12))
        f.bold = it.get("bold", False); f.italic = it.get("italic", False)
        f.color.rgb = it.get("color", INK)
    return tb


def eyebrow_title(slide, eyebrow, headline, *, hl_size=29):
    txt(slide, ML, TITLE_Y, CW, 0.34, eyebrow.upper(),
        size=12.5, color=RED, bold=True, font=MONO)
    txt(slide, ML, TITLE_Y + 0.32, CW, 0.7, headline,
        size=hl_size, color=INK, bold=True, font=HEAD)
    rect(slide, ML, TITLE_Y + 1.02, 0.9, 0.05, fill=RED, line=None)


def card(slide, x, y, w, h, header, body_items, *, accent=RED, header_color=WHITE,
         header_size=12.5):
    rect(slide, x, y, w, h, fill=WHITE, line=LINE, line_w=1.25, rounded=True)
    rect(slide, x, y, w, 0.46, fill=accent, line=None, rounded=True)
    rect(slide, x, y + 0.24, w, 0.22, fill=accent, line=None)
    txt(slide, x + 0.18, y + 0.04, w - 0.3, 0.4, header, size=header_size,
        color=header_color, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    if body_items:
        lines(slide, x + 0.18, y + 0.58, w - 0.34, h - 0.7, body_items)


def chip(slide, x, y, w, h, text, *, fill=RED, color=WHITE, size=12, font=MONO):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = 0.5
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    shp.line.fill.background(); shp.shadow.inherit = False
    tf = shp.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text
    r.font.name = font; r.font.size = Pt(size); r.font.bold = True
    r.font.color.rgb = color
    return shp


def arrow(slide, x, y, w, h, color=RED):
    shp = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = color
    shp.line.fill.background(); shp.shadow.inherit = False
    return shp


CONTENT = []


def new_slide(eyebrow, headline, **kw):
    s = clone_frame()
    eyebrow_title(s, eyebrow, headline, **kw)
    CONTENT.append(s)
    return s


# ════════════════════════════════════════════════════════════════════════════
# PAGE 1 — TITLE / INTRO (on the branded frame)
# ════════════════════════════════════════════════════════════════════════════
s = FRAME
CONTENT.append(s)
txt(s, ML, 2.5, CW, 0.5, "RBI · iDEA 2.0 · PS — INTERNAL & PRIVILEGED-USER FRAUD EARLY-WARNING SYSTEM",
    size=14, color=RED, bold=True, font=MONO, align=PP_ALIGN.CENTER)
txt(s, ML, 3.0, CW, 1.6, "HAWK-EYE", size=115, color=INK, bold=True, font=DISP,
    align=PP_ALIGN.CENTER)
txt(s, ML, 4.85, CW, 0.55, "Real-Time Insider & Privileged-User Fraud Detection for a Public-Sector Bank",
    size=23, color=DIM, italic=True, font=HEAD, align=PP_ALIGN.CENTER)
txt(s, ML, 5.45, CW, 0.45, "Every privileged action — watched, scored, explained.  A human always decides.",
    size=15, color=INK, font=BODY, align=PP_ALIGN.CENTER)
pw, gap = 4.4, 0.3
px = (PW - (pw * 3 + gap * 2)) / 2
chip(s, px, 6.25, pw, 0.6, "7-LAYER L0–L7 ENGINE", fill=RED, size=13)
chip(s, px + pw + gap, 6.25, pw, 0.6, "ALERT-ONLY · CONTESTABLE", fill=INK, size=13)
chip(s, px + 2 * (pw + gap), 6.25, pw, 0.6, "ENTERPRISE-GRADE · ON-PREM", fill=GREEN, size=13)
txt(s, ML, 7.35, CW, 0.45, "Team NINEAGENTS  ·  SVKM's NMIMS",
    size=18, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
txt(s, ML, 7.85, CW, 0.4, "Dhruv Agrawal · Tanishq Vyas · Hanzala Saify · Aditya Dubey",
    size=14, color=DIM, font=BODY, align=PP_ALIGN.CENTER)
txt(s, ML, 8.35, CW, 0.4, "github.com/dhruvagrawal27/hawk-eye     ·     on-prem · synthetic-data demo · full test suites green",
    size=13, color=RED, bold=True, font=MONO, align=PP_ALIGN.CENTER)


# ════════════════════════════════════════════════════════════════════════════
# PILLAR 1 — PROBLEM & BUSINESS RELEVANCE (20%)
# ════════════════════════════════════════════════════════════════════════════

# PAGE 2 — Problem articulation & business impact
s = new_slide("Problem & Business Relevance (20%) · Problem & Impact",
              "The bank's biggest fraud blind spot is its own privileged staff")

def stat(x, val, label, color):
    rect(s, x, 3.45, 5.7, 1.5, fill=PANEL, line=color, line_w=1.5, rounded=True)
    txt(s, x, 3.58, 5.7, 0.75, val, size=38, color=color, bold=True, font=DISP, align=PP_ALIGN.CENTER)
    txt(s, x + 0.2, 4.4, 5.3, 0.5, label, size=13, color=DIM, font=BODY, align=PP_ALIGN.CENTER)

stat(ML, "₹36,014 cr", "bank fraud reported FY25 — up 194% YoY (RBI)", INK)
stat(ML + 6.0, "₹25,667 cr", "of that borne by public-sector banks", RED)
stat(ML + 12.0, "~12 months", "median time insider fraud runs before detection", AMBER)

card(s, ML, 5.25, 8.95, 5.05, "WHY INSIDERS ARE THE BLIND SPOT", [
    {"t": "Privileged users — DBAs, sysadmins, SWIFT/treasury operators, makers & checkers, loan officers, IAM/PAM admins — have god-mode access to core banking, treasury, loan origination and customer databases.", "size": 13, "bullet": "▸"},
    {"t": "Insider fraud runs a median ~12 months before detection and is caught 43% by tips — not systems; banking is the largest sector studied (ACFE 2024).", "size": 13, "bullet": "▸", "before": 6},
    {"t": "Advances-related frauds = ₹33,148 Cr of FY25 — the loan / OD / trade-finance instruments only privileged staff can originate or modify.", "size": 13, "bullet": "▸", "before": 6},
    {"t": "Proactive data-monitoring is one of only FOUR controls tied to a ≥50% cut in BOTH fraud loss and duration — Hawk-Eye's core value thesis.", "size": 13, "bullet": "▸", "before": 6, "bold": True, "color": GREEN},
    {"t": "Union Bank of India: merged-Finacle CBS (ex-Union / Andhra / Corporation), ~8,000+ branches, thousands of privileged users — a vast insider surface.", "size": 13, "bullet": "▸", "before": 6, "color": RED},
], accent=RED)

card(s, ML + 9.25, 5.25, 8.65, 5.05, "THE REGULATORY MANDATE (RBI 2024–2026)", [
    {"t": "RBI Master Directions on Fraud Risk Management 2024 — Red-Flagged-Account (RFA) lifecycle, staff-accountability examination on a 6-month clock, natural justice (SBI v. Rajesh Agarwal, 2023).", "size": 13.5, "bullet": "•"},
    {"t": "FMR + Central Fraud Registry (CFR) reporting of staff-fraud incidents.", "size": 13.5, "bullet": "•", "before": 6},
    {"t": "RBI FREE-AI (Aug 2025) + draft Model Risk Management (MRMF 2026) — ML models are a regulated, inspectable asset class.", "size": 13.5, "bullet": "•", "before": 6},
    {"t": "RBI Cyber Security Framework + IS Audit — insider-threat controls (privileged access, SoD, log integrity) are inspected.", "size": 13.5, "bullet": "•", "before": 6},
    {"t": "Hawk-Eye is built to sit inside this machinery — not bolted on after.", "size": 13, "italic": True, "color": GREEN, "before": 8, "bold": True},
], accent=INK)


# PAGE 3 — Solution scope, differentiation & innovation
s = new_slide("Problem & Business Relevance (20%) · Solution, Differentiation & Innovation",
              "A 7-layer, alert-only insider-fraud Early-Warning System")
card(s, ML, 3.45, 8.95, 6.85, "WHAT IT DOES  (exactly what the problem statement asks)", [
    {"t": "Continuously monitors internal & privileged users across core banking, treasury, loan origination and customer databases.", "size": 13.5, "bullet": "▸"},
    {"t": "Learns an ML behavioural baseline per user (peer-relative) and flags deviations in real time.", "size": 13.5, "bullet": "▸", "before": 6},
    {"t": "Detects unusual transaction patterns, off-hours access, bulk data downloads, unauthorized account modifications, and privilege-escalation attempts.", "size": 13.5, "bullet": "▸", "before": 6, "bold": True},
    {"t": "Produces a calibrated risk score, generates alerts with contextual explanations, and drives an investigator dashboard to triage and act.", "size": 13.5, "bullet": "▸", "before": 6},
    {"t": "→ one-to-one coverage of every clause of the PS (mapped on the next slide).", "size": 12.5, "italic": True, "color": RED, "before": 7},
], accent=BLUE)

card(s, ML + 9.3, 3.45, 8.6, 6.85, "DIFFERENTIATION & INNOVATION", [
    {"t": "Layered fusion — rules + UEBA + supervised GBDT + sequence + graph fused into ONE calibrated 0–100 score (not a single model).", "size": 13.5, "bullet": "1"},
    {"t": "Explainable by construction — SHAP + structured reason codes + an AI narrative on every alert; an alert with no reasons is rejected.", "size": 13.5, "bullet": "2", "before": 6},
    {"t": "Alert-only & contestable — the system scores and explains; a human decides. Never auto-blocks money. Enforced in code + natural justice.", "size": 13.5, "bullet": "3", "before": 6},
    {"t": "Peer-relative baselines + one-alert-per-entity — harder to game, and fights alert fatigue (the #1 killer of fraud systems).", "size": 13.5, "bullet": "4", "before": 6},
    {"t": "Wrapped in the RBI staff-fraud + FREE-AI governance machinery; on-prem, India-residency, fair (protected attributes never used), audited (tamper-evident WORM).", "size": 13.5, "bullet": "5", "before": 6, "color": RED},
], accent=RED)


# PAGE 4 — Problem-statement coverage matrix
s = new_slide("Problem & Business Relevance (20%) · Coverage",
              "Every signal the problem statement asks for — mapped to a layer")
rows = [
    ("ML behavioural baseline per user", "peer-relative UEBA (unsupervised, no labels)", "L2"),
    ("Unusual transaction patterns", "hard rules + supervised GBDT (LightGBM)", "L1 + L3"),
    ("Off-hours access", "time-of-day vs baseline + 7×24 heatmap", "L1 + L2"),
    ("Bulk data downloads", "download volume vs baseline + leaver-window + export-to-personal", "L1 + L2 + L4"),
    ("Unauthorized account modifications", "DB write with no app transaction · out-of-scope access", "L1 + L2"),
    ("Privilege-escalation attempts", "entitlement self-grant · temp-admin timed to transactions", "L1"),
    ("Real-time flagging", "fast lane: event → feature → score → alert in seconds", "L0–L6"),
    ("Risk scores", "one calibrated 0–100 score (severity × confidence)", "L6"),
    ("Alerts with contextual explanations", "SHAP + reason codes + AI narrative", "L3 / L6 / LLM"),
    ("Dashboard to triage & act", "investigator console: queue · entity-360 · EDD verdict", "L7"),
]
rect(s, ML, 3.4, CW, 0.5, fill=INK, line=None)
txt(s, ML + 0.15, 3.45, 5.6, 0.4, "PROBLEM-STATEMENT SIGNAL", size=12, color=WHITE, bold=True, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
txt(s, ML + 6.0, 3.45, 9.5, 0.4, "HOW HAWK-EYE CATCHES IT", size=12, color=WHITE, bold=True, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
txt(s, ML + 16.2, 3.45, 2.3, 0.4, "LAYER(S)", size=12, color=WHITE, bold=True, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
ry = 3.9
for i, (a, b, layer) in enumerate(rows):
    rh = 0.66
    rect(s, ML, ry, CW, rh, fill=(PANEL if i % 2 == 0 else WHITE), line=LINE)
    txt(s, ML + 0.15, ry, 5.7, rh, a, size=12.5, color=INK, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    txt(s, ML + 6.0, ry, 10.0, rh, b, size=12.5, color=DIM, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
    txt(s, ML + 16.2, ry, 2.3, rh, layer, size=12.5, color=RED, bold=True, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
    ry += rh
txt(s, ML, ry + 0.05, CW, 0.35, "Source: docs/detection-coverage-map.md (reproduces blueprint Part 12). 16 insider fraud vectors covered end-to-end.",
    size=11.5, color=FAINT, italic=True, font=BODY)


# ════════════════════════════════════════════════════════════════════════════
# PILLAR 2 — TECHNOLOGY & ENGINEERING QUALITY (40%)
# ════════════════════════════════════════════════════════════════════════════

# PAGE 5 — Technical architecture & data flow (native L0–L7 pipeline)
s = new_slide("Technology & Engineering (40%) · Architecture & Data Flow",
              "L0–L7 conveyor: event → rules → UEBA → GBDT → sequence → graph → fusion → dashboard")
layers = [
    ("L0", "Canonical event", "one JSON event\nfrom any source", INK),
    ("L1", "Rules + SoD", "hard red-flags,\nmaker-checker", BLUE),
    ("L2", "UEBA", "peer-relative\nbaseline, no labels", VIOLET),
    ("L3", "Supervised", "LightGBM\n+ SHAP", GREEN),
    ("L4", "Sequence", "order & timing\nof actions", CYAN),
    ("L5", "Graph", "collusion rings,\nshell vendors", AMBER),
    ("L6", "Fusion", "one 0–100 score\n+ reason codes", RED),
    ("L7", "Dashboard", "investigator\ntriage + EDD", INK),
]
n = len(layers)
bw = 2.14
gapx = (CW - n * bw) / (n - 1)
by = 3.5
bh = 2.5
for i, (code, name, desc, color) in enumerate(layers):
    bx = ML + i * (bw + gapx)
    rect(s, bx, by, bw, bh, fill=WHITE, line=color, line_w=2.0, rounded=True)
    rect(s, bx, by, bw, 0.7, fill=color, line=None, rounded=True)
    rect(s, bx, by + 0.4, bw, 0.3, fill=color, line=None)
    txt(s, bx, by + 0.02, bw, 0.66, code, size=26, color=WHITE, bold=True, font=DISP, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    txt(s, bx + 0.05, by + 0.8, bw - 0.1, 0.5, name, size=14, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
    txt(s, bx + 0.05, by + 1.35, bw - 0.1, 1.05, desc, size=11.5, color=DIM, font=BODY, align=PP_ALIGN.CENTER)
    if i < n - 1:
        arrow(s, bx + bw + gapx / 2 - 0.14, by + bh / 2 - 0.13, gapx - 0.02 if gapx < 0.4 else 0.28, 0.26, color=RED)

# lanes + guarantees
ly = by + bh + 0.25
rect(s, ML, ly, CW, 0.5, fill=PANEL, line=GREEN, line_w=1.2, rounded=True)
txt(s, ML + 0.2, ly, CW - 0.4, 0.5, "FAST LANE — real-time: event → feature → score → alert in SECONDS (the primary build).",
    size=13.5, color=INK, bold=True, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
rect(s, ML, ly + 0.6, CW, 0.5, fill=PANEL, line=AMBER, line_w=1.2, rounded=True)
txt(s, ML + 0.2, ly + 0.6, CW - 0.4, 0.5, "SLOW LANE — batch Early-Warning-Signal over days–weeks → feeds RBI EWS / RFA / CRILC / FMR.",
    size=13.5, color=INK, bold=True, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
rect(s, ML, ly + 1.2, CW, 0.72, fill=INK, line=None, rounded=True)
txt(s, ML + 0.2, ly + 1.2, CW - 0.4, 0.72,
    "ALERT-ONLY — scores & explains; a human decides, never auto-blocks money.  Every alert is contestable (reason codes) · reproducible · audited (hash-chained WORM).  Feedback loop: investigator EDD verdict → new label → models retrain.",
    size=13, color=WHITE, bold=True, font=BODY, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)


# PAGE 6 — Tech stack
s = new_slide("Technology & Engineering (40%) · Tech Stack",
              "Production stack — ~26 orchestrated services, on-prem")
stack = [
    ("BACKEND", BLUE, ["Python 3.13 · FastAPI", "performance-critical bits in Rust", "REST API + OpenAPI + RBAC"]),
    ("ML / MLOps", GREEN, ["LightGBM · XGBoost · CatBoost · PyOD", "PyTorch + torch-geometric (GNN) · SHAP", "MLflow · Evidently · Fairlearn · ONNX"]),
    ("DATA / STREAMING", VIOLET, ["Kafka event bus · canonical L0 event", "feature store + lineage + MDM", "synthetic simulator + public datasets"]),
    ("DATABASES", CYAN, ["ClickHouse (columnar events)", "Postgres · Redis · MinIO object store", "WORM / tamper-evident audit"]),
    ("FRONTEND", RED, ["React 19 · TypeScript · Vite", "Radix + CVA + Tailwind", "Recharts · Cytoscape · 82 components"]),
    ("INFRA / DEPLOY", INK, ["Docker Compose · Kubernetes · ArgoCD", "Terraform · HSM / Vault · mTLS", "OPA/Conftest policy gates"]),
]
cw, ch, gx, gy = 5.85, 2.55, 0.5, 0.4
for i, (h, color, items) in enumerate(stack):
    cx = ML + (i % 3) * (cw + gx)
    cy = 3.5 + (i // 3) * (ch + gy)
    card(s, cx, cy, cw, ch, h, [{"t": t, "size": 13, "bullet": "•", "before": 4} for t in items], accent=color)


# PAGE 7 — AI/ML usage & model justification
s = new_slide("Technology & Engineering (40%) · AI/ML Usage & Model Justification",
              "Layered ML — each layer covers what the others cannot")
models = [
    ("L2 · UEBA (unsupervised)", VIOLET, ["Learns each user's normal vs their PEERS", "No labels needed → solves cold-start", "Peer-relative = fairer + harder to game"]),
    ("L3 · Supervised GBDT", GREEN, ["LightGBM on confirmed-fraud labels", "SHAP shows which features drove the score", "The explainable supervised workhorse"]),
    ("L4 · Sequence / time-series", CYAN, ["Order & timing of actions (slow-burn)", "Simple methods first; deep only if", "it genuinely beats the simple baseline"]),
    ("L5 · Graph / relational", AMBER, ["GNN / GraphSAGE over the actor network", "Collusion rings, shell vendors, maker-", "checker subgraphs invisible to tabular"]),
]
cw2 = 4.3
for i, (name, color, items) in enumerate(models):
    cx = ML + i * (cw2 + 0.43)
    card(s, cx, 3.5, cw2, 3.0, name, [{"t": t, "size": 12.5, "bullet": "•", "before": 5} for t in items], accent=color, header_size=11.5)

rect(s, ML, 6.8, CW, 1.55, fill=PANEL2, line=RED, line_w=1.2, rounded=True)
lines(s, ML + 0.25, 6.92, CW - 0.5, 1.35, [
    {"t": "L6 · CALIBRATED RISK FUSION", "size": 13, "color": RED, "bold": True, "font": MONO},
    {"t": "All layers + rules fuse into ONE calibrated 0–100 score with severity × confidence and a single set of reason codes — so investigators get one alert per entity, not ten. A \"70/100\" really means ~70% likely (calibration).", "size": 13.5, "color": INK, "before": 5},
])
card(s, ML, 8.55, CW, 1.75, "MODEL JUSTIFICATION & HONEST EVALUATION", [
    {"t": "Metrics that don't lie on imbalanced data: PR-AUC / average precision, precision@k, alert-to-true-fraud ratio — not ROC-AUC alone.  Strict temporal train/test split (past→future) to avoid data & temporal leakage.  Synthetic is for training/augmentation; detection quality must be validated on real labelled outcomes.  Feedback loop retrains as investigators confirm cases.", "size": 13, "bullet": "▸"},
], accent=INK)


# PAGE 8 — Working product & feature completeness
s = new_slide("Technology & Engineering (40%) · Working Product & Completeness",
              "A working system, proven end-to-end — not slideware")
card(s, ML, 3.5, 8.95, 3.4, "END-TO-END, IN ONE COMMAND  ( python -m ml.demo )", [
    {"t": "A synthetic fraud burst flows L0 → L2 → L3 → L5 → L6 …", "size": 13.5, "bullet": "▸"},
    {"t": "… and ends in a RISK 100/100 critical alert on a genuinely fraudulent employee,", "size": 13.5, "bullet": "▸", "before": 5, "bold": True},
    {"t": "prints the reason codes + a plain-English narrative, and confirms the alert is CONTESTABLE (has reasons) and REPRODUCIBLE.", "size": 13.5, "bullet": "▸", "before": 5},
    {"t": "The whole detection idea, verifiable in miniature.", "size": 12.5, "italic": True, "color": GREEN, "before": 6},
], accent=GREEN)
card(s, ML + 9.3, 3.5, 8.6, 3.4, "TEST SUITES — ALL GREEN", [
    {"t": "ML 250   ·   BACKEND 109   ·   DATA 100", "size": 13.5, "bullet": "✓", "color": GREEN, "bold": True, "font": MONO},
    {"t": "FRONTEND 112 (+3 e2e)   ·   PLATFORM 73 (+4 contract)", "size": 13.5, "bullet": "✓", "color": GREEN, "bold": True, "font": MONO, "before": 5},
    {"t": "DATABASE 60 (+10 integration)", "size": 13.5, "bullet": "✓", "color": GREEN, "bold": True, "font": MONO, "before": 5},
    {"t": "Adversarial RED-TEAM suite found + fixed 3 real safety bugs.", "size": 13, "color": INK, "before": 7},
    {"t": "Honest ledger: 112 REAL · 20 SCAFFOLD · 17 MOCK across 149 build tasks — every capability labelled, nothing oversold.", "size": 13, "color": RED, "bold": True, "before": 7},
], accent=INK)
rect(s, ML, 7.1, CW, 3.2, fill=WHITE, line=LINE, line_w=1.25, rounded=True)
rect(s, ML, 7.1, CW, 0.46, fill=RED, line=None, rounded=True); rect(s, ML, 7.34, CW, 0.22, fill=RED, line=None)
txt(s, ML + 0.18, 7.14, CW - 0.3, 0.4, "THE FULL PLATFORM — ~26 CONNECTED SERVICES ( make up )", size=12.5, color=WHITE, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
lines(s, ML + 0.25, 7.7, CW - 0.5, 2.5, [
    {"t": "Kafka · ClickHouse · Redis · Postgres · MinIO · the FastAPI control room · model serving · the React investigator dashboard · Prometheus/Grafana monitoring — up together with one command.", "size": 13.5, "bullet": "▸"},
    {"t": "Runs on a deterministic synthetic dataset — 118,518 events, all 12 insider-fraud typologies, 14 fraud actors (seed 1405) — fully reproducible on any laptop.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Built as 6 disjoint workstreams (DATA · ML · BACKEND · FRONTEND · DATABASE · PLATFORM) across 149 tasks, each validated against a 34-part implementation blueprint.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "FastAPI with interactive docs at /api/v1/docs; synthetic role users; ranked alert queue, alert detail + reasons, EDD disposition, audited PII unmask, regulator reports.", "size": 13.5, "bullet": "▸", "before": 7},
])


# PAGE 9 — Engineering decisions & technical depth
s = new_slide("Technology & Engineering (40%) · Engineering Decisions & Depth",
              "Rigor baked in — safety, contracts and adversarial tests")
card(s, ML, 3.5, 8.95, 6.8, "SAFETY & CORRECTNESS, ENFORCED IN CODE", [
    {"t": "Alert-only enforced in code (ml/design/alert_only_contract.py) — the API only exposes a human-raised block-REQUEST; nothing is ever auto-blocked or auto-classified.", "size": 13.5, "bullet": "▸"},
    {"t": "Every alert is contestable — reason codes + narrative; an alert with NO reasons is rejected (natural justice, per SBI v. Rajesh Agarwal).", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "\"Watch the watchers\" — every sensitive action (who viewed whom, every unmask) is written to a tamper-evident, hash-chained WORM audit log.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Fair by construction — peer-relative scoring; protected attributes are never used; the build FAILS if a fairness check trips.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Red-team suite actively tries to break alert-only, leak secrets, or bypass RBAC/SoD — and gates the build.", "size": 13.5, "bullet": "▸", "before": 7, "color": RED},
], accent=RED)
card(s, ML + 9.3, 3.5, 8.6, 6.8, "DEPTH & DELIVERY DISCIPLINE", [
    {"t": "Layered defence — a 6-layer detection cascade (L0–L7) + 12 named L1 rules (5 hard-hit) + 7 SoD conflict pairs; no single evasion defeats the system.", "size": 13.5, "bullet": "•"},
    {"t": "Calibrated fusion + severity × confidence → one ranked alert per entity (designed against alert fatigue from day one).", "size": 13.5, "bullet": "•", "before": 7},
    {"t": "Feedback loop — every investigator verdict becomes a label; models retrain and improve the longer it runs.", "size": 13.5, "bullet": "•", "before": 7},
    {"t": "Contract-tested seams between workstreams; ONNX serving; simple-model-first policy (deep learning only when it beats the baseline).", "size": 13.5, "bullet": "•", "before": 7},
    {"t": "REAL / SCAFFOLD / MOCK status labels on every capability — the team never oversells what is wired vs. what needs a real key or hardware.", "size": 13.5, "bullet": "•", "before": 7, "color": GREEN},
], accent=INK)


# PAGE 10 — Data handling & privacy
s = new_slide("Technology & Engineering (40%) · Data Handling & Privacy",
              "Privacy and data governance by design")
priv = [
    ("Canonical L0 event", "Every action from any source (CBS, SWIFT, PAM, IGA, HR) becomes ONE common JSON event — who / did-what / to-what / context / links. Source-agnostic; connectors slot in behind it."),
    ("Synthetic-only, on-prem", "The whole system runs locally on synthetic + public data — no real people, no real money, no cloud secrets. API keys are injected at runtime, never written in code."),
    ("PII tokenization", "Personal identifiers are replaced by safe tokens (EMP-7f3a) before anything leaves the secure perimeter; unmasking is RBAC-gated and audited."),
    ("DPDP + RBI retention", "Retention & archival tiering to DPDP + RBI windows; data lineage + MDM staff entity-resolution across the merged CBS / AD / HR / IAM. DPIA + lawful-basis map in governance/docs."),
]
py = 3.5
for t, d in priv:
    rect(s, ML, py, 10.8, 1.55, fill=PANEL, line=LINE, line_w=1.0, rounded=True)
    rect(s, ML, py, 0.12, 1.55, fill=RED, line=None)
    txt(s, ML + 0.3, py + 0.13, 10.3, 0.4, t, size=16, color=INK, bold=True, font=HEAD)
    txt(s, ML + 0.3, py + 0.6, 10.3, 0.9, d, size=12.5, color=DIM, font=BODY)
    py += 1.7
card(s, ML + 11.1, 3.5, 6.8, 6.8, "PROPORTIONALITY & FAIRNESS", [
    {"t": "It watches STAFF — treated as a legal/cultural matter, not just a technical one.", "size": 13.5, "bullet": "▸"},
    {"t": "Proportionality — only risk-relevant signals are used, not everything.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Transparency with staff / works-council / HR / legal.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Fairness testing; protected attributes never used.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Human-in-the-loop with natural justice before any classification.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "TEE / attestation for the AI narrative — names tokenized; the model provider cannot read the data.", "size": 13.5, "bullet": "▸", "before": 7, "color": RED},
], accent=GREEN)


# ════════════════════════════════════════════════════════════════════════════
# PILLAR 3 — SECURITY, SCALABILITY & ENTERPRISE READINESS (20%)
# ════════════════════════════════════════════════════════════════════════════

# PAGE 11 — Security & access control
s = new_slide("Security, Scalability & Enterprise Readiness (20%) · Security & Access Control",
              "Enterprise security & least-privilege access")
sec = [
    ("RBAC + Separation of Duties", "Role-gated everywhere (analyst / compliance / auditor / model-engineer / admin). SoD: whoever builds models can't label data or close their own alerts.", BLUE),
    ("Secrets: HSM / Vault + mTLS", "Secrets in Vault / HSM, injected at runtime — never in code. mTLS between services; OPA/Conftest policy gates in CI.", RED),
    ("Tamper-evident audit", "Hash-chained WORM audit of every sensitive action & PII unmask — edits are detectable. \"Watch the watchers.\"", INK),
    ("TEE-attested AI narrative", "The LLM narrative runs in a Trusted Execution Environment with tokenized names — provider can't read data; falls back to a template if unavailable.", VIOLET),
    ("Threat model + red-team", "Documented threat model, admin-access policy, security-framework mapping; adversarial red-team suite gates the build.", AMBER),
]
py = 3.5
for i, (t, d, color) in enumerate(sec):
    yy = 3.5 + i * 1.37
    rect(s, ML, yy, CW, 1.22, fill=PANEL, line=LINE, line_w=1.0, rounded=True)
    rect(s, ML, yy, 0.14, 1.22, fill=color, line=None)
    txt(s, ML + 0.35, yy + 0.1, 6.4, 1.0, t, size=16, color=INK, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    txt(s, ML + 7.0, yy + 0.1, CW - 7.2, 1.0, d, size=13.5, color=DIM, font=BODY, anchor=MSO_ANCHOR.MIDDLE)


# PAGE 12 — Scalability & performance
s = new_slide("Security, Scalability & Enterprise Readiness (20%) · Scalability & Performance",
              "Built for PSB scale — 8,000+ branches, thousands of privileged users")
card(s, ML, 3.5, 8.95, 6.8, "SCALES ON THE AXES THAT MATTER", [
    {"t": "Streaming ingest on Kafka — the fast lane scores event → alert in seconds; horizontally scalable consumers.", "size": 14, "bullet": "▸"},
    {"t": "ClickHouse columnar store for high-volume privileged-action events; Redis for hot features.", "size": 14, "bullet": "▸", "before": 8},
    {"t": "~26 services orchestrated; Kubernetes + ArgoCD + an HA topology for horizontal scale and rollout.", "size": 14, "bullet": "▸", "before": 8},
    {"t": "Per-entity / per-peer baselines + peer-fair scoring across ~8,000+ branches and thousands of privileged users.", "size": 14, "bullet": "▸", "before": 8},
    {"t": "Alert budgeting + one-alert-per-entity fusion so investigators are never buried (alert fatigue is the #1 operational killer).", "size": 14, "bullet": "▸", "before": 8, "color": RED},
    {"t": "Sized for 360M events/day · 12,500 events/s peak → 3 Kafka brokers (RF3) · 1 Flink · 1 ClickHouse shard ×2. ~$480/mo AWS Lightsail pilot → ~$2,400/mo full AWS VPC. ONNX serving.", "size": 14, "bullet": "▸", "before": 8, "color": RED},
], accent=RED)
card(s, ML + 9.3, 3.5, 8.6, 6.8, "TWO-LANE PERFORMANCE MODEL", [
    {"t": "FAST LANE (real-time)", "size": 15, "bold": True, "color": GREEN, "font": HEAD},
    {"t": "event → feature → score → alert in seconds. The primary online path for privileged-user behaviour.", "size": 13.5, "before": 3},
    {"t": "SLOW LANE (batch EWS)", "size": 15, "bold": True, "color": AMBER, "font": HEAD, "before": 12},
    {"t": "credit / entity / ghost-vendor / ghost-payroll / alert-suppression signals accumulate over days–weeks–months and feed RBI EWS / RFA / CRILC / FMR.", "size": 13.5, "before": 3},
    {"t": "Honest limit: credit fraud is accelerated (years → weeks), not made instant — stated plainly, never oversold.", "size": 13, "italic": True, "color": DIM, "before": 12},
], accent=INK)


# PAGE 13 — Deployment, compliance & banking integration
s = new_slide("Security, Scalability & Enterprise Readiness (20%) · Deployment, Compliance & Integration",
              "On-prem deployable, RBI-compliant, integration-ready")
card(s, ML, 3.5, 5.85, 6.8, "DEPLOYMENT", [
    {"t": "Docker Compose → Kubernetes + ArgoCD + Terraform", "size": 13, "bullet": "▸"},
    {"t": "Lightsail pilot recipe (DEPLOY_LIGHTSAIL.md)", "size": 13, "bullet": "▸", "before": 6},
    {"t": "OPA / Conftest policy gates in CI", "size": 13, "bullet": "▸", "before": 6},
    {"t": "On-prem, India data-residency by design", "size": 13, "bullet": "▸", "before": 6},
    {"t": "HA topology · HSM / Vault · mTLS · secrets at runtime", "size": 13, "bullet": "▸", "before": 6},
    {"t": "versioned bill-of-materials (deploy/versions.bom.yaml)", "size": 13, "bullet": "▸", "before": 6},
], accent=BLUE)
card(s, ML + 6.1, 3.5, 5.85, 6.8, "BANKING-SYSTEM INTEGRATION", [
    {"t": "Canonical L0 event = one connector interface", "size": 13, "bullet": "▸"},
    {"t": "Core banking (Finacle) · SWIFT / treasury", "size": 13, "bullet": "▸", "before": 6},
    {"t": "PAM (CyberArk / BeyondTrust) session content", "size": 13, "bullet": "▸", "before": 6},
    {"t": "IGA / IAM entitlements · HR / JML events", "size": 13, "bullet": "▸", "before": 6},
    {"t": "SWIFT ↔ CBS reconciliation (the PNB seam)", "size": 13, "bullet": "▸", "before": 6},
    {"t": "Connectors are SCAFFOLD until the bank wires credentials — same pattern across all feeds.", "size": 12.5, "italic": True, "color": DIM, "before": 8},
], accent=VIOLET)
card(s, ML + 12.2, 3.5, 5.7, 6.8, "RBI COMPLIANCE WRAPPER", [
    {"t": "RFA lifecycle state machine", "size": 13, "bullet": "•"},
    {"t": "Staff-accountability (6-month clock)", "size": 13, "bullet": "•", "before": 6},
    {"t": "FMR + Central Fraud Registry generation", "size": 13, "bullet": "•", "before": 6},
    {"t": "FREE-AI model governance + kill-switch", "size": 13, "bullet": "•", "before": 6},
    {"t": "MRMF 7-dimension model validation", "size": 13, "bullet": "•", "before": 6},
    {"t": "IS-audit insider-control evidence pack", "size": 13, "bullet": "•", "before": 6},
    {"t": "MLflow registry with Ed25519 signing + model cards", "size": 13, "bullet": "•", "before": 6},
    {"t": "Windows: CRILC ₹3 Cr / 7-day / 180-day · RBI TAT ≤30d · CERT-In 6h · DPDP ≤ ₹250 Cr · go-live gate 17/17 GO", "size": 12, "bullet": "•", "before": 6, "color": RED},
], accent=RED)


# ════════════════════════════════════════════════════════════════════════════
# PILLAR 4 — SOLUTION EXECUTION & DEMO QUALITY (15%)
# ════════════════════════════════════════════════════════════════════════════

# PAGE 14 — End-to-end demo with working data
s = new_slide("Solution Execution & Demo (15%) · End-to-End Demo with Working Data",
              "See it work — from one command to the full console")
steps = [
    ("1", "python -m ml.demo", "Synthetic fraud burst flows L0 → L2 → L3 → L5 → L6 → a RISK 100/100 critical alert with reason codes + narrative, contestable & reproducible."),
    ("2", "npm run dev  (dashboard)", "The investigator console on built-in mock data: triage queue, entity-360, explanation panel (SHAP + narrative + connection graph), review actions."),
    ("3", "python backend/run_api.py", "The API + interactive docs at /api/v1/docs; log in as synthetic analyst / compliance / auditor; ranked queue, alert detail, EDD verdict, regulator reports."),
    ("4", "make up  (full platform)", "The whole ~26-service stack — Kafka, ClickHouse, Redis, Postgres, MinIO, serving, dashboards, monitoring — up together."),
    ("5", "Replay Studio", "Inject a scripted scenario — e.g. \"after-hours bulk export by a treasury RM\" — and watch it drive the live event tape and fire alerts."),
]
sy = 3.5
for n_, cmd, desc in steps:
    rect(s, ML, sy, CW, 1.22, fill=PANEL, line=LINE, line_w=1.0, rounded=True)
    chip(s, ML + 0.2, sy + 0.36, 0.5, 0.5, n_, fill=RED, size=18, font=DISP)
    txt(s, ML + 0.95, sy + 0.12, 4.6, 1.0, cmd, size=15, color=INK, bold=True, font=MONO, anchor=MSO_ANCHOR.MIDDLE)
    txt(s, ML + 5.8, sy + 0.12, CW - 6.0, 1.0, desc, size=13.5, color=DIM, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
    sy += 1.36


# PAGE 15 — UX & workflow
s = new_slide("Solution Execution & Demo (15%) · User Experience & Workflow",
              "Investigator console (L7): triage → investigate → decide → learn")
wf = ["Alert fires (ranked)", "Investigate (SHAP + graph)", "Decide (EDD verdict)", "Learn (verdict → label)"]
wx = ML
seg_w = (CW - 3 * 0.55) / 4
for i, step in enumerate(wf):
    rect(s, wx, 3.5, seg_w, 0.85, fill=PANEL2, line=RED, line_w=1.2, rounded=True)
    txt(s, wx + 0.1, 3.5, seg_w - 0.2, 0.85, step, size=14, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if i < 3:
        arrow(s, wx + seg_w + 0.08, 3.77, 0.4, 0.32, color=RED)
    wx += seg_w + 0.55
card(s, ML, 4.7, 8.95, 5.6, "WHAT THE INVESTIGATOR SEES", [
    {"t": "Ranked triage queue — one alert per entity, severity-colored, sortable/filterable, bulk-select, RBAC-gated actions.", "size": 13.5, "bullet": "▸"},
    {"t": "Entity-360 timeline — the user's history, score-over-time, and a 7×24 off-hours heatmap.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Explanation panel — SHAP contributions + rule provenance + the AI narrative + a Cytoscape connection graph (expand / find-path).", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "EDD disposition — the investigator's verdict (fraud / false-positive / inconclusive) that teaches the system.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Masked PII by default; RBAC-gated, audited unmask.", "size": 13.5, "bullet": "▸", "before": 7},
], accent=INK)
card(s, ML + 9.3, 4.7, 8.6, 5.6, "A TERMINAL, NOT A DASHBOARD", [
    {"t": "Bloomberg-terminal aesthetic — live status bar (clock + service health + EPS), streaming event tape, score gauges, tokenized severity everywhere.", "size": 13.5, "bullet": "▸"},
    {"t": "Never-empty demo states + a first-run onboarding overlay + one \"load demo scenario\" button — legible to a 60-second evaluator.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "Five roles with capability gating; contract + Playwright e2e tests keep the UX honest against the API.", "size": 13.5, "bullet": "▸", "before": 7},
    {"t": "82 React components (Radix + CVA), built to grade — correctness first, terminal soul on top.", "size": 13.5, "bullet": "▸", "before": 7, "color": RED},
], accent=RED)


# ════════════════════════════════════════════════════════════════════════════
# PILLAR 5 — COMMERCIALIZATION & STARTUP POTENTIAL (10%)
# ════════════════════════════════════════════════════════════════════════════

# PAGE 16 — Business viability & market sizing (TAM / SAM / SOM)
s = new_slide("Commercialization & Startup Potential (10%) · Business Viability & Market",
              "Viable, with a real wedge — a market pulled by regulation")
card(s, ML, 3.5, 8.95, 6.8, "THE PROBLEM IS HUGE, GROWING & POORLY SERVED", [
    {"t": "₹36,014 Cr (~$4.2 B) of bank fraud reported in FY25 — up 194% YoY; PSBs alone = ₹25,667 Cr (RBI Annual Report 2024-25).", "size": 14, "bullet": "▸"},
    {"t": "Insider fraud runs a median ~12 months before detection; 43% is caught by TIPS not systems; banking is the largest sector studied (ACFE 2024).", "size": 14, "bullet": "▸", "before": 9},
    {"t": "Proactive data-monitoring is one of only FOUR controls tied to a ≥50% cut in BOTH loss and duration — that is the value thesis in one line.", "size": 14, "bullet": "▸", "before": 9, "bold": True, "color": GREEN},
    {"t": "Today's tools are transaction-fraud / AML engines — the insider & privileged-user surface is acute pain, poorly served.", "size": 14, "bullet": "▸", "before": 9, "color": RED},
], accent=BLUE)
card(s, ML + 9.3, 3.5, 8.6, 6.8, "MARKET SIZING  (TAM / SAM / SOM)", [
    {"t": "global fraud detection & prevention ~$32.8 B (2024) → $65.68 B (2030). Purest-fit insider-threat detection $0.42 B → $1.81 B @ 27.9% CAGR.", "size": 13.5, "bullet": "TAM", "font": MONO, "bold": True},
    {"t": "India fraud-detection $1.28 B → $3.89 B @ 20.9% CAGR; realistic BFSI-insider subset ~$0.35–0.55 B → $1.0–1.3 B.", "size": 13.5, "bullet": "SAM", "font": MONO, "bold": True, "before": 9},
    {"t": "bottom-up ₹1.2 Cr ARR (Yr 1) → ₹50 Cr (~$6 M) ARR / 50 customers by Yr 5 = <3% of just the ~150–200 large-bank segment (deliberately conservative).", "size": 13.5, "bullet": "SOM", "font": MONO, "bold": True, "before": 9},
    {"t": "Sources in the business-viability file — RBI AR 2024-25, ACFE 2024, market-research CAGRs, Carta 2024 fintech medians.", "size": 11.5, "italic": True, "color": FAINT, "before": 10},
], accent=RED)


# PAGE 17 — Competition & the defensible wedge
s = new_slide("Commercialization & Startup Potential (10%) · Competition & Defensibility",
              "A challenger with a defensible wedge incumbents don't serve")
card(s, ML, 3.5, 8.95, 6.8, "INCUMBENTS  (strong on transaction-fraud / AML)", [
    {"t": "Feedzai — ~$2 B unicorn.", "size": 14, "bullet": "•"},
    {"t": "Featurespace — acquired by Visa (Dec 2024, ~$925 M).", "size": 14, "bullet": "•", "before": 8},
    {"t": "NICE Actimize — established market leader.", "size": 14, "bullet": "•", "before": 8},
    {"t": "All strong on transaction fraud & AML — but NONE is built for on-prem, India-sovereign, insider-focused, alert-only, CRILC / FMR-native detection.", "size": 14, "bullet": "▸", "before": 10, "bold": True, "color": RED},
    {"t": "That seam is our defensibility.", "size": 14, "italic": True, "color": INK, "before": 8},
], accent=INK)
card(s, ML + 9.3, 3.5, 8.6, 6.8, "OUR WEDGE + UNIT ECONOMICS", [
    {"t": "Wedge: on-prem + RBI / DPDP-native + insider-focus + alert-only + explainable — precisely the seam the incumbents leave open.", "size": 14, "bullet": "▸", "bold": True},
    {"t": "~57% steady-state per-customer gross margin (trending 70–80% at scale).", "size": 14, "bullet": "✓", "color": GREEN, "before": 9},
    {"t": "~8× customer ROI (₹8 Cr value vs ~₹1 Cr cost) — conservative; survives halving every driver.", "size": 14, "bullet": "✓", "color": GREEN, "before": 9},
    {"t": "Pricing ₹10 L – ₹3 Cr/yr by tier — ~30–60% under the incumbents.", "size": 14, "bullet": "✓", "color": GREEN, "before": 9},
], accent=RED)


# PAGE 18 — Go-to-market, traction ramp & the ask
s = new_slide("Commercialization & Startup Potential (10%) · Go-To-Market & The Ask",
              "Pilot-ready, phased, honest — and fundable")
card(s, ML, 3.5, 8.95, 6.8, "GO-TO-MARKET & TRACTION RAMP", [
    {"t": "Land-and-expand: on-prem pilot on synthetic data (zero real-data risk) → the highest-risk privileged surface → entitlements, collusion, slow-lane EWS.", "size": 14, "bullet": "▸"},
    {"t": "Connectors are SCAFFOLD that swap to real feeds on credentials — same pattern across CBS / SWIFT / PAM / IGA / HR.", "size": 14, "bullet": "▸", "before": 8},
    {"t": "SOM ramp:  ₹1.2 Cr ARR (Yr 1)  →  ₹5 Cr ARR / ~9 banks (Series-A trigger)  →  ₹50 Cr (~$6 M) / 50 customers (Yr 5).", "size": 14, "bullet": "▸", "before": 8, "bold": True, "color": GREEN},
    {"t": "Honest & alert-only → low adoption risk; complements audit / SoD / culture, never replaces them.", "size": 13.5, "italic": True, "color": DIM, "before": 8},
], accent=RED)
card(s, ML + 9.3, 3.5, 8.6, 6.8, "THE ASK", [
    {"t": "Immediate seed: ₹10 Cr for ~18% at ~₹55 Cr post-money.", "size": 15, "bullet": "▸", "bold": True, "color": INK},
    {"t": "(benchmarked to Carta 2024 fintech medians)", "size": 12.5, "italic": True, "color": DIM, "before": 2},
    {"t": "Use of funds → ₹5 Cr ARR / ~9 paying banks → Series A.", "size": 14, "bullet": "▸", "before": 10},
    {"t": "Why now: RBI Fraud-Risk 2024 + FREE-AI + IS-Audit make insider controls mandatory — and the on-prem / India-sovereign / insider seam is wide open.", "size": 14, "bullet": "▸", "before": 9, "color": RED},
], accent=GREEN)


# CLOSING — PAGE 19 — Team + thank you
s = new_slide("Team & Deliverables", "Team NINEAGENTS — thank you")
members = [
    ("Dhruv Agrawal", "ML / Backend Lead", "Detection layers, fusion, MLOps, backend & platform integration"),
    ("Tanishq Vyas", "Frontend / UX", "Investigator console — triage, entity-360, explanation & graph"),
    ("Hanzala Saify", "Infra / DevOps", "~26-service stack, k8s/ArgoCD/Terraform, security, observability"),
    ("Aditya Dubey", "Domain Research", "RBI Fraud-Risk / FREE-AI mapping, detection-coverage, honest limits"),
]
cw4 = 4.3
for i, (name, role, blurb) in enumerate(members):
    cx = ML + i * (cw4 + 0.43)
    rect(s, cx, 3.5, cw4, 3.5, fill=WHITE, line=LINE, line_w=1.25, rounded=True)
    circ = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx + cw4 / 2 - 0.6), Inches(3.8), Inches(1.2), Inches(1.2))
    circ.fill.solid(); circ.fill.fore_color.rgb = RED; circ.line.fill.background(); circ.shadow.inherit = False
    tf = circ.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = name[0]; r.font.name = DISP; r.font.size = Pt(38); r.font.bold = True; r.font.color.rgb = WHITE
    txt(s, cx + 0.2, 5.2, cw4 - 0.4, 0.5, name, size=17, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
    txt(s, cx + 0.2, 5.7, cw4 - 0.4, 0.4, role, size=12.5, color=RED, bold=True, font=MONO, align=PP_ALIGN.CENTER)
    txt(s, cx + 0.25, 6.15, cw4 - 0.5, 0.8, blurb, size=12, color=DIM, font=BODY, align=PP_ALIGN.CENTER)

rect(s, ML, 7.4, CW, 2.9, fill=PANEL2, line=RED, line_w=1.2, rounded=True)
txt(s, ML, 7.65, CW, 0.9, "HAWK-EYE", size=54, color=RED, bold=True, font=DISP, align=PP_ALIGN.CENTER)
txt(s, ML, 8.7, CW, 0.5, "Real-Time Insider & Privileged-User Fraud Detection  ·  Alert-only · Explainable · RBI-compliant · On-prem",
    size=17, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
txt(s, ML, 9.35, CW, 0.5, "github.com/dhruvagrawal27/hawk-eye     ·     read GETTING_STARTED.md · docs/detection-coverage-map.md · docs/honest-limits.md",
    size=14, color=RED, bold=True, font=MONO, align=PP_ALIGN.CENTER)


# ── Footer pass ─────────────────────────────────────────────────────────────
total = len(CONTENT)
for i, s in enumerate(CONTENT, start=1):
    txt(s, ML, 10.78, 13.0, 0.35,
        "HAWK-EYE  ·  Team NINEAGENTS  ·  iDEA 2.0 · PSBs Hackathon Series 2026",
        size=10, color=FAINT, italic=True, font=MONO)
    txt(s, PW - 2.5, 10.78, 1.8, 0.35, f"{i} / {total}", size=10, color=FAINT, font=MONO, align=PP_ALIGN.RIGHT)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB, {len(prs.slides)} slides)")
