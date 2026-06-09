# Knowledge Base Scoping Implementation Plan

> **STATUS: COMPLETED** — All tasks implemented, reviewed, and merged to `main` (2026-06-07).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authenticated, knowledge-base scoped stats, search, chat, stream, and build endpoints while keeping legacy session endpoints compatible.

**Architecture:** Put the new multi-user API surface under `app/routers/knowledge_bases.py`. Use a shared `get_knowledge_base_for_user` dependency to authorize the current system user through their workspace before any RAG read or write. Keep old `/chat/*`, `/knowledge/*`, and `/favorites/*` endpoints unchanged in this phase.

**Tech Stack:** FastAPI, SQLAlchemy async, SQLite, Chroma/LangChain RAG service, pytest, pytest-asyncio, httpx ASGITransport, Next.js TypeScript API client.

---

## Scope

This plan implements the second multi-user slice: all new RAG-facing work is scoped by `knowledge_base_id`.

Included:

- Reusable knowledge-base ownership dependency.
- Scoped stats endpoint.
- Scoped search endpoint.
- Scoped chat endpoint.
- Scoped stream endpoint.
- Scoped build endpoint skeleton with source-binding ownership checks and scoped RAG write contract.
- Frontend API client additions.
- Focused tests for auth, ownership, scoped retrieval, and scoped write metadata.

Excluded:

- Removing legacy endpoints.
- Full frontend UI migration.
- Automatic old-data migration.
- Persistent task queue replacement.
- Production database migration.

## File Structure

Create:

- `tests/test_knowledge_base_scoping.py`: endpoint ownership and scoped RAG contract tests.

Modify:

- `app/dependencies.py`: add `get_knowledge_base_for_user`.
- `app/models.py`: add scoped request and response models used by the new endpoints.
- `app/routers/knowledge_bases.py`: add stats, search, chat, stream, and build endpoints under `/knowledge-bases/{knowledge_base_id}`.
- `frontend/lib/api.ts`: add scoped `knowledgeBaseApi` methods and request/response types.
- `docs/API接口改造草案.md`: mark scoped knowledge-base endpoints as implemented in the second phase.

## Task 1: Knowledge Base Ownership Dependency

**Files:**

- Modify: `app/dependencies.py`
- Create: `tests/test_knowledge_base_scoping.py`

- [ ] **Step 1: Create failing ownership tests**

Create `tests/test_knowledge_base_scoping.py`:

```python
import pytest


async def register_user(client, email: str, display_name: str) -> None:
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
        },
    )
    assert response.status_code == 200


async def create_knowledge_base(client, name: str = "Scoped KB") -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name, "description": "scope test"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_scoped_stats_requires_login(client):
    response = await client.get("/knowledge-bases/1/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scoped_stats_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/stats")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py -v
```

Expected:

```text
test_scoped_stats_requires_login PASSED
test_scoped_stats_hides_other_users_knowledge_base FAILED
404 route not found or endpoint missing
```

- [ ] **Step 3: Add ownership dependency**

Modify `app/dependencies.py`.

Change the imports:

```python
from app.models import (
    KnowledgeBase,
    SystemSession,
    SystemUser,
    Workspace,
    WorkspaceMember,
)
```

Add this function after `get_current_workspace`:

```python
async def get_knowledge_base_for_user(
    knowledge_base_id: int,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.workspace_id == current_workspace.id,
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return knowledge_base
```

- [ ] **Step 4: Add minimal scoped stats endpoint**

Modify `app/routers/knowledge_bases.py`.

Add imports:

```python
from app.dependencies import (
    get_current_user,
    get_current_workspace,
    get_knowledge_base_for_user,
)
```

Add this endpoint after `create_knowledge_base`:

```python
@router.get("/{knowledge_base_id}/stats")
async def get_knowledge_base_stats(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
) -> dict:
    return {
        "knowledge_base_id": knowledge_base.id,
        "workspace_id": knowledge_base.workspace_id,
        "scoped": True,
    }
```

- [ ] **Step 5: Run ownership tests**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run existing multi-user tests**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_system_auth.py tests\test_source_bindings.py tests\test_knowledge_scope.py tests\test_knowledge_base_scoping.py -v
```

Expected:

```text
All collected tests pass.
```

- [ ] **Step 7: Commit**

Run:

```powershell
git add app\dependencies.py app\routers\knowledge_bases.py tests\test_knowledge_base_scoping.py
git commit -m "feat: add knowledge base ownership dependency"
```

## Task 2: Scoped Search Endpoint

**Files:**

- Modify: `app/models.py`
- Modify: `app/routers/knowledge_bases.py`
- Test: `tests/test_knowledge_base_scoping.py`

- [ ] **Step 1: Add failing scoped search test**

Append to `tests/test_knowledge_base_scoping.py`:

```python
@pytest.mark.asyncio
async def test_scoped_search_uses_workspace_and_knowledge_base_filter(
    client,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Search KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "chunk text",
                        "metadata": {
                            "bvid": "BV1xx411c7mD",
                            "title": "Test Video",
                            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/search",
        json={"query": "人工智能", "k": 3},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "Test Video"
    assert captured == {
        "query": "人工智能",
        "workspace_id": knowledge_base["workspace_id"],
        "knowledge_base_id": knowledge_base["id"],
        "k": 3,
    }
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_search_uses_workspace_and_knowledge_base_filter -v
```

Expected:

```text
FAILED with 404 route not found
```

- [ ] **Step 3: Add scoped search Pydantic models**

Modify `app/models.py` after `KnowledgeBaseResponse`:

```python
class KnowledgeBaseSearchRequest(BaseModel):
    query: str
    k: int = 5


class KnowledgeBaseSearchResult(BaseModel):
    content: str
    bvid: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None


class KnowledgeBaseSearchResponse(BaseModel):
    results: list[KnowledgeBaseSearchResult]
```

- [ ] **Step 4: Add search endpoint**

Modify `app/routers/knowledge_bases.py`.

Add imports:

```python
from app.models import (
    KnowledgeBase,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
    SystemUser,
    Workspace,
)
from app.routers.knowledge import get_rag_service
```

Add this helper:

```python
def _search_result(document) -> KnowledgeBaseSearchResult:
    metadata = document.metadata or {}
    return KnowledgeBaseSearchResult(
        content=document.page_content,
        bvid=metadata.get("bvid"),
        title=metadata.get("title"),
        url=metadata.get("url"),
    )
```

Add this endpoint:

```python
@router.post("/{knowledge_base_id}/search", response_model=KnowledgeBaseSearchResponse)
async def search_knowledge_base(
    payload: KnowledgeBaseSearchRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> KnowledgeBaseSearchResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    k = max(1, min(payload.k, 20))
    rag = get_rag_service()
    documents = rag.search_in_knowledge_base(
        query,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
    )
    return KnowledgeBaseSearchResponse(
        results=[_search_result(document) for document in documents]
    )
```

- [ ] **Step 5: Run scoped search test**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_search_uses_workspace_and_knowledge_base_filter -v
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run all scope tests**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_scope.py tests\test_knowledge_base_scoping.py -v
```

Expected:

```text
All collected tests pass.
```

- [ ] **Step 7: Commit**

Run:

```powershell
git add app\models.py app\routers\knowledge_bases.py tests\test_knowledge_base_scoping.py
git commit -m "feat: add scoped knowledge base search"
```

## Task 3: Scoped Chat Endpoint

**Files:**

- Modify: `app/models.py`
- Modify: `app/routers/knowledge_bases.py`
- Test: `tests/test_knowledge_base_scoping.py`

- [ ] **Step 1: Add failing scoped chat test**

Append to `tests/test_knowledge_base_scoping.py`:

```python
@pytest.mark.asyncio
async def test_scoped_chat_uses_scoped_retrieval(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Chat KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Python 是一种编程语言。",
                        "metadata": {
                            "bvid": "BV1py411c7mD",
                            "title": "Python Intro",
                            "url": "https://www.bilibili.com/video/BV1py411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "Python 是什么？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Python" in body["answer"]
    assert body["sources"][0]["title"] == "Python Intro"
    assert captured["workspace_id"] == knowledge_base["workspace_id"]
    assert captured["knowledge_base_id"] == knowledge_base["id"]
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_chat_uses_scoped_retrieval -v
```

Expected:

```text
FAILED with 404 route not found
```

- [ ] **Step 3: Add scoped chat request model**

Modify `app/models.py` after `KnowledgeBaseSearchResponse`:

```python
class KnowledgeBaseChatRequest(BaseModel):
    question: str
    k: int = 5
    smart_search: bool = False
    deep_think: bool = False
```

- [ ] **Step 4: Add chat helpers**

Modify `app/routers/knowledge_bases.py`.

Add imports:

```python
from app.models import (
    ChatResponse,
    KnowledgeBase,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
    SystemUser,
    Workspace,
)
```

Add these helpers:

```python
def _source_from_document(document) -> dict:
    metadata = document.metadata or {}
    return {
        "bvid": metadata.get("bvid"),
        "title": metadata.get("title") or metadata.get("bvid") or "Untitled",
        "url": metadata.get("url")
        or f"https://www.bilibili.com/video/{metadata.get('bvid', '')}",
    }


def _answer_from_documents(question: str, documents: list) -> ChatResponse:
    if not documents:
        return ChatResponse(
            answer="当前知识库中没有找到相关内容。",
            sources=[],
        )
    context = "\n\n".join(document.page_content for document in documents)
    return ChatResponse(
        answer=f"基于当前知识库内容，关于“{question}”可以参考：\n\n{context}",
        sources=[_source_from_document(document) for document in documents],
    )
```

- [ ] **Step 5: Add scoped chat endpoint**

Add this endpoint to `app/routers/knowledge_bases.py`:

```python
@router.post("/{knowledge_base_id}/chat", response_model=ChatResponse)
async def chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> ChatResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    k = max(1, min(payload.k, 20))
    rag = get_rag_service()
    documents = rag.search_in_knowledge_base(
        question,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
    )
    return _answer_from_documents(question, documents)
```

- [ ] **Step 6: Run scoped chat test**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_chat_uses_scoped_retrieval -v
```

Expected:

```text
1 passed
```

- [ ] **Step 7: Run scoped endpoint tests**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py -v
```

Expected:

```text
All collected tests pass.
```

- [ ] **Step 8: Commit**

Run:

```powershell
git add app\models.py app\routers\knowledge_bases.py tests\test_knowledge_base_scoping.py
git commit -m "feat: add scoped knowledge base chat"
```

## Task 4: Scoped Stream Endpoint

**Files:**

- Modify: `app/routers/knowledge_bases.py`
- Test: `tests/test_knowledge_base_scoping.py`

- [ ] **Step 1: Add failing stream test**

Append to `tests/test_knowledge_base_scoping.py`:

```python
@pytest.mark.asyncio
async def test_scoped_chat_stream_requires_owned_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice Stream KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.post(
        f"/knowledge-bases/{alice_kb['id']}/chat/stream",
        json={"question": "hello"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_chat_stream_requires_owned_knowledge_base -v
```

Expected:

```text
FAILED with 404 route not found or ownership dependency not applied
```

- [ ] **Step 3: Add stream endpoint**

Modify `app/routers/knowledge_bases.py`.

Add import:

```python
from fastapi.responses import StreamingResponse
```

Add endpoint:

```python
@router.post("/{knowledge_base_id}/chat/stream")
async def stream_chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    response = await chat_with_knowledge_base(
        payload=payload,
        knowledge_base=knowledge_base,
        current_workspace=current_workspace,
    )

    def generate():
        yield response.answer
        if response.thinking:
            yield "\n[[THINKING_JSON]]"
            yield response.thinking
        if response.sources:
            import json

            yield "\n[[SOURCES_JSON]]"
            yield json.dumps(response.sources, ensure_ascii=False)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
```

- [ ] **Step 4: Run stream test**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_chat_stream_requires_owned_knowledge_base -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Run scoped endpoint tests**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py -v
```

Expected:

```text
All collected tests pass.
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add app\routers\knowledge_bases.py tests\test_knowledge_base_scoping.py
git commit -m "feat: add scoped knowledge base chat stream"
```

## Task 5: Scoped Build Contract

**Files:**

- Modify: `app/models.py`
- Modify: `app/routers/knowledge_bases.py`
- Test: `tests/test_knowledge_base_scoping.py`

- [ ] **Step 1: Add failing build ownership test**

Append to `tests/test_knowledge_base_scoping.py`:

```python
@pytest.mark.asyncio
async def test_scoped_build_rejects_unknown_source_binding(client):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build KB")

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": 999, "folder_ids": [1]},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Add scoped build metadata test**

Append to `tests/test_knowledge_base_scoping.py`:

```python
@pytest.mark.asyncio
async def test_scoped_build_records_scope_metadata(client, db_session_factory):
    from app.models import SourceBinding

    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build Scope KB")

    async with db_session_factory() as session:
        binding = SourceBinding(
            user_id=1,
            workspace_id=knowledge_base["workspace_id"],
            source_type="bilibili",
            external_account_id="12345",
            external_account_name="Alice Bili",
            status="active",
        )
        session.add(binding)
        await session.commit()
        await session.refresh(binding)
        binding_id = binding.id

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding_id, "folder_ids": [1, 2]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == knowledge_base["workspace_id"]
    assert body["knowledge_base_id"] == knowledge_base["id"]
    assert body["source_binding_id"] == binding_id
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_build_rejects_unknown_source_binding tests\test_knowledge_base_scoping.py::test_scoped_build_records_scope_metadata -v
```

Expected:

```text
FAILED with 404 route not found
```

- [ ] **Step 4: Add build request and response models**

Modify `app/models.py` after `KnowledgeBaseChatRequest`:

```python
class KnowledgeBaseBuildRequest(BaseModel):
    source_binding_id: int
    folder_ids: list[int]
    exclude_bvids: Optional[list[str]] = None


class KnowledgeBaseBuildResponse(BaseModel):
    task_id: str
    status: str
    workspace_id: int
    knowledge_base_id: int
    source_binding_id: int
```

- [ ] **Step 5: Add build endpoint**

Modify `app/routers/knowledge_bases.py`.

Add imports:

```python
import uuid

from app.models import (
    ChatResponse,
    KnowledgeBase,
    KnowledgeBaseBuildRequest,
    KnowledgeBaseBuildResponse,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
    SourceBinding,
    SystemUser,
    Workspace,
)
```

Add this endpoint:

```python
@router.post("/{knowledge_base_id}/build", response_model=KnowledgeBaseBuildResponse)
async def build_scoped_knowledge_base(
    payload: KnowledgeBaseBuildRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseBuildResponse:
    source_binding = await db.get(SourceBinding, payload.source_binding_id)
    if (
        source_binding is None
        or source_binding.user_id != current_user.id
        or source_binding.workspace_id != current_workspace.id
        or source_binding.status != "active"
    ):
        raise HTTPException(status_code=404, detail="Source binding not found")

    if not payload.folder_ids:
        raise HTTPException(status_code=400, detail="folder_ids cannot be empty")

    task_id = str(uuid.uuid4())
    return KnowledgeBaseBuildResponse(
        task_id=task_id,
        status="pending",
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=source_binding.id,
    )
```

- [ ] **Step 6: Run scoped build tests**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_knowledge_base_scoping.py::test_scoped_build_rejects_unknown_source_binding tests\test_knowledge_base_scoping.py::test_scoped_build_records_scope_metadata -v
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Run all backend tests**

Run:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_system_auth.py tests\test_source_bindings.py tests\test_knowledge_scope.py tests\test_knowledge_base_scoping.py -v
```

Expected:

```text
All collected tests pass.
```

- [ ] **Step 8: Commit**

Run:

```powershell
git add app\models.py app\routers\knowledge_bases.py tests\test_knowledge_base_scoping.py
git commit -m "feat: add scoped knowledge base build contract"
```

## Task 6: Frontend Scoped API Client

**Files:**

- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add scoped frontend types**

Modify `frontend/lib/api.ts` after `KnowledgeBase`:

```typescript
export interface KnowledgeBaseSearchRequest {
  query: string;
  k?: number;
}

export interface KnowledgeBaseSearchResult {
  content: string;
  bvid?: string;
  title?: string;
  url?: string;
}

export interface KnowledgeBaseSearchResponse {
  results: KnowledgeBaseSearchResult[];
}

export interface KnowledgeBaseChatRequest {
  question: string;
  k?: number;
  smart_search?: boolean;
  deep_think?: boolean;
}

export interface KnowledgeBaseBuildRequest {
  source_binding_id: number;
  folder_ids: number[];
  exclude_bvids?: string[];
}

export interface KnowledgeBaseBuildResponse {
  task_id: string;
  status: string;
  workspace_id: number;
  knowledge_base_id: number;
  source_binding_id: number;
}
```

- [ ] **Step 2: Extend `knowledgeBaseApi`**

Replace the current `knowledgeBaseApi` object with:

```typescript
export const knowledgeBaseApi = {
  list: () => request<KnowledgeBase[]>("/knowledge-bases"),

  create: (data: { name: string; description?: string }) =>
    request<KnowledgeBase>("/knowledge-bases", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  stats: (knowledgeBaseId: number) =>
    request<KnowledgeStats>(`/knowledge-bases/${knowledgeBaseId}/stats`),

  search: (knowledgeBaseId: number, data: KnowledgeBaseSearchRequest) =>
    request<KnowledgeBaseSearchResponse>(
      `/knowledge-bases/${knowledgeBaseId}/search`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  chat: (knowledgeBaseId: number, data: KnowledgeBaseChatRequest) =>
    request<ChatResponse>(`/knowledge-bases/${knowledgeBaseId}/chat`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  chatStreamUrl: (knowledgeBaseId: number) =>
    `${API_BASE_URL}/knowledge-bases/${knowledgeBaseId}/chat/stream`,

  build: (knowledgeBaseId: number, data: KnowledgeBaseBuildRequest) =>
    request<KnowledgeBaseBuildResponse>(
      `/knowledge-bases/${knowledgeBaseId}/build`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),
};
```

- [ ] **Step 3: Run Prettier check**

Run:

```powershell
npx --yes prettier --check frontend\lib\api.ts
```

Expected:

```text
All matched files use Prettier code style!
```

- [ ] **Step 4: Run frontend lint**

Run:

```powershell
cd frontend
npm run lint
```

Expected:

```text
0 errors
```

The existing `ChatPanel.tsx` image optimization warnings are acceptable in this phase.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend\lib\api.ts
git commit -m "feat: add frontend scoped knowledge base api"
```

## Task 7: API Draft Documentation Update

**Files:**

- Modify: `docs/API接口改造草案.md`

- [ ] **Step 1: Update knowledge-base endpoint section**

In `docs/API接口改造草案.md`, replace the knowledge-base endpoint section with:

```markdown
## 知识库接口

已实现的多用户范围化入口：

- `GET /knowledge-bases`
- `POST /knowledge-bases`
- `GET /knowledge-bases/{knowledge_base_id}/stats`
- `POST /knowledge-bases/{knowledge_base_id}/search`
- `POST /knowledge-bases/{knowledge_base_id}/chat`
- `POST /knowledge-bases/{knowledge_base_id}/chat/stream`
- `POST /knowledge-bases/{knowledge_base_id}/build`

所有知识库 ID 必须属于当前用户可访问的工作区。新入口不接受 `session_id` 作为身份来源。
```

- [ ] **Step 2: Run Markdown checks**

Run:

```powershell
npx --yes prettier --check docs\API接口改造草案.md
```

Expected:

```text
All matched files use Prettier code style!
```

- [ ] **Step 3: Commit**

Run:

```powershell
git add docs\API接口改造草案.md
git commit -m "docs: update scoped knowledge base api draft"
```

## Verification

Run full verification:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_system_auth.py tests\test_source_bindings.py tests\test_knowledge_scope.py tests\test_knowledge_base_scoping.py -v
cd frontend
npm run lint
cd ..
npx --yes prettier --check frontend\lib\api.ts docs\API接口改造草案.md docs\superpowers\plans\2026-06-07-knowledge-base-scoping.md
```

Expected:

```text
All pytest tests pass.
Frontend lint reports 0 errors.
Prettier reports all matched files use Prettier code style.
```

## Implementation Order

Execute tasks in order. Do not start frontend API client work before backend endpoint shapes are implemented. Do not remove legacy endpoints in this plan.

## Self-Review

Spec coverage:

- Scoped endpoints under `/knowledge-bases/{knowledge_base_id}/...`: Tasks 1-5.
- Reusable ownership dependency: Task 1.
- Scoped search and chat filters: Tasks 2-3.
- Scoped stream endpoint: Task 4.
- Scoped build metadata contract: Task 5.
- Frontend API client shape: Task 6.
- Compatibility documentation: Task 7.

Risk notes:

- Task 5 adds the scoped build contract and ownership checks, but does not implement the full asynchronous Bilibili folder ingestion path. That deeper ingestion migration should be a follow-up plan because it touches Bilibili credentials, old favorites synchronization, and background task lifecycle.
- The scoped chat endpoint in this plan returns a deterministic answer from retrieved documents for testability. A later pass can reconnect it to the richer LLM response path after the scoped retrieval contract is stable.
