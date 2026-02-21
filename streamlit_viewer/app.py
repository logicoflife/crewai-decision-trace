from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode


st.set_page_config(layout="wide", page_title="Decision Trace Demo")

st.markdown(
    """
<style>
.stApp {
  background-color: #f4f6f8;
}
.block-container {
  padding-top: 1.2rem;
  padding-bottom: 1.5rem;
  max-width: 1400px;
}
.card {
  background: white;
  border: 1px solid #e6e9ee;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.card-title {
  font-weight: 650;
  font-size: 1.02rem;
  margin-bottom: 0.35rem;
}
.muted {
  color: #5f6b7a;
  font-size: 0.92rem;
}
.kpi-value {
  font-size: 1.4rem;
  font-weight: 700;
}
.callout {
  background: #eef6ff;
  border: 1px solid #cfe4ff;
  border-radius: 10px;
  padding: 10px 12px;
}
</style>
""",
    unsafe_allow_html=True,
)


def discover_personas(runs_root: Path) -> list[str]:
    if not runs_root.exists():
        return []
    return sorted([p.name for p in runs_root.iterdir() if p.is_dir()])


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    except Exception:
        return []
    return events


def read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def safe_get(obj: Any, keys: list[str], default: Any = None) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def compute_human_summary(event: dict[str, Any]) -> str:
    actor = event.get("actor", "Unknown actor")
    decision_type = event.get("decision_type", "Unknown decision")
    timestamp = event.get("timestamp", "Unknown time")
    outcome = event.get("outcome", {})
    status = (
        outcome.get("status")
        or outcome.get("policy_status")
        or outcome.get("risk_status")
        or "N/A"
    )
    return f"{actor} emitted {decision_type} at {timestamp} with status {status}."


def _event_label(event: dict[str, Any]) -> str:
    decision_id = str(event.get("decision_id", ""))
    short_decision_id = decision_id[:8] if decision_id else "no-id"
    return (
        f"{event.get('timestamp', 'N/A')} • "
        f"{event.get('actor', 'N/A')} • "
        f"{event.get('decision_type', 'N/A')} • "
        f"{short_decision_id}"
    )


def _event_key(event: dict[str, Any], index: int) -> str:
    decision_id = str(event.get("decision_id", "")).strip()
    if decision_id:
        return decision_id
    return (
        f"{event.get('timestamp', 'N/A')}|"
        f"{event.get('actor', 'N/A')}|"
        f"{event.get('decision_type', 'N/A')}|"
        f"{index}"
    )


def _event_needles(event: dict[str, Any]) -> list[str]:
    needles = [
        str(event.get("decision_id", "")),
        str(event.get("actor", "")),
        str(event.get("decision_type", "")),
    ]
    plan_name = safe_get(event, ["outcome", "selected_plan_name"], "")
    if isinstance(plan_name, str) and plan_name:
        needles.append(plan_name)
    return [n for n in needles if n]


def find_log_snippet(log_text: str, needles: list[str], radius: int = 16) -> str:
    lines = log_text.splitlines()
    if not lines:
        return "No plain logs available."

    hit_index = None
    for idx, line in enumerate(lines):
        if any(needle and needle in line for needle in needles):
            hit_index = idx
            break

    if hit_index is None:
        return "No related snippet found for selected event."

    start = max(0, hit_index - radius)
    end = min(len(lines), hit_index + radius + 1)
    snippet = "\n".join(lines[start:end])
    return snippet or "No related snippet found for selected event."


def _selected_rows_from_aggrid(response: dict[str, Any]) -> list[dict[str, Any]]:
    selected = response.get("selected_rows", [])
    if isinstance(selected, list):
        return [row for row in selected if isinstance(row, dict)]
    if hasattr(selected, "to_dict"):
        try:
            rows = selected.to_dict(orient="records")
            return [row for row in rows if isinstance(row, dict)]
        except Exception:
            return []
    return []


runs_root = Path("out/runs")
personas = discover_personas(runs_root)
print(f"personas discovered: {len(personas)}")

st.sidebar.header("Controls")
if not personas:
    st.error("No runs found. Execute `make demo_all` first.")
    st.stop()

persona = st.sidebar.selectbox("Persona", personas)
run_dir = runs_root / persona

scorecard_path = run_dir / "scorecard.json"
trace_path = run_dir / "decision_trace.jsonl"
logs_path = run_dir / "plain_trace.log"
budget_path = run_dir / "budget_plan.md"

scorecard = read_json(scorecard_path)
events = read_jsonl(trace_path)
plain_log = read_text(logs_path) or ""
budget_plan = read_text(budget_path)

print(f"scorecard loaded: {scorecard is not None}")
print(f"timeline loaded: {len(events)} events")

st.sidebar.markdown("### Artifact Status")
for label, path in [
    ("decision_trace.jsonl", trace_path),
    ("scorecard.json", scorecard_path),
    ("plain_trace.log", logs_path),
    ("budget_plan.md", budget_path),
]:
    icon = "✅" if path.exists() else "⚠️"
    st.sidebar.write(f"{icon} {label}")

search_text = st.sidebar.text_input("Search", placeholder="actor / decision_type / decision_id")
auto_select_key = st.sidebar.checkbox("Auto-select key event (FINAL_PLAN_SELECTED)", value=True)

actors = sorted({str(e.get("actor", "")) for e in events if e.get("actor")})
decision_types = sorted({str(e.get("decision_type", "")) for e in events if e.get("decision_type")})

selected_actors = st.sidebar.multiselect("Actor filter", actors, default=actors)
selected_types = st.sidebar.multiselect("Decision Type filter", decision_types, default=decision_types)

filtered_events: list[dict[str, Any]] = []
for event in events:
    actor = str(event.get("actor", ""))
    dtype = str(event.get("decision_type", ""))
    decision_id = str(event.get("decision_id", ""))
    haystack = f"{actor} {dtype} {decision_id}".lower()
    if selected_actors and actor not in selected_actors:
        continue
    if selected_types and dtype not in selected_types:
        continue
    if search_text and search_text.lower() not in haystack:
        continue
    filtered_events.append(event)

st.title("Decision Trace Demo")
st.caption("Inspect decisions by persona, compare explainable trace data with plain logs, and review the final budget plan.")

k1, k2, k3, k4 = st.columns(4)
baseline = safe_get(scorecard, ["baseline_spend"], None)
target = safe_get(scorecard, ["target_reduction_amount"], None)
selected_plan = safe_get(scorecard, ["selected_plan", "plan_name"], "N/A")
selected_risk = safe_get(scorecard, ["selected_plan", "risk_status"], "N/A")

with k1:
    st.markdown('<div class="card"><div class="card-title">Baseline Spend</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value">${baseline:,.2f}</div>' if isinstance(baseline, (int, float)) else '<div class="kpi-value">N/A</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
with k2:
    st.markdown('<div class="card"><div class="card-title">Target Reduction</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value">${target:,.2f}</div>' if isinstance(target, (int, float)) else '<div class="kpi-value">N/A</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
with k3:
    st.markdown('<div class="card"><div class="card-title">Selected Plan</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value" style="font-size:1.05rem;">{selected_plan}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
with k4:
    st.markdown('<div class="card"><div class="card-title">Risk</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value">{selected_risk}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

plans = safe_get(scorecard, ["plans"], []) if isinstance(scorecard, dict) else []
if isinstance(plans, list) and plans:
    df_plans = pd.DataFrame(plans)
    wanted_cols = [
        "plan_name",
        "projected_savings",
        "policy_status",
        "risk_status",
        "savings_transfer_amount",
    ]
    plan_cols = [c for c in wanted_cols if c in df_plans.columns]
    if plan_cols:
        st.markdown('<div class="card-title">Plans</div>', unsafe_allow_html=True)
        st.dataframe(df_plans[plan_cols], use_container_width=True, hide_index=True)

trace_tab, logs_tab, budget_tab = st.tabs(["Decision Trace", "Plain Logs (Compare)", "Budget Plan"])

with trace_tab:
    left, right = st.columns([1.3, 1.1])
    selected_event = None

    with left:
        st.markdown('<div class="card-title">Timeline</div>', unsafe_allow_html=True)
        if not filtered_events:
            st.warning("No events match current filters.")
            st.session_state.pop("selected_event_key", None)
        else:
            timeline_rows = [
                {
                    "event_key": _event_key(e, idx),
                    "timestamp": e.get("timestamp", ""),
                    "actor": e.get("actor", ""),
                    "decision_type": e.get("decision_type", ""),
                    "outcome_status": safe_get(e, ["outcome", "status"], None)
                    or safe_get(e, ["outcome", "policy_status"], None)
                    or safe_get(e, ["outcome", "risk_status"], None)
                    or "",
                }
                for idx, e in enumerate(filtered_events)
            ]
            timeline_df = pd.DataFrame(timeline_rows)
            key_to_event = {row["event_key"]: event for row, event in zip(timeline_rows, filtered_events)}

            default_key = timeline_rows[0]["event_key"]
            if auto_select_key:
                for idx, e in enumerate(filtered_events):
                    if e.get("decision_type") == "FINAL_PLAN_SELECTED":
                        default_key = timeline_rows[idx]["event_key"]
                        break

            current_key = st.session_state.get("selected_event_key")
            if current_key not in key_to_event:
                st.session_state["selected_event_key"] = default_key

            selected_key = st.session_state["selected_event_key"]
            selected_index_list = timeline_df.index[timeline_df["event_key"] == selected_key].tolist()
            pre_selected_rows = selected_index_list[:1]

            gb = GridOptionsBuilder.from_dataframe(timeline_df)
            gb.configure_column("event_key", hide=True)
            gb.configure_selection(
                selection_mode="single",
                use_checkbox=False,
                pre_selected_rows=pre_selected_rows,
            )
            gb.configure_grid_options(suppressRowClickSelection=False, rowSelection="single")
            grid_options = gb.build()
            grid_response = AgGrid(
                timeline_df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                fit_columns_on_grid_load=True,
                allow_unsafe_jscode=False,
                theme="streamlit",
                height=320,
                key="timeline_aggrid",
            )

            selected_rows = _selected_rows_from_aggrid(grid_response)
            if selected_rows:
                picked_key = str(selected_rows[0].get("event_key", ""))
                if picked_key in key_to_event:
                    st.session_state["selected_event_key"] = picked_key

            selected_event = key_to_event.get(st.session_state["selected_event_key"], filtered_events[0])

    with right:
        st.markdown('<div class="card-title">Decision Inspector</div>', unsafe_allow_html=True)
        if not selected_event:
            st.info("Choose an event to inspect.")
        else:
            st.caption(f"Selected: {_event_label(selected_event)}")
            outcome = selected_event.get("outcome", {})
            status = (
                safe_get(selected_event, ["outcome", "status"], "")
                or safe_get(selected_event, ["outcome", "policy_status"], "")
                or safe_get(selected_event, ["outcome", "risk_status"], "")
                or "N/A"
            )

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">Decision Summary</div>', unsafe_allow_html=True)
            st.write(f"**Actor:** {selected_event.get('actor', 'N/A')}")
            st.write(f"**Decision Type:** {selected_event.get('decision_type', 'N/A')}")
            st.write(f"**Outcome Status:** {status}")
            st.markdown(f"<div class='muted'>{compute_human_summary(selected_event)}</div>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            tie_breakers = safe_get(selected_event, ["evidence", "tie_breakers_applied"], [])
            rationale = safe_get(selected_event, ["evidence", "rationale"], "")
            if tie_breakers or rationale:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="card-title">Why?</div>', unsafe_allow_html=True)
                if tie_breakers:
                    st.write("**Tie-breakers applied:**")
                    for item in tie_breakers:
                        st.write(f"- {item}")
                if rationale:
                    st.write(f"**Rationale:** {rationale}")
                st.markdown('</div>', unsafe_allow_html=True)

            reason_codes = safe_get(selected_event, ["evidence", "reason_codes"], [])
            if isinstance(reason_codes, list) and reason_codes:
                st.markdown('<div class="card-title">Evidence Highlights</div>', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(reason_codes), use_container_width=True, hide_index=True)

            candidates = safe_get(selected_event, ["evidence", "candidate_comparison_summary"], [])
            if isinstance(candidates, list) and candidates:
                st.write("**Candidate Comparison**")
                st.dataframe(pd.DataFrame(candidates), use_container_width=True, hide_index=True)

            lineage = selected_event.get("lineage", []) if isinstance(selected_event.get("lineage"), list) else []
            st.write(f"**Lineage links:** {len(lineage)}")
            with st.expander("Lineage IDs"):
                if lineage:
                    st.code("\n".join(lineage), language="text")
                else:
                    st.write("No lineage links.")

            with st.expander("Raw Event JSON"):
                raw = json.dumps(selected_event, indent=2, sort_keys=True)
                st.code(raw, language="json")
                st.download_button(
                    "Download JSON",
                    data=raw,
                    file_name=f"{selected_event.get('decision_id', 'event')}.json",
                    mime="application/json",
                    key=f"download_{selected_event.get('decision_id', 'event')}",
                )

with logs_tab:
    st.markdown('<div class="card-title">Plain Logs</div>', unsafe_allow_html=True)
    st.text_area("Full logs", value=plain_log or "No log file found.", height=320)

    snippet = "No related snippet available."
    if filtered_events:
        default_event = filtered_events[0]
        snippet = find_log_snippet(plain_log, _event_needles(default_event), radius=20)
        if 'selected_event' in locals() and selected_event:
            snippet = find_log_snippet(plain_log, _event_needles(selected_event), radius=20)

    st.markdown('<div class="card-title">Related Snippet</div>', unsafe_allow_html=True)
    st.code(snippet, language="text")

    st.markdown(
        """
<div class="callout">
<b>What logs don’t provide</b>
<ul>
  <li>Explicit lineage links across decisions</li>
  <li>Structured policy/risk reason codes for easy analysis</li>
  <li>Planner tie-breakers and rationale in a queryable form</li>
</ul>
</div>
""",
        unsafe_allow_html=True,
    )

with budget_tab:
    st.markdown('<div class="card-title">Budget Plan</div>', unsafe_allow_html=True)
    if budget_plan:
        st.markdown(budget_plan)
    else:
        st.info("Budget plan artifact is missing for this persona.")
