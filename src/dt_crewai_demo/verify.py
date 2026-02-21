from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pipeline import CANONICAL_PERSONAS, REQUIRED_FIELDS

COUNTS_EXPECTED = {
    "PLAN_PROPOSED": 3,
    "PLAN_EVALUATED_POLICY": 3,
    "PLAN_EVALUATED_RISK": 3,
    "FINAL_PLAN_SELECTED": 1,
    "BUDGET_PLAN_PUBLISHED": 1,
}

FORBIDDEN_PLACEHOLDER_TOKENS = (
    "Plan A",
    "Plan B",
    "Plan C",
    "Option 1",
    "Option 2",
    "Option 3",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _contains_placeholder(obj: Any) -> bool:
    if isinstance(obj, str):
        return any(token in obj for token in FORBIDDEN_PLACEHOLDER_TOKENS)
    if isinstance(obj, list):
        return any(_contains_placeholder(item) for item in obj)
    if isinstance(obj, dict):
        return any(_contains_placeholder(v) for v in obj.values())
    return False


def _validate_event_fields(events: list[dict[str, Any]]) -> None:
    for event in events:
        for field in REQUIRED_FIELDS:
            if field not in event:
                raise AssertionError(f"Missing field {field} in event {event}")
        if not isinstance(event["lineage"], list):
            raise AssertionError("lineage must be a list")


def _validate_counts(events: list[dict[str, Any]]) -> None:
    by_type: dict[str, int] = {}
    for event in events:
        by_type[event["decision_type"]] = by_type.get(event["decision_type"], 0) + 1
    for key, expected in COUNTS_EXPECTED.items():
        got = by_type.get(key, 0)
        if got != expected:
            raise AssertionError(f"Expected {expected} {key} events, found {got}")


def _validate_lineage(events: list[dict[str, Any]]) -> None:
    ids = {e["decision_id"] for e in events}
    for event in events:
        for parent in event["lineage"]:
            if parent not in ids:
                raise AssertionError(f"Unknown lineage decision_id {parent}")


def _validate_semantics(events: list[dict[str, Any]]) -> None:
    for event in events:
        if _contains_placeholder(event):
            raise AssertionError("Found placeholder semantics in decision trace")

        if event["decision_type"] == "PLAN_EVALUATED_POLICY":
            reason_codes = event["evidence"].get("reason_codes", [])
            if not reason_codes:
                raise AssertionError("Policy event must include non-empty reason_codes")
        if event["decision_type"] == "PLAN_EVALUATED_RISK":
            reason_codes = event["evidence"].get("reason_codes", [])
            if not reason_codes:
                raise AssertionError("Risk event must include non-empty reason_codes")
        if event["decision_type"] == "FINAL_PLAN_SELECTED":
            tie = event["evidence"].get("tie_breakers_applied", [])
            rationale = event["evidence"].get("rationale", "")
            summary = event["evidence"].get("candidate_comparison_summary", [])
            if not tie:
                raise AssertionError("Planner must emit tie_breakers_applied")
            if not rationale:
                raise AssertionError("Planner must emit rationale")
            if not summary:
                raise AssertionError("Planner must emit candidate_comparison_summary")


def verify_outputs() -> None:
    selected_plan_names: list[str] = []
    driver_sets: list[tuple[str, ...]] = []

    for persona in CANONICAL_PERSONAS:
        run_dir = Path("out/runs") / persona
        if not run_dir.exists():
            raise AssertionError(f"Missing run output directory for {persona}")

        required = [
            run_dir / "plain_trace.log",
            run_dir / "decision_trace.jsonl",
            run_dir / "budget_plan.md",
            run_dir / "scorecard.json",
        ]
        for path in required:
            if not path.exists():
                raise AssertionError(f"Missing required artifact: {path}")

        events = read_jsonl(run_dir / "decision_trace.jsonl")
        _validate_event_fields(events)
        _validate_counts(events)
        _validate_lineage(events)
        _validate_semantics(events)

        scorecard = read_json(run_dir / "scorecard.json")
        selected_plan_names.append(scorecard["selected_plan"]["plan_name"])
        driver_sets.append(tuple(item["category"] for item in scorecard["top_drivers"]))

    if len(set(selected_plan_names)) == 1 and len(set(driver_sets)) == 1:
        raise AssertionError("Persona variation invariant failed: selected plans and drivers are identical")

    viewer_path = Path("out/decision_trace_view.html")
    if not viewer_path.exists():
        raise AssertionError("Offline viewer file out/decision_trace_view.html is missing")

    html = viewer_path.read_text(encoding="utf-8")
    if "embedded-data" not in html:
        raise AssertionError("Offline viewer must embed persona data")


if __name__ == "__main__":
    verify_outputs()
    print("Verification passed")
