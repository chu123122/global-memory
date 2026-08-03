---
doc_type: guide
status: active
last_updated: 2026-06-01
trigger:
  keywords: [concept:subsystem, tool:harness, concept:context-control]
  tags: [workflow, tooling]
---

# ~/.claude/global-memory 子系统功能图

五大主功能 + 配套关系速查。机器源真相在 `harness/*_manifest.json`，本页解释每块干啥、怎么触发、与谁配套。

## 1. 上下文召回注入器 (injector)

- **入口**: `harness/hooks/retrieve_inject.py`（主）+ `harness/scripts/harness_retrieve.py`（核心逻辑）
- **作用**: 扫记忆库，按 keywords+tags+stage 评分，回传 Top-N 文件路径**指针**（不注正文），AI 按需 Read
- **触发**: UserPromptSubmit hook（每条用户消息后的 Context Brief）。env `HARNESS_RETRIEVE_INJECT` / `HARNESS_RETRIEVE_LOG`
- **配套**: `context_meter.py`(token 度量)、`retrieve_trace.py`(评分 trace)、`triggers_aliases.yaml`(别名表)、`retrieve_calls.jsonl`(日志)

## 2. Schema 检查器 + MD→HTML 编译器 (compiler)

- **入口**: `harness/scripts/harness_memory_lint.py` + `harness/md2html/md2html.py` + `harness/hooks/doc_gate.py`
- **作用**: ① 校验记忆 frontmatter 合 `triggers_vocab.yaml` 受控词表；② Markdown→美观 HTML（目录/高亮/12 组件模板布局，含 Haiku 分类器）
- **触发**: CLI `harness_memory_lint.py FILE|--batch|--proposed`、`md2html.py file|dir`；PreToolUse hook `doc_gate.py` 拦编辑
- **配套**: `triggers_vocab.yaml`(词表)、`memory_*.md.tmpl`(4 模板)、`md2html_classifier.py`(规则+Haiku)、`md2html_components.py`(12 组件)、`verify_docs.py`(漂移检测)

## 3. 质量门 / 全局检查 (global check)

- **入口**: `harness/scripts/quality_gate.py` + `gate_check.py` + `assurance_gate.py` + `harness/hooks/quality_gate_stop.py` + `harness/task_complete.py`
- **作用**: 4 层门 —— Tier0-3 风险分级要证据 / G1-G9 前置条件 / 任务交接就绪 / Stop hook 自动 verify 可 BLOCK
- **触发**: CLI `quality_gate.py {plan|verify|review-pack}`、`gate_check.py [--phase][--strict-sunset]`、`assurance_gate.py --gate task-handoff-ready --task <id>`；Stop + task_complete 自动 hook
- **配套**: `quality_gate.yaml`(thresholds/risk_paths)、4 视角审查(correctness/test-quality/risk-security/maintainability)、`quality/verification.md`、`HANDOFF.md`+设计文档、`ASSURANCE.json`(Hash 新鲜度)

## 4. 启动 + 记忆同步 (startup)

- **入口**: `bootstrap.py` + `deploy_hooks.py` + `sync_index.py` + `maintain.py semantic-sync` + `semantic_refresh_worker.py` + legacy `auto_sync_daemon.py`
- **作用**: bootstrap 建 ~/.claude(junction+settings.json hooks)；Stop hook 做轻量检查并排队 semantic refresh；one-shot worker drain queue 后调用统一 `maintain.py semantic-sync`；Git checkpoint 走人工 `sync --preview` + `sync --source manual`。legacy daemon 仅保留兼容。
- **触发**: 会话启动 `bootstrap.py install`→加载 `hook_manifest.json`；Stop→`post_task_hook.py --auto-fix`→`semantic-sync --check-only --trigger stop-hook --json`→stale 时写 queue 并启动 `semantic_refresh_worker.py --drain-once`；Git 同步由人手动触发 `maintain.py sync --preview` / `sync --source manual`。
- **配套**: `hook_manifest.json`(钩子源)、`maintain.py`(manual Git sync + semantic-sync 总控)、`semantic_refresh_worker.py`(queue-backed one-shot refresh)、`memory_lint_gate.py`(护写)、`audit_logger.py`(审计)、`_lib.py`(共享配置/扫描)

## 5. 治理 / 审计 / GUI 层 (governance)

- **入口**: `harness/maintain.py`(主) + `route_audit.py` + `task_sync.py` + `panel_api.py` + `health/registry.py` + `control_panel_pyside/main_window.py` + `verify/verify_all.py`
- **作用**: 路由审计(missed opportunities)、多 Agent 任务同步(锁协议)、健康体检+自动修复、memory GC、PySide 主控台 GUI、session 报告
- **触发**: `maintain.py {doctor|fix|sync}`、`route_audit.py --days 7`、GUI `control_panel_pyside.bat`、task 收尾 `task_complete.py`

## 配套关系（如何"控制上下文"）

```
写入侧:  doc_gate(hook) → memory_lint(schema校验) → 落库 → sync_index(重建 MEMORY.md 索引)
读取侧:  UserPromptSubmit → retrieve_inject(injector) → 回传指针 → context_meter(度量 token)
质量侧:  Stop/task_complete → quality_gate + gate_check(全局检查) → BLOCK/PASS
底座:    bootstrap(装) + maintain(manual sync/semantic-sync) + semantic_refresh_worker(一次性刷新) + legacy auto_sync_daemon + route_audit(审计)
```

核心闭环：compiler 保证写入合 schema（可被检索）→ injector 检索时只给指针省 context → context_meter 度量成本 → 全局门把关交付。**1+2 配套控写质量，2+1 配套控读成本** —— 即"配套使用控制上下文"。

## 关联文档

- `docs/hook-chain.md` — hook 触发链细节
- `docs/scripts-registry.md` — 全脚本清单
- `docs/capabilities.md` — 能力清单（机器源 `capability_manifest.json`）
- `docs/task-lifecycle.md` — 任务生命周期
