# 登录页桌面布局对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复桌面登录页账号提示横向错位，并将左上 Logo 向左、左侧登录主体向上做小幅视觉调整，同时保持移动端布局不变。

**Architecture:** 保持现有 `AuthPage` 组件结构，仅补充语义化品牌类和明确的纵向 Flex 类；桌面位移集中在 `auth.css`，并在既有 `max-width: 1024px` 响应式区间清除。组件测试负责锁定结构契约，渲染检查负责验证真实视觉位置。

**Tech Stack:** Next.js、React、TypeScript、Tailwind CSS、CSS、Vitest、Testing Library、Playwright

---

### Task 1: 锁定桌面登录页布局结构

**Files:**

- Modify: `frontend/components/AuthPage.test.tsx`
- Test: `frontend/components/AuthPage.test.tsx`

- [ ] **Step 1: 写入失败的结构回归测试**

在 `AuthPage` 测试中加入以下两个断言：

```tsx
it("stacks the desktop login content and account hint vertically", () => {
  const { container } = render(<AuthPage onAuthSuccess={vi.fn()} />);

  expect(container.querySelector(".auth-form-section")).toHaveClass("flex-col");
});

it("marks the brand separately so desktop alignment does not move header actions", () => {
  const { container } = render(<AuthPage onAuthSuccess={vi.fn()} />);
  const brand = container.querySelector(".auth-brand");

  expect(brand).toBeInTheDocument();
  expect(brand).toContainElement(screen.getByText("智库云"));
  expect(container.querySelector(".auth-header-actions")).not.toContainElement(
    brand,
  );
});
```

- [ ] **Step 2: 运行测试并确认按预期失败**

Run: `npm test -- --run frontend/components/AuthPage.test.tsx`

Expected: FAIL，第一项缺少 `flex-col`，第二项找不到 `.auth-brand`。

- [ ] **Step 3: 提交测试红灯（与实现一起提交，不单独留下失败提交）**

记录失败输出后继续 Task 2；最终提交同时包含测试与实现，避免主分支出现不可运行提交。

### Task 2: 实现纵向排列与桌面位移

**Files:**

- Modify: `frontend/components/AuthPage.tsx`
- Modify: `frontend/app/styles/auth.css`
- Test: `frontend/components/AuthPage.test.tsx`

- [ ] **Step 1: 为品牌和表单区补充布局类**

在 `AuthPage.tsx` 中将品牌容器和表单区域更新为：

```tsx
<div className="auth-brand flex items-center gap-2.5">
```

```tsx
className =
  "auth-form-section auth-form-section-lowered flex flex-col items-center justify-center py-6";
```

- [ ] **Step 2: 添加桌面位移和响应式清除规则**

在 `auth.css` 的基础规则中加入：

```css
.auth-page .auth-brand {
  transform: translateX(-16px);
}

.auth-page .auth-form-section-lowered {
  transform: translateY(-24px);
}
```

在 `@media (max-width: 1024px)` 中加入：

```css
.auth-page .auth-brand,
.auth-page .auth-form-section-lowered {
  transform: none;
}
```

- [ ] **Step 3: 运行组件测试并确认通过**

Run: `npm test -- --run frontend/components/AuthPage.test.tsx`

Expected: PASS，`AuthPage.test.tsx` 全部测试通过。

- [ ] **Step 4: 检查格式与类型构建**

Run: `npm run lint`

Expected: exit 0，无 lint 错误。

Run: `npm run build`

Expected: exit 0，Next.js production build 成功。

### Task 3: 渲染验证与提交

**Files:**

- Verify: `frontend/components/AuthPage.tsx`
- Verify: `frontend/app/styles/auth.css`
- Verify: `frontend/components/AuthPage.test.tsx`

- [ ] **Step 1: 启动前端并检查桌面视口**

Run: `npm run dev`

用 Playwright 打开本地登录页，桌面视口使用 `2048x1152`。验证账号提示位于认证卡片正下方、品牌仅向左位移、左侧主体整体向上，页面无框架错误遮罩和相关控制台错误。

- [ ] **Step 2: 检查移动视口**

使用 `390x844` 视口重新加载登录页。验证桌面 transform 已清除，账号提示仍采用现有底部定位且无裁切、重叠或横向滚动。

- [ ] **Step 3: 检查最终差异**

Run: `git diff --check`

Expected: exit 0，无空白错误。

Run: `git diff -- frontend/components/AuthPage.tsx frontend/app/styles/auth.css frontend/components/AuthPage.test.tsx`

Expected: 仅包含纵向排列、品牌标记、桌面位移和对应测试。

- [ ] **Step 4: 提交实现**

```powershell
git add -- frontend/components/AuthPage.tsx frontend/app/styles/auth.css frontend/components/AuthPage.test.tsx docs/superpowers/specs/2026-07-28-auth-page-desktop-alignment-design.md docs/superpowers/plans/2026-07-28-auth-page-desktop-alignment.md
git commit -m "fix: align auth page desktop layout"
```
