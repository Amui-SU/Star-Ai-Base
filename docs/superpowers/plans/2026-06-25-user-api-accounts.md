# User API Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build user-owned AI service key management so normal users configure their own LLM/Tavily credentials, while reserving an explicit official channel for the future paid platform path.

**Architecture:** Add encrypted `user_api_accounts` and lightweight `usage_events` tables, expose user-scoped CRUD/validation endpoints, then route chat credential selection through an `ApiCredentialResolver`. Keep existing admin global `.env.local` configuration as compatibility/admin tooling and as the temporary backing store for the explicit `official` channel; the `personal` channel uses the current user's account records.

**Tech Stack:** FastAPI, SQLAlchemy async, SQLite, Pydantic, Fernet encryption via `app.security`, Next.js 16, React 19, TypeScript, Vitest, Pytest.

---

## File Structure

- `app/models.py`: add SQLAlchemy models and Pydantic request/response schemas for AI service keys and usage events.
- `app/database.py`: extend SQLite legacy column/index creation for local databases.
- `app/services/api_credentials.py`: create provider metadata helpers, encrypted persistence helpers, account validation, credential resolver, and usage event writer.
- `app/routers/api_accounts.py`: user-scoped account CRUD, validate, and set-default endpoints.
- `app/main.py`: register the new router.
- `app/routers/chat.py`: expose model config from user accounts for normal users, keep admin global config, and health-check through the resolver.
- `app/routers/knowledge_bases.py`: make scoped chat use the resolver and return `api_account_required` when no account exists.
- `app/services/web_search.py`: accept an optional Tavily API key override.
- `frontend/lib/api.ts`: add API service key types/client methods.
- `frontend/components/ApiAccountsPanel.tsx`: add a compact modal for managing the current user's AI service keys.
- `frontend/components/UserMenu.tsx`: add an "AI 服务密钥" entry.
- `frontend/app/page.tsx`: own the API accounts modal state and pass the opener to `UserMenu` and `ChatPanel`.
- `frontend/components/ChatPanel.tsx`: show "先添加 AI 服务密钥" when the personal channel has no usable model, provide an opener callback, and expose the official/personal switch in the model menu.
- Tests: `tests/test_user_api_accounts.py`, `tests/test_chat_user_credentials.py`, `frontend/components/ApiAccountsPanel.test.tsx`, updates to existing ChatPanel/UserMenu tests.

---

### Task 1: Backend User API Account CRUD

**Files:**
- Modify: `app/models.py`
- Modify: `app/database.py`
- Create: `app/services/api_credentials.py`
- Create: `app/routers/api_accounts.py`
- Modify: `app/main.py`
- Test: `tests/test_user_api_accounts.py`

- [x] **Step 1: Write failing API account tests**

Create `tests/test_user_api_accounts.py` with tests proving:

```python
async def test_user_can_create_list_and_delete_own_api_account(client):
    user = await register_and_login(client, "api-owner@example.com")
    created = await client.post("/api-accounts", json={
        "provider": "deepseek",
        "display_name": "我的 DeepSeek",
        "api_key": "sk-user-secret",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "is_default": True,
    })
    assert created.status_code == 200
    payload = created.json()
    assert payload["provider"] == "deepseek"
    assert payload["configured"] is True
    assert "api_key" not in payload

    listing = await client.get("/api-accounts")
    assert listing.status_code == 200
    assert listing.json()[0]["display_name"] == "我的 DeepSeek"
    assert "sk-user-secret" not in str(listing.json())

    deleted = await client.delete(f"/api-accounts/{payload['id']}")
    assert deleted.status_code == 204
```

Also include cross-user isolation, update-without-retyping-key, and set-default tests.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_user_api_accounts.py -q`

Expected: FAIL because `/api-accounts` does not exist.

- [x] **Step 3: Add models and schemas**

Add `UserApiAccount` and `UsageEvent` SQLAlchemy models to `app/models.py`. Add schemas:

```python
class ApiAccountCreateRequest(BaseModel):
    provider: str
    display_name: Optional[str] = None
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_config: Optional[dict] = None
    is_default: bool = False

class ApiAccountUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_config: Optional[dict] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None

class ApiAccountResponse(BaseModel):
    id: int
    provider: str
    provider_label: str
    display_name: str
    base_url: str
    model: str
    thinking_config: dict = {}
    enabled: bool
    is_default: bool
    configured: bool = True
    last_validated_at: Optional[datetime] = None
    last_error: Optional[str] = None
```

- [x] **Step 4: Add database compatibility**

Extend `_ensure_sqlite_legacy_columns` to create indexes for `user_api_accounts` and `usage_events` when the tables exist. Rely on `Base.metadata.create_all` for table creation.

- [x] **Step 5: Add service and router**

Create `app/services/api_credentials.py` with:

```python
SUPPORTED_API_PROVIDERS = {"dashscope", "deepseek", "openai", "kimi", "siliconflow", "zhipu", "tavily"}
normalize_provider(value: str) -> str
account_response(account: UserApiAccount) -> ApiAccountResponse
encrypt_api_key(api_key: str) -> str
decrypt_api_key(encrypted: str) -> str
```

Create `app/routers/api_accounts.py` with:

```python
router = APIRouter(prefix="/api-accounts", tags=["api-accounts"])
GET /
POST /
PATCH /{account_id}
DELETE /{account_id}
POST /{account_id}/set-default
POST /{account_id}/validate
```

Every query filters by `UserApiAccount.user_id == current_user.id`.

- [x] **Step 6: Run tests to verify GREEN**

Run: `python -m pytest tests/test_user_api_accounts.py -q`

Expected: all tests pass.

---

### Task 2: Credential Resolver and Chat Behavior

**Files:**
- Modify: `app/services/api_credentials.py`
- Modify: `app/routers/chat.py`
- Modify: `app/routers/knowledge_bases.py`
- Modify: `app/services/web_search.py`
- Test: `tests/test_chat_user_credentials.py`
- Test: `tests/test_chat_config_permissions.py`

- [x] **Step 1: Write failing resolver/chat tests**

Create `tests/test_chat_user_credentials.py` proving:

```python
async def test_chat_requires_user_api_account(client):
    await register_and_login(client, "missing-key@example.com")
    response = await client.post("/knowledge-bases/1/chat", json={"question": "hi"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "api_account_required"

async def test_model_config_reflects_user_accounts(client):
    await register_and_login(client, "cfg-owner@example.com")
    await client.post("/api-accounts", json={
        "provider": "deepseek",
        "api_key": "sk-user-secret",
        "model": "deepseek-chat",
        "is_default": True,
    })
    response = await client.get("/chat/llm/config")
    assert response.status_code == 200
    provider = next(p for p in response.json()["providers"] if p["provider"] == "deepseek")
    assert provider["enabled"] is True
    assert response.json()["current_provider"] == "deepseek"
```

Patch LLM completion helpers so tests do not call external APIs when proving resolver selection.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_chat_user_credentials.py -q`

Expected: FAIL because chat still uses global settings.

- [x] **Step 3: Implement resolver**

Add to `app/services/api_credentials.py`:

```python
class ApiAccountRequired(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "code": "api_account_required",
                "message": "请先添加 AI 服务密钥后再使用 AI 功能。",
            },
        )

async def resolve_user_llm_credentials(db: AsyncSession, user: SystemUser, provider: str | None = None) -> ResolvedApiCredential:
    ...
```

It reads the requested provider account or the user's default enabled account, decrypts the key, and returns provider/base_url/model/thinking_config.

- [x] **Step 4: Wire chat model config**

Update `get_llm_config` so normal users see `enabled=True` only for their own accounts. Admin global config remains available through existing admin write endpoints, but regular users do not get global-account enabled state.

- [x] **Step 5: Wire scoped chat**

Before calling `_complete_llm_answer` or `_stream_llm_events` in `knowledge_bases.py`, resolve user credentials and pass the resolved config into chat helpers. If no account exists, return `api_account_required`.

- [x] **Step 6: Add usage event writing**

Add `record_usage_event` and call it for successful and failed chat attempts with `feature="chat"`, `api_source="personal" | "official"`, provider, model, and status.

- [x] **Step 7: Wire Tavily override**

Update `search_web(..., tavily_api_key: str | None = None)` and `_search_tavily` so user Tavily accounts can be used without `settings.tavily_api_key`.

- [x] **Step 8: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_chat_user_credentials.py tests/test_user_api_accounts.py tests/test_chat_config_permissions.py -q
```

Expected: all tests pass.

---

### Task 3: Frontend API Account Manager

**Files:**
- Modify: `frontend/lib/api.ts`
- Create: `frontend/components/ApiAccountsPanel.tsx`
- Modify: `frontend/components/UserMenu.tsx`
- Modify: `frontend/app/page.tsx`
- Test: `frontend/components/ApiAccountsPanel.test.tsx`
- Test: `frontend/components/UserMenu.test.tsx`

- [x] **Step 1: Write failing frontend tests**

Add tests proving the user menu has `AI 服务密钥`, the modal lists keys, and save calls `apiAccountsApi.create`.

- [x] **Step 2: Run tests to verify RED**

Run: `cd frontend; npm test -- ApiAccountsPanel.test.tsx UserMenu.test.tsx`

Expected: FAIL because the component and API client do not exist.

- [x] **Step 3: Add API client**

Add types and `apiAccountsApi` to `frontend/lib/api.ts`:

```ts
export interface ApiAccount {
  id: number;
  provider: string;
  provider_label: string;
  display_name: string;
  base_url: string;
  model: string;
  enabled: boolean;
  is_default: boolean;
  configured: boolean;
  last_validated_at?: string | null;
  last_error?: string | null;
}

export const apiAccountsApi = {
  list: () => request<ApiAccount[]>("/api-accounts"),
  create: (data: ApiAccountPayload) => request<ApiAccount>("/api-accounts", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<ApiAccountPayload>) => request<ApiAccount>(`/api-accounts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  remove: (id: number) => request<void>(`/api-accounts/${id}`, { method: "DELETE" }),
  setDefault: (id: number) => request<ApiAccount>(`/api-accounts/${id}/set-default`, { method: "POST" }),
};
```

- [x] **Step 4: Add manager modal**

Create `ApiAccountsPanel.tsx` with list, add/edit form, delete, and set-default controls. Keep styling on existing modal/provider classes.

- [x] **Step 5: Wire UserMenu and page state**

Add `onOpenApiAccounts` to `UserMenu`, render the menu button, and render `ApiAccountsPanel` from `frontend/app/page.tsx`.

- [x] **Step 6: Run tests to verify GREEN**

Run: `cd frontend; npm test -- ApiAccountsPanel.test.tsx UserMenu.test.tsx`

Expected: tests pass.

---

### Task 4: Frontend Chat Empty State and Model Config

**Files:**
- Modify: `frontend/components/ChatPanel.tsx`
- Modify: `frontend/components/ChatPanel.test.tsx`
- Test: `frontend/components/ChatPanel.test.tsx`

- [x] **Step 1: Write failing ChatPanel tests**

Add tests proving that when `/chat/llm/config` has no enabled providers, ChatPanel shows `先添加 AI 服务密钥` and a `配置密钥` button.

- [x] **Step 2: Run tests to verify RED**

Run: `cd frontend; npm test -- ChatPanel.test.tsx`

Expected: FAIL because the UI does not show the new prompt.

- [x] **Step 3: Add opener prop and UI**

Add `onOpenApiAccounts?: () => void` to ChatPanel. Show the prompt in the model status/empty chat area when no provider is enabled. The button calls `onOpenApiAccounts`.

- [x] **Step 4: Run tests to verify GREEN**

Run: `cd frontend; npm test -- ChatPanel.test.tsx`

Expected: tests pass.

---

### Task 4.5: Official/Personal Source Switch and API Key Modal Layout

**Files:**
- Modify: `app/models.py`
- Modify: `app/database.py`
- Modify: `app/services/api_credentials.py`
- Modify: `app/routers/chat.py`
- Modify: `app/routers/knowledge_bases.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/ChatPanel.tsx`
- Modify: `frontend/app/globals.css`
- Test: `tests/test_chat_user_credentials.py`
- Test: `frontend/components/ChatPanel.test.tsx`
- Test: `frontend/app/api-accounts-layout.test.ts`
- Test: `frontend/app/mobile-chat-layout.test.ts`

- [x] **Step 1: Persist user model source**

Add `SystemUser.llm_api_source` with SQLite compatibility migration. Supported values are `personal` and `official`.

- [x] **Step 2: Add source-aware resolver behavior**

When source is `personal`, resolve the current user's enabled LLM account. When source is `official`, resolve the admin global model config and return `official_api_required` if no global Key is available.

- [x] **Step 3: Expose source config APIs**

Add `POST /chat/llm/source`, return `current_api_source` from `GET /chat/llm/config`, and include `official_enabled` / `personal_enabled` per provider.

- [x] **Step 4: Add source switch above model selection**

Add the official/personal segmented switch at the top of the model provider menu. Official is labeled as the future paid channel, and personal is the user-owned Key channel.

- [x] **Step 5: Fix API key modal clipping**

Increase `ApiAccountsPanel` modal width, isolate `.modal-card.api-accounts-panel` styling from the generic modal card rule, raise modal z-index above chat status controls, and make the mobile layout single-column with internal scrolling.

- [x] **Step 6: Verify source switch and responsive layout**

Verification results:

- `python -m pytest tests/test_chat_user_credentials.py tests/test_chat_config_permissions.py tests/test_user_api_accounts.py tests/test_knowledge_base_scoping.py tests/test_knowledge_scope.py -q`: 82 passed.
- `cd frontend; npm test`: 22 files passed, 125 tests passed.
- `cd frontend; npm run lint`: passed.
- `cd frontend; npm run build`: passed.
- Playwright desktop/mobile smoke check passed for the model source menu and AI service key modal.

---

### Task 5: Full Verification and Docs

**Files:**
- Modify: `docs/大版本完善执行方案.md`
- Modify: `.env.example`
- Modify: `README.md`

- [x] **Step 1: Update docs and env template**

Document:

```env
API_ACCOUNT_MODE=user_required
PLATFORM_API_ENABLED=false
BILLING_ENABLED=false
```

Update README to say formal product usage requires users to add AI service keys from the user menu.

- [x] **Step 2: Run backend verification**

Run: `python -m pytest -q`

Expected: all backend tests pass.

- [x] **Step 3: Run frontend verification**

Run:

```powershell
cd frontend
npm test
npm run lint
npm run build
```

Expected: all frontend tests, lint, and production build pass.

- [x] **Step 4: Mark plan items complete**

Update this plan and `docs/大版本完善执行方案.md` with checked boxes for completed tasks and the exact verification results.

Verification results:

- `python -m pytest -q`: 205 passed.
- `cd frontend; npm test`: 21 files passed, 119 tests passed.
- `cd frontend; npm run lint`: passed.
- `cd frontend; npm run build`: passed.
