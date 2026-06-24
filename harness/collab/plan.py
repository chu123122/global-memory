"""Build deterministic collaboration dispatch plans."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .adapters import ADAPTER_CONTRACTS, get_adapter_contract
from .config import CollabConfig, load_config

DEFAULT_INTENT = "Coordinate a global-memory collaboration task."
DEFAULT_TASK = "Execute the assigned collaboration role and report only decisive evidence."


def build_dispatch_plan(
    config: CollabConfig | None = None,
    *,
    intent: str = DEFAULT_INTENT,
    decisions: Iterable[str] | None = None,
    boundaries: Iterable[str] | None = None,
    task: str = DEFAULT_TASK,
) -> dict[str, Any]:
    """Return a stable host-neutral plan for the configured collaboration agents."""

    cfg = config or load_config()
    normalized_intent = _text_or_default(intent, DEFAULT_INTENT)
    normalized_task = _text_or_default(task, DEFAULT_TASK)
    normalized_decisions = _normalize_list(decisions)
    normalized_boundaries = _normalize_list(boundaries)

    dispatches: list[dict[str, Any]] = []
    for index, agent in enumerate(cfg.agents, start=1):
        contract = get_adapter_contract(agent.client)
        prompt = _worker_prompt(
            agent_name=agent.name,
            role=agent.role,
            model=agent.model,
            reasoning_effort=agent.reasoning_effort,
            permission_mode=agent.permission_mode,
            intent=normalized_intent,
            decisions=normalized_decisions,
            boundaries=normalized_boundaries,
            task=normalized_task,
            report_contract=cfg.report_contract,
            stop_policy=cfg.stop_policy,
            extra_prompt=agent.prompt,
        )
        dispatches.append(
            {
                "id": f"{index:02d}-{agent.name}",
                "agent": agent.name,
                "role": agent.role,
                "model": agent.model,
                "reasoning_effort": agent.reasoning_effort,
                "permission_mode": agent.permission_mode,
                "adapter": contract.to_dict(),
                "prompt": prompt,
            }
        )

    seed = {
        "schema_version": cfg.schema_version,
        "workflow": cfg.workflow,
        "intent": normalized_intent,
        "decisions": normalized_decisions,
        "boundaries": normalized_boundaries,
        "task": normalized_task,
        "agents": [agent.to_dict() for agent in cfg.agents],
    }
    plan_id = _plan_id(seed)

    return {
        "schema_version": cfg.schema_version,
        "plan_id": plan_id,
        "workflow": cfg.workflow,
        "intent": normalized_intent,
        "decisions": normalized_decisions,
        "boundaries": normalized_boundaries,
        "task": normalized_task,
        "stop_policy": dict(cfg.stop_policy),
        "report_contract": cfg.report_contract,
        "agents": [agent.to_dict() for agent in cfg.agents],
        "adapter_contracts": {name: contract.to_dict() for name, contract in ADAPTER_CONTRACTS.items()},
        "dispatches": dispatches,
    }


def render_plan_markdown(plan: dict[str, Any]) -> str:
    """Render a dispatch plan as stable human-readable Markdown."""

    lines = [
        "# Collaboration Dispatch Plan",
        "",
        f"Plan ID: `{plan['plan_id']}`",
        f"Workflow: `{plan['workflow']}`",
        f"Intent: {plan['intent']}",
        "",
        "## Decisions",
        *_bullets(plan.get("decisions", [])),
        "",
        "## Boundaries",
        *_bullets(plan.get("boundaries", [])),
        "",
        "## Dispatches",
    ]
    for item in plan.get("dispatches", []):
        lines.extend(
            [
                "",
                f"### {item['agent']}",
                f"- role: {item['role']}",
                f"- adapter: {item['adapter']['name']}",
                f"- model: {item['model']}",
                f"- reasoning_effort: {item['reasoning_effort']}",
                "",
                "```text",
                item["prompt"],
                "```",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def dumps_plan_json(plan: dict[str, Any]) -> str:
    """Serialize a plan with stable formatting for CLI output."""

    return json.dumps(plan, ensure_ascii=False, indent=2) + "\n"


def _plan_id(seed: dict[str, Any]) -> str:
    encoded = json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _worker_prompt(
    *,
    agent_name: str,
    role: str,
    model: str,
    reasoning_effort: str,
    permission_mode: str,
    intent: str,
    decisions: list[str],
    boundaries: list[str],
    task: str,
    report_contract: str,
    stop_policy: dict[str, Any],
    extra_prompt: str,
) -> str:
    lines = [
        f"You are the {agent_name} worker in a host-neutral global-memory collaboration plan.",
        f"Role: {role}",
        f"Model: {model}",
        f"Reasoning Effort: {reasoning_effort}",
        f"Permission Mode: {permission_mode}",
        "",
        "Intent:",
        intent,
        "",
        "Decisions:",
        *_bullets(decisions),
        "",
        "Boundaries:",
        *_bullets(boundaries),
        "",
        "Task:",
        task,
        "",
        "Report Contract:",
        report_contract,
        "",
        "Stop Policy:",
        f"- same_error_limit: {stop_policy.get('same_error_limit', 3)}",
    ]
    if extra_prompt:
        lines.extend(["", "Agent Notes:", extra_prompt])
    return "\n".join(lines).rstrip()


def _normalize_list(items: Iterable[str] | None) -> list[str]:
    return [str(item).strip() for item in items or [] if str(item).strip()]


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def _text_or_default(text: str, default: str) -> str:
    normalized = str(text or "").strip()
    return normalized or default
