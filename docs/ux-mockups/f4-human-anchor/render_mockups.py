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
    "amber": "#D9A452",
}

FONT = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(MONO if mono else FONT, size=size)


def wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for part in text.split("\n"):
        lines.extend(textwrap.wrap(part, width=width) or [""])
    return lines


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=TOKENS["hair"], radius=12, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, xy, value, size=20, fill=TOKENS["fg"], mono=False):
    draw.text(xy, value, fill=fill, font=font(size, mono=mono))


def paragraph(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, size=18, fill=TOKENS["fg_2"], chars=72, leading=8):
    line_h = size + leading
    for line in wrap(value, chars):
        text(draw, (x, y), line, size, fill)
        y += line_h
    return y


def chip(draw: ImageDraw.ImageDraw, x, y, value, fill=None, outline=TOKENS["hair"], fg=TOKENS["fg_2"]):
    f = font(16)
    pad_x = 12
    pad_y = 6
    box = draw.textbbox((0, 0), value, font=f)
    w = box[2] - box[0] + pad_x * 2
    h = box[3] - box[1] + pad_y * 2
    rounded(draw, (x, y, x + w, y + h), fill or TOKENS["canvas"], outline, radius=7)
    draw.text((x + pad_x, y + pad_y - 1), value, font=f, fill=fg)
    return x + w + 8


def card_title(draw, x, y, title, kicker=None):
    if kicker:
        text(draw, (x, y), kicker.upper(), 15, TOKENS["fg_2"])
        y += 24
    text(draw, (x, y), title, 27, TOKENS["fg"])
    return y + 40


def queue_list(draw, x, y, w, selected="Trailhead Logistics"):
    accounts = [
        ("Harborview Fleet", "renewal risk", "35"),
        ("Trailhead Logistics", "champion active", "90"),
        ("Ironhorse Freight Co", "hardware blocker", "74"),
        ("Pinehill Transport", "training drift", "69"),
        ("Quarry Stone Logistics", "silent account", "52"),
    ]
    rounded(draw, (x, y, x + w, y + 430), TOKENS["chrome"], TOKENS["hair"], 14)
    text(draw, (x + 18, y + 18), "Queue", 19)
    text(draw, (x + 18, y + 45), "human-reviewed actions", 15, TOKENS["fg_2"])
    yy = y + 82
    for name, reason, score in accounts:
        sel = name == selected
        fill = TOKENS["card"] if sel else TOKENS["chrome"]
        outline = TOKENS["accent"] if sel else TOKENS["hair_soft"]
        rounded(draw, (x + 12, yy, x + w - 12, yy + 62), fill, outline, 10, width=2 if sel else 1)
        text(draw, (x + 26, yy + 13), name, 17, TOKENS["fg"])
        text(draw, (x + 26, yy + 37), reason, 14, TOKENS["fg_2"])
        text(draw, (x + w - 58, yy + 21), score, 20, TOKENS["fg"], mono=True)
        yy += 72


def factor_stack(draw, x, y, w, factors=None):
    factors = factors or [
        ("Usage adoption", "+18", "155 active assets"),
        ("Champion engagement", "+14", "Vanessa replied today"),
        ("Single-threading risk", "-8", "Mike quiet 85 days"),
        ("Outcome evidence", "0", "no terminal renewal yet"),
    ]
    for label, value, proof in factors:
        rounded(draw, (x, y, x + w, y + 54), TOKENS["card"], TOKENS["hair"], 8)
        text(draw, (x + 14, y + 12), label, 17)
        text(draw, (x + w - 70, y + 11), value, 18, TOKENS["fg"], mono=True)
        text(draw, (x + 14, y + 34), proof, 13, TOKENS["fg_2"])
        y += 64


def stakeholder_stack(draw, x, y, w, people):
    for name, role, state, color in people:
        rounded(draw, (x, y, x + w, y + 58), TOKENS["card"], TOKENS["hair"], 9)
        draw.ellipse((x + 14, y + 15, x + 42, y + 43), fill=TOKENS["card_2"], outline=TOKENS["hair"])
        text(draw, (x + 22, y + 19), name[:1], 17)
        text(draw, (x + 54, y + 11), name, 17)
        text(draw, (x + 54, y + 34), role, 13, TOKENS["fg_2"])
        chip(draw, x + w - 145, y + 16, state, outline=color, fg=color)
        y += 68


def render_csm_presence():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    text(d, (36, 24), "Ultra CSM", 24)
    chip(d, 178, 22, "Day 140")
    chip(d, 266, 22, "Maya Chen")
    text(d, (1050, 29), "Approval gate: required", 16, TOKENS["warn"])
    queue_list(d, 36, 90, 330)
    rounded(d, (396, 90, 1404, 826), TOKENS["chrome"], TOKENS["hair"], 16)
    text(d, (426, 120), "Your book, Maya", 30)
    text(d, (426, 158), "The agents have drafted 7 customer moves. You are approving the work, not hunting for it.", 18, TOKENS["fg_2"])
    rounded(d, (426, 210, 848, 350), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (452, 236), "Next customer to protect", 16, TOKENS["fg_2"])
    text(d, (452, 267), "Trailhead Logistics", 34)
    paragraph(d, 452, 313, "Vanessa is still active; Mike has gone quiet. Expansion stays safe if the relationship is widened this week.", 16, chars=43)
    rounded(d, (876, 210, 1374, 350), TOKENS["card"], TOKENS["hair"], 12)
    card_title(d, 902, 236, "Agent draft waiting on you", "human gate")
    paragraph(d, 902, 307, "Send Vanessa the compliance-reporting expansion brief and ask her to pull Mike into the next review.", 16, chars=50)
    stakeholder_stack(
        d,
        426,
        392,
        430,
        [
            ("Vanessa Torres", "VP Ops, champion", "active today", TOKENS["ok"]),
            ("Mike Lindgren", "Fleet Director", "quiet 85d", TOKENS["warn"]),
            ("Samira Ali", "Safety Manager", "engaged", TOKENS["ok"]),
        ],
    )
    factor_stack(d, 896, 392, 430)
    img.save(OUT / "01_csm_presence.png")


def render_relationship_map():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    queue_list(d, 36, 70, 300)
    rounded(d, (366, 70, 1404, 824), TOKENS["chrome"], TOKENS["hair"], 16)
    text(d, (398, 104), "Trailhead Logistics", 31)
    text(d, (398, 144), "Start with the people, then show the receipts.", 18, TOKENS["fg_2"])
    center = (798, 396)
    draw_nodes = [
        ((798, 240), "Vanessa", "champion", TOKENS["ok"]),
        ((560, 392), "Paul", "CTO", TOKENS["fg_2"]),
        ((1030, 392), "Mike", "quiet 85d", TOKENS["warn"]),
        ((798, 550), "Samira", "safety", TOKENS["ok"]),
    ]
    for (x, y), _, _, color in draw_nodes:
        d.line((center[0], center[1], x, y), fill=TOKENS["hair"], width=2)
    rounded(d, (690, 340, 906, 452), TOKENS["card"], TOKENS["accent"], 14, 2)
    text(d, (722, 371), "Account", 17, TOKENS["fg_2"])
    text(d, (722, 400), "Expansion path", 26)
    for (x, y), name, label, color in draw_nodes:
        d.ellipse((x - 62, y - 62, x + 62, y + 62), fill=TOKENS["card"], outline=color, width=3)
        text(d, (x - 40, y - 16), name, 22)
        text(d, (x - 42, y + 15), label, 14, color)
    rounded(d, (398, 638, 724, 774), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (424, 662), "Relationship read", 19)
    paragraph(d, 424, 696, "Champion is warm, but expansion is single-threaded unless Mike is brought back into the conversation.", 15, chars=38)
    rounded(d, (752, 638, 1372, 774), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (778, 662), "Receipts", 19)
    x = 778
    y = 700
    x = chip(d, x, y, "16 gmail signals")
    x = chip(d, x, y, "1 call transcript")
    x = chip(d, x, y, "usage 155 assets")
    chip(d, x, y, "no open cases")
    img.save(OUT / "02_relationship_map.png")


def render_relationship_overlay():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    queue_list(d, 36, 70, 300, selected="Harborview Fleet")
    rounded(d, (366, 70, 1404, 824), TOKENS["chrome"], TOKENS["hair"], 16)
    text(d, (398, 104), "Harborview Fleet", 31)
    chip(d, 398, 151, "renewal")
    chip(d, 500, 151, "score 35")
    chip(d, 600, 151, "2 high cases", outline=TOKENS["danger"], fg=TOKENS["danger"])
    rounded(d, (398, 210, 1372, 388), TOKENS["card"], TOKENS["danger"], 14, 2)
    text(d, (426, 236), "Relationship health overlay", 18, TOKENS["fg_2"])
    paragraph(d, 426, 272, "Gregory wants the ERP fix before renewal, Michelle is carrying fleet pain, and David needs a risk recap.", 29, TOKENS["fg"], chars=68, leading=7)
    text(d, (426, 348), "The agent should draft a sales handoff and CSM escalation packet, then wait for approval.", 18, TOKENS["fg_2"])
    stakeholder_stack(
        d,
        398,
        430,
        420,
        [
            ("Gregory Foster", "VP Ops", "blocked", TOKENS["danger"]),
            ("Michelle Park", "Fleet Manager", "active pain", TOKENS["warn"]),
            ("David Cross", "CFO", "renewal buyer", TOKENS["fg_2"]),
        ],
    )
    factor_stack(d, 864, 430, 458)
    rounded(d, (864, 700, 1322, 770), TOKENS["card"], TOKENS["hair"], 10)
    text(d, (888, 720), "Drafted motion: sales handoff", 19)
    text(d, (888, 748), "Owner approval required before any customer-facing send.", 14, TOKENS["warn"])
    img.save(OUT / "03_relationship_health_overlay.png")


def render_people_first_hierarchy():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    queue_list(d, 36, 70, 300)
    rounded(d, (366, 70, 1404, 824), TOKENS["chrome"], TOKENS["hair"], 16)
    text(d, (398, 104), "Trailhead Logistics", 31)
    text(d, (398, 143), "People and source signals move above the factor grid.", 18, TOKENS["fg_2"])
    rounded(d, (398, 192, 1372, 418), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (424, 218), "Human layer", 18, TOKENS["fg_2"])
    stakeholder_stack(
        d,
        424,
        258,
        420,
        [
            ("Vanessa Torres", "VP Ops, champion", "active today", TOKENS["ok"]),
            ("Mike Lindgren", "Fleet Director", "quiet 85d", TOKENS["warn"]),
        ],
    )
    rounded(d, (882, 258, 1342, 374), TOKENS["canvas"], TOKENS["hair"], 10)
    text(d, (906, 282), "Latest relationship evidence", 19)
    paragraph(d, 906, 316, "Vanessa replied today. Mike has not engaged in 85 days. Compliance reporting remains the expansion thread.", 15, chars=48)
    rounded(d, (398, 462, 1372, 770), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (424, 488), "Deterministic receipts", 18, TOKENS["fg_2"])
    factor_stack(
        d,
        424,
        528,
        430,
        [
            ("Usage adoption", "+18", "155 active assets"),
            ("Champion engagement", "+14", "Vanessa replied today"),
        ],
    )
    factor_stack(
        d,
        896,
        528,
        430,
        [
            ("Single-threading risk", "-8", "Mike quiet 85 days"),
            ("Outcome evidence", "0", "no terminal renewal yet"),
        ],
    )
    img.save(OUT / "04_people_first_hierarchy.png")


def render_who_why_header():
    img = Image.new("RGB", (1440, 900), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    queue_list(d, 36, 70, 300, selected="Ironhorse Freight Co")
    rounded(d, (366, 70, 1404, 824), TOKENS["chrome"], TOKENS["hair"], 16)
    text(d, (398, 104), "Ironhorse Freight Co", 31)
    rounded(d, (398, 162, 1372, 358), TOKENS["card"], TOKENS["accent"], 14, 2)
    text(d, (426, 192), "Who and why", 18, TOKENS["fg_2"])
    lines = wrap("Marcus and Lisa need a working session to unblock GPS hardware compatibility before route optimization stalls further.", 72)
    yy = 226
    for line in lines:
        text(d, (426, yy), line, 31)
        yy += 40
    text(d, (426, 316), "The agent has drafted the agenda and evidence pack. You approve or edit before it leaves.", 18, TOKENS["fg_2"])
    stakeholder_stack(
        d,
        398,
        402,
        420,
        [
            ("Marcus Webb", "Dir Fleet Ops", "primary operator", TOKENS["ok"]),
            ("Lisa Chang", "IT Manager", "implementation owner", TOKENS["ok"]),
            ("Robert Haines", "CFO", "no consent", TOKENS["fg_3"]),
        ],
    )
    rounded(d, (864, 402, 1322, 558), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (890, 428), "Proof bundle", 19)
    x = 890
    y = 468
    x = chip(d, x, y, "case: GPS hardware")
    chip(d, x, y + 44, "usage: 104 active assets")
    rounded(d, (864, 604, 1322, 740), TOKENS["card"], TOKENS["hair"], 12)
    text(d, (890, 630), "Drafted action", 19)
    paragraph(d, 890, 666, "Schedule a technical working session with Marcus and Lisa; include the compatibility case and rollout objective.", 16, chars=49)
    img.save(OUT / "05_who_why_header.png")


HTML_CSS = """
:root, [data-theme="dark"] {
  --canvas: #222321; --chrome: #1B1C1A; --card: #2A2B28; --card-2: #33342F;
  --hair: rgba(255,255,255,.09); --hair-soft: rgba(255,255,255,.05);
  --fg: #F1F0EC; --fg-2: #B7B5AC; --fg-3: #858379;
  --accent: #8189E6; --accent-fg: #fff; --accent-dim: rgba(129,137,230,.15); --accent-line: rgba(129,137,230,.45);
  --ok: #5DBE93; --warn: #D9A452; --danger: #E67B80; --amber: #D9A452;
  --ok-dim: rgba(93,190,147,.12); --warn-dim: rgba(217,164,82,.11); --danger-dim: rgba(230,123,128,.11);
  --shadow: 0 10px 34px -10px rgba(0,0,0,.65);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--canvas); color: var(--fg); font-family: -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif; font-size: 13.5px; line-height: 1.5; }
.mock { min-height: 100vh; padding: 26px; display: grid; grid-template-columns: 324px 1fr; gap: 22px; }
.queue, .detail, .card { background: var(--chrome); border: 1px solid var(--hair); border-radius: 12px; }
.queue { padding: 14px; }
.queue h2, .detail h1, .card h3 { margin: 0; font-weight: 650; }
.muted { color: var(--fg-2); }
.row { padding: 11px 12px; border: 1px solid var(--hair-soft); border-radius: 9px; margin-top: 8px; background: transparent; }
.row.sel { background: var(--card); border-color: var(--accent-line); }
.row strong, .person strong { display: block; font-size: 13px; }
.score { float: right; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.detail { padding: 28px; }
.hero { border: 1px solid var(--accent-line); background: var(--card); border-radius: 12px; padding: 24px; margin: 22px 0; }
.hero.danger { border-color: rgba(230,123,128,.6); }
.hero h2 { margin: 0; font-size: 30px; line-height: 1.18; font-weight: 650; max-width: 980px; }
.section { margin-top: 22px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.card { padding: 18px; background: var(--card); }
.person { display: grid; grid-template-columns: 36px 1fr auto; gap: 12px; align-items: center; padding: 10px 0; border-top: 1px solid var(--hair-soft); }
.person:first-of-type { border-top: 0; }
.avatar { width: 36px; height: 36px; border-radius: 9px; border: 1px solid var(--hair); display: grid; place-items: center; background: var(--card-2); font-weight: 700; }
.chip { display: inline-flex; align-items: center; border: 1px solid var(--hair); border-radius: 6px; padding: 2px 8px; color: var(--fg-2); font-size: 11px; margin: 0 6px 6px 0; white-space: nowrap; }
.ok { color: var(--ok); border-color: rgba(93,190,147,.45); }
.warn { color: var(--warn); border-color: rgba(217,164,82,.45); }
.danger-text { color: var(--danger); border-color: rgba(230,123,128,.5); }
.factor { padding: 10px 12px; border: 1px solid var(--hair); border-radius: 8px; margin-top: 8px; background: var(--canvas); }
.factor b { float: right; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.map { position: relative; min-height: 430px; }
.node { position: absolute; width: 136px; height: 92px; border: 1px solid var(--hair); border-radius: 14px; background: var(--card); display: grid; place-items: center; text-align: center; padding: 10px; }
.node.account { left: calc(50% - 95px); top: 170px; width: 190px; border-color: var(--accent-line); }
.n1 { left: calc(50% - 68px); top: 12px; }
.n2 { left: 12%; top: 175px; }
.n3 { right: 12%; top: 175px; }
.n4 { left: calc(50% - 68px); bottom: 10px; }
.proposal-note { margin-top: 18px; color: var(--fg-2); font-size: 12px; }
"""


QUEUE = """
<aside class="queue">
  <h2>Queue</h2>
  <p class="muted">human-reviewed actions</p>
  <div class="row {harbor}"><span class="score">35</span><strong>Harborview Fleet</strong><span class="muted">renewal risk</span></div>
  <div class="row {trailhead}"><span class="score">90</span><strong>Trailhead Logistics</strong><span class="muted">champion active</span></div>
  <div class="row {ironhorse}"><span class="score">74</span><strong>Ironhorse Freight Co</strong><span class="muted">hardware blocker</span></div>
  <div class="row"><span class="score">69</span><strong>Pinehill Transport</strong><span class="muted">training drift</span></div>
  <div class="row"><span class="score">52</span><strong>Quarry Stone Logistics</strong><span class="muted">silent account</span></div>
</aside>
"""


def page(title: str, selected: str, body: str) -> str:
    queue = QUEUE.format(
        harbor="sel" if selected == "harbor" else "",
        trailhead="sel" if selected == "trailhead" else "",
        ironhorse="sel" if selected == "ironhorse" else "",
    )
    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{HTML_CSS}</style>
</head>
<body>
  <main class="mock">
    {queue}
    <section class="detail">
      {body}
    </section>
  </main>
</body>
</html>
"""


def person(name: str, role: str, state: str, klass: str = "") -> str:
    return f"""<div class="person"><div class="avatar">{html.escape(name[:1])}</div><div><strong>{html.escape(name)}</strong><span class="muted">{html.escape(role)}</span></div><span class="chip {klass}">{html.escape(state)}</span></div>"""


def factors() -> str:
    return """
<div class="factor"><b>+18</b>Usage adoption<br><span class="muted">155 active assets</span></div>
<div class="factor"><b>+14</b>Champion engagement<br><span class="muted">Vanessa replied today</span></div>
<div class="factor"><b>-8</b>Single-threading risk<br><span class="muted">Mike quiet 85 days</span></div>
<div class="factor"><b>0</b>Outcome evidence<br><span class="muted">no terminal renewal yet</span></div>
"""


def write_html():
    pages = {
        "01_csm_presence.html": page(
            "CSM presence",
            "trailhead",
            """
<h1>Your book, Maya</h1>
<p class="muted">The agents have drafted 7 customer moves. You are approving the work, not hunting for it.</p>
<div class="hero"><p class="muted">Next customer to protect</p><h2>Trailhead Logistics: Vanessa is active, but Mike has gone quiet.</h2><p class="muted">Expansion stays safe if the relationship is widened this week.</p></div>
<div class="section"><div class="card"><h3>People in the motion</h3>{people}</div><div class="card"><h3>Agent draft waiting on you</h3><p>Send Vanessa the compliance-reporting expansion brief and ask her to pull Mike into the next review.</p><span class="chip warn">approval required</span></div></div>
<p class="proposal-note">Hypothesis: make the CSM operator explicit so the product reads as agents scaling a human book of business, not as an anonymous dashboard.</p>
""".format(
                people="\n".join(
                    [
                        person("Vanessa Torres", "VP Ops, champion", "active today", "ok"),
                        person("Mike Lindgren", "Fleet Director", "quiet 85d", "warn"),
                        person("Samira Ali", "Safety Manager", "engaged", "ok"),
                    ]
                )
            ),
        ),
        "02_relationship_map.html": page(
            "Relationship map",
            "trailhead",
            """
<h1>Trailhead Logistics</h1>
<p class="muted">Start with the people, then show the receipts.</p>
<div class="card map">
  <div class="node n1"><strong>Vanessa</strong><span class="chip ok">champion</span></div>
  <div class="node n2"><strong>Paul</strong><span class="chip">CTO</span></div>
  <div class="node account"><strong>Expansion path</strong><span class="muted">account</span></div>
  <div class="node n3"><strong>Mike</strong><span class="chip warn">quiet 85d</span></div>
  <div class="node n4"><strong>Samira</strong><span class="chip ok">safety</span></div>
</div>
<div class="section"><div class="card"><h3>Relationship read</h3><p>Champion is warm, but expansion is single-threaded unless Mike is brought back into the conversation.</p></div><div class="card"><h3>Receipts</h3><span class="chip">16 gmail signals</span><span class="chip">1 call transcript</span><span class="chip">usage 155 assets</span><span class="chip">no open cases</span></div></div>
<p class="proposal-note">Hypothesis: the stakeholder graph becomes the first read; deterministic factors remain the audit trail beneath it.</p>
""",
        ),
        "03_relationship_health_overlay.html": page(
            "Relationship health overlay",
            "harbor",
            """
<h1>Harborview Fleet</h1>
<span class="chip">renewal</span><span class="chip">score 35</span><span class="chip danger-text">2 high cases</span>
<div class="hero danger"><p class="muted">Relationship health overlay</p><h2>Gregory wants the ERP fix before renewal, Michelle is carrying fleet pain, and David needs a risk recap.</h2><p class="muted">The agent should draft a sales handoff and CSM escalation packet, then wait for approval.</p></div>
<div class="section"><div class="card"><h3>Stakeholders</h3>{people}</div><div class="card"><h3>Deterministic receipts</h3>{factors}<span class="chip warn">customer-facing send blocked by gate</span></div></div>
<p class="proposal-note">Hypothesis: use a relationship diagnosis as the primary read for renewal and sales handoff moments.</p>
""".format(
                people="\n".join(
                    [
                        person("Gregory Foster", "VP Ops", "blocked", "danger-text"),
                        person("Michelle Park", "Fleet Manager", "active pain", "warn"),
                        person("David Cross", "CFO", "renewal buyer", ""),
                    ]
                ),
                factors=factors(),
            ),
        ),
        "04_people_first_hierarchy.html": page(
            "People first hierarchy",
            "trailhead",
            """
<h1>Trailhead Logistics</h1>
<p class="muted">People and source signals move above the factor grid.</p>
<div class="section"><div class="card"><h3>Human layer</h3>{people}</div><div class="card"><h3>Latest relationship evidence</h3><p>Vanessa replied today. Mike has not engaged in 85 days. Compliance reporting remains the expansion thread.</p><span class="chip">16 gmail</span><span class="chip">1 call</span><span class="chip">1 internal note</span></div></div>
<div class="section"><div class="card"><h3>Deterministic receipts</h3>{factors}</div><div class="card"><h3>Agent draft</h3><p>Ask Vanessa to pull Mike into the compliance-reporting review, with usage evidence attached.</p><span class="chip warn">approval required</span></div></div>
<p class="proposal-note">Hypothesis: the lowest-risk production path is hierarchy-only; it keeps the current surface but changes what the eye sees first.</p>
""".format(
                people="\n".join(
                    [
                        person("Vanessa Torres", "VP Ops, champion", "active today", "ok"),
                        person("Mike Lindgren", "Fleet Director", "quiet 85d", "warn"),
                    ]
                ),
                factors=factors(),
            ),
        ),
        "05_who_why_header.html": page(
            "Who and why header",
            "ironhorse",
            """
<h1>Ironhorse Freight Co</h1>
<div class="hero"><p class="muted">Who and why</p><h2>Marcus and Lisa need a working session to unblock GPS hardware compatibility before route optimization stalls further.</h2><p class="muted">The agent has drafted the agenda and evidence pack. You approve or edit before it leaves.</p></div>
<div class="section"><div class="card"><h3>People in the action</h3>{people}</div><div class="card"><h3>Proof bundle</h3><span class="chip">case: GPS hardware</span><span class="chip">usage: 104 active assets</span><span class="chip">objective: driver onboarding</span></div></div>
<div class="card" style="margin-top:16px"><h3>Drafted action</h3><p>Schedule a technical working session with Marcus and Lisa; include the compatibility case and rollout objective.</p><span class="chip warn">human approval required</span></div>
<p class="proposal-note">Hypothesis: a plain-language header performs the story before the data and gives the demo a fast, truthful first sentence.</p>
""".format(
                people="\n".join(
                    [
                        person("Marcus Webb", "Dir Fleet Ops", "primary operator", "ok"),
                        person("Lisa Chang", "IT Manager", "implementation owner", "ok"),
                        person("Robert Haines", "CFO", "no consent", ""),
                    ]
                )
            ),
        ),
    }

    for name, body in pages.items():
        (OUT / name).write_text(body, encoding="utf-8")

    index_items = []
    for name in pages:
        png = name.replace(".html", ".png")
        label = name.removesuffix(".html").replace("_", " ")
        index_items.append(
            f'<li><a href="{html.escape(name)}">{html.escape(label)}</a> '
            f'<a href="{html.escape(png)}">(png)</a></li>'
        )
    (OUT / "index.html").write_text(
        f"""<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8" />
<title>F4 human-anchor proposals</title><style>{HTML_CSS} body{{padding:28px}} .mock{{display:block;min-height:auto}} li{{margin:10px 0;font-size:18px}} a{{color:var(--accent)}} </style></head><body>
<h1>F4 human-anchor proposals</h1>
<p class="muted">Static proposal artifacts only. They use the real token sheet and real day-140 account data shapes; no production implementation is selected here.</p>
<ol>{''.join(index_items)}</ol>
</body></html>""",
        encoding="utf-8",
    )


def contact_sheet():
    names = [
        "01_csm_presence",
        "02_relationship_map",
        "03_relationship_health_overlay",
        "04_people_first_hierarchy",
        "05_who_why_header",
    ]
    thumbs = [Image.open(OUT / f"{name}.png").resize((640, 400)) for name in names]
    img = Image.new("RGB", (1360, 1500), TOKENS["canvas"])
    d = ImageDraw.Draw(img)
    text(d, (36, 28), "F4 human-anchor proposal series", 34)
    text(d, (36, 72), "Rendered previews from static proposal artifacts. Owner ratification required before implementation.", 18, TOKENS["fg_2"])
    positions = [(36, 120), (684, 120), (36, 560), (684, 560), (36, 1000)]
    for i, (name, thumb, pos) in enumerate(zip(names, thumbs, positions), start=1):
        x, y = pos
        rounded(d, (x - 1, y - 1, x + 641, y + 401), TOKENS["chrome"], TOKENS["hair"], 12)
        img.paste(thumb, (x, y))
        text(d, (x + 12, y + 410), f"{i}. {name[3:].replace('_', ' ')}", 20)
    img.save(OUT / "contact-sheet.png")


def main():
    render_csm_presence()
    render_relationship_map()
    render_relationship_overlay()
    render_people_first_hierarchy()
    render_who_why_header()
    write_html()
    contact_sheet()


if __name__ == "__main__":
    main()
