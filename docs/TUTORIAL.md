# CrewAI + Decision Trace Tutorial

This tutorial teaches you how to use **Decision Trace** in any CrewAI
workflow --- not just this demo.

You will learn:

-   How to identify decision points
-   How to model decisions correctly
-   How to emit events using the SDK
-   How to preserve lineage
-   What best practices to follow
-   What mistakes to avoid

------------------------------------------------------------------------

# What Is Decision Trace?

Decision Trace is not structured logging.

It is a first-class semantic record of a decision.

Each decision event must contain:

1.  Context --- the environmental state
2.  Actor --- who made the decision
3.  Logic --- the checks, rules, or model signals used
4.  Outcome --- the result
5.  Lineage --- causal chain of prior decisions

Whitepaper:\
https://github.com/logicoflife/decision-telemetry-whitepaper/blob/main/pdf/decision-telemetry-v0.4.pdf

SDK:\
https://github.com/logicoflife/decision-trace

DeepWiki:\
https://deepwiki.com/logicoflife/decision-trace

------------------------------------------------------------------------

# Step 1 --- Identify Decision Points

In any CrewAI workflow, ask:

-   Where is a decision made?
-   Where does logic evaluate something?
-   Where is a result chosen?

If a choice is made --- emit a decision.

------------------------------------------------------------------------

# Step 2 --- Model Decisions Using the Universal Structure

Every event must include:

``` json
{
  "decision_id": "uuid",
  "decision_type": "PLAN_EVALUATED_POLICY",
  "timestamp": "ISO8601",
  "context": {...},
  "actor": {...},
  "logic": {...},
  "outcome": {...},
  "lineage": [...]
}
```

Do NOT:

-   Dump raw input data blobs
-   Leave reason codes empty
-   Skip lineage
-   Use placeholder semantics

------------------------------------------------------------------------

# Step 3 --- Emit Events Using the SDK

``` python
from decision_trace.exporters.file import FileJsonlExporter
from decision_trace.tracer import decision

exporter = FileJsonlExporter("out/runs/my_case/.sdk_decision_trace.jsonl")

with decision(
    tenant_id="my-system",
    environment="local",
    decision_type="MODEL_SCORING",
    actor={"id": "RiskModelAgent", "name": "RiskModelAgent", "type": "agent"},
    decision_id="uuid",
    exporter=exporter,
) as ctx:
    ctx.action({
        "context": {"input_id": "abc123"},
        "logic": {
            "model_score": 0.87,
            "threshold": 0.8,
            "reason_codes": [
                {"code": "SCORE_ABOVE_THRESHOLD", "status": "PASS", "explain": "Score 0.87 >= 0.8"}
            ]
        },
        "outcome": {"decision": "APPROVED"},
        "confidence": 0.93,
        "lineage": ["parent-decision-id"]
    })
```

------------------------------------------------------------------------

# Step 4 --- Preserve Lineage

Lineage connects decisions into a trace.

Always reference the parent `decision_id`.

Never reference logs.

------------------------------------------------------------------------

# Step 5 --- Keep Evidence Compact and Meaningful

Good evidence:

-   Short reason codes
-   Clear one-line explanations
-   Compact comparison tables
-   Stable identifiers

Bad evidence:

-   Raw transaction dumps
-   Entire prompt histories
-   Empty reason lists
-   Arbitrary labels like "Option 1"

------------------------------------------------------------------------

# Planner Best Practices

When selecting between candidates, include:

-   candidate_comparison_summary
-   tie_breakers_applied (ordered)
-   rationale (1--2 sentences)

------------------------------------------------------------------------

# Adopter Checklist

Before emitting any decision event:

-   Context references inputs
-   Actor is explicit
-   Logic includes non-empty checks
-   Outcome has a clear status
-   Lineage references existing decision_ids
-   Identifiers are stable
-   Business names are meaningful

------------------------------------------------------------------------

# Final Thought

If your system makes decisions, it should emit decisions.

Logs tell you what happened.

Decision Trace tells you why.
