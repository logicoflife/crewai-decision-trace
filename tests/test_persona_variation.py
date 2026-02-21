from pathlib import Path
import json

from dt_crewai_demo.pipeline import CANONICAL_PERSONAS


def test_persona_variation_exists():
    selected = []
    drivers = []
    for persona in CANONICAL_PERSONAS:
        scorecard = json.loads((Path("out/runs") / persona / "scorecard.json").read_text(encoding="utf-8"))
        selected.append(scorecard["selected_plan"]["plan_name"])
        drivers.append(tuple(d["category"] for d in scorecard["top_drivers"]))
    assert len(set(selected)) > 1 or len(set(drivers)) > 1
