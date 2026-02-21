from pathlib import Path
import json

from dt_crewai_demo.pipeline import CANONICAL_PERSONAS, REQUIRED_FIELDS


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_event_counts_and_required_fields():
    expected = {
        "PLAN_PROPOSED": 3,
        "PLAN_EVALUATED_POLICY": 3,
        "PLAN_EVALUATED_RISK": 3,
        "FINAL_PLAN_SELECTED": 1,
        "BUDGET_PLAN_PUBLISHED": 1,
    }
    for persona in CANONICAL_PERSONAS:
        events = read_jsonl(Path("out/runs") / persona / "decision_trace.jsonl")
        counts = {}
        ids = set()
        for event in events:
            for field in REQUIRED_FIELDS:
                assert field in event
            ids.add(event["decision_id"])
            counts[event["decision_type"]] = counts.get(event["decision_type"], 0) + 1

        for decision_type, count in expected.items():
            assert counts.get(decision_type, 0) == count

        for event in events:
            for parent in event["lineage"]:
                assert parent in ids


def test_whitepaper_semantics_present():
    for persona in CANONICAL_PERSONAS:
        events = read_jsonl(Path("out/runs") / persona / "decision_trace.jsonl")
        for event in events:
            assert isinstance(event["context"], dict)
            assert isinstance(event["evidence"], dict)
            assert isinstance(event["outcome"], dict)
            assert isinstance(event["lineage"], list)

            if event["decision_type"] == "PLAN_EVALUATED_POLICY":
                assert event["evidence"]["reason_codes"]
            if event["decision_type"] == "PLAN_EVALUATED_RISK":
                assert event["evidence"]["reason_codes"]
            if event["decision_type"] == "FINAL_PLAN_SELECTED":
                assert event["evidence"]["tie_breakers_applied"]
                assert event["evidence"]["candidate_comparison_summary"]
                assert event["evidence"]["rationale"]
