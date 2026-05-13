# 智库云·收藏夹知识库 — 前端界面优化文档

> 基于 DeepSeek 对话界面风格，针对当前 Bilibili RAG 项目的前端全面优化方案。
> 创建日期：2026-04-27

---

## 一、现状分析

### 1.1 当前技术栈

- **框架**: Next.js 16 (App Router) + React 19 + TypeScript
- **样式**: Tailwind CSS v4 + 全局自定义 CSS (`globals.css`, ~1058 行)
- **字体**: ZCOOL XiaoWei (展示) + Noto Sans SC (正文)
- **Markdown 渲染**: react-markdown + remark-gfm

### 1.2 当前界面结构

```
┌─────────────────────────────────────────┐
│  Topbar: 品牌标识 ─────── 登录/用户信息  │
├─────────────────────────────────────────┤
│                                         │
│  未登录: Hero 欢迎页 (居中)              │
│  已登录: [SourcesPanel | ChatPanel]     │
│                                         │
├─────────────────────────────────────────┤
│              Footer 版权信息             │
└─────────────────────────────────────────┘
```

### 1.3 当前设计风格

- 暖纸色调 (paper: `#f7f1e8`) + 琥珀/青色点缀
- 毛玻璃背景 (`backdrop-filter: blur`) + 微弱网格纹理
- 圆角卡片 (`border-radius: 14px~20px`)
- 双面板工作台 (左 320px 收藏夹 + 右自适应对话)

### 1.4 关键痛点

| 问题 | 描述 |
|------|------|
| 没有暗色模式 | 仅有暖色浅色主题，缺少夜间使用舒适度 |
| 无对话历史侧边栏 | 对话清空后数据完全丢失，无法回溯 |
| 输入区交互单一 | 仅有文本 input + 发送按钮 |
| 欢迎页与工作台割裂 | 登录后直接进入双面板，缺少空状态引导 |
| 移动端体验不佳 | ≤1024px 直接堆叠为纵向 |
| 缺少加载骨架屏 | 数据加载时仅显示文字"加载中..." |

---

## 二、DeepSeek 参考界面特征

### 2.1 布局结构

```
┌──────────┬──────────────────────────────────┐
│ Sidebar  │                                  │
│ ────────  │   居中欢迎区域                    │
│ 新建对话  │   "使用快速模式开始对话"            │
│          │   [快问模式] [交谈模式]             │
│ 历史分组  │                                  │
│  今天     │                                  │
│  7天内    │                                  │
│  30天内   │   ┌─────────────────────────┐    │
│  2026-03  │   │  输入框 + 工具按钮        │    │
│  2026-02  │   └─────────────────────────┘    │
│  ...      │                                  │
│ ────────  │                                  │
│ 用户头像  │                                  │
└──────────┴──────────────────────────────────┘
```

### 2.2 核心设计特征

| 特征 | 描述 |
|------|------|
| 深色主题 | 近黑色背景，低对比度文字 |
| 左侧边栏 | 固定宽度，包含"新建对话"按钮 + 按时间分组的历史记录 |
| 时间分组 | 今天 / 7天内 / 30天内 / 按月归档 |
| 居中引导 | 空状态时主区域居中显示欢迎语 + 模式选择 |
| 底部输入 | 圆角输入框悬浮在主区域底部，附带附件/搜索图标 + 发送按钮 |
| 模式切换 | 支持多种对话风格 |
| 用户入口 | 左下角用户头像 + 状态指示 |

---

## 三、优化方案

### 3.1 整体布局重构

从 "Topbar + 双面板" 过渡为 "Sidebar + 主内容区"。

#### 新布局

```
┌───────────────┬─────────────────────────────────────────────┐
│   Sidebar     │              Main Content Area              │
│   (280px)     │                                             │
│               │  ┌─────────────────────────────────────┐    │
│  Logo/Brand   │  │  Topbar: 收藏夹状态 / 设置按钮       │    │
│  ───────────  │  ├─────────────────────────────────────┤    │
│  + 新建对话    │  │                                     │    │
│               │  │  空状态: 居中欢迎 + 预设问题          │    │
│  对话历史      │  │  对话中: 消息流                      │    │
│   ├ 今天       │  │                                     │    │
│   │  对话1     │  ├─────────────────────────────────────┤    │
│   │  对话2     │  │  Input Bar (浮动底部)                │    │
│   ├ 7天内      │  │  [附件] [输入框] [收藏夹] [发送]     │    │
│   ...         │  └─────────────────────────────────────┘    │
│  ───────────  │                                             │
│  收藏夹管理    │                                             │
│  ───────────  │                                             │
│  用户信息      │                                             │
└───────────────┴─────────────────────────────────────────────┘
```

#### 新组件树

```
App (layout.tsx)
├── Sidebar/
│   ├── SidebarHeader        (Logo + 新建对话按钮)
│   ├── ConversationList     (对话历史, 按时间分组)
│   ├── FavoritesDrawer      (收藏夹管理, 可折叠)
│   └── SidebarFooter        (用户头像 + 设置)
├── MainContent/
│   ├── ContentHeader        (当前对话标题 + 操作按钮)
│   ├── ChatArea/
│   │   ├── WelcomeScreen    (空状态引导)
│   │   └── MessageList      (消息流)
│   └── InputBar             (底部浮动输入区)
├── LoginModal
└── DemoFlowModal
```

### 3.2 暗色主题系统

建立双主题 CSS 变量体系，通过 `<html data-theme="dark">` 切换。

**亮色主题** (保留当前)：

```css
:root {
  --bg-primary: #f7f1e8;
  --bg-secondary: #efe6d7;
  --bg-tertiary: #e6d7c2;
  --bg-surface: rgba(255, 255, 255, 0.75);
  --text-primary: #1b1713;
  --text-secondary: #2b241d;
  --text-muted: #7b7167;
  --border-default: #dccbb4;
  --accent-primary: #d98b2b;
  --accent-secondary: #2f7c78;
}
```

**暗色主题** (参考 DeepSeek)：

```css
[data-theme="dark"] {
  --bg-primary: #0d0f11;
  --bg-secondary: #151719;
  --bg-tertiary: #1a1d21;
  --bg-surface: rgba(30, 33, 38, 0.85);
  --text-primary: #e8e6e3;
  --text-secondary: #b0aca6;
  --text-muted: #6b6760;
  --border-default: rgba(255, 255, 255, 0.08);
  --accent-primary: #4d9de0;
  --accent-secondary: #3ecf8e;
  --sidebar-bg: #111315;
  --sidebar-hover: rgba(255, 255, 255, 0.06);
  --sidebar-active: rgba(77, 157, 224, 0.12);
}
```

### 3.3 侧边栏设计

#### SidebarHeader

- Logo 区域精简为图标 + 短标题
- "开启新对话"按钮使用醒目描边样式
- 侧边栏可通过汉堡菜单折叠

#### ConversationList

对话历史按时间分组：今天 / 7天内 / 30天内 / 按月归档。

数据结构：

```typescript
interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  folder_ids: number[];
}
```

初期使用 `localStorage` 持久化，后续对接后端 API。

#### FavoritesDrawer

将 SourcesPanel 浓缩为可折叠区域：
- 默认折叠，点击展开
- 列表简化为：复选框 + 标题 + 入库状态图标
- 入库操作按钮在折叠区底部

### 3.4 主内容区

#### WelcomeScreen

空状态居中引导：

```
              ┌─────────────────────┐
              │      Logo 图标       │
              │ 把"收藏"变成可用的知识  │
              │ [智能问答] [快速检索]  │
              └─────────────────────┘
```

模式选择：
- **智能问答**: 基于 RAG 深度回答，带来源引用
- **快速检索**: 直接返回相关视频列表

#### InputBar

底部浮动输入区：

```
┌─────────────────────────────────────────────────┐
│  在此输入问题，按 Enter 发送...                   │
│  ────────────────────────────────────            │
│  [📎 附件] [🔍 深度搜索] [📂 收藏夹]       [➤]  │
└─────────────────────────────────────────────────┘
```

- `textarea` 替代 `input`，自动扩高 (最多 5 行)
- `Shift+Enter` 换行，`Enter` 发送
- 收藏夹选择器嵌入输入栏

#### MessageList 改进

- AI 消息带头像图标，去掉边框改用微妙底色
- 来源链接改为可折叠引用卡片组
- 新增消息操作栏：复制 / 重新生成 / 点赞点踩
- 流式回答时显示打字机闪烁光标

### 3.5 动效

- 消息入场: `translateY(12px)` 淡入
- 打字机光标: `▊` 闪烁效果
- 侧边栏过渡: `width` 动画 + 移动端覆盖式抽屉
- 骨架屏: `shimmer` 渐变动画

### 3.6 响应式策略

| 断点 | 宽度 | 策略 |
|------|------|------|
| Desktop | ≥1280px | 侧边栏(280px) + 主区域 |
| Tablet | 768~1279px | 侧边栏可折叠(图标模式 64px) |
| Mobile | <768px | 侧边栏为覆盖式抽屉 + 全宽主区域 |

---

## 四、文件改动清单

### 新增文件

| 文件 | 用途 |
|------|------|
| `components/Sidebar.tsx` | 侧边栏主组件 |
| `components/ConversationList.tsx` | 对话历史列表 |
| `components/FavoritesDrawer.tsx` | 收藏夹折叠区 |
| `components/WelcomeScreen.tsx` | 空状态欢迎引导 |
| `components/InputBar.tsx` | 底部输入区 |
| `components/MessageActions.tsx` | 消息操作栏 |
| `components/ThemeToggle.tsx` | 主题切换 |
| `components/SkeletonLoader.tsx` | 骨架屏 |
| `hooks/useTheme.ts` | 主题管理 |
| `hooks/useConversations.ts` | 对话历史管理 |

### 改动文件

| 文件 | 改动 |
|------|------|
| `app/layout.tsx` | 添加 data-theme 支持 |
| `app/page.tsx` | 重构为 Sidebar + MainContent |
| `app/globals.css` | 双主题变量 + 侧边栏样式 |
| `components/ChatPanel.tsx` | 拆分/集成新组件 |
| `components/SourcesPanel.tsx` | 简化为 FavoritesDrawer |
| `lib/api.ts` | 新增对话 API 类型 |

---

## 五、实施优先级

### P0 — 核心体验

1. 暗色主题系统
2. 侧边栏布局重构
3. 输入栏重设计
4. 空状态欢迎引导页

### P1 — 交互增强

5. 对话历史 (localStorage)
6. 消息操作栏
7. 收藏夹折叠抽屉
8. 骨架屏加载

### P2 — 体验打磨

9. 流式动效
10. 移动端适配
11. 全局搜索
12. 键盘快捷键

---

## 六、注意事项

1. **渐进迁移**: 保留亮色主题作为可选，暗色作为默认
2. **性能**: 对话历史列表考虑虚拟滚动
3. **无障碍**: 暗色模式确保 WCAG AA 级对比度
4. **数据持久化**: 后端就绪前用 localStorage
5. **字体**: 暗色下 ZCOOL XiaoWei 考虑增大 font-weight
6. **兼容**: OrganizePreviewModal / DemoFlowModal 保持独立模态框
