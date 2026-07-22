# 历史记录“开启新对话”实时伸缩设计

## 背景

桌面端历史记录侧栏支持拖动右侧边框调整宽度。最初的问题有两层：

- 顶部“开启新对话”按钮使用 `width: min(100%, 220px)`，达到 220px 后不再随侧栏继续变宽。
- 首轮真实浏览器拖动验证发现，内部历史面板会在每次 `mousemove` 后立即应用新宽度，但外层 `.sidebar-shell` 保留 `width 0.36s` 过渡。拖动过程中外壳宽度滞后于内部面板，配合 `overflow: hidden` 会短暂裁切搜索和收起按钮。

因此，仅移除按钮的 220px 上限不足以保证“实时变化”；外层壳体也必须在正在拖动时立即同步宽度。

## 目标

- “开启新对话”按钮始终占满历史面板顶部除搜索和收起操作区以外的剩余宽度。
- 拖动侧栏边框时，外层壳体、内部面板和新对话按钮随每次鼠标移动同步伸缩。
- 搜索和收起操作区保持固定宽度，拖动前、中、后均不被裁切或遮挡。
- 鼠标松开后恢复侧栏原有的打开、关闭及非拖动宽度动画。
- 保持新建对话、搜索、收起、历史列表及宽度持久化行为不变。

## 非目标

- 不修改侧栏最小宽度、最大宽度、拖拽计算或本地宽度持久化逻辑。
- 不新增拖拽状态；复用 `useWorkspaceState` 已有的 `isDragging`。
- 不改变新对话按钮的颜色、圆角、图标或点击行为。
- 不调整历史记录分组、搜索和数据加载逻辑。

## 方案

### 1. 顶部操作区使用 Flex 分配剩余空间

`.sidebar-history-new-chat` 移除 `width: min(100%, 220px)` 和固定收缩规则，改为：

```css
width: auto;
min-width: 0;
flex: 1 1 auto;
```

`.sidebar-history-actions` 继续使用 `flex-shrink: 0`。浏览器由此把搜索和收起按钮占用后的全部剩余宽度分给“开启新对话”按钮，并允许按钮在较窄布局中安全收缩。

### 2. 拖动期间关闭外层宽度过渡

复用现有状态流：

```text
useWorkspaceState.isDragging
  -> page.tsx
  -> WorkspaceSidebar.isDragging
  -> .sidebar-shell.resizing
```

`WorkspaceSidebar` 在拖动时为外层壳体增加 `resizing` 类；样式只在该状态下关闭宽度过渡：

```css
.sidebar-shell.resizing {
  transition: none;
}
```

正常状态仍保留 `.sidebar-shell` 的 `width 0.36s cubic-bezier(...)`，因此打开、关闭和非拖动宽度变化的动画不受影响。鼠标松开后，现有 `handleMouseUp` 将 `isDragging` 设为 `false`，`resizing` 类随 React 重渲染移除，默认动画自动恢复。

这一方案不重复计算按钮宽度，也不新增鼠标监听或状态；Flex 负责内部剩余空间，`isDragging` 只负责区分“实时拖动”和“正常动画”两种外壳表现。

## 响应式行为

移动端没有桌面拖拽边框，但沿用同一 Flex 规则：按钮填满固定操作区之外的空间，并可在窄宽度中收缩。桌面端拖动时，外壳不再因过渡滞后而裁切内部操作区；拖动结束后恢复原有动画。

## 自动化测试

- `frontend/app/mobile-chat-layout.test.ts`：守卫新对话按钮采用 `width: auto`、`min-width: 0`、`flex: 1 1 auto`，并禁止恢复 `width: min(100%, 220px)`。
- `frontend/app/page.test.tsx`：触发 `.resizer` 的 `mousedown`，断言 `.sidebar-shell` 获得 `resizing`；在 `window` 上触发 `mouseup`，断言该类被移除。
- `frontend/app/workspace-layout.test.ts`：守卫 `.sidebar-shell.resizing` 包含 `transition: none`，同时保留默认壳体过渡规则。
- 历史面板组件及相邻首页、移动布局测试继续覆盖既有交互与响应式回归。

## 真实浏览器验证

Browser 插件在当前会话不可用，因此使用项目依赖和 Microsoft Edge 执行常规 Playwright 验证。验证必须在同一次拖动中采集 `before`、`during`、`after` 三个阶段，并程序化断言：

- `during.sidebar - before.sidebar` 与 `during.button - before.button` 的增量近似相等，证明外壳和按钮同步变化，而不是只在松手后追上。
- `after.sidebar - before.sidebar` 与 `after.button - before.button` 的增量近似相等。
- `.sidebar-history-actions` 宽度保持不变，搜索和收起按钮的边界始终位于外壳可视区域内。
- 顶部栏、内部面板和外层壳体没有水平 overflow、重叠或裁切。
- 页面 URL、标题和主体内容有效；没有框架错误覆盖层、相关控制台错误或 `pageerror`。
- 保存并人工检查拖动前、拖动中、拖动后三张截图。

## 验收标准

- 在桌面端按住历史侧栏边框移动鼠标时，外层壳体与“开启新对话”按钮随每次移动实时同步变化。
- 按钮右边缘始终与搜索/收起操作区保持既有间距。
- 搜索和收起按钮在拖动前、中、后及最小、默认、最大侧栏宽度下均可见、可点击。
- 松开鼠标后 `.resizing` 被移除，侧栏正常动画恢复。
- 移动端历史面板顶部无横向溢出。
- 相关自动化测试、真实浏览器验证、lint 和生产构建通过。
