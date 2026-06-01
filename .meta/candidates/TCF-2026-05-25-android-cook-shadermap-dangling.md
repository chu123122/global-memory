# Task-Context Fallback Candidate: android-cook-shadermap-dangling

- recommendation / 建议: `ALREADY_ENABLED`
- risk / 风险: `LOW`
- zero_hit / 空召回: `20`
- short_followup_rate / 短追问比例: `0.9`
- new_hits / 新命中: `3/3`
- still_empty / 仍为空: `0`
- concrete_pointer_rate / 具体指针比例: `1.0`
- generic_pointer_rate / 泛指针比例: `0.0`
- reason_codes / 原因: `task_level_config_already_enabled`

## Samples / 样本

### NEW_HIT - 数据采集到了吗？e2e我记得是有数据测试的？
- shape / 形态: `task_specific`
- context_chars / 注入字符数: `617`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/fixes/fix_cook_av_dangling_shadermap.md, ~/.claude/global-memory/fixes/fix_uat_silent_cook_failure.md`
- trace_top / 最高候选:
  - rank 1 score=9.6 `~/.claude/global-memory/fixes/fix_cook_av_dangling_shadermap.md` - kw:error:cook_av, kw:error:shader, kw:concept:shadermap
  - rank 2 score=4.8 `~/.claude/global-memory/fixes/fix_uat_silent_cook_failure.md` - kw:error:cook_av, kw:platform:android
  - rank 3 score=4.0 `~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md` - kw:error:shader, kw:concept:cpp

### NEW_HIT - 我是指这台机器测试看一下能不能拿到API数据，用这个新打的包
- shape / 形态: `short_followup`
- context_chars / 注入字符数: `617`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/fixes/fix_cook_av_dangling_shadermap.md, ~/.claude/global-memory/fixes/fix_uat_silent_cook_failure.md`
- trace_top / 最高候选:
  - rank 1 score=9.6 `~/.claude/global-memory/fixes/fix_cook_av_dangling_shadermap.md` - kw:error:cook_av, kw:error:shader, kw:concept:shadermap
  - rank 2 score=4.8 `~/.claude/global-memory/fixes/fix_uat_silent_cook_failure.md` - kw:error:cook_av, kw:platform:android
  - rank 3 score=4.0 `~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md` - kw:error:shader, kw:concept:cpp

### NEW_HIT - 目前情况？
- shape / 形态: `short_followup`
- context_chars / 注入字符数: `617`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/fixes/fix_cook_av_dangling_shadermap.md, ~/.claude/global-memory/fixes/fix_uat_silent_cook_failure.md`
- trace_top / 最高候选:
  - rank 1 score=9.6 `~/.claude/global-memory/fixes/fix_cook_av_dangling_shadermap.md` - kw:error:cook_av, kw:error:shader, kw:concept:shadermap
  - rank 2 score=4.8 `~/.claude/global-memory/fixes/fix_uat_silent_cook_failure.md` - kw:error:cook_av, kw:platform:android
  - rank 3 score=4.0 `~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md` - kw:error:shader, kw:concept:cpp
