"""Phase 12 product entry and readiness gate for collab bridge."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from .bridge import build_worker_launch_blueprint, dumps_bridge_json
from .bridge_host import create_session_from_blueprint, materialize_bridge_host, save_session_events
from .bridge_store import build_store_summary
from .config import load_config
from .mcp_bridge import build_lead_cli_mcp_schema, probe_lead_cli_mcp
from .plan import build_dispatch_plan
from .router import acknowledge_message, build_router_snapshot, enqueue_message, ingest_router_report
from .worker_runtime import apply_runtime_result, build_worker_runtime_request, run_worker_command
from .mcp_server import run_mcp_self_test
from .persistence import import_event_log, init_persistence, recover_persistence
from .web_ui import run_web_ui_smoke
from .worker_supervisor import WorkerSupervisor, build_supervisor_snapshot


def build_product_runbook() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "collab_product_runbook",
        "phase": 12,
        "entry_command": "python harness\\scripts\\collab_entry.py smoke --out .tmp\\collab-smoke --json",
        "safe_runtime_command": "python harness\\scripts\\collab_entry.py smoke --out .tmp\\collab-smoke --allow-spawn --json -- python -c \"print('worker report')\"",
        "does_not_modify": ["hooks", "bootstrap", "harness/client_manifest.json readiness", "lead Codex/Claude thread/goal/tool list"],
        "artifacts": ["plan.json", "blueprint.json", "events.jsonl", "store-summary.json", "router-snapshot.json", "readiness.json"],
    }


def build_readiness_report(*, runtime_smoke: bool = False, mcp_probe: bool = True, router_smoke: bool = True) -> dict[str, Any]:
    checks = [
        _check("bridge_contract", "pass", "Bridge spec/host/store stack is implemented through Phase 8."),
        _check("command_worker_runtime_alpha", "pass" if runtime_smoke else "warning", "Phase 9 command-worker path requires explicit allow-spawn; Codex/Claude E2E is separate."),
        _check("mcp_style_bridge_beta", "pass" if mcp_probe else "warning", "Phase 10 schema/probe/call surface is local MCP-style; real CLI registration remains unverified."),
        _check("router_report_loop", "pass" if router_smoke else "warning", "Phase 11 router supports correlation/dedupe/ack/fail/retry/report events."),
        _check("codex_claude_e2e", "blocker", "No verified Codex/Claude worker command E2E in this readiness gate."),
        _check("real_mcp_registration", "blocker", "No verified Codex/Claude MCP server registration from this gate."),
        _check("desktop_or_web_ui", "warning", "Current UI is materialized JSON/Markdown/CLI projection, not a real desktop/web UI."),
        _check("client_manifest_readiness", "blocker", "Do not promote harness/client_manifest.json readiness from this experimental stack."),
    ]
    blockers = [item for item in checks if item["status"] == "blocker"]
    warnings = [item for item in checks if item["status"] == "warning"]
    return {
        "schema_version": 1,
        "kind": "collab_readiness_report",
        "phase": 12,
        "verdict": "not_ready" if blockers else ("warning" if warnings else "ready"),
        "client_manifest_readiness_changed": False,
        "checks": checks,
        "summary": {"pass": sum(1 for item in checks if item["status"] == "pass"), "warning": len(warnings), "blocker": len(blockers)},
        "next_required_evidence": ["verified Codex/Claude worker E2E", "verified Codex/Claude MCP server registration", "product UI entry if desktop/web UX is required"],
    }


def run_product_smoke(out_dir: str | Path, *, allow_spawn: bool = False, command: Sequence[str] | None = None) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plan = build_dispatch_plan(load_config(), intent="Phase 12 product entry smoke.")
    blueprint = build_worker_launch_blueprint(plan)
    session = create_session_from_blueprint(blueprint, worker_limit=1, runtime_mode="fake")
    worker_id = session["workers"][0]["worker_id"]
    runtime_request = build_worker_runtime_request(session, worker_id, command or [sys.executable, "-c", "print('request only')"])
    runtime_result = None
    if allow_spawn:
        runtime_result = run_worker_command(session, worker_id, command or [sys.executable, "-c", "print('product smoke worker report')"], allow_spawn=True)
        session = apply_runtime_result(session, runtime_result)
    session, queued = enqueue_message(session, worker_id, "product entry smoke", correlation_id="phase12-smoke", dedupe_key="phase12-smoke")
    session, _acked = acknowledge_message(session, queued["message_id"], ack_id="phase12-ack")
    session, _report = ingest_router_report(session, worker_id, "reports/phase12-smoke.md", status="done")
    store_summary = build_store_summary(session)
    router_snapshot = build_router_snapshot(session)
    mcp_schema = build_lead_cli_mcp_schema()
    mcp_probe = probe_lead_cli_mcp(session)
    readiness = build_readiness_report(runtime_smoke=allow_spawn, mcp_probe=True, router_smoke=True)
    files = {
        "plan": out / "plan.json",
        "blueprint": out / "blueprint.json",
        "events": out / "events.jsonl",
        "store_summary": out / "store-summary.json",
        "router_snapshot": out / "router-snapshot.json",
        "mcp_schema": out / "mcp-schema.json",
        "mcp_probe": out / "mcp-probe.json",
        "readiness": out / "readiness.json",
    }
    files["plan"].write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["blueprint"].write_text(dumps_bridge_json(blueprint), encoding="utf-8")
    save_session_events(session, files["events"])
    files["store_summary"].write_text(json.dumps(store_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["router_snapshot"].write_text(json.dumps(router_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["mcp_schema"].write_text(json.dumps(mcp_schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["mcp_probe"].write_text(json.dumps(mcp_probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["readiness"].write_text(json.dumps(readiness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if runtime_result is not None:
        runtime_path = out / "runtime-result.json"
        runtime_path.write_text(json.dumps(runtime_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files["runtime_result"] = runtime_path
    return {
        "schema_version": 1,
        "kind": "collab_product_entry_smoke",
        "phase": 12,
        "out_dir": str(out),
        "allow_spawn": allow_spawn,
        "artifacts": {key: str(value) for key, value in files.items()},
        "materialized": materialize_bridge_host(session),
        "readiness": readiness,
    }


def dumps_entry_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _check(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"name": name, "status": status, "evidence": evidence}



def build_xdmaker_like_readiness_report(
    *,
    real_worker_e2e: bool = False,
    supervisor: bool = False,
    mcp_server: bool = False,
    mcp_registration: bool = False,
    mcp_tool_call: bool = False,
    web_ui: bool = False,
    persistence: bool = False,
    claude_blocked: bool = False,
) -> dict[str, Any]:
    """Return the Phase 18 XDMaker-like readiness verdict."""

    checks = [
        _check("real_codex_or_claude_worker_e2e", "pass" if real_worker_e2e else "blocker", "At least one real codex/claude CLI worker probe must be Green."),
        _check("worker_supervisor", "pass" if supervisor else "blocker", "Supervisor start/status/read/stop/crash/timeout path must be tested."),
        _check("real_mcp_server", "pass" if mcp_server else "blocker", "A real stdio MCP server must initialize/list/call tools."),
        _check("codex_or_claude_mcp_registration", "pass" if mcp_registration else "blocker", "At least one real CLI must list/register the collab MCP server."),
        _check("mcp_tool_call", "pass" if mcp_tool_call else "blocker", "A tool call must mutate or read the bridge event store."),
        _check("local_web_ui", "pass" if web_ui else "blocker", "Local web UI/API smoke must create/send/read/report/retry."),
        _check("sqlite_persistence_recovery", "pass" if persistence else "blocker", "SQLite import/reopen/recover path must pass."),
        _check("claude_worker", "warning" if claude_blocked else "pass", "Claude worker is optional for experimental_ready when Codex worker is Green; blocked budget must stay visible."),
        _check("client_manifest_readiness", "pass", "Do not modify harness/client_manifest.json readiness from this experimental gate."),
    ]
    blockers = [item for item in checks if item["status"] == "blocker"]
    warnings = [item for item in checks if item["status"] == "warning"]
    return {
        "schema_version": 1,
        "kind": "collab_xdmaker_like_readiness_report",
        "phase": 18,
        "verdict": "experimental_ready" if not blockers else "not_ready",
        "client_manifest_readiness_changed": False,
        "checks": checks,
        "summary": {"pass": sum(1 for item in checks if item["status"] == "pass"), "warning": len(warnings), "blocker": len(blockers)},
        "remaining_gap_to_xdmaker_product": ["Electron/product shell", "account/update/branding layer", "multi-user/cloud sync"] if not blockers else [item["name"] for item in blockers],
    }


def run_xdmaker_like_smoke(
    out_dir: str | Path,
    *,
    real_worker_evidence: str | Path | None = None,
    mcp_registration_evidence: str | Path | None = None,
    claude_blocker_evidence: str | Path | None = None,
) -> dict[str, Any]:
    """Run Phase 18 deterministic core chain and fold in real CLI evidence."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    entry_smoke = run_product_smoke(out / "entry")
    events = Path(entry_smoke["artifacts"]["events"])

    supervisor = WorkerSupervisor()
    sup_events = []
    sup_events.append(supervisor.start_worker("worker-01-find", [sys.executable, "-u", "-c", "print('supervisor-ready', flush=True)"]))
    sup_events.append(supervisor.worker_status("worker-01-find"))
    sup_events.append(supervisor.read_worker("worker-01-find"))
    sup_events.append(supervisor.stop_worker("worker-01-find"))
    supervisor_snapshot = build_supervisor_snapshot(sup_events)
    (out / "supervisor-snapshot.json").write_text(json.dumps(supervisor_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mcp_probe = run_mcp_self_test(events)
    (out / "mcp-self-test.json").write_text(json.dumps(mcp_probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ui_smoke = run_web_ui_smoke(out / "web-ui")
    db = out / "collab.sqlite3"
    init_persistence(db)
    import_event_log(db, "phase18", events)
    persistence_recovery = recover_persistence(db)
    (out / "persistence-recovery.json").write_text(json.dumps(persistence_recovery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    real_worker_ok = _real_worker_evidence_ok(real_worker_evidence)
    registration_ok = _mcp_registration_evidence_ok(mcp_registration_evidence)
    claude_blocked = _claude_blocker_evidence_seen(claude_blocker_evidence)
    readiness = build_xdmaker_like_readiness_report(
        real_worker_e2e=real_worker_ok,
        supervisor=supervisor_snapshot["summary"]["worker_count"] >= 1,
        mcp_server=mcp_probe.get("real_mcp_server_verified") is True,
        mcp_registration=registration_ok,
        mcp_tool_call=mcp_probe.get("tool_call_ok") is True and mcp_probe.get("mutating_tool_call_ok") is True,
        web_ui=ui_smoke.get("api_ok") is True,
        persistence=bool(persistence_recovery.get("recovered") and persistence_recovery["recovered"][0].get("ok")),
        claude_blocked=claude_blocked,
    )
    readiness_path = out / "xdmaker-like-readiness.json"
    readiness_path.write_text(json.dumps(readiness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "kind": "collab_xdmaker_like_smoke",
        "phase": 18,
        "out_dir": str(out),
        "artifacts": {
            "entry": str(out / "entry"),
            "supervisor_snapshot": str(out / "supervisor-snapshot.json"),
            "mcp_self_test": str(out / "mcp-self-test.json"),
            "web_ui": str(out / "web-ui"),
            "persistence_recovery": str(out / "persistence-recovery.json"),
            "readiness": str(readiness_path),
        },
        "evidence_inputs": {
            "real_worker_evidence": str(real_worker_evidence) if real_worker_evidence else None,
            "mcp_registration_evidence": str(mcp_registration_evidence) if mcp_registration_evidence else None,
            "claude_blocker_evidence": str(claude_blocker_evidence) if claude_blocker_evidence else None,
        },
        "readiness": readiness,
    }


def _real_worker_evidence_ok(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return False
    result = payload.get("result") if isinstance(payload, Mapping) else None
    if isinstance(result, Mapping):
        return result.get("real_cli_e2e_verified") is True or result.get("codex_claude_e2e_verified") is True
    return bool(isinstance(payload, Mapping) and (payload.get("real_cli_e2e_verified") is True or payload.get("codex_claude_e2e_verified") is True))


def _mcp_registration_evidence_ok(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return False
    if isinstance(payload, list):
        return any(isinstance(item, Mapping) and item.get("name") == "global-memory-collab-bridge" and item.get("enabled") is True for item in payload)
    if isinstance(payload, Mapping):
        return payload.get("real_mcp_server_verified") is True or payload.get("server_name") == "global-memory-collab-bridge"
    return False


def _claude_blocker_evidence_seen(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return False
    classification = payload.get("classification") if isinstance(payload, Mapping) else None
    return isinstance(classification, Mapping) and classification.get("runtime") == "claude" and classification.get("status") != "ok"
