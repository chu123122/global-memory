#!/bin/bash
# Lua 语法批量检查
# 用法：bash check_lua_syntax.sh [目录，默认当前目录]

DIR="${1:-.}"
ERRORS=0

echo "=== Lua 语法检查: $DIR ==="
for f in $(find "$DIR" -name "*.lua" -type f); do
    OUTPUT=$(luac -p "$f" 2>&1)
    if [ $? -ne 0 ]; then
        echo "❌ $f"
        echo "   $OUTPUT"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ $f"
    fi
done

echo ""
if [ $ERRORS -gt 0 ]; then
    echo "⚠️ $ERRORS 个文件有语法错误"
    exit 1
else
    echo "✅ 所有 Lua 文件语法正确"
    exit 0
fi
