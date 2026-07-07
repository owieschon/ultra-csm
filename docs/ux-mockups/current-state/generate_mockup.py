#!/usr/bin/env python3
"""Generate the current-state interactive HTML mockup from hosted demo data."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "ui" / "public" / "demo-api"
OUT = Path(__file__).with_name("index.html")


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main() -> None:
    accounts = load("accounts-day-140.json")
    sweep = load("sweep-day-140.json")
    ledger = load("ledger.json")
    payload = {
        "accounts": accounts["accounts"],
        "sweep": sweep,
        "ledger": ledger["events"][:18],
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Ultra CSM current-state interactive mockup</title>
  <style>
    :root {
      --canvas:#222321; --chrome:#1B1C1A; --card:#2A2B28; --card2:#33342F;
      --hair:rgba(255,255,255,.09); --hair2:rgba(255,255,255,.05);
      --fg:#F1F0EC; --fg2:#B7B5AC; --fg3:#858379;
      --accent:#8189E6; --accent-dim:rgba(129,137,230,.15); --accent-line:rgba(129,137,230,.45);
      --ok:#5DBE93; --ok-dim:rgba(93,190,147,.12);
      --warn:#D9A452; --warn-dim:rgba(217,164,82,.11);
      --danger:#E67B80; --danger-dim:rgba(230,123,128,.11);
    }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--canvas); color:var(--fg); font:13.5px/1.5 -apple-system,BlinkMacSystemFont,"Inter",system-ui,sans-serif; letter-spacing:-.011em; }
    button,input,textarea { font:inherit; color:inherit; }
    button { border:0; background:none; cursor:pointer; }
    .app { height:100vh; display:grid; grid-template-rows:52px 1fr; }
    .top { display:flex; align-items:center; gap:14px; padding:0 16px; border-bottom:1px solid var(--hair); background:var(--chrome); }
    .brand { display:flex; align-items:center; gap:10px; font-weight:700; font-size:15px; }
    .mark { width:22px; height:22px; border:2px solid var(--accent); border-radius:7px; position:relative; }
    .mark:before,.mark:after { content:""; position:absolute; background:var(--accent); border-radius:99px; }
    .mark:before { width:7px; height:7px; left:6px; top:6px; }
    .mark:after { width:2px; height:18px; left:10px; top:0; transform:rotate(45deg); opacity:.7; }
    .seg { display:flex; border:1px solid var(--hair); border-radius:8px; overflow:hidden; background:var(--canvas); }
    .seg button { padding:6px 14px; font-size:12.5px; font-weight:650; color:var(--fg2); }
    .seg button.on { color:var(--fg); background:var(--card2); }
    .env { margin-left:auto; display:flex; align-items:center; gap:10px; color:var(--fg2); font-size:12px; }
    .pill { display:inline-flex; align-items:center; gap:5px; border:1px solid var(--hair); border-radius:6px; padding:2px 8px; color:var(--fg2); font-size:10.5px; font-weight:700; letter-spacing:.03em; text-transform:uppercase; }
    .layout { min-height:0; display:grid; grid-template-columns:1fr 310px; }
    .stage { min-width:0; min-height:0; overflow:hidden; display:grid; }
    .rail { border-left:1px solid var(--hair); background:var(--chrome); min-height:0; overflow:auto; }
    .view { min-height:0; overflow:auto; padding:22px 26px 60px; display:none; }
    .view.on { display:block; }
    .hero { display:flex; align-items:center; gap:16px; padding:16px 18px; border:1px solid var(--hair); border-radius:12px; background:var(--card); margin-bottom:18px; }
    .hero h1 { font-size:16px; line-height:1.2; margin:0 0 4px; font-weight:700; }
    .sub { color:var(--fg2); font-size:12.5px; }
    .cta { margin-left:auto; background:var(--accent); color:white; border-radius:8px; padding:8px 14px; font-weight:650; font-size:12.5px; }
    .panel { border:1px solid var(--hair); border-radius:12px; background:var(--card); overflow:hidden; margin-bottom:18px; }
    .panel-head { display:flex; align-items:flex-start; gap:10px; padding:14px 16px 12px; border-bottom:1px solid var(--hair2); }
    .eyebrow { font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; color:var(--fg3); }
    .title { margin-top:3px; font-size:15px; font-weight:700; color:var(--fg); }
    .panel-head .right { margin-left:auto; display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
    .filters { display:flex; flex-wrap:wrap; gap:7px; padding:11px 14px; border-bottom:1px solid var(--hair2); }
    .filter { display:inline-flex; gap:7px; align-items:center; border:1px solid var(--hair); border-radius:7px; background:var(--canvas); color:var(--fg2); padding:5px 9px; font-size:11.5px; font-weight:650; }
    .filter.on,.filter:hover { color:var(--fg); border-color:var(--accent-line); background:var(--accent-dim); }
    .receipt { padding:14px 16px 15px; border-left:3px solid var(--hair); }
    .receipt.needs_human { border-left-color:var(--accent); }
    .receipt.prepared_work { border-left-color:var(--ok); }
    .receipt.covered { border-left-color:var(--hair); }
    .receipt.source_degraded,.receipt.insufficient_evidence,.receipt.not_scanned { border-left-color:var(--warn); background:var(--warn-dim); }
    .receipt-main { display:flex; align-items:flex-start; gap:14px; }
    .state { font-size:10.5px; color:var(--fg3); font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
    .receipt h2 { margin:3px 0; font-size:15px; }
    .score { margin-left:auto; color:var(--fg2); font-weight:700; white-space:nowrap; }
    .chips { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
    .chip { border:1px solid var(--hair); border-radius:5px; padding:2px 7px; font-size:10.5px; color:var(--fg2); background:var(--canvas); }
    .chip.warn { color:var(--warn); border-color:rgba(217,164,82,.45); background:var(--warn-dim); }
    .mini { margin-left:auto; border:1px solid var(--accent-line); border-radius:7px; background:var(--accent-dim); padding:6px 10px; font-size:12px; font-weight:700; }
    .toolbar { display:flex; align-items:center; gap:8px; margin:0 0 12px; }
    .search { width:260px; max-width:100%; border:1px solid var(--hair); border-radius:8px; background:var(--chrome); color:var(--fg); padding:8px 10px; outline:none; }
    .band-h { display:flex; align-items:baseline; gap:12px; padding:0 2px 9px; }
    .band-h .bt { font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
    .band-h .stats { color:var(--fg2); font-size:12px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(165px,1fr)); gap:8px; margin-bottom:22px; }
    .tile { min-height:66px; display:flex; flex-direction:column; gap:4px; text-align:left; border:1px solid var(--hair2); border-radius:9px; background:transparent; padding:10px 11px; }
    .tile:hover,.tile.sel { background:var(--card); border-color:var(--accent-line); }
    .tile.hot { background:var(--card); border-color:var(--hair); }
    .tile.warn { border-color:rgba(217,164,82,.36); background:var(--warn-dim); }
    .tname { font-size:12.5px; font-weight:650; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .tsub { color:var(--fg2); font-size:11px; }
    .queue { height:100%; display:grid; grid-template-columns:330px 1fr; min-height:0; }
    .lanes { border-right:1px solid var(--hair); background:var(--chrome); overflow:auto; }
    .lane-intro { padding:15px 14px 13px; border-bottom:1px solid var(--hair); }
    .lane-h { display:flex; align-items:center; gap:8px; padding:14px 14px 8px; }
    .lane-h b { font-size:12px; }
    .lane-h .badge { margin-left:auto; }
    .row { width:100%; display:flex; flex-direction:column; gap:5px; text-align:left; padding:10px 14px 10px 13px; border-left:2px solid transparent; border-bottom:1px solid var(--hair2); }
    .row:hover,.row.sel { background:var(--card); border-left-color:var(--accent); }
    .row .l1,.row .l2 { display:flex; align-items:center; gap:7px; min-width:0; }
    .row .acct { font-weight:650; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .row .score { margin-left:auto; font-size:12px; }
    .cadence { font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.04em; padding:1px 6px; border-radius:5px; border:1px solid var(--hair); color:var(--fg2); }
    .cadence.daily { color:var(--accent); border-color:var(--accent-line); background:var(--accent-dim); }
    .cadence.weekly { color:var(--ok); border-color:rgba(93,190,147,.42); background:var(--ok-dim); }
    .cadence.quarterly { color:var(--warn); border-color:rgba(217,164,82,.45); background:var(--warn-dim); }
    .cadence.event { color:var(--danger); border-color:rgba(230,123,128,.45); background:var(--danger-dim); }
    .detail { min-height:0; overflow:auto; padding:22px 28px 48px; }
    .packet { border:1px solid var(--accent-line); border-radius:12px; background:var(--card); padding:17px 18px; }
    .packet-top { display:flex; align-items:flex-start; gap:14px; }
    .avatar { width:46px; height:46px; border-radius:10px; background:var(--card2); border:1px solid var(--hair); color:var(--fg2); display:flex; align-items:center; justify-content:center; font-weight:800; }
    .kicker { display:flex; gap:8px; flex-wrap:wrap; color:var(--fg2); font-size:11px; }
    .packet h2 { margin:8px 0 5px; font-size:22px; line-height:1.15; }
    .sec { margin-top:26px; }
    .sec-h { display:flex; align-items:center; gap:8px; margin-bottom:11px; }
    .sec-h b { font-size:11.5px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
    .factor,.box { border:1px solid var(--hair); border-radius:9px; background:var(--card); padding:11px 13px; margin-bottom:7px; }
    .factor { display:flex; gap:10px; align-items:center; }
    .factor .contrib { margin-left:auto; color:var(--fg2); font-weight:800; }
    .draft { white-space:pre-wrap; line-height:1.62; }
    .rail-top { padding:15px; border-bottom:1px solid var(--hair); }
    .rail-top .t { font-size:11.5px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
    .gate { color:var(--fg2); font-size:12px; margin-top:6px; }
    .actions { display:flex; flex-direction:column; gap:8px; padding:13px 15px; }
    .btn { display:flex; align-items:center; justify-content:center; border:1px solid var(--hair); border-radius:8px; background:var(--card); padding:10px 13px; font-weight:700; }
    .btn.approve { background:var(--accent); border-color:var(--accent); color:white; }
    .btn:hover { border-color:var(--accent-line); }
    .edit { margin:0 15px 13px; display:none; }
    .edit.on { display:block; }
    textarea { width:100%; min-height:90px; resize:vertical; border:1px solid var(--hair); border-radius:8px; background:var(--canvas); padding:9px 10px; outline:none; }
    .ledger { padding:0 13px 13px; }
    .lg { display:flex; gap:8px; padding:5px 2px; border-bottom:1px solid var(--hair2); font-size:11px; color:var(--fg2); }
    .lg b { color:var(--fg); flex:0 0 80px; }
    .empty { height:100%; display:flex; align-items:center; justify-content:center; color:var(--fg2); }
    @media (max-width: 900px) {
      .layout { grid-template-columns:1fr; }
      .rail { display:none; }
      .queue { grid-template-columns:1fr; }
      .lanes { max-height:42vh; border-right:0; border-bottom:1px solid var(--hair); }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="top">
      <div class="brand"><span class="mark"></span>Ultra CSM</div>
      <div class="seg"><button id="bookTab" class="on">Book</button><button id="todayTab">Today <span id="todayCount"></span></button></div>
      <div class="env"><span class="pill">readonly mock</span><span>day <b>140</b></span></div>
    </header>
    <div class="layout">
      <main class="stage">
        <section id="bookView" class="view on">
          <div class="hero">
            <div><h1 id="bookHeadline"></h1><div class="sub" id="bookSub"></div></div>
            <button class="cta" id="workToday">Work today</button>
          </div>
          <div class="panel">
            <div class="panel-head">
              <div><div class="eyebrow">Book coverage</div><div class="title" id="coverageTitle"></div></div>
              <div class="right"><span class="pill">backend receipts</span><span class="pill" id="degradedPill"></span></div>
            </div>
            <div class="filters" id="filters"></div>
            <div id="receipt"></div>
          </div>
          <div class="toolbar"><input id="search" class="search" placeholder="Search the full book" /><span class="sub">Click any account to inspect its receipt.</span></div>
          <div id="bookGrid"></div>
        </section>
        <section id="todayView" class="view">
          <div class="queue">
            <aside class="lanes">
              <div class="lane-intro"><div class="eyebrow">CSM operating cadence</div><div class="title">Today’s agent work</div><div class="sub">Prioritized packets prepared from the backend sweep.</div></div>
              <div id="lanes"></div>
            </aside>
            <section class="detail" id="detail"></section>
          </div>
        </section>
      </main>
      <aside class="rail" id="rail"></aside>
    </div>
  </div>
  <script>
    const DATA = __DATA__;
    const accounts = DATA.accounts;
    const sweep = DATA.sweep;
    const ledger = [...DATA.ledger];
    const workItems = sweep.work_items;
    const receipts = sweep.coverage_receipts;
    const accountById = new Map(accounts.map(a => [a.account_id, a]));
    const itemByAccount = new Map(workItems.filter(i => i.account_id).map(i => [i.account_id, i]));
    const labels = {needs_human:"Needs human",prepared_work:"Prepared",covered:"Covered",reviewed:"Reviewed",insufficient_evidence:"Insufficient",source_degraded:"Source degraded",not_scanned:"Not scanned"};
    const tierLabels = {high_touch:"High touch",mid_touch:"Mid touch",tech_touch:"Self-serve tier"};
    const motionLabels = {personal_email:"Personal email",working_session:"Working session",qbr:"QBR",escalation:"Escalate",content_route:"Send help content",campaign_enroll:"Campaign",cohort_action:"Cohort action"};
    let view = "book";
    let filter = "all";
    let query = "";
    let selectedAccount = receipts.find(r => r.state === "needs_human")?.account_id || receipts[0]?.account_id;
    let selectedWorkKey = receipts.find(r => r.state === "needs_human")?.work_item_key || workKey(workItems[0]);
    let editOpen = false;

    function workKey(item) {
      if (!item) return null;
      if (item.proposal?.proposal_id) return item.proposal.proposal_id;
      const subject = item.account_id || (item.candidate_account_ids || []).join(",") || "program";
      return [item.disposition || "work", subject, item.motion || item.recommended_action || "work", item.swept_at || ""].join(":");
    }
    function describeWork(item) {
      const hasBridge = item?.internal_bridge_decision && !item.internal_bridge_decision.abstained;
      let cadence = "daily", kind = "Customer", packet = "Customer action packet";
      if (hasBridge && !item.proposal) { cadence = "event"; kind = "Internal"; packet = `${targetLabel(item)} handoff packet`; }
      else if (hasBridge) { cadence = "event"; kind = "Briefing"; packet = `${targetLabel(item)} briefing packet`; }
      else if (item?.motion === "qbr") { cadence = "quarterly"; kind = "Briefing"; packet = "QBR packet"; }
      else if (item?.motion === "cohort_action" || item?.recommended_action === "cohort_action") { cadence = "monthly"; kind = "Cohort"; packet = "Cohort packet"; }
      else if (item?.motion === "campaign_enroll" || item?.recommended_action === "campaign_enroll") { cadence = "weekly"; kind = "Customer"; packet = "Campaign packet"; }
      else if (item?.disposition === "internal_review") { cadence = "weekly"; kind = "Integrity"; packet = "Integrity task"; }
      else if (item?.motion && motionLabels[item.motion]) packet = `${motionLabels[item.motion]} packet`;
      const authority = item?.proposal ? (item.proposal.status === "pending" ? "human approval required" : `proposal ${item.proposal.status}`) : "no customer-facing release";
      return {cadence, kind, packet, authority};
    }
    function targetLabel(item) {
      const t = item?.internal_bridge_decision?.target;
      return t === "engineering" ? "Engineering" : t === "product" ? "Product" : "Internal";
    }
    function receiptFor(id) { return receipts.find(r => r.account_id === id); }
    function itemForKey(key) { return workItems.find(i => workKey(i) === key || i.proposal?.proposal_id === key); }
    function counts() {
      const c = {all: receipts.length};
      receipts.forEach(r => c[r.state] = (c[r.state] || 0) + 1);
      return c;
    }
    function setView(next) {
      view = next;
      document.getElementById("bookView").classList.toggle("on", view === "book");
      document.getElementById("todayView").classList.toggle("on", view === "today");
      document.getElementById("bookTab").classList.toggle("on", view === "book");
      document.getElementById("todayTab").classList.toggle("on", view === "today");
      renderRail();
    }
    function render() {
      const c = counts();
      const needs = c.needs_human || 0;
      document.getElementById("todayCount").textContent = needs ? needs : "";
      document.getElementById("bookHeadline").textContent = needs ? `Today: ${needs} agent-prepared items need you.` : "Book covered.";
      document.getElementById("bookSub").innerHTML = `<b>${accounts.length}</b> accounts · day <b>140</b> · <b>${sweep.escalations.length}</b> escalations · <span class="pill">deterministic brief</span>`;
      document.getElementById("coverageTitle").textContent = `${c.all || 0} accounted for · ${c.covered || 0} covered · ${(c.source_degraded || 0) + (c.not_scanned || 0)} need source review`;
      document.getElementById("degradedPill").textContent = `${sweep.degraded_items || 0} degraded`;
      renderFilters(c);
      renderReceipt();
      renderBookGrid();
      renderLanes();
      renderDetail();
      renderRail();
    }
    function renderFilters(c) {
      const keys = ["all","needs_human","prepared_work","covered","reviewed","insufficient_evidence","source_degraded","not_scanned"];
      document.getElementById("filters").innerHTML = keys.map(k => `<button class="filter ${filter===k?"on":""}" data-filter="${k}"><span>${k==="all"?"All":labels[k]}</span><span>${c[k] || 0}</span></button>`).join("");
      document.querySelectorAll("[data-filter]").forEach(b => b.onclick = () => { filter = b.dataset.filter; render(); });
    }
    function renderReceipt() {
      const r = receiptFor(selectedAccount) || receipts[0];
      if (!r) return;
      const open = r.work_item_key ? `<button class="mini" id="openPacket">${r.action_label}</button>` : "";
      document.getElementById("receipt").innerHTML = `<div class="receipt ${r.state}">
        <div class="receipt-main"><div><div class="state">${r.label}</div><h2>${r.account_name}</h2><div class="sub">${r.reason}</div></div><div class="score">${r.score_label}</div></div>
        <div class="chips">${r.evidence_lines.map(x=>`<span class="chip">${escapeHtml(x)}</span>`).join("")}${r.missing_lines.map(x=>`<span class="chip warn">${escapeHtml(x)}</span>`).join("")}</div>
        <div class="chips"><span class="pill">coverage receipt</span>${open}</div>
      </div>`;
      const btn = document.getElementById("openPacket");
      if (btn) btn.onclick = () => { selectedWorkKey = r.work_item_key; setView("today"); render(); };
    }
    function renderBookGrid() {
      const q = query.toLowerCase();
      const filtered = receipts.filter(r => (filter === "all" || r.state === filter) && (!q || r.account_name.toLowerCase().includes(q)));
      const byTier = {};
      filtered.forEach(r => {
        const acct = accountById.get(r.account_id) || {};
        const tier = acct.tier || "unknown";
        (byTier[tier] ||= []).push(r);
      });
      const order = ["high_touch","mid_touch","tech_touch","unknown"].filter(t => byTier[t]);
      document.getElementById("bookGrid").innerHTML = order.map(t => `<section><div class="band-h"><span class="bt">${tierLabels[t] || t}</span><span class="stats"><b>${byTier[t].length}</b> visible accounts</span></div><div class="grid">${byTier[t].map(tile).join("")}</div></section>`).join("") || `<div class="empty">No accounts match this filter.</div>`;
      document.querySelectorAll("[data-account]").forEach(b => b.onclick = () => { selectedAccount = b.dataset.account; render(); });
    }
    function tile(r) {
      const hot = r.state === "needs_human";
      const warn = ["source_degraded","not_scanned","insufficient_evidence"].includes(r.state);
      return `<button class="tile ${hot?"hot":""} ${warn?"warn":""} ${selectedAccount===r.account_id?"sel":""}" data-account="${r.account_id}"><span class="tname">${r.account_name}</span><span class="tsub">${r.label}</span></button>`;
    }
    function laneItems(type) {
      if (type === "needs") return workItems.filter(i => i.proposal?.status === "pending");
      if (type === "prepared") return workItems.filter(i => !i.proposal);
      return workItems.filter(i => i.proposal && i.proposal.status !== "pending");
    }
    function renderLanes() {
      const groups = [["needs","Needs judgment","approval gate"],["prepared","Prepared work","no customer send"],["done","Completed this run","approved/denied · logged"]];
      document.getElementById("lanes").innerHTML = groups.map(([k,label,badge]) => {
        const items = laneItems(k);
        return `<div class="lane-h"><b>${label}</b><span class="sub">${items.length}</span><span class="pill badge">${badge}</span></div>${items.map(row).join("") || `<div class="row"><span class="sub">none this sweep</span></div>`}`;
      }).join("");
      document.querySelectorAll("[data-work]").forEach(b => b.onclick = () => { selectedWorkKey = b.dataset.work; render(); });
    }
    function row(item) {
      const key = workKey(item);
      const acct = accountById.get(item.account_id) || {};
      const desc = describeWork(item);
      const score = item.priority?.score ?? "—";
      return `<button class="row ${selectedWorkKey===key?"sel":""}" data-work="${key}"><div class="l1"><span class="acct">${acct.account_name || item.account_id || "program"}</span><span class="score">${score}</span></div><div class="l2"><span class="cadence ${desc.cadence}">${desc.cadence}</span><span class="chip">${desc.kind}</span></div></button>`;
    }
    function renderDetail() {
      const item = itemForKey(selectedWorkKey) || workItems[0];
      if (!item) { document.getElementById("detail").innerHTML = `<div class="empty">No packet selected.</div>`; return; }
      const acct = accountById.get(item.account_id) || {};
      const desc = describeWork(item);
      const factors = item.priority?.factors || [];
      document.getElementById("detail").innerHTML = `<div class="packet"><div class="packet-top"><div class="avatar">${(acct.account_name || "P").slice(0,2).toUpperCase()}</div><div><div class="kicker"><span class="cadence ${desc.cadence}">${desc.cadence}</span><span>${desc.kind}</span><span>${desc.authority}</span></div><h2>${desc.packet}</h2><div class="sub">${acct.account_name || item.account_id || "Program work"}</div></div></div><div class="chips"><span class="chip">${factors.length} value signals</span><span class="chip">${item.proposal ? "customer-facing release gated" : "no customer-facing release"}</span></div></div>
      <div class="sec"><div class="sec-h"><b>Evidence receipt</b><span class="pill">Rule-based · no AI</span></div>${factors.map(f=>`<div class="factor"><span>${f.name}</span><span class="contrib">+${f.contribution}</span><span class="sub">${f.threshold_name || "threshold"} ${f.threshold_value ?? ""}</span></div>`).join("") || `<div class="box sub">No factor list on this packet.</div>`}</div>
      <div class="sec"><div class="sec-h"><b>Agent-prepared work</b><span class="pill">Operator review</span></div><div class="box"><b>${motionLabels[item.motion] || item.motion || "Prepared review"}</b><div class="sub" style="margin-top:8px">${escapeHtml(item.reason || "")}</div></div></div>
      ${item.customer_draft ? `<div class="sec"><div class="sec-h"><b>Draft or packet body</b><span class="pill">AI-written · needs approval</span></div><div class="box draft">${escapeHtml(item.customer_draft)}</div></div>` : ""}`;
    }
    function renderRail() {
      const rail = document.getElementById("rail");
      if (view !== "today") { rail.innerHTML = `<div class="rail-top"><div class="t">Book supervision</div><div class="gate">Today prioritizes attention. Book coverage keeps the full book reviewable.</div></div><div class="ledger">${ledger.slice(0,10).map(lg).join("")}</div>`; return; }
      const item = itemForKey(selectedWorkKey);
      if (!item) { rail.innerHTML = `<div class="rail-top"><div class="t">Human control</div><div class="gate">select a packet</div></div>`; return; }
      const desc = describeWork(item);
      const canAct = item.proposal?.status === "pending";
      rail.innerHTML = `<div class="rail-top"><div class="t">Human control</div><div class="gate">${item.proposal ? `proposal <b>${item.proposal.proposal_id.slice(0,8)}</b> · ${item.proposal.status}` : "prepared work has no customer-facing release"}</div><div class="gate">${desc.cadence} · ${desc.packet}</div></div>
      <div class="actions"><button class="btn approve" id="approve" ${canAct?"":"disabled"}>Approve & send</button><button class="btn" id="edit" ${canAct?"":"disabled"}>Edit draft</button><button class="btn" id="deny" ${canAct?"":"disabled"}>Deny</button></div>
      <div class="edit ${editOpen?"on":""}" id="editBox"><textarea id="editText" placeholder="Make the tone warmer."></textarea><div class="actions" style="padding:8px 0 0"><button class="btn approve" id="saveEdit">Save edit</button></div></div>
      <div class="sec" style="padding:0 15px"><div class="sec-h"><b>Audit ledger</b></div></div><div class="ledger">${ledger.slice(0,14).map(lg).join("")}</div>`;
      const approve = document.getElementById("approve");
      const deny = document.getElementById("deny");
      const edit = document.getElementById("edit");
      const save = document.getElementById("saveEdit");
      if (approve) approve.onclick = () => decide(item, "approved");
      if (deny) deny.onclick = () => decide(item, "denied");
      if (edit) edit.onclick = () => { editOpen = !editOpen; renderRail(); };
      if (save) save.onclick = () => { ledger.unshift({ts:new Date().toISOString(), label:"Revised", detail:document.getElementById("editText").value || "Edit instruction saved"}); editOpen=false; renderRail(); };
    }
    function decide(item, status) {
      if (!item.proposal) return;
      item.proposal.status = status;
      const receipt = receipts.find(r => r.work_item_key === workKey(item));
      if (receipt) { receipt.state = "reviewed"; receipt.label = "Reviewed"; receipt.proposal_status = status; receipt.reason = `The proposal was ${status}.`; }
      ledger.unshift({ts:new Date().toISOString(), label: status === "approved" ? "Approved" : "Denied", detail: `${item.recommended_action || "packet"} · ${accountById.get(item.account_id)?.account_name || ""}`});
      render();
    }
    function lg(e) { return `<div class="lg"><span>${(e.ts || "").slice(11,19)}</span><b>${e.label || e.event}</b><span>${escapeHtml(e.detail || "")}</span></div>`; }
    function escapeHtml(s) { return String(s).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch])); }
    document.getElementById("bookTab").onclick = () => setView("book");
    document.getElementById("todayTab").onclick = () => setView("today");
    document.getElementById("workToday").onclick = () => setView("today");
    document.getElementById("search").oninput = e => { query = e.target.value; renderBookGrid(); };
    render();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
