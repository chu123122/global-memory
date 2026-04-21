#!/bin/bash
# C++ 语法检查
# 用法：bash check_cpp_syntax.sh [目录，默认当前目录]

DIR="${1:-.}"
ERRORS=0

echo "=== C++ 语法检查: $DIR ==="
for f in $(find "$DIR" -name "*.cpp" -o -name "*.h" -o -name "*.hpp" | head -50); do
    OUTPUT=$(g++ -fsyntax-only -std=c++17 "$f" 2>&1)
    if [ $? -ne 0 ]; then
        echo "❌ $f"
        echo "   $OUTPUT" | head -3
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
    echo "✅ 所有 C++ 文件语法正确"
    exit 0
fi
