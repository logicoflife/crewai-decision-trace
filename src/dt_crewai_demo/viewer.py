from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pipeline import CANONICAL_PERSONAS


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def collect_view_data() -> dict[str, Any]:
    personas: dict[str, Any] = {}
    for persona in CANONICAL_PERSONAS:
        run_dir = Path("out/runs") / persona
        personas[persona] = {
            "scorecard": _read_json(run_dir / "scorecard.json"),
            "events": _read_jsonl(run_dir / "decision_trace.jsonl"),
            "plain_log": (run_dir / "plain_trace.log").read_text(encoding="utf-8"),
            "budget_plan": (run_dir / "budget_plan.md").read_text(encoding="utf-8"),
        }
    return {"personas": personas}


def build_offline_viewer() -> Path:
    payload = collect_view_data()
    out_path = Path("out/decision_trace_view.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Decision Trace Viewer</title>
<style>
:root {{
  --bg: #f5f1e7;
  --ink: #1f2933;
  --card: #ffffff;
  --accent: #0d9488;
  --muted: #6b7280;
}}
body {{ margin: 0; font-family: "Source Sans 3", "Helvetica Neue", sans-serif; background: radial-gradient(circle at top right, #d1fae5 0, var(--bg) 45%); color: var(--ink); }}
header {{ padding: 20px 24px; background: linear-gradient(120deg, #0f766e, #14b8a6); color: white; }}
main {{ padding: 20px 24px; display: grid; gap: 16px; }}
.panel {{ background: var(--card); border-radius: 12px; padding: 14px; box-shadow: 0 6px 18px rgba(0,0,0,.08); }}
label, select {{ font-size: 14px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border-bottom: 1px solid #e5e7eb; text-align: left; padding: 8px; vertical-align: top; }}
.timeline-item {{ padding: 8px; border-left: 4px solid var(--accent); margin: 8px 0; cursor: pointer; background: #f9fafb; }}
pre {{ white-space: pre-wrap; word-break: break-word; background: #111827; color: #e5e7eb; padding: 10px; border-radius: 8px; max-height: 320px; overflow: auto; }}
.grid {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
.small {{ color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>
<header>
  <h1>Decision Trace vs Plain Logs</h1>
  <div class=\"small\">Offline self-contained viewer (no fetch calls)</div>
</header>
<main>
  <div class=\"panel\">
    <label for=\"persona\">Persona</label>
    <select id=\"persona\"></select>
  </div>
  <div class=\"grid\">
    <section class=\"panel\"><h2>Scorecard</h2><pre id=\"scorecard\"></pre></section>
    <section class=\"panel\"><h2>Budget Plan</h2><pre id=\"budget\"></pre></section>
  </div>
  <section class=\"panel\">
    <h2>Plan Comparison</h2>
    <table>
      <thead><tr><th>Plan</th><th>Summary</th><th>Policy</th><th>Risk</th><th>Savings</th></tr></thead>
      <tbody id=\"plans\"></tbody>
    </table>
  </section>
  <div class=\"grid\">
    <section class=\"panel\"><h2>Timeline (grouped by agent)</h2><div id=\"timeline\"></div></section>
    <section class=\"panel\"><h2>Event JSON Inspector</h2><pre id=\"event-json\"></pre><h3>Lineage</h3><pre id=\"lineage\"></pre></section>
  </div>
  <section class=\"panel\"><h2>Plain Logs Contrast</h2><pre id=\"plain\"></pre></section>
</main>
<script id=\"embedded-data\" type=\"application/json\">{json.dumps(payload)}</script>
<script>
const db = JSON.parse(document.getElementById('embedded-data').textContent);
const personas = Object.keys(db.personas);
const personaSelect = document.getElementById('persona');
const scorecardEl = document.getElementById('scorecard');
const plansEl = document.getElementById('plans');
const timelineEl = document.getElementById('timeline');
const eventJsonEl = document.getElementById('event-json');
const lineageEl = document.getElementById('lineage');
const plainEl = document.getElementById('plain');
const budgetEl = document.getElementById('budget');

for (const p of personas) {{
  const opt = document.createElement('option');
  opt.value = p;
  opt.textContent = p;
  personaSelect.appendChild(opt);
}}

function render() {{
  const persona = personaSelect.value;
  const data = db.personas[persona];
  const score = data.scorecard;
  scorecardEl.textContent = JSON.stringify({{baseline_spend: score.baseline_spend, target_reduction_amount: score.target_reduction_amount, top_drivers: score.top_drivers, selected_plan: score.selected_plan}}, null, 2);
  budgetEl.textContent = data.budget_plan;
  plainEl.textContent = data.plain_log;

  plansEl.innerHTML = '';
  for (const plan of score.plans) {{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${{plan.plan_name}}</td><td>${{plan.plan_summary}}</td><td>${{plan.policy_status}}</td><td>${{plan.risk_status}}</td><td>${{plan.projected_savings}}</td>`;
    plansEl.appendChild(tr);
  }}

  timelineEl.innerHTML = '';
  const groups = {{}};
  for (const event of data.events) {{
    if (!groups[event.actor]) groups[event.actor] = [];
    groups[event.actor].push(event);
  }}
  for (const [actor, events] of Object.entries(groups)) {{
    const h = document.createElement('h3');
    h.textContent = actor;
    timelineEl.appendChild(h);
    for (const evt of events) {{
      const div = document.createElement('div');
      div.className = 'timeline-item';
      div.textContent = `${{evt.timestamp}} | ${{evt.decision_type}} | ${{evt.outcome.status || evt.outcome.policy_status || evt.outcome.risk_status || ''}}`;
      div.onclick = () => {{
        eventJsonEl.textContent = JSON.stringify(evt, null, 2);
        lineageEl.textContent = JSON.stringify(evt.lineage, null, 2);
      }};
      timelineEl.appendChild(div);
    }}
  }}

  if (data.events.length > 0) {{
    eventJsonEl.textContent = JSON.stringify(data.events[0], null, 2);
    lineageEl.textContent = JSON.stringify(data.events[0].lineage, null, 2);
  }}
}}

personaSelect.value = personas[0];
personaSelect.addEventListener('change', render);
render();
</script>
</body>
</html>
"""

    out_path.write_text(html, encoding="utf-8")
    return out_path
