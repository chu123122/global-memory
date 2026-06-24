"""Validate host-neutral collaboration agent configuration."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ConfigError(ValueError):
    """Raised when a collaboration config is structurally invalid."""


ALLOWED_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
ALLOWED_CLIENTS = {"codex", "claude-code", "orca", "manual"}
ALLOWED_PERMISSION_MODES = {"ask", "read-only", "workspace-write", "full-access"}
DEFAULT_AGENT_NAMES = ("find", "designer", "dev", "test", "main")
DEFAULT_WORKFLOW = "global-memory-collab"
DEFAULT_REPORT_CONTRACT = "Outcome -> Evidence -> Changes -> Verification -> Next"
DEFAULT_STOP_POLICY = {"same_error_limit": 3}
DEFAULTS = {
    "client": "codex",
    "model": "gpt-5.5",
    "reasoning_effort": "medium",
    "permission_mode": "ask",
}
DEFAULT_AGENTS = [
    {"name": "find", "role": "source locator", "reasoning_effort": "medium"},
    {"name": "designer", "role": "architecture designer", "reasoning_effort": "high"},
    {"name": "dev", "role": "implementation", "reasoning_effort": "high"},
    {"name": "test", "role": "verification", "reasoning_effort": "high"},
    {"name": "main", "role": "documentation and state", "reasoning_effort": "medium"},
]


@dataclass(frozen=True)
class AgentSpec:
    """A single collaboration worker role after defaults are applied."""

    name: str
    role: str
    client: str
    model: str
    reasoning_effort: str
    permission_mode: str
    prompt: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], defaults: Mapping[str, Any]) -> "AgentSpec":
        merged = {**defaults, **dict(raw)}
        name = _required_text(merged, "name")
        role = _required_text(merged, "role")
        client = _required_text(merged, "client")
        model = _required_text(merged, "model")
        reasoning_effort = _required_text(merged, "reasoning_effort")
        permission_mode = _required_text(merged, "permission_mode")
        prompt = str(merged.get("prompt", "")).strip()

        if client not in ALLOWED_CLIENTS:
            raise ConfigError(f"agent {name!r} client must be one of {sorted(ALLOWED_CLIENTS)}")
        if reasoning_effort not in ALLOWED_REASONING_EFFORTS:
            raise ConfigError(
                f"agent {name!r} reasoning_effort must be one of {sorted(ALLOWED_REASONING_EFFORTS)}"
            )
        if permission_mode not in ALLOWED_PERMISSION_MODES:
            raise ConfigError(
                f"agent {name!r} permission_mode must be one of {sorted(ALLOWED_PERMISSION_MODES)}"
            )
        return cls(
            name=name,
            role=role,
            client=client,
            model=model,
            reasoning_effort=reasoning_effort,
            permission_mode=permission_mode,
            prompt=prompt,
        )

    def to_dict(self) -> dict[str, str]:
        data = {
            "name": self.name,
            "role": self.role,
            "client": self.client,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "permission_mode": self.permission_mode,
        }
        if self.prompt:
            data["prompt"] = self.prompt
        return data


@dataclass(frozen=True)
class CollabConfig:
    """Validated collaboration workflow configuration."""

    schema_version: int
    workflow: str
    defaults: dict[str, Any]
    agents: tuple[AgentSpec, ...]
    stop_policy: dict[str, Any]
    report_contract: str

    def agent(self, name: str) -> AgentSpec:
        for agent in self.agents:
            if agent.name == name:
                return agent
        raise KeyError(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow": self.workflow,
            "defaults": dict(self.defaults),
            "agents": [agent.to_dict() for agent in self.agents],
            "stop_policy": dict(self.stop_policy),
            "report_contract": self.report_contract,
        }


def default_config_payload() -> dict[str, Any]:
    """Return a fresh default config payload before validation."""

    return {
        "schema_version": 1,
        "workflow": DEFAULT_WORKFLOW,
        "defaults": dict(DEFAULTS),
        "agents": [dict(agent) for agent in DEFAULT_AGENTS],
        "stop_policy": dict(DEFAULT_STOP_POLICY),
        "report_contract": DEFAULT_REPORT_CONTRACT,
    }


def load_config(path: str | Path | None = None) -> CollabConfig:
    """Load and validate a collaboration config from JSON, or use defaults."""

    if path is None:
        return parse_config(default_config_payload())
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"failed to read config {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config {config_path} is not valid JSON: {exc}") from exc
    return parse_config(payload)


def parse_config(payload: Mapping[str, Any]) -> CollabConfig:
    """Validate a raw mapping and return a normalized collaboration config."""

    if not isinstance(payload, Mapping):
        raise ConfigError("config root must be an object")
    schema_version = payload.get("schema_version")
    if schema_version != 1:
        raise ConfigError("schema_version must be 1")
    workflow = _required_text(payload, "workflow")

    defaults_raw = payload.get("defaults", {})
    if not isinstance(defaults_raw, Mapping):
        raise ConfigError("defaults must be an object")
    defaults = {**DEFAULTS, **dict(defaults_raw)}
    _validate_defaults(defaults)

    agents_raw = payload.get("agents")
    if not isinstance(agents_raw, list) or not agents_raw:
        raise ConfigError("agents must be a non-empty list")
    agents: list[AgentSpec] = []
    seen: set[str] = set()
    for index, raw_agent in enumerate(agents_raw):
        if not isinstance(raw_agent, Mapping):
            raise ConfigError(f"agents[{index}] must be an object")
        agent = AgentSpec.from_mapping(raw_agent, defaults)
        if agent.name in seen:
            raise ConfigError(f"duplicate agent name: {agent.name}")
        seen.add(agent.name)
        agents.append(agent)

    missing = sorted(set(DEFAULT_AGENT_NAMES) - seen)
    if missing:
        raise ConfigError(f"missing required agents: {', '.join(missing)}")

    stop_policy = payload.get("stop_policy", DEFAULT_STOP_POLICY)
    if not isinstance(stop_policy, Mapping):
        raise ConfigError("stop_policy must be an object")
    same_error_limit = stop_policy.get("same_error_limit", DEFAULT_STOP_POLICY["same_error_limit"])
    if not isinstance(same_error_limit, int) or same_error_limit < 1:
        raise ConfigError("stop_policy.same_error_limit must be a positive integer")
    normalized_stop_policy = {**dict(stop_policy), "same_error_limit": same_error_limit}

    report_contract = str(payload.get("report_contract", DEFAULT_REPORT_CONTRACT)).strip()
    if not report_contract:
        raise ConfigError("report_contract must be non-empty")

    return CollabConfig(
        schema_version=1,
        workflow=workflow,
        defaults=defaults,
        agents=tuple(agents),
        stop_policy=normalized_stop_policy,
        report_contract=report_contract,
    )


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = str(mapping.get(field, "")).strip()
    if not value:
        raise ConfigError(f"{field} is required")
    return value


def _validate_defaults(defaults: Mapping[str, Any]) -> None:
    for field in ["client", "model", "reasoning_effort", "permission_mode"]:
        _required_text(defaults, field)
    if defaults["client"] not in ALLOWED_CLIENTS:
        raise ConfigError(f"defaults.client must be one of {sorted(ALLOWED_CLIENTS)}")
    if defaults["reasoning_effort"] not in ALLOWED_REASONING_EFFORTS:
        raise ConfigError(f"defaults.reasoning_effort must be one of {sorted(ALLOWED_REASONING_EFFORTS)}")
    if defaults["permission_mode"] not in ALLOWED_PERMISSION_MODES:
        raise ConfigError(f"defaults.permission_mode must be one of {sorted(ALLOWED_PERMISSION_MODES)}")
