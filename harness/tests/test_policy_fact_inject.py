from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POLICY_FACT = REPO / "harness" / "hooks" / "policy_fact.py"
RETRIEVE_INJECT = REPO / "harness" / "hooks" / "retrieve_inject.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_policy_fact_matches_review_decision_question():
    module = load_module(POLICY_FACT, "policy_fact_for_test_review")

    match = module.match_policy_fact("代码审查反馈后可以直接帮我修所有问题吗")

    assert match is not None
    assert match.fact_id == "code_review_no_patch"
    assert match.decision == "deny"
    assert "agents/code-reviewer.md" in match.evidence_paths
    assert "审查只报告" in match.summary


def test_policy_fact_ignores_plain_search_question():
    module = load_module(POLICY_FACT, "policy_fact_for_test_plain")

    assert module.match_policy_fact("代码审查规则在哪个文档") is None


def test_retrieve_inject_outputs_rag_brief_from_gm_search(monkeypatch, capsys):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_rag_for_test")
    payload = {"prompt": "代码审查规则在哪个文档", "session_id": "s1", "client": "pytest"}
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), encoding="utf-8"))
    monkeypatch.setattr(module, "_resolve_task", lambda _session_id="": "unknown")
    monkeypatch.setattr(module, "_run_policy_fact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "_run_retrieve", lambda *_args, **_kwargs: "source: gm.search\ndelivery_profile: interactive_hook\npointers:\n  - path: rules/接入索引.md\n")
    monkeypatch.setattr(module.time, "perf_counter", iter([0.0, 0.1]).__next__)

    module.main()

    out = capsys.readouterr().out
    assert "RAG Brief" in out
    assert "source: gm.search" in out
    assert "interactive_hook" in out
    assert "Policy Brief" not in out
    assert "Context Brief" not in out


def test_retrieve_inject_outputs_nothing_when_gm_search_abstains(monkeypatch, capsys):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_rag_abstain_for_test")
    payload = {"prompt": "今天天气不错", "session_id": "s1", "client": "pytest"}
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), encoding="utf-8"))
    monkeypatch.setattr(module, "_resolve_task", lambda _session_id="": "unknown")
    monkeypatch.setattr(module, "_run_policy_fact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "_run_retrieve", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.time, "perf_counter", iter([0.0, 0.1]).__next__)

    module.main()

    assert capsys.readouterr().out == ""


def test_retrieve_inject_runtime_config_disabled_by_default(monkeypatch, capsys, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_runtime_config_disabled_for_test")
    payload = {"prompt": "当前有什么 hook 列表", "session_id": "s1", "client": "pytest"}
    called = {"policy": False, "retrieve": False}

    def fake_policy(*_args, **_kwargs):
        called["policy"] = True
        return None

    def fake_retrieve(*_args, **_kwargs):
        called["retrieve"] = True
        return None

    monkeypatch.delenv("HARNESS_RUNTIME_BRIEF_INJECT", raising=False)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), encoding="utf-8"))
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "_resolve_task", lambda _session_id="": "unknown")
    monkeypatch.setattr(module, "_run_policy_fact", fake_policy)
    monkeypatch.setattr(module, "_run_retrieve", fake_retrieve)
    monkeypatch.setattr(module.time, "perf_counter", iter([0.0, 0.1]).__next__)

    module.main()

    assert called == {"policy": True, "retrieve": True}
    assert capsys.readouterr().out == ""


def test_retrieve_inject_runtime_config_short_circuits_gm_search_when_enabled(monkeypatch, capsys, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_runtime_config_for_test")
    payload = {"prompt": "当前有什么 hook 列表", "session_id": "s1", "client": "pytest"}
    monkeypatch.setenv("HARNESS_RUNTIME_BRIEF_INJECT", "1")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), encoding="utf-8"))
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "_run_policy_fact", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("runtime brief must not call policy fact")))
    monkeypatch.setattr(module, "_run_retrieve", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("runtime brief must not call gm.search")))

    module.main()

    out = capsys.readouterr().out
    assert "Runtime Config Brief" in out
    assert "deterministic_runtime_config" in out
    assert "hook_manifest_path" in out
    assert "RAG Brief" not in out


def test_retrieve_inject_outputs_policy_brief_when_rule_matches(monkeypatch, capsys):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_policy_output_for_test")
    payload = {"prompt": "代码审查反馈后可以直接帮我修所有问题吗", "session_id": "s1", "client": "pytest"}
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), encoding="utf-8"))
    monkeypatch.setattr(module, "_resolve_task", lambda _session_id="": "unknown")
    monkeypatch.setattr(module, "_run_policy_fact", lambda *_args, **_kwargs: "fact_id: code_review_no_patch\ndecision: deny\n")
    monkeypatch.setattr(module, "_run_retrieve", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.time, "perf_counter", iter([0.0, 0.1]).__next__)

    module.main()

    out = capsys.readouterr().out
    assert "Policy Brief" in out
    assert "code_review_no_patch" in out
    assert "RAG Brief" not in out


def test_write_rag_log_includes_threshold_observability_fields(monkeypatch, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_log_fields_for_test")
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "is_runtime_logs_dir_in_repo", lambda _path=None: False)
    result = {
        "hit": True,
        "abstained": False,
        "delivery_profile": "interactive_hook",
        "pointers": [{"path": "rules/接入索引.md"}],
        "diagnostics": {"sidecar": {"status": "ready"}},
        "debug": {
            "best_raw_cosine": 0.7,
            "top_candidates": [{"path": "rules/接入索引.md", "raw_cosine": 0.7, "retrieval_score": 0.8}],
            "thresholds": {"pre_rerank_min_raw_cosine": 0.622, "rerank_abstain_threshold": 4.625},
            "deliver_gate": {"best_reranker_score": 4.9, "rerank_abstain_threshold": 4.625},
        },
    }

    module._write_rag_log(task_name="unknown", user_msg="规则在哪", result=result, elapsed_ms=12.3, session_id="s1", client="pytest")

    record = json.loads((tmp_path / "retrieve_calls.jsonl").read_text(encoding="utf-8"))
    assert record["query_id"]
    assert record["best_raw_cosine"] == 0.7
    assert record["best_reranker_score"] == 4.9
    assert record["rerank_threshold"] == 4.625
    assert record["pre_rerank_threshold"] == 0.622
    assert record["top_candidate_paths"] == ["rules/接入索引.md"]
    assert record["sidecar_status"] == "ready"
    assert record["decision_reason"] == "inject"


def test_retrieve_inject_no_longer_imports_legacy_harness_retrieve():
    text = RETRIEVE_INJECT.read_text(encoding="utf-8")
    assert "from harness_retrieve import" not in text
    assert "harness_retrieve.retrieve" not in text

def test_retrieve_inject_policy_can_be_disabled(monkeypatch):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_policy_disabled_for_test")
    monkeypatch.setenv("HARNESS_POLICY_FACT_INJECT", "0")

    assert module._run_policy_fact("构建失败后能不能升级编译器再试") is None


def test_retrieve_inject_starts_sidecar_when_unavailable_without_cold_fallback(monkeypatch, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_sidecar_unavailable_for_test")
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "is_runtime_logs_dir_in_repo", lambda _path=None: False)
    starts: list[bool] = []
    monkeypatch.delenv("HARNESS_RAG_HOOK_ALLOW_COLD_FALLBACK", raising=False)
    monkeypatch.setattr(module, "_trace", lambda *_args, **_kwargs: None)

    def unavailable(*_args, **_kwargs):
        raise module.SidecarUnavailable("connection refused")

    def cold(*_args, **_kwargs):
        raise AssertionError("cold gm.search fallback is disabled by default")

    monkeypatch.setattr(module, "_request_sidecar", unavailable)
    monkeypatch.setattr(module, "_start_sidecar_fire_and_forget", lambda: starts.append(True))
    monkeypatch.setattr(module, "_run_retrieve_cold", cold)

    assert module._run_retrieve("unknown", "代码审查规则在哪", session_id="s1", client="pytest") is None
    assert starts == [True]


def test_retrieve_inject_cold_fallback_requires_explicit_env(monkeypatch, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_sidecar_cold_fallback_for_test")
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "is_runtime_logs_dir_in_repo", lambda _path=None: False)
    monkeypatch.setenv("HARNESS_RAG_HOOK_ALLOW_COLD_FALLBACK", "1")
    monkeypatch.setattr(module, "_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "_request_sidecar", lambda *_args, **_kwargs: (_ for _ in ()).throw(module.SidecarUnavailable("down")))
    monkeypatch.setattr(module, "_start_sidecar_fire_and_forget", lambda: None)
    monkeypatch.setattr(module, "_run_retrieve_cold", lambda *_args, **_kwargs: "source: gm.search\n")

    assert module._run_retrieve("unknown", "代码审查规则在哪", session_id="s1", client="pytest") == "source: gm.search\n"




def test_retrieve_inject_sidecar_degraded_enters_cooldown(monkeypatch, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_sidecar_cooldown_for_test")
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "is_runtime_logs_dir_in_repo", lambda _path=None: False)
    monkeypatch.setattr(module, "SIDECAR_COOLDOWN_FAILURE_THRESHOLD", 3)
    monkeypatch.setattr(module, "SIDECAR_COOLDOWN_SEC", 300)
    monkeypatch.setattr(module, "_trace", lambda *_args, **_kwargs: None)
    degraded = {
        "hit": False,
        "abstained": True,
        "abstain_reason": "sidecar_degraded:timeout_ms_exceeded:3500>3000",
        "pointers": [],
        "sidecar_status": "degraded",
    }
    calls = []
    monkeypatch.setattr(module, "_request_sidecar", lambda *_args, **_kwargs: calls.append(True) or degraded)

    for _ in range(3):
        assert module._run_retrieve("unknown", "代码审查规则在哪", session_id="s1", client="pytest") is None

    state = json.loads((tmp_path / "gm_search_sidecar_cooldown.json").read_text(encoding="utf-8"))
    assert state["failure_count"] == 3
    assert state["cooling_down"] is True
    assert state["cooldown_until"]
    assert state["last_reason"] == "sidecar_degraded"
    assert len(calls) == 3


def test_retrieve_inject_cooldown_skips_sidecar_and_logs(monkeypatch, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_sidecar_cooldown_skip_for_test")
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "is_runtime_logs_dir_in_repo", lambda _path=None: False)
    monkeypatch.setattr(module, "_trace", lambda *_args, **_kwargs: None)
    (tmp_path / "gm_search_sidecar_cooldown.json").write_text(
        json.dumps({"failure_count": 3, "cooling_down": True, "cooldown_until_epoch": module.time.time() + 300, "cooldown_until": "2099-01-01T00:00:00", "last_reason": "sidecar_unavailable"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_request_sidecar", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cooldown must not call sidecar")))

    assert module._run_retrieve("unknown", "代码审查规则在哪", session_id="s1", client="pytest") is None

    records = [json.loads(line) for line in (tmp_path / "retrieve_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[-1]["abstained"] is True
    assert records[-1]["abstain_reason"] == "sidecar_cooldown"
    assert records[-1]["decision_reason"] == "abstain:sidecar_cooldown"
    assert records[-1]["sidecar_status"] == "cooldown"


def test_retrieve_inject_sidecar_success_clears_failure_count(monkeypatch, tmp_path):
    module = load_module(RETRIEVE_INJECT, "retrieve_inject_sidecar_success_clears_for_test")
    monkeypatch.setattr(module, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    monkeypatch.setattr(module, "is_runtime_logs_dir_in_repo", lambda _path=None: False)
    monkeypatch.setattr(module, "_trace", lambda *_args, **_kwargs: None)
    (tmp_path / "gm_search_sidecar_cooldown.json").write_text(json.dumps({"failure_count": 2, "last_reason": "sidecar_unavailable"}), encoding="utf-8")
    ready = {
        "hit": True,
        "abstained": False,
        "pointers": [{"path": "rules/接入索引.md"}],
        "diagnostics": {"sidecar": {"status": "ready"}},
    }
    monkeypatch.setattr(module, "_request_sidecar", lambda *_args, **_kwargs: ready)

    assert module._run_retrieve("unknown", "代码审查规则在哪", session_id="s1", client="pytest")
    assert not (tmp_path / "gm_search_sidecar_cooldown.json").exists()


def test_runtime_brief_reads_missing_logs_and_cooldown(tmp_path):
    runtime_brief = load_module(REPO / "harness" / "hooks" / "runtime_brief.py", "runtime_brief_for_test")
    (tmp_path / "gm_search_sidecar_cooldown.json").write_text(
        json.dumps({"failure_count": 3, "cooling_down": True, "cooldown_until_epoch": runtime_brief.time.time() + 300, "cooldown_until": "2099-01-01T00:00:00", "last_reason": "sidecar_degraded"}),
        encoding="utf-8",
    )

    brief = runtime_brief.build_runtime_brief("当前 RAG 状态", logs_dir=tmp_path, harness_root=REPO / "harness")

    assert brief is not None
    assert "sidecar_cooldown" in brief
    assert "cooling_down: True" in brief
    assert "failure_count: 3" in brief



def test_runtime_brief_does_not_reinject_forwarded_hook_context(tmp_path):
    runtime_brief = load_module(REPO / "harness" / "hooks" / "runtime_brief.py", "runtime_brief_forwarded_context_for_test")
    forwarded = """UserPromptSubmit hook (completed)
  hook context:  Runtime Config Brief (deterministic current-state snapshot):
    ```yaml
    topic: mcp_status
    source: deterministic_runtime_config
    mcp:
      codex_global_memory_present: True
    rag_runtime:
      last_retrieve_call:
        abstain_reason: sidecar_cooldown
    ```
这个问题是什么？"""

    assert runtime_brief.runtime_brief_topic(forwarded) is None
    assert runtime_brief.build_runtime_brief(forwarded, logs_dir=tmp_path, harness_root=REPO / "harness") is None


def test_runtime_brief_still_triggers_for_direct_runtime_question(tmp_path):
    runtime_brief = load_module(REPO / "harness" / "hooks" / "runtime_brief.py", "runtime_brief_direct_question_for_test")

    assert runtime_brief.runtime_brief_topic("当前 MCP 状态是什么") == "mcp_status"
    assert runtime_brief.build_runtime_brief("当前 MCP 状态是什么", logs_dir=tmp_path, harness_root=REPO / "harness") is not None



def test_runtime_brief_does_not_trigger_for_previous_agent_plan_prompt(tmp_path):
    runtime_brief = load_module(REPO / "harness" / "hooks" / "runtime_brief.py", "runtime_brief_plan_prompt_for_test")
    prompt = """A previous agent produced the plan below to accomplish the user's task. Implement the plan in a fresh context.

# Plan

Update docs and tests. Later in this long plan there is a copied diagnostic token: topic: mcp_status and runtime status.

```yaml
mcp:
  codex_global_memory_present: True
rag_runtime:
  sidecar_cooldown:
    cooling_down: True
```
"""

    assert runtime_brief.runtime_brief_topic(prompt) is None
    assert runtime_brief.build_runtime_brief(prompt, logs_dir=tmp_path, harness_root=REPO / "harness") is None


def test_runtime_brief_ignores_mcp_status_inside_later_body(tmp_path):
    runtime_brief = load_module(REPO / "harness" / "hooks" / "runtime_brief.py", "runtime_brief_late_body_for_test")
    prompt = "请继续执行这个实现任务，先读文件再修改。" + ("。" * 600) + "\n后面引用旧日志 topic: mcp_status runtime status"

    assert runtime_brief.runtime_brief_topic(prompt) is None
    assert runtime_brief.build_runtime_brief(prompt, logs_dir=tmp_path, harness_root=REPO / "harness") is None
