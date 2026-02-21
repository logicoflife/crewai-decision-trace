from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from crewai_decision_trace import set_default_emitter, trace_decision
from crewai import Agent, Crew, Process, Task
from crewai.llms.base_llm import BaseLLM
from decision_trace.exporters.file import FileJsonlExporter
from decision_trace.tracer import decision

CANONICAL_PERSONAS = ("movie_buff", "sports_fan", "foodie")
CANONICAL_INPUTS = (
    Path("data/personas/movie_buff/transactions.csv"),
    Path("data/personas/sports_fan/transactions.csv"),
    Path("data/personas/foodie/transactions.csv"),
    Path("data/constraints.yaml"),
)
REQUIRED_FIELDS = (
    "decision_id",
    "timestamp",
    "actor",
    "decision_type",
    "context",
    "evidence",
    "outcome",
    "confidence",
    "lineage",
)


@dataclass(frozen=True)
class Transaction:
    date: str
    category: str
    merchant: str
    amount: float


class DeterministicLLM(BaseLLM):
    """Local non-network LLM to keep CrewAI orchestration offline."""

    def __init__(self) -> None:
        super().__init__(model="deterministic/local", provider="local")

    def call(self, messages, **kwargs):  # type: ignore[override]
        if isinstance(messages, str):
            content = messages
        else:
            content = "\n".join(str(m.get("content", "")) for m in messages)
        if "SpendAnalystAgent" in content:
            return "Spend analysis task acknowledged."
        if "OptimizationAgent" in content:
            return "Optimization task acknowledged."
        if "PolicyGuardAgent" in content:
            return "Policy evaluation task acknowledged."
        if "RiskFeasibilityAgent" in content:
            return "Risk evaluation task acknowledged."
        if "PlannerAgent" in content:
            return "Planning task acknowledged."
        return "Task acknowledged."


class DecisionTraceEmitter:
    def __init__(self, persona: str, output_path: Path, sdk_path: Path):
        self.persona = persona
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.output_path.open("w", encoding="utf-8")
        self._sdk_exporter = FileJsonlExporter(str(sdk_path))

    def close(self) -> None:
        self._file.close()

    def emit(self, event: dict[str, Any]) -> None:
        for field in REQUIRED_FIELDS:
            if field not in event:
                raise ValueError(f"Missing required field: {field}")

        actor_name = event["actor"]
        parent = event["lineage"][0] if event["lineage"] else None
        with decision(
            tenant_id="dt-crewai-demo",
            environment="local",
            decision_type=event["decision_type"],
            actor={"id": actor_name, "type": "agent"},
            decision_id=event["decision_id"],
            parent_decision_id=parent,
            exporter=self._sdk_exporter,
            validate=False,
        ) as ctx:
            ctx.action(
                {
                    "context": event["context"],
                    "evidence": event["evidence"],
                    "outcome": event["outcome"],
                    "confidence": event["confidence"],
                    "lineage": event["lineage"],
                }
            )

        self._file.write(json.dumps(event, sort_keys=True) + "\n")
        self._file.flush()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_decision_id() -> str:
    return str(uuid.uuid4())


def load_transactions(path: Path) -> list[Transaction]:
    rows: list[Transaction] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                Transaction(
                    date=row["date"],
                    category=row["category"],
                    merchant=row["merchant"],
                    amount=float(row["amount"]),
                )
            )
    return rows


def load_constraints(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("constraints.yaml must parse to object")
    return data


def build_agents() -> dict[str, Agent]:
    llm = DeterministicLLM()
    return {
        "SpendAnalystAgent": Agent(
            role="SpendAnalystAgent",
            goal="Compute baseline spend and top discretionary drivers",
            backstory="Deterministic financial analyst",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        ),
        "OptimizationAgent": Agent(
            role="OptimizationAgent",
            goal="Propose exactly three deterministic plans",
            backstory="Deterministic optimizer",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        ),
        "PolicyGuardAgent": Agent(
            role="PolicyGuardAgent",
            goal="Evaluate each plan against policy constraints",
            backstory="Deterministic policy checker",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        ),
        "RiskFeasibilityAgent": Agent(
            role="RiskFeasibilityAgent",
            goal="Evaluate each plan for feasibility and concentration risk",
            backstory="Deterministic risk assessor",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        ),
        "PlannerAgent": Agent(
            role="PlannerAgent",
            goal="Select final plan using explicit tie-breakers",
            backstory="Deterministic planner",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        ),
    }


def build_crew(agents: dict[str, Agent], persona: str) -> Crew:
    tasks = [
        Task(
            description=f"Persona {persona}: SpendAnalystAgent prepares baseline and drivers.",
            expected_output="Spend analysis acknowledgment",
            agent=agents["SpendAnalystAgent"],
        ),
        Task(
            description=f"Persona {persona}: OptimizationAgent drafts three plans.",
            expected_output="Optimization acknowledgment",
            agent=agents["OptimizationAgent"],
        ),
        Task(
            description=f"Persona {persona}: PolicyGuardAgent checks constraints.",
            expected_output="Policy acknowledgment",
            agent=agents["PolicyGuardAgent"],
        ),
        Task(
            description=f"Persona {persona}: RiskFeasibilityAgent checks risk.",
            expected_output="Risk acknowledgment",
            agent=agents["RiskFeasibilityAgent"],
        ),
        Task(
            description=f"Persona {persona}: PlannerAgent selects final plan.",
            expected_output="Planner acknowledgment",
            agent=agents["PlannerAgent"],
        ),
    ]
    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )


def category_totals(transactions: list[Transaction]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for t in transactions:
        if t.category == "Income":
            continue
        totals[t.category] = totals.get(t.category, 0.0) + t.amount
    return totals


def discretionary_drivers(totals: dict[str, float], protected: set[str]) -> list[tuple[str, float]]:
    pairs = [(c, v) for c, v in totals.items() if c not in protected and c != "Income"]
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return pairs


def _choose_cut_categories(drivers: list[tuple[str, float]], count: int) -> list[str]:
    selected: list[str] = []
    for cat, _ in drivers:
        if cat in {"Groceries"}:
            continue
        selected.append(cat)
        if len(selected) == count:
            break
    return selected


def build_plans(totals: dict[str, float], drivers: list[tuple[str, float]], constraints: dict[str, Any]) -> list[dict[str, Any]]:
    selected = _choose_cut_categories(drivers, 4)
    while len(selected) < 4:
        fallback = [cat for cat in sorted(totals) if cat not in selected and cat not in {"Income", "Groceries", "Rent", "Utilities", "Healthcare", "Savings"}]
        if not fallback:
            break
        selected.append(fallback[0])

    p1_primary = selected[0] if selected else "Dining"
    p1_secondary = selected[1] if len(selected) > 1 else p1_primary
    p2_primary = selected[2] if len(selected) > 2 else p1_secondary
    p2_secondary = selected[3] if len(selected) > 3 else p2_primary

    plans = [
        {
            "plan_id": "focused_trim_and_savings_shift",
            "plan_name": f"Reduce {p1_primary} and {p1_secondary} with aggressive savings transfer",
            "plan_summary": f"Cut {p1_primary} deeply, trim {p1_secondary}, and route most savings into reserves.",
            "cuts": {p1_primary: 0.35, p1_secondary: 0.25},
        },
        {
            "plan_id": "targeted_lifestyle_rebalance",
            "plan_name": f"Rebalance {p2_primary} and {p2_secondary} with moderate cutbacks",
            "plan_summary": f"Spread moderate reductions across {p2_primary} and {p2_secondary} to protect consistency.",
            "cuts": {p2_primary: 0.25, p2_secondary: 0.2},
        },
        {
            "plan_id": "broad_based_efficiency_plan",
            "plan_name": f"Broad efficiency plan across {p1_primary}, {p2_primary}, and {p1_secondary}",
            "plan_summary": f"Use lighter reductions across three discretionary categories for behavioral feasibility.",
            "cuts": {p1_primary: 0.2, p2_primary: 0.2, p1_secondary: 0.15},
        },
    ]

    pct = float(constraints["savings_transfer"]["percentage"])
    for plan in plans:
        projected_savings = 0.0
        for cat, cut_pct in plan["cuts"].items():
            projected_savings += totals.get(cat, 0.0) * cut_pct
        plan["projected_savings"] = round(projected_savings, 2)
        plan["savings_transfer_amount"] = round(projected_savings * pct, 2)
        plan["category_changes"] = len(plan["cuts"])
    return plans


def evaluate_policy(plan: dict[str, Any], totals: dict[str, float], constraints: dict[str, Any]) -> dict[str, Any]:
    protected = set(constraints["protected_categories"])
    checks = []

    protected_changed = any(cat in protected for cat in plan["cuts"])
    checks.append(
        {
            "code": "PROTECTED_CATEGORIES_UNCHANGED",
            "status": "FAIL" if protected_changed else "PASS",
            "explain": "Protected categories remain unchanged." if not protected_changed else "Plan attempts to cut a protected category.",
        }
    )

    groceries_total = totals.get("Groceries", 0.0)
    groceries_cut = plan["cuts"].get("Groceries", 0.0)
    groceries_after = groceries_total * (1 - groceries_cut)
    groceries_ok = groceries_after >= float(constraints["min_groceries"])
    checks.append(
        {
            "code": "GROCERY_MINIMUM_MET",
            "status": "PASS" if groceries_ok else "FAIL",
            "explain": f"Projected groceries {groceries_after:.2f} must be at least {float(constraints['min_groceries']):.2f}.",
        }
    )

    max_changes_ok = plan["category_changes"] <= int(constraints["max_category_changes"])
    checks.append(
        {
            "code": "MAX_CATEGORY_CHANGES_WITHIN_LIMIT",
            "status": "PASS" if max_changes_ok else "FAIL",
            "explain": f"Plan changes {plan['category_changes']} categories; limit is {int(constraints['max_category_changes'])}.",
        }
    )

    transfer_enabled = bool(constraints["savings_transfer"]["enabled"])
    required_pct = float(constraints["savings_transfer"]["percentage"])
    expected_transfer = round(plan["projected_savings"] * required_pct, 2)
    transfer_ok = (not transfer_enabled) or plan["savings_transfer_amount"] >= expected_transfer
    checks.append(
        {
            "code": "SAVINGS_TRANSFER_RULE_APPLIED",
            "status": "PASS" if transfer_ok else "FAIL",
            "explain": f"Savings transfer is {plan['savings_transfer_amount']:.2f} and required minimum is {expected_transfer:.2f}.",
        }
    )

    policy_status = "ACCEPT" if all(c["status"] == "PASS" for c in checks) else "REJECT"
    return {"policy_status": policy_status, "checks": checks}


def evaluate_risk(plan: dict[str, Any], totals: dict[str, float], constraints: dict[str, Any]) -> dict[str, Any]:
    checks = []

    cut_limit = float(constraints["single_category_cut_limit_pct"])
    over_limit = [cat for cat, cut in plan["cuts"].items() if cut > cut_limit]
    checks.append(
        {
            "code": "SINGLE_CATEGORY_CUT_LIMIT_RESPECTED" if not over_limit else "SINGLE_CATEGORY_CUT_LIMIT_EXCEEDED",
            "status": "PASS" if not over_limit else "FAIL",
            "explain": "No category exceeds the single-category cut limit." if not over_limit else f"Categories over cut limit: {', '.join(sorted(over_limit))}.",
        }
    )

    category_savings = {cat: round(totals.get(cat, 0.0) * pct, 2) for cat, pct in plan["cuts"].items()}
    total_savings = sum(category_savings.values())
    largest_share = 0.0
    if total_savings > 0:
        largest_share = max(value / total_savings for value in category_savings.values())
    concentration_limit = float(constraints["overconcentration_limit_pct"])
    concentrated = largest_share > concentration_limit
    checks.append(
        {
            "code": "OVERCONCENTRATION_LIMIT_OK" if not concentrated else "OVERCONCENTRATION_LIMIT_EXCEEDED",
            "status": "PASS" if not concentrated else "WARN",
            "explain": f"Largest category contributes {largest_share:.2%} of savings vs limit {concentration_limit:.2%}.",
        }
    )

    avg_cut = sum(plan["cuts"].values()) / len(plan["cuts"]) if plan["cuts"] else 0.0
    behavioral_warn = avg_cut > 0.25
    checks.append(
        {
            "code": "BEHAVIORAL_REALISM_PLAUSIBLE" if not behavioral_warn else "BEHAVIORAL_REALISM_STRETCH",
            "status": "PASS" if not behavioral_warn else "WARN",
            "explain": f"Average category cut is {avg_cut:.2%}; higher cuts are harder to sustain.",
        }
    )

    statuses = {c["status"] for c in checks}
    if "FAIL" in statuses:
        risk_status = "REJECT"
    elif "WARN" in statuses:
        risk_status = "WARN"
    else:
        risk_status = "OK"

    return {
        "risk_status": risk_status,
        "checks": checks,
        "largest_savings_share": round(largest_share, 4),
    }


def select_plan(plans: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    risk_rank = {"OK": 0, "WARN": 1, "REJECT": 2}
    candidates = [p for p in plans if p["policy"]["policy_status"] == "ACCEPT"]
    if not candidates:
        candidates = list(plans)

    candidates_sorted = sorted(
        candidates,
        key=lambda p: (
            risk_rank[p["risk"]["risk_status"]],
            -p["projected_savings"],
            p["plan_id"],
        ),
    )
    selected = candidates_sorted[0]

    comparison = [
        {
            "plan_id": p["plan_id"],
            "plan_name": p["plan_name"],
            "policy": p["policy"]["policy_status"],
            "risk": p["risk"]["risk_status"],
            "projected_savings": p["projected_savings"],
        }
        for p in candidates_sorted
    ]
    details = {
        "candidates": comparison,
        "tie_breakers_applied": [
            "policy_acceptance",
            "risk_preference_ok_over_warn",
            "projected_savings_desc",
            "lexicographic_plan_id",
        ],
        "rationale": (
            f"{selected['plan_name']} won because it satisfied policy and had the best risk-adjusted savings among candidates. "
            "Tie-breakers resolved any remaining ordering deterministically."
        ),
    }
    return selected, details


@trace_decision()
def _event(
    actor: str,
    decision_type: str,
    context: dict[str, Any],
    evidence: dict[str, Any],
    outcome: dict[str, Any],
    confidence: float,
    lineage: list[str],
) -> dict[str, Any]:
    return {
        "decision_id": new_decision_id(),
        "timestamp": now_iso(),
        "actor": actor,
        "decision_type": decision_type,
        "context": context,
        "evidence": evidence,
        "outcome": outcome,
        "confidence": round(confidence, 2),
        "lineage": list(lineage),
    }


def validate_canonical_inputs() -> None:
    missing = [str(path) for path in CANONICAL_INPUTS if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing canonical inputs: {missing}")


def run_persona(persona: str) -> dict[str, Any]:
    if persona not in CANONICAL_PERSONAS:
        raise ValueError(f"Unsupported persona: {persona}")

    validate_canonical_inputs()

    persona_dir = Path("out/runs") / persona
    persona_dir.mkdir(parents=True, exist_ok=True)
    plain_log_path = persona_dir / "plain_trace.log"
    trace_path = persona_dir / "decision_trace.jsonl"
    sdk_trace_path = persona_dir / ".sdk_decision_trace.jsonl"

    if sdk_trace_path.exists():
        sdk_trace_path.unlink()

    transactions = load_transactions(Path(f"data/personas/{persona}/transactions.csv"))
    constraints = load_constraints(Path("data/constraints.yaml"))

    agents = build_agents()
    crew = build_crew(agents, persona)
    crew.kickoff(inputs={"persona": persona})

    log_lines: list[str] = []
    emitter = DecisionTraceEmitter(persona, trace_path, sdk_trace_path)
    set_default_emitter(emitter)
    emitted: list[dict[str, Any]] = []

    totals = category_totals(transactions)
    baseline_spend = round(sum(totals.values()), 2)
    target_reduction = round(baseline_spend * float(constraints["target_reduction_pct"]), 2)
    protected = set(constraints["protected_categories"])
    drivers = discretionary_drivers(totals, protected)
    top_drivers = [{"category": c, "amount": round(v, 2)} for c, v in drivers[:3]]

    baseline_event = _event(
        "SpendAnalystAgent",
        "BASELINE_SPEND_COMPUTED",
        {
            "persona": persona,
            "input_files": [
                f"data/personas/{persona}/transactions.csv",
                "data/constraints.yaml",
            ],
        },
        {
            "category_totals": {k: round(v, 2) for k, v in sorted(totals.items())},
            "target_reduction_pct": float(constraints["target_reduction_pct"]),
        },
        {
            "baseline_spend": baseline_spend,
            "target_reduction_amount": target_reduction,
            "status": "COMPUTED",
        },
        0.99,
        [],
    )
    emitted.append(baseline_event)

    drivers_event = _event(
        "SpendAnalystAgent",
        "TOP_DRIVERS_IDENTIFIED",
        {"persona": persona},
        {
            "protected_categories": sorted(protected),
            "discretionary_candidates": top_drivers,
        },
        {"top_drivers": top_drivers, "status": "IDENTIFIED"},
        0.97,
        [baseline_event["decision_id"]],
    )
    emitted.append(drivers_event)

    plans = build_plans(totals, drivers, constraints)
    for plan in plans:
        plan_event = _event(
            "OptimizationAgent",
            "PLAN_PROPOSED",
            {"persona": persona, "target_reduction_amount": target_reduction},
            {
                "plan_id": plan["plan_id"],
                "plan_name": plan["plan_name"],
                "plan_summary": plan["plan_summary"],
                "cuts": plan["cuts"],
            },
            {
                "projected_savings": plan["projected_savings"],
                "savings_transfer_amount": plan["savings_transfer_amount"],
                "status": "PROPOSED",
            },
            0.94,
            [drivers_event["decision_id"]],
        )
        plan["proposal_decision_id"] = plan_event["decision_id"]
        emitted.append(plan_event)

    for plan in plans:
        policy = evaluate_policy(plan, totals, constraints)
        plan["policy"] = policy
        policy_event = _event(
            "PolicyGuardAgent",
            "PLAN_EVALUATED_POLICY",
            {"persona": persona, "plan_id": plan["plan_id"], "plan_name": plan["plan_name"]},
            {
                "reason_codes": [
                    {"code": c["code"], "status": c["status"], "explain": c["explain"]}
                    for c in policy["checks"]
                ]
            },
            {"policy_status": policy["policy_status"]},
            0.96,
            [plan["proposal_decision_id"]],
        )
        plan["policy_decision_id"] = policy_event["decision_id"]
        emitted.append(policy_event)

    for plan in plans:
        risk = evaluate_risk(plan, totals, constraints)
        plan["risk"] = risk
        risk_event = _event(
            "RiskFeasibilityAgent",
            "PLAN_EVALUATED_RISK",
            {"persona": persona, "plan_id": plan["plan_id"], "plan_name": plan["plan_name"]},
            {
                "reason_codes": [
                    {"code": c["code"], "status": c["status"], "explain": c["explain"]}
                    for c in risk["checks"]
                ],
                "largest_savings_share": risk["largest_savings_share"],
            },
            {"risk_status": risk["risk_status"]},
            0.93,
            [plan["policy_decision_id"]],
        )
        plan["risk_decision_id"] = risk_event["decision_id"]
        emitted.append(risk_event)

    selected, planner_details = select_plan(plans)
    selected_event = _event(
        "PlannerAgent",
        "FINAL_PLAN_SELECTED",
        {"persona": persona},
        {
            "candidate_comparison_summary": planner_details["candidates"],
            "tie_breakers_applied": planner_details["tie_breakers_applied"],
            "rationale": planner_details["rationale"],
        },
        {
            "selected_plan_id": selected["plan_id"],
            "selected_plan_name": selected["plan_name"],
            "status": "SELECTED",
        },
        0.95,
        [selected["risk_decision_id"]],
    )
    emitted.append(selected_event)

    markdown = [
        f"# Budget Plan for {persona}",
        "",
        f"## Selected Plan: {selected['plan_name']}",
        "",
        f"{selected['plan_summary']}",
        "",
        "### Category Changes",
    ]
    for cat, pct in sorted(selected["cuts"].items()):
        markdown.append(f"- {cat}: reduce by {pct:.0%}")
    markdown.extend(
        [
            "",
            "### Financial Impact",
            f"- Projected savings: ${selected['projected_savings']:.2f}",
            f"- Transfer to savings: ${selected['savings_transfer_amount']:.2f}",
            "",
            "### Planner Rationale",
            planner_details["rationale"],
        ]
    )
    budget_markdown = "\n".join(markdown) + "\n"

    published_event = _event(
        "PlannerAgent",
        "BUDGET_PLAN_PUBLISHED",
        {"persona": persona},
        {
            "selected_plan_id": selected["plan_id"],
            "selected_plan_name": selected["plan_name"],
            "markdown_sections": ["Selected Plan", "Category Changes", "Financial Impact", "Planner Rationale"],
        },
        {"status": "PUBLISHED", "artifact": str(persona_dir / "budget_plan.md")},
        0.99,
        [selected_event["decision_id"]],
    )
    emitted.append(published_event)

    scorecard = {
        "persona": persona,
        "baseline_spend": baseline_spend,
        "target_reduction_amount": target_reduction,
        "top_drivers": top_drivers,
        "plans": [
            {
                "plan_id": p["plan_id"],
                "plan_name": p["plan_name"],
                "plan_summary": p["plan_summary"],
                "projected_savings": p["projected_savings"],
                "savings_transfer_amount": p["savings_transfer_amount"],
                "policy_status": p["policy"]["policy_status"],
                "risk_status": p["risk"]["risk_status"],
                "cuts": p["cuts"],
            }
            for p in plans
        ],
        "selected_plan": {
            "plan_id": selected["plan_id"],
            "plan_name": selected["plan_name"],
            "projected_savings": selected["projected_savings"],
            "risk_status": selected["risk"]["risk_status"],
            "policy_status": selected["policy"]["policy_status"],
        },
    }

    for event in emitted:
        log_lines.append(
            f"{event['timestamp']} | {event['actor']} | {event['decision_type']} | {event['outcome']}"
        )

    (persona_dir / "budget_plan.md").write_text(budget_markdown, encoding="utf-8")
    (persona_dir / "scorecard.json").write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plain_log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    emitter.close()

    return {
        "persona": persona,
        "scorecard": scorecard,
        "events": emitted,
        "budget_markdown": budget_markdown,
        "plain_log": "\n".join(log_lines),
    }


def run_all_personas() -> list[dict[str, Any]]:
    return [run_persona(persona) for persona in CANONICAL_PERSONAS]
