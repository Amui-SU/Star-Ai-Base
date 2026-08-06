# Forgot Password Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a secure email-code password reset flow to the login page that revokes existing sessions and returns the user to password login.

**Architecture:** Store password-reset codes in a dedicated SQLAlchemy table so registration and reset codes cannot be exchanged. Keep HTTP wiring in the system-auth router, reset orchestration in a focused backend service, request methods in the existing frontend API module, and UI state transitions in the existing auth form hook. Reuse the current validation, hashing, IP throttling, email delivery, visual primitives, and countdown conventions.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pydantic, pytest/httpx, Next.js 16, React 19, TypeScript, Vitest, Testing Library.

---

## File map

- Create `app/services/system_auth_password_reset.py`: send and confirm password-reset orchestration only.
- Create `tests/system_auth/test_password_reset.py`: backend password-reset behavior and security regressions.
- Create `frontend/lib/api/__tests__/systemPasswordResetApi.test.ts`: frontend request contract tests.
- Create `frontend/components/AuthPage.password-reset.test.tsx`: user-visible reset flow tests.
- Modify `app/models.py`: add the independent `PasswordResetCode` ORM table and import new auth schemas.
- Modify `app/schemas/auth.py`: add send/confirm password-reset request DTOs.
- Modify `app/routers/system_auth.py`: expose two thin password-reset endpoints.
- Modify `tests/service_boundaries/test_model_boundaries.py`: keep auth DTOs out of the ORM model module.
- Modify `tests/test_schema_compatibility.py`: verify the compatibility re-exports used by router/service code.
- Modify `frontend/lib/api/systemAuth.ts`: add reset-code and confirm-reset request methods.
- Modify `frontend/components/auth/authPageLogic.ts`: add the `forgot-password` auth state.
- Modify `frontend/components/auth/useAuthForm.ts`: own reset form state, validation, async actions, cleanup, and success notice.
- Modify `frontend/components/auth/AuthCard.tsx`: render the reset step.
- Modify `frontend/components/auth/AuthCardSteps.tsx`: render the reset form and login-page entry point.
- Modify `frontend/components/AuthPage.tsx`: provide the reset-step heading and current-email subtitle.

### Task 1: Add the isolated reset-code model and request contracts

**Files:**

- Modify: `app/models.py`
- Modify: `app/schemas/auth.py`
- Modify: `tests/service_boundaries/test_model_boundaries.py`
- Modify: `tests/test_schema_compatibility.py`

- [x] **Step 1: Write failing schema and boundary tests**

Add `PasswordResetSendCodeRequest` and `PasswordResetConfirmRequest` to the auth schema name set in `tests/service_boundaries/test_model_boundaries.py`, and add compatibility assertions in `tests/test_schema_compatibility.py`:

```python
send_request = models.PasswordResetSendCodeRequest(email="member@example.com")
confirm_request = models.PasswordResetConfirmRequest(
    email="member@example.com",
    code="123456",
    new_password="new password",
)
assert send_request.email == "member@example.com"
assert confirm_request.new_password == "new password"
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/service_boundaries/test_model_boundaries.py tests/test_schema_compatibility.py -q
```

Expected: FAIL because both request classes are missing.

- [x] **Step 3: Add the minimal DTOs and ORM table**

Add to `app/schemas/auth.py`:

```python
class PasswordResetSendCodeRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    email: str
    code: str
    new_password: str
```

Import those DTOs from `app.schemas.auth` in `app/models.py`, then add:

```python
class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), index=True, nullable=False)
    code_hash = Column(String(128), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utc_now)
```

The new table is created for existing SQLite installations by the existing `Base.metadata.create_all` startup path; do not add a legacy-column migration.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command. Expected: all selected tests PASS.

- [x] **Step 5: Commit the model boundary**

```powershell
git add app/models.py app/schemas/auth.py tests/service_boundaries/test_model_boundaries.py tests/test_schema_compatibility.py
git commit -m "feat: add password reset contracts"
```

### Task 2: Implement reset-code delivery without account disclosure

**Files:**

- Create: `app/services/system_auth_password_reset.py`
- Create: `tests/system_auth/test_password_reset.py`
- Modify: `app/routers/system_auth.py`

- [x] **Step 1: Write failing send-code behavior tests**

Create helpers and tests in `tests/system_auth/test_password_reset.py` that register an active user, call the dedicated endpoint, and inspect the debug response:

```python
async def send_reset_code(client, email: str) -> str | None:
    response = await client.post(
        "/system-auth/password-reset/send-code", json={"email": email}
    )
    assert response.status_code == 200
    return response.json().get("code")


@pytest.mark.asyncio
async def test_existing_user_receives_dedicated_reset_code(client):
    await register_user(client, "reset@example.com")
    code = await send_reset_code(client, "reset@example.com")
    assert code and len(code) == 6


@pytest.mark.asyncio
async def test_unknown_email_gets_generic_send_response(client):
    response = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "missing@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "濡傛灉璇ラ偖绠卞凡娉ㄥ唽锛岄噸缃獙璇佺爜宸插彂閫?
    assert response.json().get("code")

```

Add these concrete send guards in the same file:

```python
@pytest.mark.asyncio
async def test_reset_send_rejects_invalid_email(client):
    response = await client.post(
        "/system-auth/password-reset/send-code", json={"email": "bad-email"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_send_uses_persisted_ip_rate_limit(client):
    for index in range(_IP_RATE_MAX):
        response = await client.post(
            "/system-auth/password-reset/send-code",
            json={"email": f"missing-{index}@example.com"},
        )
        assert response.status_code == 200
    blocked = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "blocked@example.com"},
    )
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_reset_send_rejects_a_second_active_code(client):
    await register_user(client, "duplicate@example.com")
    assert await send_reset_code(client, "duplicate@example.com")
    response = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "duplicate@example.com"},
    )
    assert response.status_code == 429
```

- [x] **Step 2: Run the send tests and verify RED**

Run:

```powershell
python -m pytest tests/system_auth/test_password_reset.py -q
```

Expected: FAIL with 404 because the reset routes do not exist.

- [x] **Step 3: Implement the send service**

In `app/services/system_auth_password_reset.py`, define constants by reusing `CODE_TTL_SECONDS` and helpers from `system_auth_codes`, then implement this interface:

```python
GENERIC_SEND_MESSAGE = "濡傛灉璇ラ偖绠卞凡娉ㄥ唽锛岄噸缃獙璇佺爜宸插彂閫?


async def send_password_reset_code(
    db: AsyncSession,
    *,
    email: str,
    client_ip: str,
    debug: bool,
) -> dict[str, str]:
    normalized_email = email.strip().lower()
    if not email_is_valid(normalized_email):
        raise HTTPException(status_code=400, detail="閭鏍煎紡涓嶆纭?)
    if not await check_ip_rate_limit(db, client_ip):
        raise HTTPException(status_code=429, detail="鍙戦€佽繃浜庨绻侊紝璇风◢鍚庡啀璇?)

    code = f"{secrets.randbelow(1000000):06d}"
    response = {"message": GENERIC_SEND_MESSAGE}
    if debug:
        response["code"] = code

    user = (await db.execute(
        select(SystemUser).where(
            SystemUser.email == normalized_email,
            SystemUser.status == "active",
        )
    )).scalar_one_or_none()
    if user is None:
        return response

    now = utc_now_naive()
    await db.execute(delete(PasswordResetCode).where(PasswordResetCode.expires_at < now))
    existing = (await db.execute(
        select(PasswordResetCode).where(
            PasswordResetCode.email == normalized_email,
            PasswordResetCode.expires_at > now,
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=429, detail="楠岃瘉鐮佸凡鍙戦€侊紝璇锋煡鏀堕偖绠辨垨绛夊緟杩囨湡鍚庨噸璇?)

    db.add(PasswordResetCode(
        email=normalized_email,
        code_hash=hash_code(code),
        expires_at=now + timedelta(seconds=CODE_TTL_SECONDS),
    ))
    await db.commit()
    if not debug and not await send_verification_email(normalized_email, code):
        raise HTTPException(status_code=500, detail="楠岃瘉鐮佸彂閫佸け璐ワ紝璇风◢鍚庨噸璇?)
    return response
```

Use the existing project strings if the source files encode Chinese wording differently; keep response semantics exactly as asserted.

- [x] **Step 4: Add the thin send route**

Import the request DTO and service, then add to `app/routers/system_auth.py`:

```python
@router.post("/password-reset/send-code")
async def send_password_reset_code_route(
    payload: PasswordResetSendCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    return await _send_password_reset_code(
        db,
        email=payload.email,
        client_ip=client_ip,
        debug=bool(settings.debug),
    )
```

- [x] **Step 5: Run the send tests and verify GREEN**

Run the send-code tests selected by `-k "send or receives"`. Expected: all selected tests PASS. The unknown-email confirmation assertion is added in Task 3 after the confirm route exists.

- [x] **Step 6: Commit the send slice**

```powershell
git add app/services/system_auth_password_reset.py app/routers/system_auth.py tests/system_auth/test_password_reset.py
git commit -m "feat: send password reset codes"
```

### Task 3: Confirm reset, consume the code, and revoke all sessions

**Files:**

- Modify: `app/services/system_auth_password_reset.py`
- Modify: `app/routers/system_auth.py`
- Modify: `tests/system_auth/test_password_reset.py`

- [x] **Step 1: Write failing confirmation and security tests**

Add tests that retain both a cookie and bearer token from registration, reset the password, then prove all security outcomes:

```python
@pytest.mark.asyncio
async def test_confirm_reset_changes_password_consumes_code_and_revokes_sessions(client):
    registration = await register_user(
        client, "secured@example.com", password="old secure password"
    )
    bearer = registration["session_token"]
    code = await send_reset_code(client, "secured@example.com")
    assert code

    reset = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "secured@example.com",
            "code": code,
            "new_password": "new secure password",
        },
    )
    assert reset.status_code == 200
    assert reset.json() == {"message": "瀵嗙爜宸查噸缃紝璇蜂娇鐢ㄦ柊瀵嗙爜鐧诲綍"}
    assert (await client.get("/system-auth/me")).status_code == 401
    assert (await client.get(
        "/system-auth/me", headers={"Authorization": f"Bearer {bearer}"}
    )).status_code == 401

    reused = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "secured@example.com",
            "code": code,
            "new_password": "another secure password",
        },
    )
    assert reused.status_code == 400
    assert (await client.post(
        "/system-auth/login",
        json={"email": "secured@example.com", "password": "old secure password"},
    )).status_code == 401
    assert (await client.post(
        "/system-auth/login",
        json={"email": "secured@example.com", "password": "new secure password"},
    )).status_code == 200
```

Add the cross-purpose and validation tests with full payloads:

```python
@pytest.mark.asyncio
async def test_registration_code_cannot_reset_a_password(client):
    await register_user(client, "purpose@example.com")
    registration_code = await send_code(client, "purpose@example.com")
    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "purpose@example.com",
            "code": registration_code,
            "new_password": "new secure password",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_code_cannot_register_an_account(client):
    await register_user(client, "reset-purpose@example.com")
    reset_code = await send_reset_code(client, "reset-purpose@example.com")
    response = await client.post(
        "/system-auth/register",
        json={
            "email": "reset-purpose@example.com",
            "code": reset_code,
            "password": "new secure password",
            "display_name": "Reset Purpose",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_code_is_deleted_at_the_attempt_limit(client):
    await register_user(client, "attempts@example.com")
    code = await send_reset_code(client, "attempts@example.com")
    assert code
    for _ in range(_MAX_ATTEMPTS):
        response = await client.post(
            "/system-auth/password-reset/confirm",
            json={
                "email": "attempts@example.com",
                "code": "000000",
                "new_password": "new secure password",
            },
        )
        assert response.status_code == 400
    rejected = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "attempts@example.com",
            "code": code,
            "new_password": "new secure password",
        },
    )
    assert rejected.status_code == 400


@pytest.mark.asyncio
async def test_reset_rejects_expired_code(client, db_session_factory):
    await register_user(client, "expired@example.com")
    code = await send_reset_code(client, "expired@example.com")
    async with db_session_factory() as db:
        await db.execute(
            update(PasswordResetCode)
            .where(PasswordResetCode.email == "expired@example.com")
            .values(expires_at=utc_now_naive() - timedelta(seconds=1))
        )
        await db.commit()
    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "expired@example.com",
            "code": code,
            "new_password": "new secure password",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_rejects_password_over_bcrypt_limit(client):
    await register_user(client, "long-password@example.com")
    code = await send_reset_code(client, "long-password@example.com")
    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "long-password@example.com",
            "code": code,
            "new_password": "瀵? * 25,
        },
    )
    assert response.status_code == 400
```

Import `timedelta`, SQLAlchemy `update`, `PasswordResetCode`, `SystemUser`, `_MAX_ATTEMPTS`, and `utc_now_naive` explicitly. Add the non-disclosure confirmation guards:

```python
@pytest.mark.asyncio
async def test_unknown_email_debug_code_cannot_reset(client):
    sent = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "missing@example.com"},
    )
    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "missing@example.com",
            "code": sent.json()["code"],
            "new_password": "new secure password",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_inactive_account_cannot_reset(client, db_session_factory):
    await register_user(client, "inactive-reset@example.com")
    async with db_session_factory() as db:
        await db.execute(
            update(SystemUser)
            .where(SystemUser.email == "inactive-reset@example.com")
            .values(status="inactive")
        )
        await db.commit()
    sent = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "inactive-reset@example.com"},
    )
    assert sent.status_code == 200
    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "inactive-reset@example.com",
            "code": sent.json()["code"],
            "new_password": "new secure password",
        },
    )
    assert response.status_code == 400
```

- [x] **Step 2: Run confirmation tests and verify RED**

Run:

```powershell
python -m pytest tests/system_auth/test_password_reset.py -q
```

Expected: FAIL because `/password-reset/confirm` is missing.

- [x] **Step 3: Implement confirmation as one success transaction**

Add this public interface in `app/services/system_auth_password_reset.py`:

```python
async def confirm_password_reset(
    db: AsyncSession, *, payload: PasswordResetConfirmRequest
) -> dict[str, str]:
    email = payload.email.strip().lower()
    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="閭鏍煎紡涓嶆纭?)
    if password_exceeds_bcrypt_limit(payload.new_password):
        raise HTTPException(status_code=400, detail="瀵嗙爜闀垮害涓嶈兘瓒呰繃 72 瀛楄妭")

    now = utc_now_naive()
    code_row = (await db.execute(
        select(PasswordResetCode).where(
            PasswordResetCode.email == email,
            PasswordResetCode.expires_at > now,
        )
    )).scalar_one_or_none()
    if code_row is None:
        raise HTTPException(status_code=400, detail="楠岃瘉鐮佹湭鍙戦€佹垨宸茶繃鏈燂紝璇烽噸鏂拌幏鍙?)

    if not secrets.compare_digest(code_row.code_hash, hash_code(payload.code.strip())):
        code_row.attempts += 1
        if code_row.attempts >= MAX_ATTEMPTS:
            await db.delete(code_row)
        await db.commit()
        raise HTTPException(status_code=400, detail="楠岃瘉鐮侀敊璇?)

    user = (await db.execute(
        select(SystemUser).where(
            SystemUser.email == email,
            SystemUser.status == "active",
        )
    )).scalar_one_or_none()
    if user is None:
        await db.delete(code_row)
        await db.commit()
        raise HTTPException(status_code=400, detail="楠岃瘉鐮佹湭鍙戦€佹垨宸茶繃鏈燂紝璇烽噸鏂拌幏鍙?)

    user.password_hash = hash_password(payload.new_password)
    await db.delete(code_row)
    await db.execute(
        update(SystemSession)
        .where(SystemSession.user_id == user.id, SystemSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()
    return {"message": "瀵嗙爜宸查噸缃紝璇蜂娇鐢ㄦ柊瀵嗙爜鐧诲綍"}
```

- [x] **Step 4: Add the thin confirm route**

```python
@router.post("/password-reset/confirm")
async def confirm_password_reset_route(
    payload: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    return await _confirm_password_reset(db, payload=payload)
```

- [x] **Step 5: Run backend reset and authentication regressions**

Run:

```powershell
python -m pytest tests/system_auth/test_password_reset.py tests/system_auth/test_account_sessions.py tests/system_auth/test_email_codes.py -q
```

Expected: all selected tests PASS.

- [x] **Step 6: Commit the confirm slice**

```powershell
git add app/services/system_auth_password_reset.py app/routers/system_auth.py tests/system_auth/test_password_reset.py
git commit -m "feat: confirm password resets securely"
```

### Task 4: Add the frontend reset API contract

**Files:**

- Modify: `frontend/lib/api/systemAuth.ts`
- Create: `frontend/lib/api/__tests__/systemPasswordResetApi.test.ts`

- [x] **Step 1: Write failing request-contract tests**

Use `importApiForLocation` and a mocked fetch to assert both paths and bodies:

```typescript
await api.systemAuthApi.sendPasswordResetCode("member@example.com");
await api.systemAuthApi.confirmPasswordReset({
  email: "member@example.com",
  code: "123456",
  new_password: "new secure password",
});

expect(fetchMock).toHaveBeenNthCalledWith(
  1,
  "http://localhost:8000/system-auth/password-reset/send-code",
  expect.objectContaining({
    method: "POST",
    body: JSON.stringify({ email: "member@example.com" }),
  }),
);
expect(fetchMock).toHaveBeenNthCalledWith(
  2,
  "http://localhost:8000/system-auth/password-reset/confirm",
  expect.objectContaining({
    method: "POST",
    body: JSON.stringify({
      email: "member@example.com",
      code: "123456",
      new_password: "new secure password",
    }),
  }),
);
```

- [x] **Step 2: Run the API test and verify RED**

Run:

```powershell
Set-Location frontend
npx vitest run lib/api/__tests__/systemPasswordResetApi.test.ts
```

Expected: FAIL because the methods do not exist.

- [x] **Step 3: Add the minimal API methods**

Add to `systemAuthApi`:

```typescript
sendPasswordResetCode: (email: string) =>
  request<{ message: string; code?: string }>(
    "/system-auth/password-reset/send-code",
    { method: "POST", body: JSON.stringify({ email }) },
  ),

confirmPasswordReset: (data: {
  email: string;
  code: string;
  new_password: string;
}) =>
  request<{ message: string }>("/system-auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify(data),
  }),
```

- [x] **Step 4: Run the API test and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [x] **Step 5: Commit the API slice**

```powershell
git add frontend/lib/api/systemAuth.ts frontend/lib/api/__tests__/systemPasswordResetApi.test.ts
git commit -m "feat: add password reset client"
```

### Task 5: Add the login-page reset form and state transitions

**Files:**

- Modify: `frontend/components/auth/authPageLogic.ts`
- Modify: `frontend/components/auth/useAuthForm.ts`
- Modify: `frontend/components/auth/AuthCard.tsx`
- Modify: `frontend/components/auth/AuthCardSteps.tsx`
- Modify: `frontend/components/AuthPage.tsx`
- Create: `frontend/components/AuthPage.password-reset.test.tsx`

- [x] **Step 1: Write failing interaction tests**

Mock `sendPasswordResetCode` and `confirmPasswordReset`, then test the full visible flow:

```typescript
await user.type(screen.getByPlaceholderText("杈撳叆閭鍦板潃"), "member@example.com");
await user.click(screen.getByRole("button", { name: "缁х画" }));
await user.click(screen.getByRole("button", { name: "蹇樿瀵嗙爜锛? }));

expect(screen.getByRole("heading", { name: "閲嶇疆瀵嗙爜" })).toBeInTheDocument();
expect(screen.getByText("member@example.com")).toBeInTheDocument();

await user.click(screen.getByRole("button", { name: "鑾峰彇楠岃瘉鐮? }));
expect(systemAuthApi.sendPasswordResetCode).toHaveBeenCalledWith(
  "member@example.com",
);
```

Add separate test cases with the same explicit form queries and API mocks that:

- prevent submission when code is empty;
- prevent submission and show an error when passwords differ;
- call `confirmPasswordReset` with trimmed email/code and the new password;
- return to login, show `瀵嗙爜宸查噸缃紝璇蜂娇鐢ㄦ柊瀵嗙爜鐧诲綍`, and clear password fields after success;
- display request errors and allow retry;
- return to login without changing the email.

- [x] **Step 2: Run the component test and verify RED**

Run:

```powershell
Set-Location frontend
npx vitest run components/AuthPage.password-reset.test.tsx
```

Expected: FAIL because the forgot-password button and auth state do not exist.

- [x] **Step 3: Add the reset auth state and hook contract**

Change the type to:

```typescript
export type AuthStep = "email" | "login" | "register" | "forgot-password";
```

Extend `UseAuthFormResult` with:

```typescript
success: string | null;
handleSendPasswordResetCode: () => Promise<void>;
handlePasswordReset: (event: FormEvent) => Promise<void>;
startPasswordReset: () => void;
backToLogin: () => void;
```

Implement `handleSendPasswordResetCode` with the existing countdown helper and dedicated API method. Implement `handlePasswordReset` with these exact client checks in order: code required, password required, matching confirmation; on success clear code/password/confirmation, set step to `login`, and set the success notice. `startPasswordReset` clears login errors/passwords but preserves email; `backToLogin` clears reset secrets/errors and preserves email.

- [x] **Step 4: Render the entry point and reset form**

In `AuthLoginStep`, add:

```tsx
<button type="button" onClick={startPasswordReset}>
  蹇樿瀵嗙爜锛?
</button>
```

Add `AuthForgotPasswordStep` using existing `inputStyle`, `passwordInputStyle`, `authCodeRowStyle`, `getCodeButtonStateStyle`, `fieldButtonStyle`, `AuthError`, and `AuthCodeHint`. Use `autoComplete="one-time-code"` for the code and `autoComplete="new-password"` for both password inputs.

Render it from `AuthCard`:

```tsx
{
  form.step === "forgot-password" && <AuthForgotPasswordStep form={form} />;
}
```

Show the success notice above the login form with an accessible status element. Update `AuthPage` so the forgot-password title is `閲嶇疆瀵嗙爜` and its subtitle remains the normalized current email.

- [x] **Step 5: Run the component test and verify GREEN**

Run the Step 2 command. Expected: all reset component tests PASS.

- [x] **Step 6: Run existing auth layout regressions**

Run:

```powershell
npx vitest run components/AuthPage.test.tsx components/AuthPage.layout.test.ts
```

Expected: all selected tests PASS.

- [x] **Step 7: Commit the UI slice**

```powershell
git add frontend/components/AuthPage.tsx frontend/components/AuthPage.password-reset.test.tsx frontend/components/auth/AuthCard.tsx frontend/components/auth/AuthCardSteps.tsx frontend/components/auth/authPageLogic.ts frontend/components/auth/useAuthForm.ts
git commit -m "feat: add forgot password form"
```

### Task 6: Verify architecture, behavior, build, and rendered viewports

**Files:**

- Modify only if verification exposes a defect in files already listed above.

- [x] **Step 1: Run targeted backend verification**

```powershell
python -m pytest tests/system_auth/test_password_reset.py tests/system_auth/test_account_sessions.py tests/system_auth/test_email_codes.py tests/service_boundaries/test_model_boundaries.py tests/test_schema_compatibility.py -q
```

Expected: all selected tests PASS with no new warnings.

- [x] **Step 2: Run targeted frontend verification**

```powershell
Set-Location frontend
npx vitest run lib/api/__tests__/systemPasswordResetApi.test.ts components/AuthPage.password-reset.test.tsx components/AuthPage.test.tsx components/AuthPage.layout.test.ts
npm run lint
npm run build
```

Expected: all selected tests PASS, ESLint exits 0, and Next.js production build exits 0.

- [x] **Step 3: Inspect desktop and mobile rendering**

Start the app with the repository's normal local startup path and inspect the email, login, and forgot-password states at approximately 1440脳900 and 390脳844. Confirm the card stays within the viewport, all controls remain tappable, the current email is visible, the reset form does not overlap the header/demo panel, and keyboard focus order follows code 鈫?send button 鈫?password 鈫?confirmation 鈫?submit 鈫?back.

- [x] **Step 4: Run repository commit verification**

From the repository root:

```powershell
git status --short
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1
```

Expected: full backend tests, frontend formatting, lint, tests, build, and whitespace checks PASS.

- [x] **Step 5: Commit any verification-only fixes**

If Step 1鈥? required changes, stage only the password-reset files and commit:

```powershell
git commit -m "test: verify forgot password flow"
```

If no files changed, do not create an empty commit.

- [x] **Step 6: Integrate and re-run targeted checks**

Follow the repository worktree workflow: merge the feature branch into the original branch with `git merge --ff-only`, re-run the targeted commands from Steps 1 and 2 on the integrated branch, then remove the isolated worktree and its feature branch.
