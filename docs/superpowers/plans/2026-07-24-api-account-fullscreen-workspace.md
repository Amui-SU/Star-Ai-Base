# API Account Fullscreen Workspace Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-screen API account configuration workspace whose provider, protocol, model mapping, request overrides, and JSON settings are persisted, validated, and used by real model requests.

**Architecture:** Keep account identity and connection fields as typed database columns, store extensible request settings in a versioned `advanced_config` JSON object, and resolve both through focused backend services. Preserve existing OpenAI-shaped runtime call sites by adding a tested Anthropic Messages facade, while the frontend replaces only the personal account editor with a full-screen workspace and keeps the account list and model dropdown behavior intact.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy async, SQLite legacy migrations, OpenAI Python SDK, Anthropic Python SDK, Next.js 16, React 19, TypeScript, Vitest, Testing Library, pytest.

---

## File Map

Backend files to create:

- `app/services/api_account_config.py`: provider presets, typed advanced-config normalization, protected-field validation, and model resolution.
- `app/services/api_account_requests.py`: merge validated User-Agent, Header, Body, and thinking options into runtime request options.
- `app/services/anthropic_chat_adapter.py`: translate the existing OpenAI-shaped chat-completion calls to Anthropic Messages and normalize responses/streams.
- `app/services/api_account_validation.py`: execute draft connection tests and classify sanitized failures.
- `tests/test_api_account_config.py`: pure configuration and security tests.
- `tests/test_api_account_requests.py`: request merge tests.
- `tests/test_anthropic_chat_adapter.py`: message, tool, response, and streaming translation tests.
- `tests/test_api_account_draft_validation.py`: draft validation endpoint and credential isolation tests.

Backend files to modify:

- `requirements.txt`: add the pinned Anthropic SDK.
- `app/models.py`: add protocol, auth, metadata, and advanced configuration columns.
- `app/services/sqlite_legacy_schema.py`: add the same columns to legacy SQLite databases.
- `app/schemas/api_accounts.py`: expose typed create, update, response, and draft-validation contracts.
- `app/services/api_credentials.py`: use the provider registry and return resolved protocol/config fields.
- `app/routers/api_accounts.py`: delegate persistence and draft validation without adding business logic.
- `app/services/llm_client.py`: select the OpenAI or Anthropic facade.
- `app/services/chat_completion.py`, `app/services/chat_runtime.py`, `app/services/chat_health.py`, `app/services/chat_routing.py`: merge validated request options at every direct model request.
- `tests/test_database_migration.py`, `tests/test_user_api_accounts.py`, `tests/test_llm_client.py`, `tests/test_chat_completion.py`, `tests/test_chat_runtime.py`, `tests/test_chat_health.py`, `tests/test_chat_routing.py`: persistence and runtime regressions.

Frontend files to create:

- `frontend/lib/apiAccountConfig.ts`: version-1 types, defaults, JSON parsing, serialization, and form conversion.
- `frontend/lib/apiAccountConfig.test.ts`: round-trip, unknown-field, and validation tests.
- `frontend/components/api-accounts/ApiAccountWorkspace.tsx`: full-screen editor composition and fixed actions.
- `frontend/components/api-accounts/ApiAccountSectionNav.tsx`: desktop section navigation and mobile disclosure headings.
- `frontend/components/api-accounts/ApiAccountIdentitySection.tsx`: provider, name, metadata, and account switches.
- `frontend/components/api-accounts/ApiAccountConnectionSection.tsx`: API Key, URL, protocol, and authentication controls.
- `frontend/components/api-accounts/ApiAccountModelSection.tsx`: alias mapping table and fallback model.
- `frontend/components/api-accounts/ApiAccountRequestSection.tsx`: User-Agent, Header/Body overrides, and existing thinking configuration.
- `frontend/components/api-accounts/AdvancedConfigEditor.tsx`: inline JSON editor and full-screen focus dialog.
- `frontend/components/api-accounts/ApiAccountWorkspace.test.tsx`: workspace behavior and accessibility tests.
- `frontend/app/styles/api-account-workspace.css`: desktop and mobile workspace layout.

Frontend files to modify:

- `frontend/lib/providers.ts`: add protocol, auth, website, and supported-section metadata to existing presets.
- `frontend/lib/api/apiAccountTypes.ts`, `frontend/lib/api/apiAccounts.ts`: expand contracts and add draft validation.
- `frontend/components/api-accounts/types.ts`: replace the compact form state with the workspace draft.
- `frontend/components/api-accounts/useApiAccountsPanel.ts`: manage baseline, dirty state, JSON draft, validation, and save.
- `frontend/components/api-accounts/ApiAccountsPanelView.tsx`: render list or full-screen workspace.
- `frontend/components/ApiAccountsPanel.tsx`: stop wrapping editor mode in the compact modal card.
- `frontend/components/ApiAccountsPanel.test.tsx`: integration and preserved-list behavior.
- `frontend/app/styles/account-panels.css`: import workspace styles.
- `frontend/app/styles/api-accounts-panel.css`: retain list styles and remove editor-only rules.
- `frontend/app/api-key-config-layout.test.ts`: replace obsolete compact-editor guards with full-screen workspace guards.
- `tests/frontend_structure/test_account_import_component_boundaries.py`: guard the new component boundaries.

## Task 1: Establish Provider and Advanced-Config Contracts

**Files:**

- Create: `app/services/api_account_config.py`
- Create: `tests/test_api_account_config.py`
- Modify: `app/services/api_credentials.py`

- [x] **Step 1: Write failing provider and advanced-config tests**

```python
from fastapi import HTTPException
import pytest

from app.services.api_account_config import (
    default_advanced_config,
    normalize_advanced_config,
    provider_preset,
    resolve_account_model,
)


def test_claude_uses_anthropic_messages_preset():
    preset = provider_preset("claude")
    assert preset.protocol == "anthropic_messages"
    assert preset.auth_scheme == "x_api_key"


def test_advanced_config_preserves_unknown_fields():
    result = normalize_advanced_config({"version": 1, "future": {"on": True}})
    assert result["future"] == {"on": True}
    assert result["headers"] == {}


def test_protected_header_is_rejected_case_insensitively():
    with pytest.raises(HTTPException, match="Authorization"):
        normalize_advanced_config(
            {"version": 1, "headers": {"aUtHoRiZaTiOn": "secret"}}
        )


def test_model_alias_and_fallback_resolution():
    config = default_advanced_config("fallback-model")
    config["model_mapping"] = {"agnes": "real-model"}
    assert resolve_account_model("agnes", config, "legacy") == "real-model"
    assert resolve_account_model("missing", config, "legacy") == "fallback-model"
```

- [x] **Step 2: Run the focused tests and verify the module is missing**

Run: `python -m pytest tests/test_api_account_config.py -q`

Expected: collection fails with `ModuleNotFoundError: app.services.api_account_config`.

- [x] **Step 3: Implement the registry and normalizer**

```python
@dataclass(frozen=True)
class ProviderPreset:
    label: str
    base_url: str
    model: str
    protocol: str | None
    auth_scheme: str | None
    website_url: str
    kind: Literal["llm", "search"]


def default_advanced_config(model: str = "") -> dict[str, Any]:
    return {
        "version": 1,
        "model_mapping": {},
        "fallback_model": model,
        "user_agent": "",
        "headers": {},
        "body": {},
    }


def normalize_advanced_config(value: object, *, model: str = "") -> dict[str, Any]:
    raw = deepcopy(value) if isinstance(value, dict) else {}
    merged = {**default_advanced_config(model), **raw, "version": 1}
    _validate_model_mapping(merged["model_mapping"])
    _validate_user_agent(merged["user_agent"])
    _validate_headers(merged["headers"])
    _validate_body(merged["body"])
    return merged
```

Move the existing provider constants from `api_credentials.py` into this module, add protocol/auth/website/kind metadata for all existing providers, and re-export focused lookup helpers to avoid duplicated registries.

- [x] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_api_account_config.py tests/test_user_api_accounts.py -q`

Expected: all tests pass and existing provider defaults remain unchanged.

- [x] **Step 5: Commit the contract slice**

```powershell
git add app/services/api_account_config.py app/services/api_credentials.py tests/test_api_account_config.py
git commit -m "feat: define API account configuration contracts"
```

## Task 2: Persist and Expose the Expanded Account Configuration

**Files:**

- Modify: `app/models.py`
- Modify: `app/services/sqlite_legacy_schema.py`
- Modify: `app/schemas/api_accounts.py`
- Modify: `app/services/api_credentials.py`
- Modify: `app/routers/api_accounts.py`
- Modify: `tests/test_database_migration.py`
- Modify: `tests/test_user_api_accounts.py`

- [x] **Step 1: Add failing migration and CRUD assertions**

```python
assert {
    "protocol",
    "auth_scheme",
    "website_url",
    "notes",
    "advanced_config",
} <= columns

created = await client.post(
    "/api-accounts",
    headers=headers,
    json={
        "provider": "deepseek",
        "api_key": "secret-key",
        "protocol": "openai_compatible",
        "auth_scheme": "bearer",
        "website_url": "https://www.deepseek.com",
        "notes": "primary account",
        "advanced_config": {
            "version": 1,
            "model_mapping": {"deepseek": "deepseek-chat"},
            "fallback_model": "deepseek-chat",
            "headers": {"X-Workspace": "mobile"},
            "body": {"temperature": 0.2},
        },
    },
)
assert created.status_code == 200
assert created.json()["advanced_config"]["body"] == {"temperature": 0.2}
assert "api_key" not in created.json()
```

- [x] **Step 2: Run tests and verify missing fields fail**

Run: `python -m pytest tests/test_database_migration.py tests/test_user_api_accounts.py -q`

Expected: assertions fail because the five columns and response fields do not exist.

- [x] **Step 3: Add model columns and SQLite compatibility types**

```python
protocol = Column(String(40), nullable=True)
auth_scheme = Column(String(40), nullable=True)
website_url = Column(String(500), nullable=True)
notes = Column(Text, nullable=True)
advanced_config = Column(JSON, nullable=True)
```

Add matching entries to `SQLITE_LEGACY_COLUMNS["user_api_accounts"]` using `VARCHAR(40)`, `VARCHAR(500)`, `TEXT`, and `JSON`. Keep nullable storage for legacy rows; normalization supplies runtime defaults.

- [x] **Step 4: Expand schemas and route persistence**

```python
class ApiAccountConfigurationFields(BaseModel):
    protocol: Optional[Literal["openai_compatible", "anthropic_messages"]] = None
    auth_scheme: Optional[Literal["bearer", "x_api_key"]] = None
    website_url: Optional[str] = None
    notes: Optional[str] = None
    advanced_config: Optional[dict] = None
```

Normalize all advanced configuration through `normalize_advanced_config`, infer missing legacy protocol/auth values from the provider preset, preserve provider immutability in PATCH, and keep an omitted or blank update API Key from replacing encrypted data.

- [x] **Step 5: Run persistence tests**

Run: `python -m pytest tests/test_database_migration.py tests/test_user_api_accounts.py tests/test_security_isolation.py -q`

Expected: all tests pass, including tenant isolation and secret non-disclosure.

- [x] **Step 6: Commit persistence**

```powershell
git add app/models.py app/services/sqlite_legacy_schema.py app/schemas/api_accounts.py app/services/api_credentials.py app/routers/api_accounts.py tests/test_database_migration.py tests/test_user_api_accounts.py
git commit -m "feat: persist advanced API account settings"
```

## Task 3: Apply Model Mapping and Safe Request Overrides

**Files:**

- Create: `app/services/api_account_requests.py`
- Create: `tests/test_api_account_requests.py`
- Modify: `app/services/api_credentials.py`
- Modify: `app/services/chat_completion.py`
- Modify: `app/services/chat_runtime.py`
- Modify: `app/services/chat_health.py`
- Modify: `app/services/chat_routing.py`
- Modify: `tests/test_chat_completion.py`
- Modify: `tests/test_chat_runtime.py`
- Modify: `tests/test_chat_health.py`
- Modify: `tests/test_chat_routing.py`

- [x] **Step 1: Write failing request-resolution tests**

```python
from app.services.api_account_requests import build_account_request_options


def test_request_options_merge_thinking_body_and_headers():
    options = build_account_request_options(
        {
            "thinking_config": {"reasoning_effort": "high"},
            "advanced_config": {
                "version": 1,
                "user_agent": "Zhiku-Mobile/1.0",
                "headers": {"X-Tenant": "demo"},
                "body": {"temperature": 0.2},
            },
        }
    )
    assert options == {
        "extra_headers": {
            "User-Agent": "Zhiku-Mobile/1.0",
            "X-Tenant": "demo",
        },
        "extra_body": {"temperature": 0.2, "reasoning_effort": "high"},
    }


def test_system_kwargs_cannot_be_replaced_by_body_override():
    with pytest.raises(HTTPException, match="model"):
        build_account_request_options(
            {"advanced_config": {"version": 1, "body": {"model": "other"}}}
        )
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_api_account_requests.py tests/test_chat_completion.py -q`

Expected: the new module is missing and current completion options only include thinking configuration.

- [x] **Step 3: Implement deterministic request option merging**

```python
def build_account_request_options(llm_config: Mapping[str, Any]) -> dict[str, Any]:
    advanced = normalize_advanced_config(
        llm_config.get("advanced_config"), model=str(llm_config.get("model") or "")
    )
    headers = dict(advanced["headers"])
    if advanced["user_agent"]:
        headers["User-Agent"] = advanced["user_agent"]
    body = dict(advanced["body"])
    body.update(llm_config.get("thinking_config") or {})
    return {
        **({"extra_headers": headers} if headers else {}),
        **({"extra_body": body} if body else {}),
    }
```

Have `ResolvedApiCredential.to_llm_config()` include protocol, auth scheme, and normalized advanced config. Resolve the account's stored model through `model_mapping`, then `fallback_model`, then legacy `model` before returning the runtime config.

- [x] **Step 4: Replace completion-option call sites without changing orchestration**

Rename `build_thinking_completion_options` to `build_completion_request_options`, update chat completion, legacy runtime, health-check, and routing injection points, and retain a compatibility alias only where existing imports require a staged transition. Every direct `client.chat.completions.create(...)` call must receive the same validated options; service-owned arguments such as model, messages, tools, streaming, and response controls remain explicit call arguments and cannot be replaced by configuration.

- [x] **Step 5: Run runtime regressions**

Run: `python -m pytest tests/test_api_account_requests.py tests/test_chat_completion.py tests/test_chat_runtime.py tests/test_chat_health.py tests/test_chat_routing.py tests/chat_thinking -q`

Expected: all tests pass and thinking options still reach existing providers.

- [x] **Step 6: Commit request overrides**

```powershell
git add app/services/api_account_requests.py app/services/api_credentials.py app/services/chat_completion.py app/services/chat_runtime.py app/services/chat_health.py app/services/chat_routing.py tests/test_api_account_requests.py tests/test_chat_completion.py tests/test_chat_runtime.py tests/test_chat_health.py tests/test_chat_routing.py
git commit -m "feat: apply API account request overrides"
```

## Task 4: Add the Anthropic Messages Runtime Adapter

**Files:**

- Modify: `requirements.txt`
- Create: `app/services/anthropic_chat_adapter.py`
- Create: `tests/test_anthropic_chat_adapter.py`
- Modify: `app/services/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [x] **Step 1: Add failing facade translation tests**

```python
def test_anthropic_facade_translates_messages_and_response():
    native = FakeAnthropicClient(
        response={"content": [{"type": "text", "text": "OK"}], "stop_reason": "end_turn"}
    )
    client = AnthropicChatClientFacade(native)
    response = client.chat.completions.create(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=16,
    )
    assert native.last_request["messages"] == [{"role": "user", "content": "ping"}]
    assert response.choices[0].message.content == "OK"


def test_anthropic_facade_translates_openai_tools():
    client.chat.completions.create(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "search"}],
        tools=[{
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search notes",
                "parameters": {"type": "object", "properties": {}},
            },
        }],
    )
    assert native.last_request["tools"][0]["input_schema"]["type"] == "object"
```

Also cover streaming `content_block_delta`, Anthropic thinking blocks, tool-use blocks, assistant tool calls, and user tool results.

- [x] **Step 2: Run tests and verify missing adapter failure**

Run: `python -m pytest tests/test_anthropic_chat_adapter.py tests/test_llm_client.py -q`

Expected: collection fails because `AnthropicChatClientFacade` does not exist.

- [x] **Step 3: Add the official SDK and facade**

Add `anthropic==0.42.0` to `requirements.txt`. Implement a facade exposing `chat.completions.create(**kwargs)` so existing runtime services remain unchanged. Translate OpenAI message/tool shapes into Anthropic Messages inputs and normalize native responses into lightweight objects with `choices[0].message` or streaming `choices[0].delta` fields consumed by current code.

```python
class AnthropicChatClientFacade:
    def __init__(self, client: Anthropic):
        self.chat = SimpleNamespace(completions=_AnthropicCompletions(client.messages))


def create_anthropic_chat_client(config: Mapping[str, Any]) -> AnthropicChatClientFacade:
    native = Anthropic(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=30.0,
        max_retries=2,
    )
    return AnthropicChatClientFacade(native)
```

- [x] **Step 4: Select the client by protocol**

```python
if cfg.get("protocol") == "anthropic_messages":
    return anthropic_client_factory(cfg)
return openai_client_factory(
    api_key=cfg["api_key"],
    base_url=cfg["base_url"],
    timeout=30.0,
    max_retries=2,
)
```

Keep factories injectable so tests never perform network requests.

- [x] **Step 5: Run protocol and chat regressions**

Run: `python -m pytest tests/test_anthropic_chat_adapter.py tests/test_llm_client.py tests/test_chat_completion.py tests/chat_thinking -q`

Expected: all tests pass for normal, streaming, thinking, and tool-call paths.

- [x] **Step 6: Commit the protocol adapter**

```powershell
git add requirements.txt app/services/anthropic_chat_adapter.py app/services/llm_client.py tests/test_anthropic_chat_adapter.py tests/test_llm_client.py
git commit -m "feat: support Anthropic Messages accounts"
```

## Task 5: Validate Unsaved Account Drafts Safely

**Files:**

- Create: `app/services/api_account_validation.py`
- Create: `tests/test_api_account_draft_validation.py`
- Modify: `app/schemas/api_accounts.py`
- Modify: `app/routers/api_accounts.py`

- [x] **Step 1: Write failing endpoint tests**

```python
response = await client.post(
    "/api-accounts/validate-draft",
    headers=headers,
    json={
        "account_id": account_id,
        "provider": "deepseek",
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek",
        "protocol": "openai_compatible",
        "auth_scheme": "bearer",
        "advanced_config": {
            "version": 1,
            "model_mapping": {"deepseek": "deepseek-chat"},
        },
    },
)
assert response.status_code == 200
assert response.json()["status"] == "success"
assert "secret" not in response.text
```

Add cases for another user's `account_id`, missing key on create, authentication failure, timeout, endpoint failure, unavailable model, and invalid protected fields.

- [x] **Step 2: Run the endpoint tests and verify 404/422 failures**

Run: `python -m pytest tests/test_api_account_draft_validation.py -q`

Expected: the route is absent and draft response schemas are undefined.

- [x] **Step 3: Implement validation service and result classification**

```python
class ApiAccountValidationResult(BaseModel):
    status: Literal[
        "success",
        "authentication_failed",
        "endpoint_unreachable",
        "timeout",
        "model_unavailable",
        "invalid_configuration",
    ]
    message: str
    http_status: int | None = None
    section: str | None = None
    latency_ms: int | None = None
```

The service constructs an in-memory resolved credential, reuses the saved encrypted key only after owner-scoped lookup, sends a small non-streaming request, and sanitizes exception text before returning it. Do not persist `last_validated_at`, `last_error`, or draft fields from this endpoint.

- [x] **Step 4: Keep the router thin**

The route should perform dependencies and delegation only:

```python
@router.post("/validate-draft", response_model=ApiAccountValidationResult)
async def validate_api_account_draft(...):
    return await validate_account_draft(db, current_user, body)
```

- [x] **Step 5: Run validation and isolation tests**

Run: `python -m pytest tests/test_api_account_draft_validation.py tests/test_user_api_accounts.py tests/test_security_isolation.py -q`

Expected: all tests pass and no secret appears in results or captured logs.

- [x] **Step 6: Commit draft validation**

```powershell
git add app/services/api_account_validation.py app/schemas/api_accounts.py app/routers/api_accounts.py tests/test_api_account_draft_validation.py
git commit -m "feat: validate unsaved API account drafts"
```

## Task 6: Add Frontend Contracts and Lossless JSON Draft Utilities

**Files:**

- Modify: `frontend/lib/providers.ts`
- Modify: `frontend/lib/api/apiAccountTypes.ts`
- Modify: `frontend/lib/api/apiAccounts.ts`
- Create: `frontend/lib/apiAccountConfig.ts`
- Create: `frontend/lib/apiAccountConfig.test.ts`
- Modify: `frontend/lib/api/__tests__/userApiAccounts.test.ts`

- [x] **Step 1: Write failing JSON round-trip and API tests**

```typescript
it("preserves unknown advanced fields while updating known fields", () => {
  const parsed = parseAdvancedConfig(
    '{"version":1,"future":{"enabled":true},"headers":{}}',
  );
  const updated = updateAdvancedConfig(parsed, {
    fallbackModel: "deepseek-chat",
  });
  expect(updated.future).toEqual({ enabled: true });
  expect(updated.fallback_model).toBe("deepseek-chat");
});

it("reports a protected header path", () => {
  expect(() =>
    parseAdvancedConfig('{"version":1,"headers":{"Authorization":"secret"}}'),
  ).toThrow("headers.Authorization");
});

expect(fetch).toHaveBeenCalledWith(
  "http://localhost:8000/api-accounts/validate-draft",
  expect.objectContaining({ method: "POST" }),
);
```

- [x] **Step 2: Run tests and verify missing exports**

Run: `cd frontend; npm test -- lib/apiAccountConfig.test.ts lib/api/__tests__/userApiAccounts.test.ts`

Expected: TypeScript/Vitest fails because advanced-config utilities and draft validation do not exist.

- [x] **Step 3: Define shared frontend contracts**

```typescript
export interface ApiAccountAdvancedConfig {
  version: 1;
  model_mapping: Record<string, string>;
  fallback_model: string;
  user_agent: string;
  headers: Record<string, string>;
  body: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ApiAccountValidationResult {
  status: ApiAccountValidationStatus;
  message: string;
  http_status?: number | null;
  section?: string | null;
  latency_ms?: number | null;
}
```

Extend each provider preset with `protocol`, `authScheme`, `websiteUrl`, and `sections`, keeping the current order, identifiers, labels, base URLs, model IDs, and logos unchanged.

- [x] **Step 4: Implement lossless parsing and serialization**

Use one parser for the inline and focus editors. It must require an object, normalize known fields, reject protected fields case-insensitively, retain unknown keys, and return errors with JSON paths. Add `apiAccountApi.validateDraft(data)`.

- [x] **Step 5: Run frontend contract tests**

Run: `cd frontend; npm test -- lib/apiAccountConfig.test.ts lib/api/__tests__/userApiAccounts.test.ts lib/providers.test.ts`

Expected: all tests pass.

- [x] **Step 6: Commit frontend contracts**

```powershell
git add frontend/lib/providers.ts frontend/lib/api/apiAccountTypes.ts frontend/lib/api/apiAccounts.ts frontend/lib/apiAccountConfig.ts frontend/lib/apiAccountConfig.test.ts frontend/lib/api/__tests__/userApiAccounts.test.ts
git commit -m "feat: add API account workspace contracts"
```

## Task 7: Replace Compact Editor State with a Full-Screen Workspace Shell

**Files:**

- Modify: `frontend/components/api-accounts/types.ts`
- Modify: `frontend/components/api-accounts/useApiAccountsPanel.ts`
- Create: `frontend/components/api-accounts/ApiAccountWorkspace.tsx`
- Create: `frontend/components/api-accounts/ApiAccountSectionNav.tsx`
- Modify: `frontend/components/api-accounts/ApiAccountsPanelView.tsx`
- Modify: `frontend/components/ApiAccountsPanel.tsx`
- Modify: `frontend/components/ApiAccountsPanel.test.tsx`
- Create: `frontend/components/api-accounts/ApiAccountWorkspace.test.tsx`

- [x] **Step 1: Write failing shell and dirty-state tests**

```typescript
it("opens editing as a full-screen workspace and keeps the provider locked", async () => {
  await user.click(await screen.findByRole("button", { name: /^My DeepSeek/ }));
  expect(screen.getByRole("dialog", { name: "编辑 API 密钥" })).toHaveClass(
    "api-account-workspace",
  );
  expect(screen.getByLabelText("服务商")).toBeDisabled();
  expect(
    screen.queryByRole("tab", { name: "基础配置" }),
  ).not.toBeInTheDocument();
});

it("asks before leaving a dirty workspace", async () => {
  vi.stubGlobal(
    "confirm",
    vi.fn(() => false),
  );
  await user.type(screen.getByLabelText("密钥名称"), " changed");
  await user.click(screen.getByRole("button", { name: "返回密钥列表" }));
  expect(window.confirm).toHaveBeenCalledWith("当前配置尚未保存，确认离开？");
  expect(screen.getByRole("dialog", { name: "编辑 API 密钥" })).toBeVisible();
});
```

- [x] **Step 2: Run component tests and verify compact editor assertions fail**

Run: `cd frontend; npm test -- components/ApiAccountsPanel.test.tsx components/api-accounts/ApiAccountWorkspace.test.tsx`

Expected: no full-screen workspace dialog exists and current editor still renders tabs.

- [x] **Step 3: Introduce a baseline-backed workspace draft**

```typescript
interface ApiAccountWorkspaceDraft {
  accountId: number | null;
  provider: string;
  displayName: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  protocol: ApiAccountProtocol | null;
  authScheme: ApiAccountAuthScheme | null;
  websiteUrl: string;
  notes: string;
  advancedConfig: ApiAccountAdvancedConfig;
  advancedJson: string;
  enabled: boolean;
  isDefault: boolean;
  thinkingMode: ThinkingMode;
  thinkingJson: string;
}
```

Keep `baseline` separate from `draft`; derive `dirty` from a stable serialization that excludes transient validation messages. Saving updates the baseline only after the request succeeds. Testing a draft never clears `dirty`.

- [x] **Step 4: Render list and workspace as sibling surfaces**

Keep `ModalShell` for the list. When `view` is `create` or `edit`, render `ApiAccountWorkspace` directly in a full-viewport overlay instead of nesting it in `.modal-card.api-accounts-panel`. Preserve list refresh, set-default, saved-account validation, and delete behavior.

- [x] **Step 5: Implement leave protection and stable actions**

Guard return, close, and `beforeunload` while dirty. Disable return, provider switching, test, and save while saving. Keep test enabled for valid dirty drafts.

- [x] **Step 6: Run shell tests**

Run: `cd frontend; npm test -- components/ApiAccountsPanel.test.tsx components/api-accounts/ApiAccountWorkspace.test.tsx`

Expected: all list, full-screen shell, provider-lock, key-retention, and dirty-state tests pass.

- [x] **Step 7: Commit the workspace shell**

```powershell
git add frontend/components/api-accounts/types.ts frontend/components/api-accounts/useApiAccountsPanel.ts frontend/components/api-accounts/ApiAccountWorkspace.tsx frontend/components/api-accounts/ApiAccountSectionNav.tsx frontend/components/api-accounts/ApiAccountsPanelView.tsx frontend/components/ApiAccountsPanel.tsx frontend/components/ApiAccountsPanel.test.tsx frontend/components/api-accounts/ApiAccountWorkspace.test.tsx
git commit -m "feat: add full-screen API account workspace"
```

## Task 8: Build Configuration Sections and Focused JSON Editing

**Files:**

- Create: `frontend/components/api-accounts/ApiAccountIdentitySection.tsx`
- Create: `frontend/components/api-accounts/ApiAccountConnectionSection.tsx`
- Create: `frontend/components/api-accounts/ApiAccountModelSection.tsx`
- Create: `frontend/components/api-accounts/ApiAccountRequestSection.tsx`
- Create: `frontend/components/api-accounts/AdvancedConfigEditor.tsx`
- Modify: `frontend/components/api-accounts/ApiAccountWorkspace.tsx`
- Modify: `frontend/components/api-accounts/useApiAccountsPanel.ts`
- Modify: `frontend/components/api-accounts/ApiAccountWorkspace.test.tsx`

- [x] **Step 1: Write failing section and JSON synchronization tests**

```typescript
it("maps aliases and synchronizes the advanced JSON", async () => {
  await user.click(screen.getByRole("button", { name: "添加模型映射" }));
  await user.type(screen.getByLabelText("调用别名 1"), "agnes");
  await user.type(screen.getByLabelText("真实模型 ID 1"), "claude-sonnet-4-5");
  await user.click(screen.getByRole("button", { name: "JSON 配置" }));
  expect(screen.getByLabelText("高级配置 JSON")).toHaveValue(
    expect.stringContaining('"agnes": "claude-sonnet-4-5"'),
  );
});

it("cancels focused JSON changes without touching the workspace draft", async () => {
  await user.click(screen.getByRole("button", { name: "专注编辑 JSON" }));
  fireEvent.change(screen.getByLabelText("专注高级配置 JSON"), {
    target: { value: '{"version":1,"fallback_model":"changed"}' },
  });
  await user.click(screen.getByRole("button", { name: "取消专注编辑" }));
  expect(screen.getByLabelText("高级配置 JSON")).not.toHaveValue(
    expect.stringContaining("changed"),
  );
});
```

Add tests for applying valid JSON, preserving unknown fields, displaying syntax line/column, blocked headers, duplicate aliases, provider preset confirmation, current-draft connection testing, and Tavily's reduced sections.

- [x] **Step 2: Run workspace tests and verify missing section controls**

Run: `cd frontend; npm test -- components/api-accounts/ApiAccountWorkspace.test.tsx`

Expected: section navigation, mapping controls, and focus editor are absent.

- [x] **Step 3: Implement identity and connection sections**

Use existing provider icons and input/button classes. New accounts may switch provider; existing accounts render a disabled provider control. Authentication options come only from preset-supported safe values. API Key remains blank on edit with the existing “leave blank to retain” explanation.

- [x] **Step 4: Implement model and request sections**

Render model mapping as stable rows with icon remove buttons and accessible labels. Keep `ThinkingConfigEditor` inside request configuration. Render Header overrides as key/value rows, Body override as an object JSON editor, and User-Agent as a single-line input. Hide these LLM-only controls for Tavily.

- [x] **Step 5: Implement lossless inline and focused JSON editors**

```typescript
const applyFocusDraft = () => {
  const next = parseAdvancedConfig(focusText);
  onApply(next, formatAdvancedConfig(next));
  setFocusOpen(false);
};

const cancelFocusDraft = () => {
  setFocusText(jsonText);
  setFocusOpen(false);
};
```

The focus layer must use the same parser as inline editing. Applying changes the workspace draft but does not save. Invalid text remains visible with its error and cannot replace the last valid configuration.

- [x] **Step 6: Wire current-draft validation and error focus**

Call `apiAccountApi.validateDraft` with the current normalized payload. Map `section` and local validation paths to the correct section, open it on mobile, focus the first invalid control, and display sanitized result details in the fixed action area.

- [x] **Step 7: Run workspace and API integration tests**

Run: `cd frontend; npm test -- components/api-accounts/ApiAccountWorkspace.test.tsx components/ApiAccountsPanel.test.tsx lib/apiAccountConfig.test.ts`

Expected: all tests pass, including form/JSON round trips and Tavily reduction.

- [x] **Step 8: Commit the complete editor**

```powershell
git add frontend/components/api-accounts/ApiAccountIdentitySection.tsx frontend/components/api-accounts/ApiAccountConnectionSection.tsx frontend/components/api-accounts/ApiAccountModelSection.tsx frontend/components/api-accounts/ApiAccountRequestSection.tsx frontend/components/api-accounts/AdvancedConfigEditor.tsx frontend/components/api-accounts/ApiAccountWorkspace.tsx frontend/components/api-accounts/useApiAccountsPanel.ts frontend/components/api-accounts/ApiAccountWorkspace.test.tsx
git commit -m "feat: add advanced API account editing"
```

## Task 9: Finish Responsive Styling and Update Architecture Guards

**Files:**

- Create: `frontend/app/styles/api-account-workspace.css`
- Modify: `frontend/app/styles/account-panels.css`
- Modify: `frontend/app/styles/api-accounts-panel.css`
- Modify: `frontend/app/api-key-config-layout.test.ts`
- Modify: `tests/frontend_structure/test_account_import_component_boundaries.py`

- [x] **Step 1: Replace obsolete compact-editor style assertions with failing workspace guards**

```typescript
expect(stylesheet).toMatch(
  /\.api-account-workspace\s*\{[^}]*position:\s*fixed;[^}]*inset:\s*0;/s,
);
expect(stylesheet).toMatch(
  /grid-template-columns:\s*minmax\(180px,\s*240px\)\s+minmax\(0,\s*1fr\)/,
);
expect(stylesheet).toMatch(
  /@media \(max-width:\s*720px\)[\s\S]*\.api-account-workspace-nav\s*\{[^}]*display:\s*none;/,
);
```

Update the Python boundary guard to require focused workspace/section imports and prevent configuration logic from moving into `ApiAccountsPanel.tsx`.

- [x] **Step 2: Run guards and verify missing stylesheet failure**

Run: `cd frontend; npm test -- app/api-key-config-layout.test.ts; cd ..; python -m pytest tests/frontend_structure/test_account_import_component_boundaries.py -q`

Expected: guards fail because the new stylesheet and imports do not exist.

- [x] **Step 3: Implement desktop workspace layout**

Create a full-viewport overlay with fixed header, stable left navigation, one scrolling content column, and fixed action placement. Use existing theme variables, no nested cards, maximum `8px` item radii, and stable control dimensions. Keep `.api-accounts-panel` rules only for the list modal.

- [x] **Step 4: Implement mobile layout**

At `720px` and below, hide the left navigation, render section disclosure buttons, switch all field grids to one column, and keep the bottom action bar above safe-area insets. Ensure textarea/code areas use `max-width: 100%`, `overflow: auto`, and stable minimum heights.

- [x] **Step 5: Run style and structure guards**

Run: `cd frontend; npm test -- app/api-key-config-layout.test.ts; cd ..; python -m pytest tests/frontend_structure/test_account_import_component_boundaries.py tests/frontend_structure/test_global_style_boundaries.py -q`

Expected: all guards pass; obsolete compact-editor assertions are removed rather than weakened into contradictory checks.

- [x] **Step 6: Commit responsive styling**

```powershell
git add frontend/app/styles/api-account-workspace.css frontend/app/styles/account-panels.css frontend/app/styles/api-accounts-panel.css frontend/app/api-key-config-layout.test.ts tests/frontend_structure/test_account_import_component_boundaries.py
git commit -m "style: finish API account workspace layout"
```

## Task 10: Full Regression, Browser QA, and Integration

**Files:**

- Modify only files required by failures found in this task.

- [x] **Step 1: Run backend tests**

Run: `python -m pytest -q`

Expected: the complete backend suite passes with no new warnings that expose credentials.

- [x] **Step 2: Run frontend lint, tests, and production build**

```powershell
Set-Location frontend
npm run lint
npm test
npm run build
Set-Location ..
```

Expected: lint, all Vitest tests, and the Next.js production build pass.

- [x] **Step 3: Run repository commit verification**

```powershell
git status --short
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1
```

Expected: formatting and all configured verification checks pass.

- [x] **Step 4: Verify desktop behavior in Edge/Playwright**

At a desktop viewport, exercise list -> edit -> each section -> alias mapping -> JSON focus cancel/apply -> draft validation -> save -> return. Confirm the workspace is full-screen, the account list remains a modal, long URLs/model IDs do not overflow, and the model dropdown is unchanged.

- [x] **Step 5: Verify mobile behavior in Edge/Playwright**

At a mobile viewport, exercise disclosure sections, fixed bottom actions, focused JSON editing, validation errors, keyboard focus, and unsaved-leave confirmation. Capture screenshots and check there is no clipping, overlap, or horizontal page scrolling.

- [x] **Step 6: Inspect credential safety and runtime payloads**

Confirm browser network responses, application logs, error messages, test snapshots, and screenshots do not contain API Key plaintext. With stubbed upstreams, verify OpenAI and Anthropic payloads use mapped real model IDs and only allowed overrides.

- [x] **Step 7: Request two-stage subagent review**

First review implementation against `docs/superpowers/specs/2026-07-24-api-account-fullscreen-workspace-design.md`; then review code quality, security boundaries, and missing regression coverage. Address every confirmed finding and rerun the affected tests.

- [x] **Step 8: Create the final implementation commit if verification fixes remain**

```powershell
git add -- app frontend tests requirements.txt
git diff --cached --check
git commit -m "fix: complete API account workspace verification"
```

Skip this commit when the worktree is already clean after the task commits.

- [x] **Step 9: Fast-forward the verified worktree branch into `main`**

```powershell
git switch main
git merge --ff-only api-account-fullscreen-workspace
```

Re-run the targeted backend and frontend workspace tests on `main`, then remove the worktree and feature branch according to `AGENTS.md`.
