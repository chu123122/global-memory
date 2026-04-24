# HANDOFF · token-cost-governance

> Status: implementation
> 更新时间: 2026-04-24

## 当前进度

本任务已从 `harness-governance-v1` 独立出来,并进入实现期。首批 token saver 的实现路径:

- `audit_skill.py`:已实现 Skill 结构审计,支持 `--skill` / `--all` / `--json`,以 `bootstrap.SKILLS` 为 canonical 集合,额外 deployed skill 只标 WARNING。
- `work_context_pack.py`:已实现 `/work` 上下文短摘要,支持 task/cwd 解析、stage 检测、缺失文档、最小 Read 清单。
- `check_prepare.py`:已实现 `/check` preflight,支持任务名/绝对路径解析、待审文档、缺失项、TODO/占位符/空章节扫描、prompt input 清单。
- `harness_status.py`:已改为默认只读,只有 `--write-snapshot` 才写 `STATUS_SNAPSHOT.md`。
- 三个 Skill 入口已改为优先调用对应脚本。
- `maintenance_manifest.json` 已加入 `token_savers` 分组。

## 下次开始

1. 先跑 `python check_health.py` 确认全局健康。
2. 再跑 `python harness/audit_skill.py --all --json`、`python harness/work_context_pack.py --task token-cost-governance`、`python harness/check_prepare.py --task token-cost-governance --json`。
3. 如果三项都稳定,再考虑是否把 `maintain.py` 增加一个聚合入口;当前默认不加,避免过度设计。

## 注意事项

- `audit_skill.py --all` 现在可能返回 `CONDITIONAL`,原因是历史 Skill 示例里引用了不存在的可选 assets/references,以及部署位存在 `xdap-test-device` 但未登记在 `bootstrap.SKILLS`。这不是脚本失败。
- `fix_hardcoded_paths.py` 的 Python 脚本检查已可清零;Markdown 历史文档中仍有旧绝对路径引用,不属于本任务首批代码实现范围。
- 本任务不处理 review/bug/memory 三个后续 pack,等真实使用数据证明收益后再立项。
