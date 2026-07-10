#!/bin/bash

# 笔记功能修复验证脚本

echo "=== 笔记功能修复验证 ==="
echo ""

# 检查修改的文件
echo "1. 检查修改的文件..."
files=(
  "VideoNoteAiPanel.tsx"
  "VideoNoteMarkdownEditor.tsx"
  "VideoNoteToolRail.tsx"
  "VideoNoteWorkspace.tsx"
  "../app/styles/video-notes/side-panels.css"
  "../app/styles/video-notes/tool-rail-export.css"
  "../app/styles/video-notes/editor.css"
  "../app/styles/video-notes/responsive.css"
)

for file in "${files[@]}"; do
  if [ -f "$file" ]; then
    echo "  ✓ $file 存在"
  else
    echo "  ✗ $file 不存在"
  fi
done

echo ""
echo "2. 验证关键修复..."

# 检查 AI 按钮状态
if grep -q "aria-busy" VideoNoteAiPanel.tsx; then
  echo "  ✓ AI 按钮加载状态已添加"
else
  echo "  ✗ AI 按钮加载状态缺失"
fi

# 检查加载动画
if grep -q "loading-progress" ../app/styles/video-notes/side-panels.css; then
  echo "  ✓ 加载动画已添加"
else
  echo "  ✗ 加载动画缺失"
fi

# 检查错误处理
error_count=$(grep -c "catch.*error" VideoNoteWorkspace.tsx)
if [ "$error_count" -ge 4 ]; then
  echo "  ✓ 错误处理已添加 ($error_count 处)"
else
  echo "  ✗ 错误处理不完整 (仅 $error_count 处)"
fi

# 检查展开按钮
if grep -q "video-note-ai-expand" VideoNoteAiPanel.tsx; then
  echo "  ✓ AI 面板展开按钮已添加"
else
  echo "  ✗ AI 面板展开按钮缺失"
fi

# 检查移动端优化
if grep -q "touch-action" ../app/styles/video-notes/responsive.css; then
  echo "  ✓ 移动端触摸优化已添加"
else
  echo "  ✗ 移动端触摸优化缺失"
fi

# 检查编辑器错误恢复
if grep -q "重新加载页面" VideoNoteMarkdownEditor.tsx; then
  echo "  ✓ 编辑器错误恢复已添加"
else
  echo "  ✗ 编辑器错误恢复缺失"
fi

# 检查导出状态提示
if grep -q "已复制到剪贴板" VideoNoteToolRail.tsx; then
  echo "  ✓ 导出状态提示已优化"
else
  echo "  ✗ 导出状态提示未优化"
fi

echo ""
echo "3. 统计代码变更..."
total_lines=0
for file in "${files[@]}"; do
  if [ -f "$file" ]; then
    lines=$(wc -l < "$file" 2>/dev/null || echo 0)
    total_lines=$((total_lines + lines))
  fi
done
echo "  总行数: $total_lines"

echo ""
echo "=== 验证完成 ==="
echo ""
echo "下一步："
echo "1. 启动开发服务器: npm run dev"
echo "2. 访问笔记功能并测试以下场景："
echo "   - AI 按钮加载状态显示"
echo "   - 工具栏按钮交互"
echo "   - AI 面板折叠/展开"
echo "   - 导出功能状态提示"
echo "   - 错误场景处理"
echo "3. 在移动端测试响应式布局"
