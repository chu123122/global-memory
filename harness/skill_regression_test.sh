#!/bin/bash
# Skill 回归测试运行器
# 用法：bash skill_regression_test.sh <skill_name>

SKILL_NAME="$1"
if [ -z "$SKILL_NAME" ]; then
    echo "用法: bash skill_regression_test.sh <skill_name>"
    exit 1
fi

SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"

echo "=== 回归测试: $SKILL_NAME ==="

if [ ! -d "$SKILL_DIR" ]; then
    echo "❌ Skill 目录不存在: $SKILL_DIR"
    exit 1
fi

# 检查 SKILL.md（-L 追踪 symlink）
SKILL_MD=$(find -L "$SKILL_DIR" -name "SKILL.md" | head -1)
if [ -z "$SKILL_MD" ]; then
    echo "❌ SKILL.md 不存在"
    exit 1
else
    echo "✅ SKILL.md 存在"

    LINES=$(wc -l < "$SKILL_MD")
    if [ "$LINES" -gt 500 ]; then
        echo "⚠️ SKILL.md 行数 ($LINES) 超过 500 行限制"
    else
        echo "✅ SKILL.md 行数: $LINES"
    fi

    HEAD=$(head -1 "$SKILL_MD")
    if [ "$HEAD" != "---" ]; then
        echo "❌ SKILL.md 缺少 YAML 头部"
    else
        echo "✅ YAML 头部存在"
    fi
fi

# 运行 Skill 自带脚本
SCRIPTS_DIR=$(find -L "$SKILL_DIR" -type d -name "scripts" | head -1)
if [ -n "$SCRIPTS_DIR" ] && [ -d "$SCRIPTS_DIR" ]; then
    for script in "$SCRIPTS_DIR"/*.sh; do
        [ ! -f "$script" ] && continue
        echo "--- 运行: $(basename $script) ---"
        bash "$script"
        if [ $? -ne 0 ]; then
            echo "❌ $(basename $script) 失败"
        else
            echo "✅ $(basename $script) 通过"
        fi
    done
fi

echo ""
echo "=== 回归测试完成 ==="
