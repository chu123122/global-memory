# Codex 工作约束

本仓库的代码改动默认受 AI 代码质量门约束。

## 交付前质量门

修改代码后，在最终回复前运行：

```powershell
python harness\scripts\quality_gate.py verify --json
```

长期 dirty 仓库中，必须用 `--path` 限定本轮实际修改范围，避免把历史未提交变更混入质量门：

```powershell
python harness\scripts\quality_gate.py verify --path harness\scripts\quality_gate.py --path harness\tests\test_quality_gate.py --json
```

如果需要强制阻断语义，运行：

```powershell
python harness\scripts\quality_gate.py verify --enforce --json
```

规则入口：`docs/spec/QUALITY_GATE.md`。项目配置：`quality_gate.yaml`。

执行原则：

- Tier 0/1 可以只记录验证说明。
- Tier 2 必须有测试证据和 `correctness` / `test-quality` 两个审查结果。
- Tier 3 必须有四视角审查、人工裁决、回滚或恢复说明。
- AI review 不能替代确定性检查。
- Review 结果必须放在 `quality/reviews/<kind>.md` 或用 `--review-dir` 指定；文件需要合法 `Verdict`、`Confidence` 和固定 section，不能只保存 review prompt。
