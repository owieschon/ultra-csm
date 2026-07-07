from __future__ import annotations

import html
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).parent

TOKENS = {
    "canvas": "#222321",
    "chrome": "#1B1C1A",
    "card": "#2A2B28",
    "card_2": "#33342F",
    "hair": "#3A3B37",
    "hair_soft": "#30312E",
    "fg": "#F1F0EC",
    "fg_2": "#B7B5AC",
    "fg_3": "#858379",
    "accent": "#8189E6",
    "ok": "#5DBE93",
    "warn": "#D9A452",
    "danger": "#E67B80",
}

FONT = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(MONO if mono else FONT, size=size)


def wrap(value: str, width: int) -> list[str]:
    lines: list[str] = []
    for part in value.split("\n"):
        lines.extend(textwrap.wrap(part, width=width) or [""])
    return lines


def text(draw: ImageDraw.ImageDraw, xy, value, size=20, fill=TOKENS["fg"], mono=False):
    draw.text(xy, value, font=font(size, mono=mono), fill=fill)


def paragraph(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, size=17, fill=TOKENS["fg_2"], chars=68, leading=8):
    for line in wrap(value, chars):
        text(draw, (x, y), line, size, fill)
        y += size + leading
    return y


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=TOKENS["hair"], radius=12, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def chip(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, outline=TOKENS["hair"], fg=TOKENS["fg_2"]):
    f = font(16)
    bbox = draw.textbbox((0, 0), value, font=f)
    w = bbox[2] - bbox[0] + 24
    h = bbox[3] - bbox[1] + 12
    rounded(draw, (x, y, x + w, y + h), TOKENS["canvas"], outline, 7)
    draw.text((x + 12, y + 5), value, font=f, fill=fg)
    return x + w + 8


def work_queue(draw: ImageDraw.ImageDraw, selected: str):
    rounded(draw, (36, 70, 350, 824), TOKENS["chrome"], TOKENS["hair"], 14)
    text(draw, (58, 96), "Agent work queue", 21)
    text(draw, (58, 127), "drafted work, waiting for owner", 15, TOKENS["fg_2"])
    rows = [
        ("sales-handoff", "Harborview Fleet", "sales handoff", "approval"),
        ("route", "Pinehill Transport", "route to enablement", "review"),
        ("packet", "Ironhorse Freight Co", "CSM action packet", "approval"),
        ("evidence", "Trailhead Logistics", "evidence receipt", "ready"),
        ("audit", "Meridian Fleet Group", "post-action audit", "logged"),
    ]
    y = 170
    for key, account, motion, state in rows:
        is_selected = key == selected
        rounded(
            draw,
            (58, y, 328, y + 72),
            TOKENS["card"] if is_selected else TOKENS["chrome"],
            TOKENS["accent"] if is_selected else TOKENS["hair_soft"],
            9,
            2 if is_selected else 1,
        )
        text(draw, (74, y + 13), account, 17)
        text(draw, (74, y + 38), motion, 14, TOKENS["fg_2"])
        text(draw, (248, y + 38), state, 13, TOKENS["warn" if state in {"approval", "review"} else "ok"])
        y += 84


def shell(draw: ImageDraw.ImageDraw, title: str, subtitle: str, selected: str):
    img = draw.im
    work_queue(draw, selected)
    rounded(draw, (382, 70, 1404, 824), TOKENS["chrome"], TOKENS["hair"], 16)
    text(draw, (414, 104), title, 31)
    paragraph(draw, 414, 145, subtitle, 18, TOKENS["fg_2"], chars=95)
    return img


def evidence_list(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[tuple[str, str]]):
    for label, body in items:
        rounded(draw, (x, y, x + 438, y + 70), TOKENS["card"], TOKENS["hair"], 9)
        text(draw, (x + 16, y + 12), label, 16, TOKENS["fg"])
        paragraph(draw, x + 16, y + 36, body, 13, TOKENS["fg_2"], chars=54, leading=4)
        y += 82


def render_agent_run_queue():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    shell(d, "Agent run queue", "The first screen is not a dashboard. It is the list of customer-success work the agents already prepared for the CSM to approve, edit, route, or reject.", "packet")
    rounded(d, (414, 220, 1368, 394), TOKENS["card"], TOKENS["accent"], 14, 2)
    text(d, (442, 248), "Ironhorse Freight Co", 22)
    text(d, (442, 286), "Agent-drafted CSM action packet", 34)
    paragraph(d, 442, 333, "Schedule a technical working session with Marcus and Lisa to unblock GPS hardware compatibility before rollout stalls.", 17, chars=92)
    rounded(d, (414, 430, 830, 742), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (442, 458), "Owner controls", 20)
    for i, label in enumerate(["Approve send", "Edit draft", "Route to engineering", "Reject with reason"]):
        y = 506 + i * 48
        rounded(d, (442, y, 770, y + 36), TOKENS["canvas"], TOKENS["hair"], 8)
        text(d, (460, y + 8), label, 16, TOKENS["fg"] if i == 0 else TOKENS["fg_2"])
    evidence_list(d, 870, 430, [("Case", "GPS hardware compatibility issue with older vehicles."), ("Usage", "104 daily active assets observed in the day-140 snapshot."), ("Success plan", "Driver onboarding remains an active rollout objective.")])
    img.save(OUT / "01_agent_run_queue.png")


def render_action_packet():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    shell(d, "Action packet", "The account detail becomes a single proposed piece of work: what to do, why now, evidence used, draft text, and the approval gate.", "packet")
    rounded(d, (414, 220, 1368, 740), TOKENS["card"], TOKENS["hair"], 14)
    text(d, (446, 250), "CSM action packet", 20, TOKENS["fg_2"])
    paragraph(d, 446, 288, "Ask Marcus and Lisa to join a hardware-compatibility working session before the rollout slips.", 34, TOKENS["fg"], chars=58, leading=8)
    x = 446
    y = 404
    x = chip(d, x, y, "human approval required", TOKENS["warn"], TOKENS["warn"])
    x = chip(d, x, y, "customer-facing draft")
    chip(d, x, y, "evidence attached")
    rounded(d, (446, 466, 846, 674), TOKENS["canvas"], TOKENS["hair"], 10)
    text(d, (470, 492), "Draft", 20)
    paragraph(d, 470, 530, "Marcus, Lisa — I want to get ahead of the GPS hardware compatibility issue before driver onboarding slows down. Can we book 30 minutes this week with the fleet and IT owners?", 16, chars=44)
    evidence_list(d, 884, 466, [("Evidence 1", "Open case: GPS hardware compatibility issue, Medium priority."), ("Evidence 2", "Active objective: complete driver onboarding by 2026-07-15.")])
    img.save(OUT / "02_action_packet.png")


def render_route_decision():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    shell(d, "Route decision", "This version foregrounds the agent's classification work: CSM action, engineering escalation, product feedback, sales handoff, or abstain.", "route")
    rounded(d, (414, 220, 1368, 380), TOKENS["card"], TOKENS["accent"], 14, 2)
    text(d, (442, 250), "Pinehill Transport", 22)
    text(d, (442, 288), "Route to enablement, not product or engineering", 32)
    paragraph(d, 442, 335, "Training drift is the live signal; no defect or missing capability is evidenced strongly enough to route elsewhere.", 17, chars=94)
    lanes = [("CSM", "selected", TOKENS["accent"]), ("Engineering", "not supported", TOKENS["fg_3"]), ("Product", "not supported", TOKENS["fg_3"]), ("Sales", "not needed", TOKENS["fg_3"])]
    x = 414
    for label, status, color in lanes:
        rounded(d, (x, 430, x + 220, 558), TOKENS["card"], color, 12, 2 if status == "selected" else 1)
        text(d, (x + 22, 456), label, 24)
        text(d, (x + 22, 496), status, 16, color)
        x += 244
    evidence_list(d, 414, 610, [("Required evidence", "Recent training/adoption drift and account usage context."), ("Forbidden motions", "Do not call this a product gap without feature-request evidence."), ("Mode", "Deterministic route; abstain remains available when evidence is thin.")])
    img.save(OUT / "03_route_decision.png")


def render_sales_handoff():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    shell(d, "Sales handoff packet", "Sales appears as an output packet, not a relationship-intelligence surface: renewal risk, account facts, customer pain, suggested seller motion, and approval status.", "sales-handoff")
    rounded(d, (414, 220, 1368, 412), TOKENS["card"], TOKENS["danger"], 14, 2)
    text(d, (442, 250), "Harborview Fleet", 22)
    paragraph(d, 442, 290, "Prepare a renewal-risk handoff: ERP integration is blocking value realization and two high-priority cases are open.", 31, TOKENS["fg"], chars=67)
    rounded(d, (414, 458, 820, 720), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (442, 486), "Handoff contents", 20)
    for i, item in enumerate(["Renewal risk summary", "Open-case evidence", "Customer pain in plain language", "Suggested AE/CSM next step"]):
        text(d, (462, 536 + i * 42), f"{i + 1}. {item}", 17, TOKENS["fg_2"])
    rounded(d, (866, 458, 1368, 720), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (894, 486), "Governance", 20)
    paragraph(d, 894, 526, "The agent can draft the handoff and attach evidence. It cannot send to Sales, the customer, or CRM until the CSM approves.", 18, TOKENS["fg_2"], chars=53)
    chip(d, 894, 648, "approval required", TOKENS["warn"], TOKENS["warn"])
    img.save(OUT / "04_sales_handoff_packet.png")


def render_audit_trail():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    shell(d, "Approval audit trail", "The human anchor can be the ledger: what the agents saw, what they drafted, what the CSM changed, and what was actually released.", "audit")
    steps = [
        ("1", "Agent assembled packet", "Used renewal opportunity, open cases, usage, and comms evidence."),
        ("2", "CSM edited draft", "Changed tone and removed an unsupported product claim."),
        ("3", "Approval gate passed", "Owner approved customer-facing send."),
        ("4", "Released action logged", "Audit record preserves source IDs and final text."),
    ]
    y = 228
    for number, title, body in steps:
        rounded(d, (414, y, 1368, y + 104), TOKENS["card"], TOKENS["hair"], 12)
        draw_color = TOKENS["ok"] if number in {"3", "4"} else TOKENS["accent"]
        d.ellipse((442, y + 28, 490, y + 76), fill=TOKENS["canvas"], outline=draw_color, width=2)
        text(d, (459, y + 39), number, 20, draw_color, mono=True)
        text(d, (520, y + 24), title, 24)
        paragraph(d, 520, y + 60, body, 16, TOKENS["fg_2"], chars=88)
        y += 124
    img.save(OUT / "05_approval_audit_trail.png")


HTML_CSS = """
:root, [data-theme="dark"] {
  --canvas: #222321; --chrome: #1B1C1A; --card: #2A2B28; --card-2: #33342F;
  --hair: rgba(255,255,255,.09); --hair-soft: rgba(255,255,255,.05);
  --fg: #F1F0EC; --fg-2: #B7B5AC; --fg-3: #858379;
  --accent: #8189E6; --accent-fg: #fff; --accent-line: rgba(129,137,230,.45);
  --ok: #5DBE93; --warn: #D9A452; --danger: #E67B80;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--canvas); color: var(--fg); font-family: -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif; font-size: 13.5px; line-height: 1.5; }
.mock { min-height: 100vh; padding: 26px; display: grid; grid-template-columns: 324px 1fr; gap: 22px; }
.queue, .detail, .card { background: var(--chrome); border: 1px solid var(--hair); border-radius: 12px; }
.queue { padding: 14px; }
h1, h2, h3 { margin: 0; font-weight: 650; }
.muted { color: var(--fg-2); }
.row { padding: 11px 12px; border: 1px solid var(--hair-soft); border-radius: 9px; margin-top: 8px; background: transparent; }
.row.sel { background: var(--card); border-color: var(--accent-line); }
.row strong { display: block; font-size: 13px; }
.state { float: right; color: var(--warn); }
.detail { padding: 28px; }
.hero { border: 1px solid var(--accent-line); background: var(--card); border-radius: 12px; padding: 24px; margin: 22px 0; }
.hero.danger { border-color: rgba(230,123,128,.6); }
.hero h2 { font-size: 30px; line-height: 1.2; max-width: 980px; }
.section { margin-top: 18px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.card { padding: 18px; background: var(--card); }
.chip { display: inline-flex; align-items: center; border: 1px solid var(--hair); border-radius: 6px; padding: 2px 8px; color: var(--fg-2); font-size: 11px; margin: 0 6px 6px 0; white-space: nowrap; }
.warn { color: var(--warn); border-color: rgba(217,164,82,.45); }
.danger { color: var(--danger); border-color: rgba(230,123,128,.5); }
.button { border: 1px solid var(--hair); border-radius: 8px; padding: 9px 11px; margin: 8px 0; background: var(--canvas); }
.route { border: 1px solid var(--hair); border-radius: 10px; padding: 18px; }
.route.on { border-color: var(--accent-line); }
.timeline { display: grid; gap: 14px; margin-top: 22px; }
.step { display: grid; grid-template-columns: 42px 1fr; gap: 14px; align-items: start; }
.num { width: 34px; height: 34px; border: 1px solid var(--accent-line); border-radius: 50%; display: grid; place-items: center; font-family: ui-monospace, "SF Mono", Menlo, monospace; color: var(--accent); }
.proposal-note { margin-top: 18px; color: var(--fg-2); font-size: 12px; }
"""


QUEUE = """
<aside class="queue">
  <h2>Agent work queue</h2>
  <p class="muted">drafted work, waiting for owner</p>
  <div class="row {sales}"><span class="state">approval</span><strong>Harborview Fleet</strong><span class="muted">sales handoff</span></div>
  <div class="row {route}"><span class="state">review</span><strong>Pinehill Transport</strong><span class="muted">route to enablement</span></div>
  <div class="row {packet}"><span class="state">approval</span><strong>Ironhorse Freight Co</strong><span class="muted">CSM action packet</span></div>
  <div class="row {evidence}"><span class="state">ready</span><strong>Trailhead Logistics</strong><span class="muted">evidence receipt</span></div>
  <div class="row {audit}"><span class="state">logged</span><strong>Meridian Fleet Group</strong><span class="muted">post-action audit</span></div>
</aside>
"""


def page(title: str, selected: str, body: str) -> str:
    queue = QUEUE.format(
        sales="sel" if selected == "sales" else "",
        route="sel" if selected == "route" else "",
        packet="sel" if selected == "packet" else "",
        evidence="sel" if selected == "evidence" else "",
        audit="sel" if selected == "audit" else "",
    )
    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)}</title><style>{HTML_CSS}</style></head>
<body><main class="mock">{queue}<section class="detail">{body}</section></main></body></html>
"""


def write_html():
    pages = {
        "01_agent_run_queue.html": page(
            "Agent run queue",
            "packet",
            """
<h1>Agent run queue</h1><p class="muted">Not a dashboard: a work surface for customer-success actions already prepared by agents.</p>
<div class="hero"><p class="muted">Ironhorse Freight Co</p><h2>Schedule a technical working session with Marcus and Lisa before rollout stalls.</h2><span class="chip warn">human approval required</span><span class="chip">evidence attached</span></div>
<div class="section"><div class="card"><h3>Owner controls</h3><div class="button">Approve send</div><div class="button">Edit draft</div><div class="button">Route to engineering</div><div class="button">Reject with reason</div></div><div class="card"><h3>Evidence</h3><p>Open GPS hardware case, 104 active assets, active driver-onboarding objective.</p></div></div>
<p class="proposal-note">Hypothesis: show agents scaling the CSM function by preparing work, while the human remains the release authority.</p>
""",
        ),
        "02_action_packet.html": page(
            "Action packet",
            "packet",
            """
<h1>Action packet</h1><p class="muted">One proposed piece of work: what to do, why now, the draft, evidence, and the approval state.</p>
<div class="hero"><h2>Ask Marcus and Lisa to join a hardware-compatibility working session before the rollout slips.</h2><span class="chip warn">approval required</span><span class="chip">customer-facing draft</span></div>
<div class="section"><div class="card"><h3>Draft</h3><p>Marcus, Lisa — I want to get ahead of the GPS hardware compatibility issue before driver onboarding slows down. Can we book 30 minutes this week?</p></div><div class="card"><h3>Receipts</h3><p>Case: GPS hardware compatibility. Success plan: driver onboarding target. Usage: 104 active assets.</p></div></div>
<p class="proposal-note">Hypothesis: the product is strongest when each agent output is inspectable and approvable as a packet.</p>
""",
        ),
        "03_route_decision.html": page(
            "Route decision",
            "route",
            """
<h1>Route decision</h1><p class="muted">Foreground classification: CSM action, engineering escalation, product feedback, sales handoff, or abstain.</p>
<div class="hero"><p class="muted">Pinehill Transport</p><h2>Route to enablement, not product or engineering.</h2><p class="muted">Training drift is evidenced; no defect or missing capability is strong enough to route elsewhere.</p></div>
<div class="section"><div class="route on"><h3>CSM</h3><p>selected</p></div><div class="route"><h3>Engineering</h3><p class="muted">not supported</p></div><div class="route"><h3>Product</h3><p class="muted">not supported</p></div><div class="route"><h3>Sales</h3><p class="muted">not needed</p></div></div>
<p class="proposal-note">Hypothesis: routing is a differentiator; make the decision spine visible instead of making another account view.</p>
""",
        ),
        "04_sales_handoff_packet.html": page(
            "Sales handoff packet",
            "sales",
            """
<h1>Sales handoff packet</h1><p class="muted">Sales handoff is an output packet, not a relationship-intelligence module.</p>
<div class="hero danger"><p class="muted">Harborview Fleet</p><h2>Prepare a renewal-risk handoff: ERP integration is blocking value realization and two high-priority cases are open.</h2></div>
<div class="section"><div class="card"><h3>Handoff contents</h3><p>Renewal risk summary, open-case evidence, customer pain, suggested AE/CSM next step.</p></div><div class="card"><h3>Governance</h3><p>The agent can draft and attach evidence. It cannot send to Sales, the customer, or CRM until the CSM approves.</p><span class="chip warn">approval required</span></div></div>
<p class="proposal-note">Hypothesis: sales handoff belongs as a governed artifact emitted by CSM agents.</p>
""",
        ),
        "05_approval_audit_trail.html": page(
            "Approval audit trail",
            "audit",
            """
<h1>Approval audit trail</h1><p class="muted">Human anchor as ledger: what agents saw, drafted, what the CSM changed, and what actually released.</p>
<div class="timeline">
<div class="card step"><div class="num">1</div><div><h3>Agent assembled packet</h3><p class="muted">Used renewal opportunity, open cases, usage, and comms evidence.</p></div></div>
<div class="card step"><div class="num">2</div><div><h3>CSM edited draft</h3><p class="muted">Changed tone and removed an unsupported product claim.</p></div></div>
<div class="card step"><div class="num">3</div><div><h3>Approval gate passed</h3><p class="muted">Owner approved customer-facing send.</p></div></div>
<div class="card step"><div class="num">4</div><div><h3>Released action logged</h3><p class="muted">Audit record preserves source IDs and final text.</p></div></div>
</div>
<p class="proposal-note">Hypothesis: the trust story lands when the UI shows the agent/human boundary as history, not boilerplate.</p>
""",
        ),
    }
    for filename, body in pages.items():
        (OUT / filename).write_text(body, encoding="utf-8")
    items = []
    for filename in pages:
        png = filename.replace(".html", ".png")
        label = filename.removesuffix(".html").replace("_", " ")
        items.append(f'<li><a href="{filename}">{html.escape(label)}</a> <a href="{png}">(png)</a></li>')
    (OUT / "index.html").write_text(
        f"""<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8" /><title>F4 proposals</title><style>{HTML_CSS} body{{padding:28px}} .mock{{display:block;min-height:auto}} li{{margin:10px 0;font-size:18px}} a{{color:var(--accent)}} </style></head><body>
<h1>F4 human-anchor proposals</h1>
<p class="muted">Revised to avoid relationship-intelligence/product-map territory. These proposals foreground agent-generated CSM work, evidence, routing, handoff packets, and human approval.</p>
<ol>{''.join(items)}</ol>
</body></html>""",
        encoding="utf-8",
    )


def contact_sheet():
    names = [
        ("01_agent_run_queue", "agent run queue"),
        ("02_action_packet", "action packet"),
        ("03_route_decision", "route decision"),
        ("04_sales_handoff_packet", "sales handoff packet"),
        ("05_approval_audit_trail", "approval audit trail"),
    ]
    thumbs = [Image.open(OUT / f"{name}.png").resize((640, 400)) for name, _ in names]
    img = Image.new("RGB", (1360, 1500), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    text(d, (36, 28), "F4 proposal series: agent work, not relationship intelligence", 32)
    paragraph(d, 36, 74, "Revised after Centralize check. These boards avoid relationship maps, warm paths, and stakeholder-intelligence as the primary product.", 18, TOKENS["fg_2"], chars=120)
    positions = [(36, 130), (684, 130), (36, 570), (684, 570), (36, 1010)]
    for idx, ((_, label), thumb, pos) in enumerate(zip(names, thumbs, positions), start=1):
        x, y = pos
        rounded(d, (x - 1, y - 1, x + 641, y + 401), TOKENS["chrome"], TOKENS["hair"], 12)
        img.paste(thumb, (x, y))
        text(d, (x + 12, y + 410), f"{idx}. {label}", 20)
    img.save(OUT / "contact-sheet.png")


def main():
    stale = [
        "01_csm_presence",
        "02_relationship_map",
        "03_relationship_health_overlay",
        "04_people_first_hierarchy",
        "05_who_why_header",
    ]
    for stem in stale:
        for suffix in (".html", ".png"):
            path = OUT / f"{stem}{suffix}"
            if path.exists():
                path.unlink()
    render_agent_run_queue()
    render_action_packet()
    render_route_decision()
    render_sales_handoff()
    render_audit_trail()
    write_html()
    contact_sheet()


if __name__ == "__main__":
    main()
