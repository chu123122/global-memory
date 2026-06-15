Verdict: PASS

Blocking:
- none

Warnings:
- fixture 中现有 checker 需 monkeypatch 硬编码根路径；这是 checker 现有限制，不是 register_script 的行为缺口。

Missing tests:
- none

Red-Evidence:
- `pytest harness/tests/test_register_script.py -q` 在实现前 5 failed，失败均来自缺少 `harness/scripts/register_script.py`，证明新增测试不是空跑。
- 实现后同一测试命令 5 passed，覆盖 dry-run、apply、幂等、错误路径和 checker fixture。

Mutation:
- 若移除 dry-run 写保护，`test_dry_run_outputs_json_preview_and_does_not_write` 的 tree snapshot 会失败。
- 若遗漏 manifest append，`test_apply_adds_script_to_registry_and_capability_manifest` 会在 scripts[] 断言失败。
- 若重复注册不去重或不识别 no-op，`test_repeated_register_is_idempotent_without_duplicate_entries` 会在 count 或 `would_change=false` 断言失败。
- 若错误路径先写后报错，`test_invalid_capability_missing_script_and_escape_path_fail_without_writes` 的 snapshot 会失败。
- 若 registry/capability 结果无法被现有 checker 逻辑识别，`test_registered_fixture_passes_existing_drift_checkers_with_monkeypatched_roots` 会暴露 unregistered/unassigned。

Confidence: high
Need human decision:
- none
