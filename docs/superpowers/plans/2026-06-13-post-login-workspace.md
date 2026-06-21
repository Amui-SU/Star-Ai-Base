# Post-Login Knowledge Workspace Implementation Plan

> **STATUS: COMPLETED** — Scoped chat/search, ingestion separation, responsive workspace, model status, thinking UI, and theme polish were implemented and verified in the main codebase.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive Claude-inspired post-login workspace with clear knowledge-base and ingestion interactions, real folder/video chat scoping, compact model health, and remembered dark/light layout preferences.

**Architecture:** Keep the existing FastAPI and Next.js boundaries, but add a focused backend scope resolver that validates folder/video ownership before extending Chroma filters. On the frontend, separate ingestion selection from chat scope selection, extract new focused UI components, and let `page.tsx` coordinate only cross-panel state such as active knowledge base, build lock, drawer state, and theme.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, Chroma/LangChain, pytest, Next.js 16, React 19, TypeScript, Tailwind CSS 4, Vitest, Testing Library.

---

## Working Tree Safety

The repository already contains uncommitted user changes in frontend files, including `frontend/lib/api.ts` using `NEXT_PUBLIC_API_URL`. Treat the current worktree as the implementation baseline:

- Do not reset, checkout, or revert existing changes.
- Read each target file immediately before editing.
- Preserve `NEXT_PUBLIC_API_URL` unless the user explicitly changes it.
- Keep `.superpowers/brainstorm/` out of commits.
- Commit only files belonging to the current task.

## File Map

### Backend

- Create `app/services/knowledge_scope.py`: list valid scope options and resolve requested folder/video scope into an owned BVID set.
- Modify `app/models.py`: add optional scope fields and response models.
- Modify `app/services/rag.py`: append a BVID filter without weakening workspace/knowledge-base filters.
- Modify `app/routers/knowledge_bases.py`: expose scope options and apply validated scope to search/chat/stream.
- Create `tests/test_knowledge_scope_filters.py`: service and API ownership/filter tests.
- Modify `tests/test_knowledge_scope.py`: verify Chroma filter composition.
- Modify `tests/test_knowledge_base_scoping.py`: update fake RAG signatures and verify router propagation.

### Frontend

- Modify `frontend/package.json`: add Vitest scripts and test dependencies.
- Create `frontend/vitest.config.ts`: jsdom test configuration.
- Create `frontend/test/setup.ts`: jest-dom setup and browser API stubs.
- Create `frontend/lib/chatScope.ts`: scope types, summaries, equality, and request serialization.
- Create `frontend/lib/chatScope.test.ts`: pure scope behavior tests.
- Modify `frontend/lib/api.ts`: add scope contracts and API methods while preserving the current API base environment variable.
- Create `frontend/components/ChatScopePicker.tsx`: folder/video multi-select UI.
- Create `frontend/components/ChatScopePicker.test.tsx`: scope picker interaction tests.
- Create `frontend/components/WorkspaceHeader.tsx`: brand, mobile drawer trigger, theme, and user menu.
- Create `frontend/lib/workspacePreferences.ts`: persisted sidebar/theme preference helpers.
- Create `frontend/lib/workspacePreferences.test.ts`: persistence normalization tests.
- Modify `frontend/components/KnowledgeBasePanel.tsx`: compact selector, active metadata, disabled switching, and parent callbacks.
- Modify `frontend/components/SourcesPanel.tsx`: ingestion-only selection, video exclusions, target-aware footer, and build lock callbacks.
- Modify `frontend/components/ChatPanel.tsx`: scoped requests, compact composer, model icon/latency, and conversation reset behavior.
- Modify `frontend/components/UserMenu.tsx`: click/focus-safe menu behavior and visual alignment.
- Modify `frontend/app/page.tsx`: workspace orchestration, responsive drawer, remembered sidebar, and build lock.
- Modify `frontend/app/globals.css`: Claude-inspired dark/light tokens and responsive workspace styling.

## Task 1: Add Knowledge Scope Domain Service

**Files:**
- Create: `app/services/knowledge_scope.py`
- Modify: `app/models.py:343-377`
- Test: `tests/test_knowledge_scope_filters.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_knowledge_scope_filters.py` with fixtures that insert two knowledge bases, processed videos, folders, and folder-video associations:

```python
from datetime import datetime, timezone

import pytest

from app.models import FavoriteFolder, FavoriteVideo, VideoCache
from app.services.knowledge_scope import (
    InvalidKnowledgeScope,
    list_scope_options,
    resolve_scope_bvids,
)


async def seed_scope_data(db_session_factory, alice_kb_id: int, bob_kb_id: int):
    async with db_session_factory() as session:
        alice_folder = FavoriteFolder(
            session_id="",
            media_id=101,
            title="Alice Folder",
            media_count=2,
            last_sync_at=datetime.now(timezone.utc),
            workspace_id=1,
            knowledge_base_id=alice_kb_id,
        )
        bob_folder = FavoriteFolder(
            session_id="",
            media_id=202,
            title="Bob Folder",
            media_count=1,
            last_sync_at=datetime.now(timezone.utc),
            workspace_id=2,
            knowledge_base_id=bob_kb_id,
        )
        session.add_all([alice_folder, bob_folder])
        await session.flush()

        session.add_all(
            [
                VideoCache(
                    bvid="BV_ALICE_1",
                    title="Alice One",
                    content="indexed",
                    is_processed=True,
                    workspace_id=1,
                    knowledge_base_id=alice_kb_id,
                ),
                VideoCache(
                    bvid="BV_ALICE_2",
                    title="Alice Two",
                    content="indexed",
                    is_processed=True,
                    workspace_id=1,
                    knowledge_base_id=alice_kb_id,
                ),
                VideoCache(
                    bvid="BV_BOB_1",
                    title="Bob One",
                    content="indexed",
                    is_processed=True,
                    workspace_id=2,
                    knowledge_base_id=bob_kb_id,
                ),
            ]
        )
        session.add_all(
            [
                FavoriteVideo(
                    folder_id=alice_folder.id,
                    bvid="BV_ALICE_1",
                    workspace_id=1,
                    knowledge_base_id=alice_kb_id,
                ),
                FavoriteVideo(
                    folder_id=alice_folder.id,
                    bvid="BV_ALICE_2",
                    workspace_id=1,
                    knowledge_base_id=alice_kb_id,
                ),
                FavoriteVideo(
                    folder_id=bob_folder.id,
                    bvid="BV_BOB_1",
                    workspace_id=2,
                    knowledge_base_id=bob_kb_id,
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_scope_options_only_return_owned_processed_videos(
    db_session_factory,
):
    await seed_scope_data(db_session_factory, alice_kb_id=11, bob_kb_id=22)
    async with db_session_factory() as session:
        options = await list_scope_options(session, knowledge_base_id=11)

    assert options == [
        {
            "media_id": 101,
            "title": "Alice Folder",
            "video_count": 2,
            "videos": [
                {"bvid": "BV_ALICE_1", "title": "Alice One"},
                {"bvid": "BV_ALICE_2", "title": "Alice Two"},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_scope_resolver_unions_folder_and_explicit_videos(
    db_session_factory,
):
    await seed_scope_data(db_session_factory, alice_kb_id=11, bob_kb_id=22)
    async with db_session_factory() as session:
        result = await resolve_scope_bvids(
            session,
            knowledge_base_id=11,
            folder_media_ids=[101],
            requested_bvids=["BV_ALICE_2"],
        )

    assert result == ["BV_ALICE_1", "BV_ALICE_2"]


@pytest.mark.asyncio
async def test_scope_resolver_rejects_foreign_video(db_session_factory):
    await seed_scope_data(db_session_factory, alice_kb_id=11, bob_kb_id=22)
    async with db_session_factory() as session:
        with pytest.raises(InvalidKnowledgeScope, match="BV_BOB_1"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=11,
                folder_media_ids=None,
                requested_bvids=["BV_BOB_1"],
            )
```

- [ ] **Step 2: Run the tests and verify import failure**

Run:

```powershell
python -m pytest tests/test_knowledge_scope_filters.py -v
```

Expected: collection fails because `app.services.knowledge_scope` does not exist.

- [ ] **Step 3: Add request and response contracts**

In `app/models.py`, replace the scoped request definitions and add scope option models:

```python
class KnowledgeBaseSearchRequest(BaseModel):
    query: str
    k: int = 5
    folder_ids: Optional[list[int]] = None
    bvids: Optional[list[str]] = None


class KnowledgeBaseChatRequest(BaseModel):
    question: str
    k: int = 5
    smart_search: bool = False
    deep_think: bool = False
    folder_ids: Optional[list[int]] = None
    bvids: Optional[list[str]] = None


class KnowledgeScopeVideo(BaseModel):
    bvid: str
    title: str


class KnowledgeScopeFolder(BaseModel):
    media_id: int
    title: str
    video_count: int
    videos: list[KnowledgeScopeVideo]


class KnowledgeScopeOptionsResponse(BaseModel):
    folders: list[KnowledgeScopeFolder]
```

- [ ] **Step 4: Implement the scope service**

Create `app/services/knowledge_scope.py`:

```python
from collections import defaultdict
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteFolder, FavoriteVideo, VideoCache


class InvalidKnowledgeScope(ValueError):
    pass


def _normalized(values):
    return list(dict.fromkeys(value for value in (values or []) if value))


async def list_scope_options(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
) -> list[dict]:
    rows = await db.execute(
        select(
            FavoriteFolder.media_id,
            FavoriteFolder.title,
            FavoriteVideo.bvid,
            VideoCache.title,
        )
        .join(FavoriteVideo, FavoriteVideo.folder_id == FavoriteFolder.id)
        .join(
            VideoCache,
            and_(
                VideoCache.bvid == FavoriteVideo.bvid,
                VideoCache.knowledge_base_id == knowledge_base_id,
                VideoCache.is_processed.is_(True),
            ),
        )
        .where(FavoriteFolder.knowledge_base_id == knowledge_base_id)
        .where(FavoriteFolder.last_sync_at.isnot(None))
        .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
        .order_by(FavoriteFolder.title, VideoCache.title, FavoriteVideo.bvid)
    )

    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for media_id, folder_title, bvid, video_title in rows.all():
        grouped[(media_id, folder_title)].append(
            {"bvid": bvid, "title": video_title or bvid}
        )

    return [
        {
            "media_id": media_id,
            "title": title,
            "video_count": len(videos),
            "videos": videos,
        }
        for (media_id, title), videos in grouped.items()
    ]


async def resolve_scope_bvids(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
    folder_media_ids: Optional[list[int]],
    requested_bvids: Optional[list[str]],
) -> Optional[list[str]]:
    folder_media_ids = _normalized(folder_media_ids)
    requested_bvids = _normalized(requested_bvids)
    if not folder_media_ids and not requested_bvids:
        return None

    resolved: set[str] = set()

    if folder_media_ids:
        folder_rows = await db.execute(
            select(FavoriteFolder.id, FavoriteFolder.media_id)
            .where(FavoriteFolder.knowledge_base_id == knowledge_base_id)
            .where(FavoriteFolder.last_sync_at.isnot(None))
            .where(FavoriteFolder.media_id.in_(folder_media_ids))
        )
        owned_folders = {media_id: folder_id for folder_id, media_id in folder_rows}
        missing_folders = sorted(set(folder_media_ids) - set(owned_folders))
        if missing_folders:
            raise InvalidKnowledgeScope(
                f"收藏夹不属于当前知识库: {missing_folders}"
            )

        folder_bvid_rows = await db.execute(
            select(FavoriteVideo.bvid)
            .join(VideoCache, VideoCache.bvid == FavoriteVideo.bvid)
            .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
            .where(FavoriteVideo.folder_id.in_(owned_folders.values()))
            .where(VideoCache.knowledge_base_id == knowledge_base_id)
            .where(VideoCache.is_processed.is_(True))
        )
        resolved.update(row[0] for row in folder_bvid_rows.all())

    if requested_bvids:
        video_rows = await db.execute(
            select(FavoriteVideo.bvid)
            .join(VideoCache, VideoCache.bvid == FavoriteVideo.bvid)
            .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
            .where(FavoriteVideo.bvid.in_(requested_bvids))
            .where(VideoCache.knowledge_base_id == knowledge_base_id)
            .where(VideoCache.is_processed.is_(True))
            .distinct()
        )
        owned_bvids = {row[0] for row in video_rows.all()}
        missing_bvids = sorted(set(requested_bvids) - owned_bvids)
        if missing_bvids:
            raise InvalidKnowledgeScope(
                f"视频不属于当前知识库或尚未入库: {missing_bvids}"
            )
        resolved.update(owned_bvids)

    if not resolved:
        raise InvalidKnowledgeScope("所选范围没有可检索的已入库视频")

    return sorted(resolved)
```

- [ ] **Step 5: Run the service tests**

Run:

```powershell
python -m pytest tests/test_knowledge_scope_filters.py -v
```

Expected: all three tests pass.

- [ ] **Step 6: Commit the domain service**

```powershell
git add app/models.py app/services/knowledge_scope.py tests/test_knowledge_scope_filters.py
git commit -m "feat: add knowledge chat scope resolver"
```

## Task 2: Apply Scope Filters to RAG and Scoped APIs

**Files:**
- Modify: `app/services/rag.py:297-315`
- Modify: `app/routers/knowledge_bases.py:343-407`
- Modify: `tests/test_knowledge_scope.py`
- Modify: `tests/test_knowledge_base_scoping.py`
- Modify: `tests/test_knowledge_scope_filters.py`

- [ ] **Step 1: Add failing RAG filter tests**

Extend `tests/test_knowledge_scope.py`:

```python
def test_scoped_rag_search_appends_bvid_filter():
    from app.services.rag import RAGService

    captured = {}

    class FakeVectorStore:
        def similarity_search(self, query, k, filter=None):
            captured["filter"] = filter
            return []

    service = RAGService.__new__(RAGService)
    service.vectorstore = FakeVectorStore()

    service.search_in_knowledge_base(
        "RAG",
        workspace_id=10,
        knowledge_base_id=20,
        k=5,
        bvids=["BV2", "BV1", "BV2"],
    )

    assert captured["filter"] == {
        "$and": [
            {"workspace_id": 10},
            {"knowledge_base_id": 20},
            {"bvid": {"$in": ["BV1", "BV2"]}},
        ]
    }
```

- [ ] **Step 2: Add failing router propagation tests**

Extend `tests/test_knowledge_base_scoping.py` so fake services accept `bvids=None`, then add:

```python
from datetime import datetime, timezone

from app.models import FavoriteFolder, FavoriteVideo, VideoCache


async def seed_owned_scope_rows(
    db_session_factory,
    *,
    workspace_id: int,
    knowledge_base_id: int,
):
    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="",
            media_id=101,
            title="Scoped Folder",
            media_count=2,
            last_sync_at=datetime.now(timezone.utc),
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
        )
        session.add(folder)
        await session.flush()
        session.add_all(
            [
                VideoCache(
                    bvid="BV_ALICE_1",
                    title="Scoped One",
                    content="indexed",
                    is_processed=True,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                ),
                VideoCache(
                    bvid="BV_ALICE_2",
                    title="Scoped Two",
                    content="indexed",
                    is_processed=True,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                ),
                FavoriteVideo(
                    folder_id=folder.id,
                    bvid="BV_ALICE_1",
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                ),
                FavoriteVideo(
                    folder_id=folder.id,
                    bvid="BV_ALICE_2",
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_scoped_chat_passes_validated_bvids_to_rag(
    client,
    db_session_factory,
    monkeypatch,
):
    auth = await register_user(client, "scope@example.com", "Scope")
    knowledge_base = await create_knowledge_base(client, "Scope KB")
    await seed_owned_scope_rows(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=knowledge_base["id"],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "focus", "folder_ids": [101], "bvids": ["BV_ALICE_2"]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV_ALICE_1", "BV_ALICE_2"]


@pytest.mark.asyncio
async def test_scoped_chat_rejects_foreign_bvid(
    client,
    db_session_factory,
):
    auth = await register_user(client, "invalid-scope@example.com", "Scope")
    knowledge_base = await create_knowledge_base(client, "Invalid Scope KB")
    await seed_owned_scope_rows(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=knowledge_base["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "focus", "bvids": ["BV_NOT_OWNED"]},
    )

    assert response.status_code == 400
    assert "BV_NOT_OWNED" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scope_options_return_only_current_knowledge_base_videos(
    client,
    db_session_factory,
):
    auth = await register_user(client, "options@example.com", "Options")
    knowledge_base = await create_knowledge_base(client, "Options KB")
    await seed_owned_scope_rows(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=knowledge_base["id"],
    )

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/scope-options"
    )

    assert response.status_code == 200
    assert response.json() == {
        "folders": [
            {
                "media_id": 101,
                "title": "Scoped Folder",
                "video_count": 2,
                "videos": [
                    {"bvid": "BV_ALICE_1", "title": "Scoped One"},
                    {"bvid": "BV_ALICE_2", "title": "Scoped Two"},
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_same_scope_filter(
    client,
    db_session_factory,
    monkeypatch,
):
    auth = await register_user(client, "stream-scope@example.com", "Stream")
    knowledge_base = await create_knowledge_base(client, "Stream Scope KB")
    await seed_owned_scope_rows(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=knowledge_base["id"],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "focus", "folder_ids": [101]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV_ALICE_1", "BV_ALICE_2"]
```

- [ ] **Step 3: Run focused tests and verify signature/behavior failures**

Run:

```powershell
python -m pytest tests/test_knowledge_scope.py tests/test_knowledge_base_scoping.py tests/test_knowledge_scope_filters.py -v
```

Expected: failures show that `search_in_knowledge_base` does not accept `bvids` and routers do not resolve scope.

- [ ] **Step 4: Extend the RAG filter**

Replace `search_in_knowledge_base` in `app/services/rag.py` with:

```python
def search_in_knowledge_base(
    self,
    query: str,
    workspace_id: int,
    knowledge_base_id: int,
    k: int = 5,
    bvids: Optional[List[str]] = None,
) -> List[Document]:
    if not query or not query.strip():
        return []

    filters = [
        {"workspace_id": workspace_id},
        {"knowledge_base_id": knowledge_base_id},
    ]
    normalized_bvids = sorted(set(bvids or []))
    if normalized_bvids:
        filters.append({"bvid": {"$in": normalized_bvids}})

    return self.vectorstore.similarity_search(
        query,
        k=k,
        filter={"$and": filters},
    )
```

- [ ] **Step 5: Add the scope options endpoint and shared resolver**

In `app/routers/knowledge_bases.py`, import:

```python
from app.models import KnowledgeScopeOptionsResponse
from app.services.knowledge_scope import (
    InvalidKnowledgeScope,
    list_scope_options,
    resolve_scope_bvids,
)
```

Add:

```python
async def _resolve_request_scope(
    db: AsyncSession,
    knowledge_base_id: int,
    folder_ids: list[int] | None,
    bvids: list[str] | None,
) -> list[str] | None:
    try:
        return await resolve_scope_bvids(
            db,
            knowledge_base_id=knowledge_base_id,
            folder_media_ids=folder_ids,
            requested_bvids=bvids,
        )
    except InvalidKnowledgeScope as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{knowledge_base_id}/scope-options",
    response_model=KnowledgeScopeOptionsResponse,
)
async def get_knowledge_scope_options(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeScopeOptionsResponse:
    folders = await list_scope_options(
        db,
        knowledge_base_id=knowledge_base.id,
    )
    return KnowledgeScopeOptionsResponse(folders=folders)
```

Add `db: AsyncSession = Depends(get_db)` to scoped search/chat/stream endpoints. Before each RAG search, resolve:

```python
scope_bvids = await _resolve_request_scope(
    db,
    knowledge_base.id,
    payload.folder_ids,
    payload.bvids,
)
```

Pass `bvids=scope_bvids` to `search_in_knowledge_base`. The stream endpoint must pass the same `db` session into `chat_with_knowledge_base`:

```python
response = await chat_with_knowledge_base(
    payload=payload,
    knowledge_base=knowledge_base,
    current_workspace=current_workspace,
    db=db,
)
```

- [ ] **Step 6: Run backend scope tests**

Run:

```powershell
python -m pytest tests/test_knowledge_scope.py tests/test_knowledge_base_scoping.py tests/test_knowledge_scope_filters.py -v
```

Expected: all tests pass, including unfiltered legacy behavior and filtered stream/non-stream behavior.

- [ ] **Step 7: Run the full backend suite**

Run:

```powershell
python -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit the API integration**

```powershell
git add app/services/rag.py app/routers/knowledge_bases.py tests/test_knowledge_scope.py tests/test_knowledge_base_scoping.py tests/test_knowledge_scope_filters.py
git commit -m "feat: filter knowledge chat by folders and videos"
```

## Task 3: Add Frontend Test Harness and Scope Contracts

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/test/setup.ts`
- Create: `frontend/lib/chatScope.ts`
- Create: `frontend/lib/chatScope.test.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add test dependencies and scripts**

From `frontend`, run:

```powershell
npm install --save-dev vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Update `frontend/package.json` scripts:

```json
{
  "scripts": {
    "dev": "next dev --webpack",
    "build": "next build --webpack",
    "start": "next start",
    "lint": "eslint",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 2: Configure Vitest**

Create `frontend/vitest.config.ts`:

```typescript
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    css: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
```

Create `frontend/test/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});
```

- [ ] **Step 3: Write failing scope helper tests**

Create `frontend/lib/chatScope.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  EMPTY_CHAT_SCOPE,
  scopeEquals,
  scopeSummary,
  toScopePayload,
} from "@/lib/chatScope";

describe("chat scope helpers", () => {
  it("describes the whole knowledge base when nothing is selected", () => {
    expect(scopeSummary(EMPTY_CHAT_SCOPE)).toBe("整个知识库");
    expect(toScopePayload(EMPTY_CHAT_SCOPE)).toEqual({});
  });

  it("describes combined folder and video selections", () => {
    const scope = { folderIds: [2, 1], bvids: ["BV2", "BV1"] };
    expect(scopeSummary(scope)).toBe("2 个收藏夹 + 2 个视频");
    expect(toScopePayload(scope)).toEqual({
      folder_ids: [1, 2],
      bvids: ["BV1", "BV2"],
    });
  });

  it("compares selections without depending on order", () => {
    expect(
      scopeEquals(
        { folderIds: [2, 1], bvids: ["BV2", "BV1"] },
        { folderIds: [1, 2], bvids: ["BV1", "BV2"] },
      ),
    ).toBe(true);
  });
});
```

- [ ] **Step 4: Run the helper tests and verify import failure**

Run:

```powershell
cd frontend
npm test -- lib/chatScope.test.ts
```

Expected: FAIL because `frontend/lib/chatScope.ts` does not exist.

- [ ] **Step 5: Implement scope helpers**

Create `frontend/lib/chatScope.ts`:

```typescript
export interface ChatScopeSelection {
  folderIds: number[];
  bvids: string[];
}

export const EMPTY_CHAT_SCOPE: ChatScopeSelection = {
  folderIds: [],
  bvids: [],
};

const uniqueSortedNumbers = (values: number[]) =>
  [...new Set(values)].sort((a, b) => a - b);

const uniqueSortedStrings = (values: string[]) =>
  [...new Set(values)].sort((a, b) => a.localeCompare(b));

export function normalizeScope(
  scope: ChatScopeSelection,
): ChatScopeSelection {
  return {
    folderIds: uniqueSortedNumbers(scope.folderIds),
    bvids: uniqueSortedStrings(scope.bvids),
  };
}

export function scopeEquals(
  left: ChatScopeSelection,
  right: ChatScopeSelection,
) {
  const a = normalizeScope(left);
  const b = normalizeScope(right);
  return (
    a.folderIds.join(",") === b.folderIds.join(",") &&
    a.bvids.join(",") === b.bvids.join(",")
  );
}

export function scopeSummary(scope: ChatScopeSelection) {
  const normalized = normalizeScope(scope);
  if (!normalized.folderIds.length && !normalized.bvids.length) {
    return "整个知识库";
  }
  const parts = [];
  if (normalized.folderIds.length) {
    parts.push(`${normalized.folderIds.length} 个收藏夹`);
  }
  if (normalized.bvids.length) {
    parts.push(`${normalized.bvids.length} 个视频`);
  }
  return parts.join(" + ");
}

export function toScopePayload(scope: ChatScopeSelection) {
  const normalized = normalizeScope(scope);
  return {
    ...(normalized.folderIds.length
      ? { folder_ids: normalized.folderIds }
      : {}),
    ...(normalized.bvids.length ? { bvids: normalized.bvids } : {}),
  };
}
```

- [ ] **Step 6: Extend frontend API contracts**

In `frontend/lib/api.ts`, preserve:

```typescript
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

Add:

```typescript
export interface KnowledgeScopeVideo {
  bvid: string;
  title: string;
}

export interface KnowledgeScopeFolder {
  media_id: number;
  title: string;
  video_count: number;
  videos: KnowledgeScopeVideo[];
}

export interface KnowledgeScopeOptions {
  folders: KnowledgeScopeFolder[];
}

export interface KnowledgeScopeRequest {
  folder_ids?: number[];
  bvids?: string[];
}

export interface KnowledgeBaseSearchRequest extends KnowledgeScopeRequest {
  query: string;
  k?: number;
}

export interface KnowledgeBaseChatRequest extends KnowledgeScopeRequest {
  question: string;
  k?: number;
  smart_search?: boolean;
  deep_think?: boolean;
}
```

Replace the existing search/chat request interfaces with the definitions above. Add:

```typescript
getScopeOptions: (knowledgeBaseId: number) =>
  request<KnowledgeScopeOptions>(
    `/knowledge-bases/${knowledgeBaseId}/scope-options`,
  ),
```

- [ ] **Step 7: Run helper tests, lint, and type build**

Run:

```powershell
cd frontend
npm test -- lib/chatScope.test.ts
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 8: Commit the frontend foundation**

```powershell
git add frontend/package.json frontend/vitest.config.ts frontend/test/setup.ts frontend/lib/chatScope.ts frontend/lib/chatScope.test.ts frontend/lib/api.ts
git commit -m "test: add frontend scope contracts"
```

## Task 4: Build the Chat Scope Picker and Wire Scoped Requests

**Files:**
- Create: `frontend/components/ChatScopePicker.tsx`
- Create: `frontend/components/ChatScopePicker.test.tsx`
- Modify: `frontend/components/ChatPanel.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Write failing picker tests**

Create `frontend/components/ChatScopePicker.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatScopePicker from "@/components/ChatScopePicker";

const options = {
  folders: [
    {
      media_id: 101,
      title: "AI 课程",
      video_count: 2,
      videos: [
        { bvid: "BV1", title: "RAG 入门" },
        { bvid: "BV2", title: "评估方法" },
      ],
    },
  ],
};

describe("ChatScopePicker", () => {
  it("selects folders and videos independently", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ChatScopePicker
        options={options}
        value={{ folderIds: [], bvids: [] }}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "提问范围" }));
    await user.click(screen.getByRole("checkbox", { name: "AI 课程" }));
    expect(onChange).toHaveBeenLastCalledWith({
      folderIds: [101],
      bvids: [],
    });

    await user.click(screen.getByRole("checkbox", { name: "RAG 入门" }));
    expect(onChange).toHaveBeenLastCalledWith({
      folderIds: [],
      bvids: ["BV1"],
    });
  });

  it("resets to the whole knowledge base", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ChatScopePicker
        options={options}
        value={{ folderIds: [101], bvids: ["BV1"] }}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /提问范围/ }));
    await user.click(screen.getByRole("button", { name: "恢复整个知识库" }));
    expect(onChange).toHaveBeenCalledWith({ folderIds: [], bvids: [] });
  });
});
```

- [ ] **Step 2: Run the picker tests and verify component failure**

Run:

```powershell
cd frontend
npm test -- components/ChatScopePicker.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement `ChatScopePicker`**

Create a controlled component with this public interface:

```tsx
import type { KnowledgeScopeOptions } from "@/lib/api";
import {
  ChatScopeSelection,
  EMPTY_CHAT_SCOPE,
  scopeSummary,
} from "@/lib/chatScope";

interface Props {
  options: KnowledgeScopeOptions;
  value: ChatScopeSelection;
  onChange: (next: ChatScopeSelection) => void;
  disabled?: boolean;
}
```

Implementation requirements:

- Button accessible name starts with `提问范围`.
- Popover contains “整个知识库”, folder checkboxes, a video search field, and video checkboxes.
- Folder toggles only `folderIds`; video toggles only `bvids`.
- “恢复整个知识库” emits `EMPTY_CHAT_SCOPE`.
- Clicking outside and pressing Escape close the popover.
- Selected summary uses `scopeSummary(value)`.
- Folder expansion is local UI state and does not change selection.

Use immutable toggle helpers:

```typescript
function toggleNumber(values: number[], value: number) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function toggleString(values: string[], value: string) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}
```

- [ ] **Step 4: Integrate scope state into `ChatPanel`**

In `ChatPanel.tsx`:

1. Remove the unused `folderIds` prop.
2. Add state:

```typescript
const [scopeOptions, setScopeOptions] =
  useState<KnowledgeScopeOptions>({ folders: [] });
const [chatScope, setChatScope] =
  useState<ChatScopeSelection>(EMPTY_CHAT_SCOPE);
const [scopeNotice, setScopeNotice] = useState("");
```

3. On `knowledgeBaseId` change:

```typescript
useEffect(() => {
  stopGenerating();
  setMessages([]);
  setChatScope(EMPTY_CHAT_SCOPE);
  setScopeNotice("");
  if (!knowledgeBaseId) {
    setScopeOptions({ folders: [] });
    return;
  }
  knowledgeBaseApi
    .getScopeOptions(knowledgeBaseId)
    .then(setScopeOptions)
    .catch(() => setScopeOptions({ folders: [] }));
}, [knowledgeBaseId]);
```

4. Add:

```typescript
const handleScopeChange = (next: ChatScopeSelection) => {
  if (scopeEquals(chatScope, next)) return;
  stopGenerating();
  setMessages([]);
  setChatScope(next);
  setScopeNotice(`提问范围已更新：${scopeSummary(next)}`);
  window.setTimeout(() => setScopeNotice(""), 2200);
};
```

5. Include scope in both stream and non-stream bodies:

```typescript
const scopedPayload = {
  question: q,
  k: 5,
  smart_search: smartSearchEnabled,
  deep_think: deepThinkEnabled,
  ...toScopePayload(chatScope),
};
```

6. Render `ChatScopePicker` in the composer control row. Render `scopeNotice` as an `aria-live="polite"` toast above the composer.

- [ ] **Step 5: Add picker/composer CSS**

In `globals.css`, add focused classes:

```css
.scope-picker { position: relative; }
.scope-picker-popover {
  position: absolute;
  left: 0;
  bottom: calc(100% + 10px);
  width: min(360px, calc(100vw - 28px));
  max-height: min(520px, 70vh);
  overflow: auto;
  border: 1px solid var(--border-strong);
  border-radius: 18px;
  background: var(--panel-bg);
  box-shadow: 0 18px 52px var(--shadow);
  padding: 12px;
  z-index: 70;
}
.scope-option {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  min-height: 38px;
  border-radius: 11px;
  padding: 8px 10px;
  color: var(--ink-soft);
}
.scope-option:hover { background: var(--paper-2); }
.scope-notice {
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 11px;
  text-align: center;
}
```

- [ ] **Step 6: Run scope component and frontend checks**

Run:

```powershell
cd frontend
npm test -- lib/chatScope.test.ts components/ChatScopePicker.test.tsx
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 7: Commit scoped chat UI**

```powershell
git add frontend/components/ChatScopePicker.tsx frontend/components/ChatScopePicker.test.tsx frontend/components/ChatPanel.tsx frontend/app/globals.css
git commit -m "feat: add folder and video chat scope picker"
```

## Task 5: Clarify Knowledge Base and Ingestion Interactions

**Files:**
- Modify: `frontend/components/KnowledgeBasePanel.tsx`
- Modify: `frontend/components/SourcesPanel.tsx`
- Modify: `frontend/app/page.tsx`
- Test: `frontend/components/KnowledgeBasePanel.test.tsx`

- [ ] **Step 1: Write failing knowledge-base selector tests**

Create `frontend/components/KnowledgeBasePanel.test.tsx` using mocked `knowledgeBaseApi.list`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import KnowledgeBasePanel from "@/components/KnowledgeBasePanel";
import { knowledgeBaseApi } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      list: vi.fn(),
      create: vi.fn(),
      delete: vi.fn(),
    },
  };
});

describe("KnowledgeBasePanel", () => {
  beforeEach(() => {
    vi.mocked(knowledgeBaseApi.list).mockResolvedValue([
      { id: 7, workspace_id: 1, name: "产品学习库" },
      { id: 8, workspace_id: 1, name: "技术课程" },
    ]);
  });

  it("reports the selected knowledge base object", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <KnowledgeBasePanel
        activeId={7}
        activeVideoCount={128}
        disabled={false}
        onSelect={onSelect}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /产品学习库/ }));
    await user.click(screen.getByRole("button", { name: /技术课程/ }));
    expect(onSelect).toHaveBeenCalledWith({
      id: 8,
      workspace_id: 1,
      name: "技术课程",
    });
  });

  it("blocks switching while a build is running", async () => {
    render(
      <KnowledgeBasePanel
        activeId={7}
        activeVideoCount={128}
        disabled
        onSelect={vi.fn()}
      />,
    );
    expect(
      await screen.findByRole("button", { name: /产品学习库/ }),
    ).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run selector tests and verify prop/API failures**

Run:

```powershell
cd frontend
npm test -- components/KnowledgeBasePanel.test.tsx
```

Expected: FAIL because the selector does not expose the new controlled interface.

- [ ] **Step 3: Refactor `KnowledgeBasePanel` into a compact selector**

Change props to:

```typescript
interface Props {
  activeId: number | null;
  activeVideoCount: number;
  onSelect: (knowledgeBase: KnowledgeBase | null) => void;
  refreshKey?: number;
  disabled?: boolean;
}
```

Behavior:

- Closed control shows active name and `{activeVideoCount} 个已入库视频`.
- Opening shows all knowledge bases plus create/delete controls.
- Selecting emits the full `KnowledgeBase`.
- If the stored `activeId` is missing from the fetched list, select the first knowledge base.
- If the list is empty, emit `null`.
- Disable selection/create/delete while `disabled`.
- Keep errors inline with a retry button that reruns `knowledgeBaseApi.list()`.

- [ ] **Step 4: Make `SourcesPanel` ingestion-only**

Change props:

```typescript
interface Props {
  sourceBindingId: number;
  knowledgeBaseId: number;
  knowledgeBaseName: string;
  onBuildDone?: () => void;
  onBuildingChange?: (building: boolean) => void;
}
```

Remove `onSelectionChange`. Keep selected folder IDs internal. Add `excludedBvids: Set<string>` and per-video “本次排除” checkboxes. Submit:

```typescript
await knowledgeBaseApi.build(knowledgeBaseId, {
  source_binding_id: sourceBindingId,
  folder_ids: Array.from(selected),
  exclude_bvids: Array.from(excludedBvids),
});
```

Call `onBuildingChange?.(true)` before submission and `onBuildingChange?.(false)` in every completed/failed/final catch path.

Footer copy must be target-aware:

```typescript
const taskSummary = selected.size
  ? `已选 ${selected.size} 个收藏夹`
  : "选择要入库或更新的收藏夹";

const actionLabel = building
  ? progress?.current_step || "处理中..."
  : `${hasUnindexed ? "入库" : "更新"}到“${knowledgeBaseName}”`;
```

Disable folder/video task selection while building, but keep expansion/playback enabled.

- [ ] **Step 5: Coordinate active knowledge base and build lock in `page.tsx`**

Replace `selectedFolderIds` with:

```typescript
const [activeKnowledgeBase, setActiveKnowledgeBase] =
  useState<KnowledgeBase | null>(null);
const [isBuilding, setIsBuilding] = useState(false);
const [workspaceNotice, setWorkspaceNotice] = useState("");
```

When selecting a different knowledge base:

```typescript
const handleKnowledgeBaseSelect = (next: KnowledgeBase | null) => {
  if (isBuilding) return;
  const changed = next?.id !== activeKnowledgeBase?.id;
  setActiveKnowledgeBase(next);
  setActiveKbId(next?.id ?? null);
  localStorage.setItem("active_kb_id", next ? String(next.id) : "");
  if (changed && next) {
    setWorkspaceNotice(`已切换至 ${next.name}`);
    window.setTimeout(() => setWorkspaceNotice(""), 2200);
  }
};
```

Render `SourcesPanel` with `key={activeKbId}` so ingestion selection resets when the knowledge base changes. Pass `disabled={isBuilding}` to `KnowledgeBasePanel`.

- [ ] **Step 6: Run selector tests and frontend checks**

Run:

```powershell
cd frontend
npm test -- components/KnowledgeBasePanel.test.tsx
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 7: Commit knowledge workspace interactions**

```powershell
git add frontend/components/KnowledgeBasePanel.tsx frontend/components/KnowledgeBasePanel.test.tsx frontend/components/SourcesPanel.tsx frontend/app/page.tsx
git commit -m "feat: clarify knowledge ingestion workflow"
```

## Task 6: Build the Responsive Workspace Shell and Persist Preferences

**Files:**
- Create: `frontend/components/WorkspaceHeader.tsx`
- Create: `frontend/lib/workspacePreferences.ts`
- Create: `frontend/lib/workspacePreferences.test.ts`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/UserMenu.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Write failing preference tests**

Create `frontend/lib/workspacePreferences.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  DEFAULT_WORKSPACE_PREFERENCES,
  readWorkspacePreferences,
  writeWorkspacePreferences,
} from "@/lib/workspacePreferences";

describe("workspace preferences", () => {
  it("uses an open 320px sidebar for a new user", () => {
    localStorage.clear();
    expect(readWorkspacePreferences(localStorage)).toEqual(
      DEFAULT_WORKSPACE_PREFERENCES,
    );
  });

  it("clamps persisted sidebar widths", () => {
    localStorage.setItem(
      "workspace_preferences",
      JSON.stringify({ sidebarOpen: false, sidebarWidth: 9999 }),
    );
    expect(readWorkspacePreferences(localStorage)).toEqual({
      sidebarOpen: false,
      sidebarWidth: 480,
    });
  });

  it("writes normalized preferences", () => {
    writeWorkspacePreferences(localStorage, {
      sidebarOpen: true,
      sidebarWidth: 200,
    });
    expect(JSON.parse(localStorage.getItem("workspace_preferences")!)).toEqual({
      sidebarOpen: true,
      sidebarWidth: 280,
    });
  });
});
```

- [ ] **Step 2: Run preferences tests and verify import failure**

Run:

```powershell
cd frontend
npm test -- lib/workspacePreferences.test.ts
```

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement persisted preferences**

Create `frontend/lib/workspacePreferences.ts`:

```typescript
export interface WorkspacePreferences {
  sidebarOpen: boolean;
  sidebarWidth: number;
}

export const DEFAULT_WORKSPACE_PREFERENCES: WorkspacePreferences = {
  sidebarOpen: true,
  sidebarWidth: 320,
};

const clampWidth = (value: number) => Math.min(480, Math.max(280, value));

export function readWorkspacePreferences(
  storage: Pick<Storage, "getItem">,
): WorkspacePreferences {
  try {
    const raw = storage.getItem("workspace_preferences");
    if (!raw) return DEFAULT_WORKSPACE_PREFERENCES;
    const parsed = JSON.parse(raw);
    return {
      sidebarOpen:
        typeof parsed.sidebarOpen === "boolean"
          ? parsed.sidebarOpen
          : true,
      sidebarWidth: clampWidth(Number(parsed.sidebarWidth) || 320),
    };
  } catch {
    return DEFAULT_WORKSPACE_PREFERENCES;
  }
}

export function writeWorkspacePreferences(
  storage: Pick<Storage, "setItem">,
  preferences: WorkspacePreferences,
) {
  storage.setItem(
    "workspace_preferences",
    JSON.stringify({
      sidebarOpen: preferences.sidebarOpen,
      sidebarWidth: clampWidth(preferences.sidebarWidth),
    }),
  );
}
```

- [ ] **Step 4: Create `WorkspaceHeader`**

Public interface:

```typescript
interface Props {
  user: SystemUser;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onOpenKnowledgeDrawer: () => void;
  onLogout: () => void;
}
```

Render:

- Left: mobile-only menu button and the same layered logo/“智库云” serif brand used on the login page.
- Right: theme toggle and `UserMenu`.
- No centered knowledge-base selector.
- `aria-label="打开知识空间"` on the drawer button.

- [ ] **Step 5: Convert the desktop sidebar into a mobile drawer**

In `page.tsx`:

- Initialize sidebar state from `readWorkspacePreferences`.
- Persist width/open state after changes.
- Add `isKnowledgeDrawerOpen`.
- Render a backdrop button on widths below `1024px`.
- Close the drawer after a knowledge-base selection on tablet/mobile.
- Keep the desktop resizer only at `min-width: 1024px`.

Use semantic classes instead of inline transforms:

```tsx
<div
  className={`knowledge-shell ${
    isSidebarOpen ? "is-open" : "is-closed"
  } ${isKnowledgeDrawerOpen ? "is-drawer-open" : ""}`}
  style={{ "--sidebar-width": `${sidebarWidth}px` } as React.CSSProperties}
>
  <aside className="knowledge-sidebar">...</aside>
</div>
```

- [ ] **Step 6: Make `UserMenu` click/focus safe**

Replace hover-only visibility with local `open` state:

- Avatar button toggles the menu and sets `aria-expanded`.
- Clicking outside or pressing Escape closes it.
- Menu stays usable on touch devices and keyboard focus.
- Keep current account and logout content.

- [ ] **Step 7: Add responsive shell CSS**

Replace the current `@media (max-width: 1024px)` column fallback with:

```css
.workspace-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  padding: 0 18px;
  background: var(--header-bg);
  backdrop-filter: blur(18px);
}
.knowledge-shell {
  width: var(--sidebar-width);
  flex: 0 0 auto;
  transition: width 260ms ease;
}
.knowledge-shell.is-closed { width: 0; }
.knowledge-sidebar {
  width: var(--sidebar-width);
  height: 100%;
  border-right: 1px solid var(--border);
  background: var(--panel-bg);
}
.knowledge-drawer-backdrop { display: none; }

@media (max-width: 1023px) {
  .knowledge-shell {
    position: fixed;
    inset: 56px auto 0 0;
    width: min(88vw, 360px);
    transform: translateX(-102%);
    z-index: 60;
    transition: transform 260ms cubic-bezier(.22, 1, .36, 1);
  }
  .knowledge-shell.is-drawer-open { transform: translateX(0); }
  .knowledge-sidebar { width: 100%; }
  .knowledge-drawer-backdrop {
    display: block;
    position: fixed;
    inset: 56px 0 0;
    background: rgba(0, 0, 0, 0.42);
    z-index: 55;
  }
  .resizer,
  .desktop-sidebar-toggle { display: none; }
}
```

- [ ] **Step 8: Run preference tests and frontend checks**

Run:

```powershell
cd frontend
npm test -- lib/workspacePreferences.test.ts
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 9: Commit the responsive shell**

```powershell
git add frontend/components/WorkspaceHeader.tsx frontend/lib/workspacePreferences.ts frontend/lib/workspacePreferences.test.ts frontend/app/page.tsx frontend/components/UserMenu.tsx frontend/app/globals.css
git commit -m "feat: add responsive remembered workspace shell"
```

## Task 7: Compact the Model Status and Composer

**Files:**
- Modify: `frontend/components/ChatPanel.tsx`
- Modify: `frontend/app/globals.css`
- Test: `frontend/components/ChatPanel.test.tsx`

- [ ] **Step 1: Write focused composer/model tests**

Create `frontend/components/ChatPanel.test.tsx` with API mocks:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import { chatApi, knowledgeBaseApi } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    chatApi: {
      ...actual.chatApi,
      getModelConfig: vi.fn(),
      health: vi.fn(),
    },
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      stats: vi.fn(),
      getScopeOptions: vi.fn(),
    },
  };
});

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.mocked(chatApi.getModelConfig).mockResolvedValue({
      current_provider: "deepseek",
      providers: [
        {
          provider: "deepseek",
          label: "DeepSeek",
          enabled: true,
          model: "deepseek-chat",
        },
      ],
    });
    vi.mocked(chatApi.health).mockResolvedValue({
      status: "ok",
      message: "模型服务可用",
      latency_ms: 72,
      model: "deepseek-chat",
      provider: "deepseek",
    });
    vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
      knowledge_base_id: 7,
      workspace_id: 1,
      total_videos: 128,
      folders: [],
      scoped: true,
    });
    vi.mocked(knowledgeBaseApi.getScopeOptions).mockResolvedValue({
      folders: [],
    });
  });

  it("shows provider identity and latency", async () => {
    render(
      <ChatPanel
        knowledgeBaseId={7}
        knowledgeBaseName="产品学习库"
        statsKey={0}
      />,
    );

    expect(await screen.findByText("DeepSeek")).toBeInTheDocument();
    expect(await screen.findByText("72 ms")).toBeInTheDocument();
  });

  it("starts with a one-row composer", async () => {
    render(
      <ChatPanel
        knowledgeBaseId={null}
        knowledgeBaseName=""
        statsKey={0}
      />,
    );
    expect(screen.getByRole("textbox")).toHaveAttribute("rows", "1");
  });
});
```

- [ ] **Step 2: Run tests and verify current prop/layout failures**

Run:

```powershell
cd frontend
npm test -- components/ChatPanel.test.tsx
```

Expected: FAIL because `knowledgeBaseName` is not a prop and compact status is not rendered.

- [ ] **Step 3: Compact the model status**

Update `ChatPanel` props:

```typescript
interface Props {
  statsKey?: number;
  knowledgeBaseId?: number | null;
  knowledgeBaseName: string;
}
```

Use the existing `providerLogoMap`. Render a compact button containing:

- Provider logo.
- Provider label on desktop.
- Status dot.
- `${latency_ms} ms` when healthy.
- `检查中` while loading.
- `不可用` when down.

Keep the current provider menu and configuration modal behavior. Remove fixed left positioning based on sidebar width. Place the model control inside `.chat-toolbar` at the top of the chat panel.

- [ ] **Step 4: Reduce composer height**

Change the resize function:

```typescript
const composerMaxHeight =
  typeof window !== "undefined" && window.innerWidth < 768 ? 150 : 180;
const nextHeight = Math.min(
  Math.max(textarea.scrollHeight, 52),
  composerMaxHeight,
);
textarea.style.height = `${nextHeight}px`;
textarea.style.overflowY =
  textarea.scrollHeight > composerMaxHeight ? "auto" : "hidden";
```

Update CSS:

```css
.composer-input {
  min-height: 52px;
  max-height: 180px;
  padding: 13px 156px 13px 16px;
  line-height: 1.45;
  resize: none;
  overflow-y: hidden;
}
.composer-mode-row {
  left: auto;
  right: 10px;
  bottom: 10px;
  background: transparent;
}
@media (max-width: 767px) {
  .composer-input {
    max-height: 150px;
    padding-right: 52px;
    padding-bottom: 44px;
  }
  .composer-chip-group {
    max-width: calc(100vw - 96px);
    overflow-x: auto;
  }
}
```

If scope/mode chips do not fit beside a single-line draft, allow the composer to settle at the CSS minimum needed for controls, but do not restore the old fixed `92px` minimum.

- [ ] **Step 5: Simplify the empty state hierarchy**

Use the active knowledge base name only as subdued supporting text:

```tsx
<h1 className="chat-empty-title">探索你的收藏</h1>
<p className="chat-empty-subtitle">
  {stats?.total_videos
    ? `基于“${knowledgeBaseName}”的 ${stats.total_videos} 个已入库视频回答`
    : "先在知识空间中导入收藏夹内容"}
</p>
```

Do not add a large top knowledge-base pill.

- [ ] **Step 6: Run component tests and frontend checks**

Run:

```powershell
cd frontend
npm test -- components/ChatPanel.test.tsx
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 7: Commit model/composer polish**

```powershell
git add frontend/components/ChatPanel.tsx frontend/components/ChatPanel.test.tsx frontend/app/globals.css
git commit -m "feat: compact chat model status and composer"
```

## Task 8: Finish Dark/Light Visual System and Run End-to-End Verification

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/WorkspaceHeader.tsx`
- Modify: `frontend/components/KnowledgeBasePanel.tsx`
- Modify: `frontend/components/SourcesPanel.tsx`
- Modify: `frontend/components/ChatScopePicker.tsx`
- Modify: `frontend/components/ChatPanel.tsx`

- [ ] **Step 1: Normalize theme tokens**

Keep the dark theme as default. Update light tokens to the approved warm-paper palette:

```css
:root {
  --bg: #141413;
  --panel-bg: #222220;
  --paper: #262624;
  --paper-2: #30302e;
  --paper-3: #3d3d3a;
  --ink: #faf9f5;
  --ink-soft: #dedbd4;
  --muted: #a8a49c;
  --muted-weak: #77746e;
  --accent: #d97757;
  --accent-strong: #e2a28d;
  --success: #8fb39a;
  --border: #333230;
  --border-strong: #484744;
  --input-bg: #262624;
}

html.light {
  --bg: #f7f1e8;
  --panel-bg: rgba(250, 246, 239, 0.78);
  --paper: rgba(250, 246, 239, 0.82);
  --paper-2: #efe6d7;
  --paper-3: #e6d7c2;
  --ink: #1b1713;
  --ink-soft: #2b241d;
  --muted: #7b7167;
  --muted-weak: #9e9488;
  --accent: #b96040;
  --accent-strong: #9f4f34;
  --success: #397b68;
  --border: #dccbb4;
  --border-strong: #cdbb9f;
  --input-bg: rgba(255, 255, 255, 0.78);
}
```

Use `--success` for “已入库” and healthy model states. Remove hard-coded light-theme orange/teal values from workspace components.

- [ ] **Step 2: Apply the approved visual hierarchy**

Across workspace components:

- Serif only for brand and empty-state title.
- Persistent panels use borders, not heavy shadows.
- Drawers/popovers/menus may use shadows.
- Workbench radii stay between `12px` and `22px`.
- Primary ingestion action uses warm white in dark mode and dark brown in light mode.
- Knowledge-base selector remains in the sidebar.
- Header remains quiet and does not display a centered knowledge-base control.

- [ ] **Step 3: Run all automated verification**

Run from repository root:

```powershell
python -m pytest tests -q
cd frontend
npm test
npm run lint
npm run build
```

Expected:

- Backend suite passes.
- All Vitest suites pass.
- ESLint reports no errors.
- Next production build succeeds.

- [ ] **Step 4: Start the app for browser QA**

Run from repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 start
```

Verify:

1. Login page remains unchanged.
2. New user with no knowledge base sees create guidance.
3. Desktop side panel defaults open and remembers close/width after reload.
4. At 1023px and below, the knowledge space opens as a left drawer.
5. Knowledge-base switching clears conversation/scope and shows a notice.
6. Build running disables knowledge-base switching and task reselection.
7. Ingestion checkboxes do not alter chat scope.
8. Chat scope supports multiple folders plus videos and resets the conversation.
9. Network request bodies include `folder_ids`/`bvids` only when selected.
10. Model button shows the correct icon and latency.
11. Composer begins compact and grows with multiline content.
12. Dark/light mode keeps identical layout and restores after reload.

- [ ] **Step 5: Stop the app after QA**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 stop
```

- [ ] **Step 6: Review the final diff**

Run:

```powershell
git status --short
git diff --check
git diff --stat
```

Expected:

- No `.superpowers/brainstorm/` files staged.
- No unrelated user changes reverted.
- No whitespace errors.

- [ ] **Step 7: Commit final visual and responsive polish**

```powershell
git add frontend/app/globals.css frontend/app/page.tsx frontend/components/WorkspaceHeader.tsx frontend/components/KnowledgeBasePanel.tsx frontend/components/SourcesPanel.tsx frontend/components/ChatScopePicker.tsx frontend/components/ChatPanel.tsx
git commit -m "style: unify post-login workspace themes"
```

## Final Completion Criteria

The implementation is complete only when:

- Existing unfiltered knowledge-base search/chat behavior remains unchanged.
- Folder/video scope is validated against the current knowledge base and applied to vector retrieval.
- Stream and non-stream chat use identical scope semantics.
- Ingestion selection and chat scope are visibly and technically separate.
- Knowledge-base switching and scope switching start a new conversation.
- Build tasks lock unsafe knowledge-base/task changes.
- Desktop sidebar state/width and theme persist.
- Tablet/mobile use a full-height left drawer.
- Model icon and latency are visible.
- Composer starts near `52px` and grows within approved limits.
- Both Claude-inspired dark and warm-paper light modes pass responsive browser QA.
- Backend tests, frontend tests, lint, and production build all pass.
