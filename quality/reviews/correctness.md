Verdict: PASS

Blocking:
- none

Warnings:
- 实际仓库级 drift checker 仍失败，但失败项是历史 drift；本次新增的 `scripts/register_script.py` 已登记到 registry 与 capability manifest。

Missing tests:
- none

Confidence: high
Need human decision:
- none

Notes:
- `normalize_harness_rel()` 拒绝绝对路径、`..`、非 `.py` 和不存在脚本，写入前完成所有 fail-loud 校验。
- `build_plan()` 先完成 manifest 与 registry 解析/更新计划，只有 `--apply` 后才写文件；错误路径不会产生部分写。
- Markdown 更新只定位 `## 3. Manual 治理脚本` 的固定表；找不到 anchor 直接失败，不猜测其他表结构。
- manifest 更新对目标 capability 的 `scripts[]` 做稳定去重/append，重复注册不产生重复 entry。
