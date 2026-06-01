# Task-Context Fallback Candidate: aik-refactor-ui-provider

- recommendation / 建议: `REVIEW`
- risk / 风险: `MEDIUM`
- zero_hit / 空召回: `18`
- short_followup_rate / 短追问比例: `0.7222`
- new_hits / 新命中: `3/3`
- still_empty / 仍为空: `0`
- concrete_pointer_rate / 具体指针比例: `0.5`
- generic_pointer_rate / 泛指针比例: `0.5`
- reason_codes / 原因: `promising_but_needs_human_review`

## Samples / 样本

### NEW_HIT - 我没看懂为什么出问题，这个修改是如何导致问题的，相关名词我没看懂，请讲解一下
- shape / 形态: `short_followup`
- context_chars / 注入字符数: `617`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/feedback/feedback_compile_after_module_change.md, ~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md`
- trace_top / 最高候选:
  - rank 1 score=6.0 `~/.claude/global-memory/feedback/feedback_compile_after_module_change.md` - kw:concept:style, kw:concept:cpp, kw:tool:ue
  - rank 2 score=6.0 `~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md` - kw:concept:style, kw:concept:cpp, kw:tool:ue
  - rank 3 score=4.0 `~/.claude/global-memory/feedback/feedback_code_style.md` - kw:concept:cpp, kw:tool:ue

### NEW_HIT - 先走v1
- shape / 形态: `short_followup`
- context_chars / 注入字符数: `617`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/feedback/feedback_compile_after_module_change.md, ~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md`
- trace_top / 最高候选:
  - rank 1 score=6.0 `~/.claude/global-memory/feedback/feedback_compile_after_module_change.md` - kw:concept:style, kw:concept:cpp, kw:tool:ue
  - rank 2 score=6.0 `~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md` - kw:concept:style, kw:concept:cpp, kw:tool:ue
  - rank 3 score=4.0 `~/.claude/global-memory/feedback/feedback_code_style.md` - kw:concept:cpp, kw:tool:ue

### NEW_HIT - 目前情况？
- shape / 形态: `short_followup`
- context_chars / 注入字符数: `617`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/feedback/feedback_compile_after_module_change.md, ~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md`
- trace_top / 最高候选:
  - rank 1 score=6.0 `~/.claude/global-memory/feedback/feedback_compile_after_module_change.md` - kw:concept:style, kw:concept:cpp, kw:tool:ue
  - rank 2 score=6.0 `~/.claude/global-memory/fixes/fixes_shader_code_library_missing.md` - kw:concept:style, kw:concept:cpp, kw:tool:ue
  - rank 3 score=4.0 `~/.claude/global-memory/feedback/feedback_code_style.md` - kw:concept:cpp, kw:tool:ue
