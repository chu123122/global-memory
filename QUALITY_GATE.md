# AI 代码质量门

这份规则约束 AI 参与生成的代码改动。目标不是让每个小改动都走重流程，而是让风险越高的改动接受越强的验证。

## 总原则

- 所有代码改动都必须说明验证方式。
- 行为改动必须有自动化测试，或写明不可测试原因和替代验证。
- Bugfix 必须有回归测试，或写明为什么无法自动化。
- 高风险改动必须经过多视角审查和人工裁决。
- AI review 不能替代 format、lint、typecheck、compile、test、build。

## 风险分级

| Tier | 适用范围 | 必需项 |
|---|---|---|
| Tier 0 | 文档、注释、纯格式、小文案、无行为变化 | 验证说明 |
| Tier 1 | 小代码改动，默认不触碰核心路径 | 编译或轻量确定性检查，验证说明 |
| Tier 2 | 功能、bugfix、重构、脚本逻辑、中等 diff | 确定性检查、测试证据、Correctness Review、Test Quality Review |
| Tier 3 | hook、CI、部署、权限、数据迁移、删除、模型路由、共享核心模块、大 diff | 完整测试证据、4 视角 AI review、人工裁决、回滚/恢复说明 |

自动分级只允许提高风险，不应该因为 AI 判断而降低风险。

## 四个审查视角

1. `correctness`: 逻辑正确性、边界条件、状态流、错误处理。
2. `test-quality`: 测试是否有独立 oracle、是否覆盖关键组合、是否能复现失败。
3. `risk-security`: 权限、数据边界、异常路径、资源释放、降级和恢复。
4. `maintainability`: 架构漂移、重复实现、接口污染、文档/实现一致性。

审查输出必须包含 verdict。没有具体文件、问题、修复要求或测试要求的发现默认降权。

## Review 结果格式

`quality_gate.py verify` 会校验 review 文件最低格式。每个必需 review 文件放在 `quality/reviews/<kind>.md`，或通过 `--review-dir` 指定目录。

必需字段：

```text
Verdict: PASS | WARN | BLOCK

Blocking:
- none

Warnings:
- none

Missing tests:
- none

Confidence: high | medium | low
Need human decision:
- none
```

注意：

- `Verdict` 必须是单一值，不能保留 `PASS / WARN / BLOCK` 占位。
- `Confidence` 必须是单一值，不能保留 `high / medium / low` 占位。
- `BLOCK` verdict 必须在 `Blocking:` 下至少列出一条真实问题。
- review prompt 原样保存不会被当作有效 review。

### test-quality review 额外必需（Tier 2 强证据门）

`test-quality.md` 除上述字段外，必须再给两节，且内容非空（写 `none` 等于没写，会被判格式错误 → Tier 2 BLOCK）：

```text
Red-Evidence:
- 测试名 + 它对哪个错误实现/变异曾经失败过（红→绿证据）
- 若无法让测试先失败，说明原因 + 替代验证

Mutation:
- 关键逻辑变异是否被测试 kill（off-by-one / 边界 / 返回码 / 状态翻转）
- 无变异工具则列人工识别的变异点 + 为何被现有测试覆盖
```

为什么：防 AI 写"全绿假测试"——mock 切掉错误路径、同义反复断言，通过率 100% 却测不出真 bug。红证据强制测试证明过自己能失败；变异结论强制说明测试能 kill 错误。背景见 `feedback/ai-test-failure-modes-four-defenses.md`。可在 `quality_gate.yaml` 设 `evidence.test_quality_red_evidence: false` 关闭。

## 运行方式

```powershell
python harness\scripts\quality_gate.py plan
python harness\scripts\quality_gate.py verify
python harness\scripts\quality_gate.py review-pack --out quality\review-prompts
```

在长期 dirty 的仓库里，可以用 `--path` 限定本轮任务范围：

```powershell
python harness\scripts\quality_gate.py verify --path harness\scripts\quality_gate.py --path harness\tests\test_quality_gate.py
```

Claude Code 可以在 Stop hook 中调用 `verify --enforce`。Codex 和其他客户端应在最终回复前运行同一个命令。Git hook / CI 可以作为最后兜底。

## 例外规则

如果无法写自动化测试，必须在验证证据里说明：

- 为什么无法自动化。
- 用什么替代验证。
- 谁接受这个风险。
- 后续是否需要补测试。
