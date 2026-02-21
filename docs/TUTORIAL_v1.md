# CrewAI Decision Trace Tutorial (v1)

This tutorial teaches you how to integrate Decision Trace into any
CrewAI workflow using the official decorator-based extension pattern.

This document represents the public v1 release model.

------------------------------------------------------------------------

# What Is Decision Trace?

Decision Trace is not structured logging.

It is a first-class semantic record of a decision.

Every emitted decision follows a universal structure:

1. Context — the environmental state at the time of the decision
2. Actor — who (or what) made the decision
3. Logic — the checks, rules, or model signals evaluated
4. Outcome — the final result
5. Lineage — the causal chain of prior decisions

This structure makes agent systems:

- Auditable
- Deterministic
- Explainable
- Queryable

Decision Trace SDK:
https://github.com/logicoflife/decision-trace

Whitepaper (Conceptual Foundation):
https://github.com/logicoflife/decision-telemetry-whitepaper

------------------------------------------------------------------------

# Integration Model Overview

There are two supported integration patterns.

## 1️⃣ Decorator-Based Integration (Recommended)

Use this for CrewAI task functions.

``` python
from crewai_decision_trace import trace_decision, set_default_emitter

set_default_emitter(emitter)

@trace_decision("PLAN_EVALUATED_POLICY")
def evaluate_plan(task):
    return {
        "decision_id": "...",
        "decision_type": "PLAN_EVALUATED_POLICY",
        "timestamp": "...",
        "context": {...},
        "actor": {...},
        "logic": {...},
        "outcome": {...},
        "lineage": [...]
    }
```

The decorator:

-   Automatically emits the event
-   Preserves the universal schema
-   Prevents double emission
-   Keeps business logic clean
-   Requires zero viewer changes

------------------------------------------------------------------------

## 2️⃣ Direct SDK Control (Advanced)

Use this when you need nested scopes or advanced exporter control.

``` python
from decision_trace.exporters.file import FileJsonlExporter
from decision_trace.tracer import decision
```

------------------------------------------------------------------------

# Using Decision Trace as a CrewAI Tool Extension

You can expose decision logging as an agent tool.

``` python
from crewai_decision_trace.tools import DecisionLoggingTool
```

This allows agents to log mid-process reasoning and policy checks
explicitly.

------------------------------------------------------------------------

# Best Practices

-   Never emit raw data dumps
-   Always include reason codes
-   Always preserve lineage
-   Keep evidence compact
-   Avoid duplicate emissions
-   Verify outputs before release

------------------------------------------------------------------------

# Final Principle

If your system makes decisions, it should emit decisions.

Logs tell you what happened. Decision Trace tells you why.
