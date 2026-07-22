# 历史记录“开启新对话”实时伸缩实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让历史侧栏的“开启新对话”按钮占满固定操作区之外的空间，并在拖动边框时与侧栏外壳逐帧同步变化。

**Architecture:** Flex 布局负责按钮的剩余宽度分配；现有 `isDragging` 沿 `useWorkspaceState -> page -> WorkspaceSidebar` 传递，并在拖动期间为 `.sidebar-shell` 添加 `resizing`，仅此时禁用外壳宽度过渡。松开鼠标后类名移除，默认动画恢复。

**Tech Stack:** Next.js 16、React 19、CSS Flexbox、Vitest、Testing Library、Playwright

---

## 文件职责

- `frontend/app/styles/workspace-history.css`：移除新对话按钮的 220px 上限，让按钮占据顶部栏剩余宽度。
- `frontend/app/mobile-chat-layout.test.ts`：守卫按钮的 Flex 宽度规则。
- `frontend/app/useWorkspaceState.ts`：向页面返回已有的 `isDragging` 状态。
- `frontend/app/page.tsx`：把 `isDragging` 传给 `WorkspaceSidebar`。
- `frontend/app/WorkspaceSidebar.tsx`：拖动时给 `.sidebar-shell` 增加 `resizing` 类。
- `frontend/app/styles/workspace-sidebar.css`：仅在 `.sidebar-shell.resizing` 状态下禁用宽度过渡。
- `frontend/app/page.test.tsx`：验证 `mousedown`/`mouseup` 对 `resizing` 类的完整生命周期。
- `frontend/app/workspace-layout.test.ts`：守卫拖动状态的 `transition: none`。

## 已完成实施记录

### Task 1：按钮使用顶部栏剩余宽度

- [x] **Step 1：先写失败的布局守卫**

在 `frontend/app/mobile-chat-layout.test.ts` 中要求：

```ts
expect(stylesheet).toMatch(
  /\.sidebar-history-new-chat\s*\{[^}]*width:\s*auto;[^}]*min-width:\s*0;[^}]*min-height:\s*32px;[^}]*flex:\s*1 1 auto;[^}]*background:\s*var\(--paper-2\);/s,
);
expect(stylesheet).not.toMatch(
  /\.sidebar-history-new-chat\s*\{[^}]*width:\s*min\(100%, 220px\);/s,
);
```

- [x] **Step 2：运行测试并确认 RED**

```powershell
Set-Location frontend
npm test -- --run app/mobile-chat-layout.test.ts
```

修改生产 CSS 前，测试因仍存在 `width: min(100%, 220px)` 而失败。

- [x] **Step 3：实施最小 Flex 修改**

`frontend/app/styles/workspace-history.css` 中的按钮规则改为：

```css
.sidebar-history-new-chat {
  width: auto;
  min-width: 0;
  min-height: 32px;
  flex: 1 1 auto;
}
```

其余视觉、悬停、主题和图标规则保持不变；`.sidebar-history-actions` 继续固定收缩行为。

- [x] **Step 4：运行定向回归并提交**

```powershell
Set-Location frontend
npm test -- --run app/mobile-chat-layout.test.ts
npm test -- --run components/ChatHistorySidebarPanel.test.tsx app/page.test.tsx app/mobile-chat-layout.test.ts
```

实现已提交为 `fix: resize history new chat action live`。

### Task 2：修复真实拖动中的外壳滞后

- [x] **Step 1：用真实浏览器定位根因**

首轮 Playwright 拖动验证显示：内部面板和按钮立即变宽，但 `.sidebar-shell` 的 `width 0.36s` 过渡使外壳在 `during` 阶段滞后，`overflow: hidden` 因而短暂裁切搜索和收起按钮。问题不是 Flex 宽度分配，而是拖动状态仍在执行外壳动画。

- [x] **Step 2：先写拖动生命周期测试**

在 `frontend/app/page.test.tsx` 中使用 `fireEvent`：

```ts
fireEvent.mouseDown(resizer);
expect(sidebarShell).toHaveClass("resizing");

fireEvent.mouseUp(window);
await waitFor(() => {
  expect(sidebarShell).not.toHaveClass("resizing");
});
```

- [x] **Step 3：先写 CSS 结构守卫**

在 `frontend/app/workspace-layout.test.ts` 中要求：

```ts
expect(ruleFor(".sidebar-shell.resizing")).toContain("transition: none;");
```

- [x] **Step 4：运行两个测试并确认 RED**

```powershell
Set-Location frontend
npm test -- --run app/page.test.tsx app/workspace-layout.test.ts
```

生产代码尚未传递 `isDragging`、也没有 `.sidebar-shell.resizing` 规则时，生命周期和样式守卫失败。

- [x] **Step 5：复用现有拖动状态实施最小修复**

`useWorkspaceState` 返回已有 `isDragging`，`page.tsx` 将其传给 `WorkspaceSidebar`。组件在拖动时拼接类名：

```tsx
className={`sidebar-shell ${isSidebarOpen ? "open" : "closed"} ${
  isDragging ? "resizing" : ""
}`}
```

样式仅在拖动时禁用过渡：

```css
.sidebar-shell.resizing {
  transition: none;
}
```

默认 `.sidebar-shell` 的 `width 0.36s cubic-bezier(...)` 保留，鼠标松开后恢复正常动画。

- [x] **Step 6：运行定向回归并提交**

```powershell
Set-Location frontend
npm test -- --run app/page.test.tsx app/workspace-layout.test.ts app/mobile-chat-layout.test.ts components/ChatHistorySidebarPanel.test.tsx
```

修复已提交为 `fix: keep sidebar width live while dragging`。

## 待完成验证与交付

### Task 3：重新验证真实拖动交互

**Files:**

- 临时脚本：`$env:TEMP\history-resize-qa.cjs`
- 临时截图：`$env:TEMP\history-resize-before.png`、`$env:TEMP\history-resize-during.png`、`$env:TEMP\history-resize-after.png`

- [x] **Step 1：启动本地前端并使用 Edge 执行 Playwright**

在 `frontend` 中启动 `http://127.0.0.1:3000`，复用现有 API mock；Browser 插件在当前会话不可用，因此由 Playwright 驱动本机 Microsoft Edge，视口使用 `1280x800`。

- [x] **Step 2：采集同一次拖动的三个阶段**

脚本必须在 `mousedown` 前采集 `before`，在鼠标仍按下且移动后采集 `during`，在继续移动并 `mouseup` 后采集 `after`。每个阶段记录：

```js
{
  sidebar: await sidebar.boundingBox(),
  panel: await panel.boundingBox(),
  topbar: await topbar.boundingBox(),
  button: await newChat.boundingBox(),
  actions: await actions.boundingBox(),
  search: await searchButton.boundingBox(),
  collapse: await collapseButton.boundingBox(),
}
```

- [x] **Step 3：程序化断言同步增量和无裁切**

使用 1px 容差检查：

```js
const duringSidebarDelta = during.sidebar.width - before.sidebar.width;
const duringButtonDelta = during.button.width - before.button.width;
const afterSidebarDelta = after.sidebar.width - before.sidebar.width;
const afterButtonDelta = after.button.width - before.button.width;

assert(Math.abs(duringSidebarDelta - duringButtonDelta) <= 1);
assert(Math.abs(afterSidebarDelta - afterButtonDelta) <= 1);
assert(Math.abs(during.actions.width - before.actions.width) <= 1);
assert(Math.abs(after.actions.width - before.actions.width) <= 1);
```

另外断言搜索和收起按钮的 `left/right` 均位于 `.sidebar-shell` 可视边界内；壳体、面板和顶部栏的 `scrollWidth <= clientWidth + 1`；各操作元素的矩形不重叠。页面 URL、标题和主体内容必须有效，不得出现框架错误覆盖层、相关 `console.error` 或 `pageerror`。

- [x] **Step 4：检查三张截图并停止服务**

人工确认拖动前、中、后三张截图没有裁切、遮挡、横向 overflow 或操作按钮位移。停止且只停止本次记录的开发服务器进程；临时脚本和截图继续留在仓库外。

实际结果：Microsoft Edge + Playwright 的 `before` / `during` / `after` 测量中，sidebar 宽度依次为 `320 / 414 / 484`，新对话按钮宽度依次为 `223 / 317 / 387`，固定 actions 宽度保持 `64 / 64 / 64`；sidebar 与按钮在两个拖动阶段的宽度增量差均为 `0`。三阶段均无裁切、横向 overflow、元素重叠、控制台错误或 `pageerror`，页面内容与布局有效。QA 记录的开发服务器 PID 与端口均已清理，临时脚本和截图未进入仓库。

### Task 4：完整验证、审查与合并

- [x] **Step 1：运行仓库完整验证**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
```

预期：`git diff --check`、后端测试、前端格式化、lint、全部前端测试和生产构建通过。

实际结果：后端测试 `903 passed / 1 skipped`，前端测试 `240 passed`，lint 与生产 build 均通过。

- [x] **Step 2：审查提交范围**

```powershell
git status --short
git diff af46db0 --check
git diff af46db0 --name-only
```

预期：仅包含本设计、实施计划、Flex 样式和守卫、`isDragging` 传递、拖动类名与对应测试；不包含临时 QA 文件、截图、依赖目录、构建产物或锁文件变化。

实际结果：完整验证结束时 `git diff --check` 通过，`git diff` 与 `git status` 均为 clean；提交范围不包含临时 QA 文件、截图、依赖目录、构建产物或锁文件变化。

- [x] **Step 3：完成代码审查**

对 `af46db0..HEAD` 的完整分支差异进行规格和质量审查。若有 Critical 或 Important 问题，修复后重跑受影响测试并重复审查，直到没有阻塞项。

审查结论：Ready to merge；无 Critical 或 Important 问题。

- [ ] **Step 4：按 worktree 流程合并**

在分支验证通过且工作树干净后，使用 fast-forward 合并到 `main`；在 `main` 上重新运行：

```powershell
Set-Location frontend
npm test -- --run app/page.test.tsx app/workspace-layout.test.ts app/mobile-chat-layout.test.ts components/ChatHistorySidebarPanel.test.tsx
```

确认主工作树干净后移除临时 worktree 和功能分支。除非用户明确要求，否则不推送远端。
