from pathlib import Path
import json

from dt_crewai_demo.pipeline import CANONICAL_PERSONAS


FORBIDDEN = ("Plan A", "Plan B", "Plan C", "Option 1", "Option 2")


def test_offline_viewer_exists_and_embeds_data():
    viewer = Path("out/decision_trace_view.html")
    assert viewer.exists()
    html = viewer.read_text(encoding="utf-8")
    assert "embedded-data" in html
    for persona in CANONICAL_PERSONAS:
        assert persona in html


def test_no_placeholder_labels_in_user_fields():
    for persona in CANONICAL_PERSONAS:
        events = [
            json.loads(line)
            for line in (Path("out/runs") / persona / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        blob = json.dumps(events)
        for token in FORBIDDEN:
            assert token not in blob
