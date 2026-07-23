# API Key Configuration UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace cramped API Key editing with a shared, tabbed credential editor, give personal keys a list-first workflow, and polish only the official/personal source switch at the top of the existing model menu.

**Architecture:** Add presentation-only shared components for the editor shell and thinking JSON editor, while keeping official model persistence in `useChatModelSettings` and personal account CRUD in `useApiAccountsPanel`. The model provider menu remains structurally unchanged; only its source selector CSS changes. The personal panel gains explicit `list/create/edit` view state and reads existing provider templates from `chatApi.getModelConfig()` without changing backend APIs.

**Tech Stack:** Next.js 16, React 19, TypeScript, CSS Grid/Flexbox, Testing Library, Vitest, Playwright

---

## File Map

### New files

- `frontend/components/api-credentials/ApiCredentialEditorShell.tsx`: shared header, tabs, scroll body, and footer layout.
- `frontend/components/api-credentials/ApiCredentialEditorShell.test.tsx`: shell navigation and tab semantics.
- `frontend/components/api-credentials/ThinkingConfigEditor.tsx`: shared off/standard/custom request configuration editor.
- `frontend/components/api-credentials/ThinkingConfigEditor.test.tsx`: mode, formatting, read-only, and invalid JSON behavior.
- `frontend/components/api-accounts/types.ts`: personal account form and panel view types.
- `frontend/app/styles/api-credential-editor.css`: shared editor and JSON editor styling.
- `frontend/app/api-key-config-layout.test.ts`: focused CSS layout and responsive guards.

### Existing files to modify

- `frontend/app/styles/modals.css`: import shared editor styles.
- `frontend/app/styles/modal-provider-config.css`: widen the official provider modal and remove request-editor rules moved to the shared stylesheet.
- `frontend/app/styles/modal-responsive.css`: adapt the shared editor for narrow viewports.
- `frontend/app/styles/chat-model-controls.css`: style only the official/personal source selector.
- `frontend/app/styles/api-accounts-panel.css`: list-first desktop layout and account item styling.
- `frontend/app/styles/account-panels-responsive.css`: mobile personal-key layout.
- `frontend/components/chat/ModelConfigModal.tsx`: compose the shared shell and request editor.
- `frontend/components/chat/useChatModelSettings.ts`: preserve a custom JSON draft independently of the selected request mode.
- `frontend/components/ChatPanel.tsx`: pass the simplified request-mode callbacks.
- `frontend/components/ChatPanel.config.test.tsx`: guard official save behavior and unchanged model-menu interaction.
- `frontend/components/api-accounts/useApiAccountsPanel.ts`: add panel view state, provider templates, and thinking config payloads.
- `frontend/components/api-accounts/ApiAccountsPanelView.tsx`: switch between list and editor views.
- `frontend/components/api-accounts/ApiAccountsList.tsx`: two-column account items and compact action menu.
- `frontend/components/api-accounts/ApiAccountForm.tsx`: tabbed personal credential editor.
- `frontend/components/ApiAccountsPanel.tsx`: wire new view actions and template data.
- `frontend/components/ApiAccountsPanel.test.tsx`: cover list/create/edit flows and thinking config persistence.

No backend, API schema, provider-list JSX, lockfile, or model-switching runtime changes are planned.

### Task 1: Build Shared Credential Editor Primitives

**Files:**

- Create: `frontend/components/api-credentials/ApiCredentialEditorShell.tsx`
- Create: `frontend/components/api-credentials/ApiCredentialEditorShell.test.tsx`
- Create: `frontend/components/api-credentials/ThinkingConfigEditor.tsx`
- Create: `frontend/components/api-credentials/ThinkingConfigEditor.test.tsx`
- Create: `frontend/app/styles/api-credential-editor.css`
- Modify: `frontend/app/styles/modals.css`
- Test: `frontend/components/api-credentials/ApiCredentialEditorShell.test.tsx`
- Test: `frontend/components/api-credentials/ThinkingConfigEditor.test.tsx`

- [ ] **Step 1: Write the failing shell tests**

Create `ApiCredentialEditorShell.test.tsx` with tests that render both tabs and assert:

```tsx
render(
  <ApiCredentialEditorShell
    title="编辑 DeepSeek"
    subtitle="DeepSeek · 模型服务"
    activeTab="basic"
    showRequestTab
    saving={false}
    onBack={onBack}
    onClose={onClose}
    onTabChange={onTabChange}
    basicContent={<div>基础内容</div>}
    requestContent={<div>请求内容</div>}
    footer={<button>保存修改</button>}
  />,
);

expect(screen.getByRole("tab", { name: "基础配置" })).toHaveAttribute(
  "aria-selected",
  "true",
);
await user.click(screen.getByRole("tab", { name: "请求配置" }));
expect(onTabChange).toHaveBeenCalledWith("request");
await user.click(screen.getByRole("button", { name: "返回密钥列表" }));
expect(onBack).toHaveBeenCalled();
```

Add a second test with `showRequestTab={false}` and no `onBack`; assert the request tab and back button are absent while close and footer remain available.

- [ ] **Step 2: Write the failing request-editor tests**

Create `ThinkingConfigEditor.test.tsx` and cover:

```tsx
const template = { thinking: { type: "enabled" } };

// Standard mode renders formatted, read-only template JSON.
expect(
  screen.getByRole("textbox", { name: "请求体 JSON（标准模板）" }),
).toHaveAttribute("readonly");

// Custom mode keeps the supplied draft and formats it.
await user.click(screen.getByRole("button", { name: "格式化 JSON" }));
expect(onCustomJsonChange).toHaveBeenCalledWith(
  '{\n  "thinking": {\n    "type": "enabled"\n  }\n}',
);

// Invalid custom JSON reports the parser error without changing the draft.
expect(onErrorChange).toHaveBeenCalledWith("思考配置 JSON 格式错误");
```

Also assert that “标准模板” is disabled for an empty template and that changing modes calls `onModeChange` without overwriting `customJson`.

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```powershell
Set-Location frontend
npm test -- --run components/api-credentials/ApiCredentialEditorShell.test.tsx components/api-credentials/ThinkingConfigEditor.test.tsx
```

Expected: FAIL because both shared components do not exist.

- [ ] **Step 4: Implement the shell API**

Create `ApiCredentialEditorShell.tsx` with this public shape:

```tsx
export type ApiCredentialEditorTab = "basic" | "request";

interface ApiCredentialEditorShellProps {
  title: string;
  subtitle?: string;
  activeTab: ApiCredentialEditorTab;
  showRequestTab: boolean;
  saving: boolean;
  onBack?: () => void;
  onClose: () => void;
  onTabChange: (tab: ApiCredentialEditorTab) => void;
  basicContent: ReactNode;
  requestContent?: ReactNode;
  footer: ReactNode;
}
```

Render a single `.api-credential-editor` grid with header, `role="tablist"`, one scrollable body, and footer. Use `aria-selected`, `aria-controls`, and stable panel ids. Disable back and close while `saving`.

- [ ] **Step 5: Implement the request editor**

Create `ThinkingConfigEditor.tsx` with props:

```tsx
interface ThinkingConfigEditorProps {
  mode: ThinkingMode;
  customJson: string;
  template: ThinkingConfig;
  error: string;
  onModeChange: (mode: ThinkingMode) => void;
  onCustomJsonChange: (value: string) => void;
  onErrorChange: (value: string) => void;
}
```

Use `formatThinkingConfig` and `parseThinkingConfig`. Standard mode displays `formatThinkingConfig(template)` in a read-only textarea; custom mode displays `customJson`; off mode hides the textarea. “格式化 JSON” parses and formats custom JSON, reports parser errors through `onErrorChange`, and never mutates the draft on failure.

- [ ] **Step 6: Add shared layout styles**

Import `api-credential-editor.css` from `styles/modals.css`. Define stable structure:

```css
.api-credential-editor {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
}

.api-credential-editor-body {
  min-width: 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

.api-credential-thinking-json textarea {
  width: 100%;
  min-height: 260px;
  max-height: 42dvh;
  overflow: auto;
  resize: vertical;
}
```

Keep item and section radii at `8px` or less. Do not add another scroll container around the main body.

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
npm test -- --run components/api-credentials/ApiCredentialEditorShell.test.tsx components/api-credentials/ThinkingConfigEditor.test.tsx lib/thinkingConfig.test.ts
git diff --check
```

Expected: 3 files pass with no whitespace errors.

Commit:

```powershell
git add frontend/components/api-credentials frontend/app/styles/api-credential-editor.css frontend/app/styles/modals.css
git commit -m "feat: add shared API credential editor"
```

### Task 2: Rebuild the Official Provider Configuration Modal

**Files:**

- Modify: `frontend/components/chat/ModelConfigModal.tsx`
- Modify: `frontend/components/chat/useChatModelSettings.ts`
- Modify: `frontend/components/ChatPanel.tsx`
- Modify: `frontend/app/styles/modal-provider-config.css`
- Modify: `frontend/app/styles/modal-responsive.css`
- Test: `frontend/components/ChatPanel.config.test.tsx`

- [ ] **Step 1: Add failing official-editor interaction coverage**

Extend `ChatPanel.config.test.tsx` with an admin configuration test that:

Add `saveModelProviderConfig: vi.fn()` to the existing `chatApi` mock before rendering the test.

```tsx
await user.click(await screen.findByLabelText("模型选择"));
await user.click(screen.getByRole("button", { name: "配置 DeepSeek" }));

expect(screen.getByRole("tab", { name: "基础配置" })).toBeVisible();
await user.click(screen.getByRole("tab", { name: "请求配置" }));
await user.click(screen.getByRole("button", { name: "自定义 JSON" }));
await user.clear(screen.getByRole("textbox", { name: "请求体 JSON" }));
await user.type(
  screen.getByRole("textbox", { name: "请求体 JSON" }),
  '{"reasoning_effort":"medium"}',
);
await user.click(screen.getByRole("button", { name: "保存配置" }));

expect(chatApi.saveModelProviderConfig).toHaveBeenCalledWith(
  expect.objectContaining({
    provider: "deepseek",
    thinking_mode: "custom",
    thinking_config: { reasoning_effort: "medium" },
  }),
);
```

Add an invalid JSON case asserting that the request is not called and the request tab remains selected with “思考配置 JSON 格式错误”.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
npm test -- --run components/ChatPanel.config.test.tsx
```

Expected: FAIL because the modal does not expose the new tabs or shared editor labels.

- [ ] **Step 3: Compose the shared editor in `ModelConfigModal`**

Replace the current single-column body with `ApiCredentialEditorShell`:

```tsx
<ApiCredentialEditorShell
  title={`配置 ${provider.label}`}
  subtitle={`${provider.label} · 官方模型配置`}
  activeTab={activeTab}
  showRequestTab
  saving={saving}
  onClose={onClose}
  onTabChange={setActiveTab}
  basicContent={/* API Key, Base URL, model fields */}
  requestContent={
    <ThinkingConfigEditor
      mode={thinkingMode}
      customJson={thinkingJson}
      template={provider.thinking_template || {}}
      error={activeTab === "request" ? error : ""}
      onModeChange={onThinkingModeChange}
      onCustomJsonChange={onThinkingJsonChange}
      onErrorChange={onErrorChange}
    />
  }
  footer={/* Cancel and Save Configuration buttons */}
/>
```

Keep the API Key placeholder, current save labels, and existing save callback. Replace the old `onClearError` prop with `onErrorChange: (value: string) => void`; `ChatPanel.tsx` passes `setConfigError`. Add local `activeTab` state that resets to `basic` when the provider changes.

- [ ] **Step 4: Preserve custom JSON independently of request mode**

Change the model settings callback so selecting off or standard changes only `configThinkingMode`. Keep `configThinkingJson` as the custom draft. On opening a provider, initialize it from the current `thinking_config`; on save, continue parsing only when mode is `custom`.

When custom parsing fails in `handleSaveProviderConfig`, keep the provider modal open and set the existing error. In `ModelConfigModal`, add an effect that sets `activeTab` to `request` whenever `error === "思考配置 JSON 格式错误"` or `error === "思考配置必须是 JSON 对象"`.

- [ ] **Step 5: Widen the modal without changing save behavior**

In `modal-provider-config.css`, change `.thinking-provider-modal` to `width: min(840px, calc(100vw - 32px))`. Move duplicate `.thinking-mode-*` and `.thinking-json-*` declarations into the shared stylesheet, then delete the dead duplicates. Keep the existing modal backdrop z-index and theme tokens.

In `modal-responsive.css`, use one-column basic fields and a non-sticky page-level width at mobile sizes while retaining the editor footer inside the modal.

- [ ] **Step 6: Run official configuration regressions and commit**

Run:

```powershell
npm test -- --run components/ChatPanel.config.test.tsx components/ChatPanel.test.tsx components/api-credentials/ThinkingConfigEditor.test.tsx
git diff --check
```

Expected: all focused tests pass; saving still calls the existing official endpoint and health reload path.

Commit:

```powershell
git add frontend/components/chat/ModelConfigModal.tsx frontend/components/chat/useChatModelSettings.ts frontend/components/ChatPanel.tsx frontend/components/ChatPanel.config.test.tsx frontend/app/styles/modal-provider-config.css frontend/app/styles/modal-responsive.css frontend/app/styles/api-credential-editor.css
git commit -m "fix: expand provider API configuration editor"
```

### Task 3: Polish Only the Official and Personal Source Selector

**Files:**

- Modify: `frontend/app/styles/chat-model-controls.css`
- Create: `frontend/app/api-key-config-layout.test.ts`
- Test: `frontend/components/ChatPanel.config.test.tsx`

- [ ] **Step 1: Add a failing style guard**

Create `api-key-config-layout.test.ts` using `readStylesheetWithLocalImports()` and require:

```ts
expect(stylesheet).toMatch(
  /\.model-source-switch\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);[^}]*min-height:\s*48px;[^}]*border-radius:\s*8px;/s,
);
expect(stylesheet).toMatch(
  /\.model-source-option\.active\s*\{[^}]*border-color:\s*rgba\(217,\s*119,\s*87,\s*0\.42\);[^}]*background:/s,
);
expect(stylesheet).toMatch(
  /\.model-source-option span,\s*\.model-source-option small\s*\{[^}]*white-space:\s*nowrap;/s,
);
```

Also read `ChatModelStatus.tsx` and assert the existing provider loop and callbacks remain present:

```ts
expect(source).toContain("providers.map((provider)");
expect(source).toContain("onSwitchProvider(provider.provider)");
expect(source).toContain("onConfigureProvider(provider)");
```

- [ ] **Step 2: Run the guard and verify RED**

Run:

```powershell
npm test -- --run app/api-key-config-layout.test.ts components/ChatPanel.config.test.tsx
```

Expected: the new CSS assertions fail while existing source-switch interaction tests pass.

- [ ] **Step 3: Change source-selector CSS only**

Update `.model-source-switch`, `.model-source-option`, `.model-source-option small`, and `.model-source-option.active` to create two stable equal segments. Use the existing warm accent only as selection emphasis, not health status. Keep menu width, provider rows, JSX, click handlers, labels, and disabled logic unchanged.

Do not modify `ChatModelStatus.tsx` in this task.

- [ ] **Step 4: Run tests, inspect scope, and commit**

Run:

```powershell
npm test -- --run app/api-key-config-layout.test.ts components/ChatPanel.config.test.tsx
git diff --check
git diff --name-only HEAD
```

Expected: both tests pass and the implementation diff contains only `chat-model-controls.css` plus the new guard.

Commit:

```powershell
git add frontend/app/styles/chat-model-controls.css frontend/app/api-key-config-layout.test.ts
git commit -m "style: clarify model source channels"
```

### Task 4: Add Personal Account View and Request-Config State

**Files:**

- Create: `frontend/components/api-accounts/types.ts`
- Modify: `frontend/components/api-accounts/useApiAccountsPanel.ts`
- Modify: `frontend/components/ApiAccountsPanel.test.tsx`
- Test: `frontend/components/ApiAccountsPanel.test.tsx`

- [ ] **Step 1: Add failing personal-account state tests**

Extend `ApiAccountsPanel.test.tsx` to mock `chatApi.getModelConfig` in addition to `apiAccountApi`. Add tests for:

```tsx
expect(
  await screen.findByRole("region", { name: "AI 服务密钥列表" }),
).toBeVisible();
expect(screen.queryByRole("region", { name: "AI 服务密钥表单" })).toBeNull();

await user.click(screen.getByRole("button", { name: "新增密钥" }));
expect(screen.getByRole("button", { name: "返回密钥列表" })).toBeVisible();

await user.click(screen.getByRole("tab", { name: "请求配置" }));
await user.click(screen.getByRole("button", { name: "自定义 JSON" }));
await user.type(
  screen.getByRole("textbox", { name: "请求体 JSON" }),
  '{"thinking":true}',
);
```

Assert create sends `thinking_config: { thinking: true }`; edit initializes from an existing account’s `thinking_config`; an empty API Key remains absent from update payloads; invalid JSON blocks save and selects the request tab.

Add a template-load rejection case in which the list renders and custom JSON remains available while “标准模板” is disabled.

- [ ] **Step 2: Run the panel tests and verify RED**

Run:

```powershell
npm test -- --run components/ApiAccountsPanel.test.tsx
```

Expected: FAIL because the panel still renders list and form together and ignores `thinking_config` in create/update payloads.

- [ ] **Step 3: Centralize personal-account types**

Create `types.ts`:

```ts
export type ApiAccountsPanelView = "list" | "create" | "edit";

export interface ApiAccountFormState {
  accountId: number | null;
  provider: string;
  displayName: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  thinkingMode: ThinkingMode;
  thinkingJson: string;
  enabled: boolean;
  isDefault: boolean;
}
```

Import this type from the view and form instead of maintaining duplicate interfaces.

- [ ] **Step 4: Extend `useApiAccountsPanel` state and template loading**

Add `view`, `activeTab`, and `providerTemplates`. On open, load accounts and call `chatApi.getModelConfig()`; convert provider templates to a map. Catch template failures independently so they do not replace account-list errors.

Add explicit actions:

```ts
const openCreate = () => { reset form; setActiveTab("basic"); setView("create"); };
const editAccount = (account) => { infer mode and JSON; setActiveTab("basic"); setView("edit"); };
const returnToList = () => { clear form messages; setView("list"); };
```

In `saveAccount`, resolve the payload:

```ts
const thinkingConfig =
  form.thinkingMode === "off"
    ? {}
    : form.thinkingMode === "standard"
      ? selectedTemplate
      : parseThinkingConfig(form.thinkingJson);
```

On parsing failure set the error, switch to `request`, and do not call create/update. Include `thinking_config` in both valid payloads. After successful save, reload accounts and return to `list`.

- [ ] **Step 5: Run state tests and commit**

Run:

```powershell
npm test -- --run components/ApiAccountsPanel.test.tsx lib/thinkingConfig.test.ts lib/api/__tests__/userApiAccounts.test.ts
git diff --check
```

Expected: personal state and payload tests pass without API client changes.

Commit:

```powershell
git add frontend/components/api-accounts/types.ts frontend/components/api-accounts/useApiAccountsPanel.ts frontend/components/ApiAccountsPanel.test.tsx
git commit -m "feat: add personal credential editing state"
```

### Task 5: Replace the Split Personal Panel with List and Editor Views

**Files:**

- Modify: `frontend/components/ApiAccountsPanel.tsx`
- Modify: `frontend/components/api-accounts/ApiAccountsPanelView.tsx`
- Modify: `frontend/components/api-accounts/ApiAccountsList.tsx`
- Modify: `frontend/components/api-accounts/ApiAccountForm.tsx`
- Modify: `frontend/app/styles/api-accounts-panel.css`
- Modify: `frontend/app/styles/account-panels-responsive.css`
- Modify: `frontend/app/api-key-config-layout.test.ts`
- Test: `frontend/components/ApiAccountsPanel.test.tsx`

- [ ] **Step 1: Add failing rendered-structure assertions**

Extend the panel tests to assert:

- List state has “新增密钥”, no form, and one compact “更多操作 DeepSeek” button per item.
- Clicking the item title opens edit state and shows “返回密钥列表”.
- The action menu exposes “设为默认 / 验证 / 删除” and preserves existing handlers.
- Tavily edit has no “请求配置” tab.
- Desktop DOM has no simultaneous `.api-accounts-list` and `.api-account-form`.

Extend `api-key-config-layout.test.ts` to require a two-column `.api-accounts-grid`, a single main overflow container, two-column `.api-account-basic-grid`, and one-column mobile overrides.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
npm test -- --run components/ApiAccountsPanel.test.tsx app/api-key-config-layout.test.ts
```

Expected: FAIL because the current panel always mounts the side-by-side list and form and shows three inline action buttons.

- [ ] **Step 3: Render one personal-panel view at a time**

Change `ApiAccountsPanelView`:

```tsx
return view === "list" ? (
  <PersonalKeysListView header actions accounts ... />
) : (
  <ApiAccountForm
    mode={view}
    activeTab={activeTab}
    template={selectedTemplate}
    onBack={onReturnToList}
    onClose={onClose}
    ...
  />
);
```

Keep the outer `.modal-card.api-accounts-panel` width stable across all views.

- [ ] **Step 4: Build compact account items and action menus**

Render each account as one repeated item with optional provider logo, name, model, health text, default badge, and a `···` button with `aria-expanded`. Only one action menu may be open. Close it after an action or outside click. Use the existing callbacks without changing API behavior.

Do not add search or batch actions.

- [ ] **Step 5: Compose the personal editor**

Use `ApiCredentialEditorShell` in `ApiAccountForm`. Basic content uses a two-column grid; API Key and Base URL span the full row. Hide “启用” during create because the backend already creates enabled accounts. Disable provider selection in edit. Use `ThinkingConfigEditor` for non-Tavily accounts and omit the request tab for Tavily.

Footer behavior:

- Cancel returns to list.
- Save uses the existing create/update callbacks.
- No “验证” button appears beside unsaved form values.

- [ ] **Step 6: Replace split-panel styles**

Remove dead `.api-accounts-layout` split-column rules. Add:

```css
.api-accounts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.api-account-basic-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
```

Keep account items at `border-radius: 8px`. On `max-width: 640px`, make both grids one column and keep footer buttons within the viewport. Remove selectors that no longer match rendered elements.

- [ ] **Step 7: Run personal-panel regressions and commit**

Run:

```powershell
npm test -- --run components/ApiAccountsPanel.test.tsx components/UserMenu.test.tsx app/api-key-config-layout.test.ts app/mobile-chat-layout.test.ts
git diff --check
```

Expected: list/create/edit flows, user-menu entry, desktop guards, and mobile guards all pass.

Commit:

```powershell
git add frontend/components/ApiAccountsPanel.tsx frontend/components/api-accounts frontend/app/styles/api-accounts-panel.css frontend/app/styles/account-panels-responsive.css frontend/app/api-key-config-layout.test.ts
git commit -m "fix: give personal API keys focused editing views"
```

### Task 6: Validate Real Desktop and Mobile Interactions

**Files:**

- Create temporarily outside repository: `$env:TEMP\api-key-config-qa.cjs`
- Produce screenshots outside repository: `$env:TEMP\api-key-*.png`

- [ ] **Step 1: Define the target flows**

Validate:

```text
Model selector -> official/personal source switch -> unchanged provider list
Model selector -> configure provider -> request tab -> custom JSON
User menu -> AI service keys -> list -> edit -> request tab -> back
User menu -> AI service keys -> create -> save validation state
```

- [ ] **Step 2: Start the frontend with mocked APIs**

Run the app on `http://127.0.0.1:3000`. Use the Browser plugin first if available; otherwise record “Browser plugin not available” and use regular Playwright with Microsoft Edge. Mock auth, model config, API account CRUD, health, and unrelated startup APIs without writing secrets.

- [ ] **Step 3: Assert desktop geometry and interaction**

At `1280x800`, programmatically assert:

- Source switch dimensions remain stable before and after official/personal selection.
- Provider rows keep the same count, width, and configuration controls.
- Official editor width is materially larger than the previous 640px target and has one main body scrollbar.
- Personal list renders 8 items in two columns and does not render the form simultaneously.
- Personal editor fields and JSON area do not clip or overlap; JSON textarea is at least 260px high.
- Tab changes retain typed custom JSON.

Capture model menu, official editor, personal list, and personal editor screenshots.

- [ ] **Step 4: Assert mobile geometry and interaction**

At `390x844`, repeat official editor and personal list/edit flows. Assert one-column items and fields, visible back/close/save controls, no horizontal scroll, and no body scroll trap.

Capture personal list and request editor screenshots.

- [ ] **Step 5: Check runtime health and clean up**

For every flow verify URL/title, meaningful body content, no framework overlay, zero relevant console warnings/errors, and zero `pageerror`. Stop only the recorded dev-server PID and confirm port 3000 is closed. Keep scripts and screenshots outside the repository.

### Task 7: Complete Verification, Review, and Integration

**Files:**

- Verify all changed files; no additional production files expected.

- [ ] **Step 1: Run focused frontend regression set**

Run:

```powershell
Set-Location frontend
npm test -- --run components/api-credentials components/ApiAccountsPanel.test.tsx components/UserMenu.test.tsx components/ChatPanel.config.test.tsx components/ChatPanel.test.tsx app/api-key-config-layout.test.ts app/mobile-chat-layout.test.ts lib/thinkingConfig.test.ts lib/api/__tests__/userApiAccounts.test.ts
```

Expected: all selected files pass with zero failures.

- [ ] **Step 2: Run full repository verification**

From repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
```

Expected: git whitespace checks, backend tests, frontend formatting, lint, all frontend tests, and production build pass.

- [ ] **Step 3: Inspect scope and remove generated dependencies**

Run:

```powershell
git status --short
git diff --check
git diff 66997b5 --name-only
```

Expected: only the approved spec, plan, shared editor files, model modal/hook files, personal account files, focused styles, and tests appear. No `.superpowers`, screenshots, TEMP scripts, `.next`, logs, data, secrets, lockfile changes, or `node_modules` are staged. Remove worktree-only `frontend/node_modules` before final worktree cleanup, never stage it.

- [ ] **Step 4: Request final code review**

Review `66997b5..HEAD` against the design. Fix every Critical or Important issue, rerun affected tests, and repeat review until the branch is Ready to merge. Minor issues that affect documented behavior or regression coverage should also be resolved before integration.

- [ ] **Step 5: Fast-forward merge and post-merge verification**

After review and a clean worktree:

```powershell
git -C "G:\gitbase\智库云 - 手机版\star-base-main" merge --ff-only design/api-key-config-ux
```

On `main`, rerun the focused frontend regression set from Step 1. Confirm `git status --short` is empty, then remove `.worktrees/api-key-config-ux`, prune worktrees, and delete the feature branch. Do not push unless explicitly requested.
