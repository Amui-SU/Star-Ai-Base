# Knowledge Base Scoping Design

## Goal

Move new RAG-facing functionality from legacy `session_id` entry points to explicit knowledge-base scoped APIs. Every new chat, search, stats, and build request must be authorized through the current system user, current workspace, and target knowledge base.

This stage does not remove legacy Bilibili session APIs. It creates the safe multi-user path and leaves old endpoints as compatibility-only surfaces.

## Scope

Included:

- Add scoped endpoints under `/knowledge-bases/{knowledge_base_id}/...`.
- Add a reusable dependency for knowledge-base ownership checks.
- Ensure scoped search and chat use `workspace_id` and `knowledge_base_id` RAG filters.
- Ensure scoped build writes `workspace_id`, `knowledge_base_id`, and `source_binding_id` metadata for new vectors.
- Extend frontend API client methods for scoped knowledge-base operations.
- Add tests for authentication, ownership, RAG filters, and scoped build metadata.

Excluded:

- Removing old `/chat/*`, `/knowledge/*`, and `/favorites/*` endpoints.
- Full frontend workflow redesign.
- Automatic migration of old SQLite or Chroma data.
- Team workspaces, invitations, or role management.

## API Design

New endpoints:

- `GET /knowledge-bases/{knowledge_base_id}/stats`
- `POST /knowledge-bases/{knowledge_base_id}/search`
- `POST /knowledge-bases/{knowledge_base_id}/chat`
- `POST /knowledge-bases/{knowledge_base_id}/chat/stream`
- `POST /knowledge-bases/{knowledge_base_id}/build`

Each endpoint depends on:

- `get_current_user`
- `get_current_workspace`
- `get_knowledge_base_for_user`

Ownership failures return `404` so callers cannot infer whether another user's knowledge base exists. Missing or invalid system sessions return `401`.

## Backend Components

### Dependencies

Add `get_knowledge_base_for_user(knowledge_base_id, current_workspace, db)` in `app/dependencies.py`.

It loads `KnowledgeBase` by ID and requires:

- `KnowledgeBase.id == knowledge_base_id`
- `KnowledgeBase.workspace_id == current_workspace.id`

It returns the verified `KnowledgeBase`.

### Knowledge Base Router

Extend `app/routers/knowledge_bases.py` with scoped stats and build endpoints where practical. This keeps the new multi-user surface grouped under the knowledge-base resource.

Stats should use scoped database/vector counts where available. If Chroma scoped count support is limited, the first implementation may return collection-level stats plus an explicit `scoped: true` marker only after verifying the knowledge base. It must not expose another workspace's data.

### Chat Router

Add scoped chat and search endpoints. They may reuse existing prompt and response shaping from `app/routers/chat.py`, but the retrieval step must call `RAGService.search_in_knowledge_base(query, workspace_id, knowledge_base_id, k)`.

The legacy `/chat/ask`, `/chat/ask/stream`, and `/chat/search` remain in place for compatibility and are not expanded.

### Build Flow

Scoped build accepts a target `knowledge_base_id` from the path and a `source_binding_id` in the request body. The source binding must belong to the current user and workspace before credentials are used.

New vector writes call:

```python
rag.add_video_content(
    video,
    workspace_id=current_workspace.id,
    knowledge_base_id=knowledge_base.id,
    source_binding_id=source_binding.id,
)
```

The existing build task model can remain in-memory for this stage, but task records should include `workspace_id` and `knowledge_base_id` to avoid accidental cross-user lookup in future work.

## Data Flow

```text
HttpOnly system_session cookie
  -> get_current_user
  -> get_current_workspace
  -> get_knowledge_base_for_user
  -> source binding ownership check when needed
  -> scoped RAG search or scoped RAG write
```

No new endpoint should accept `session_id` as the identity source.

## Frontend API Client

Extend `frontend/lib/api.ts` with:

- `knowledgeBaseApi.stats(knowledgeBaseId)`
- `knowledgeBaseApi.search(knowledgeBaseId, data)`
- `knowledgeBaseApi.chat(knowledgeBaseId, data)`
- `knowledgeBaseApi.chatStreamUrl(knowledgeBaseId)` or equivalent stream helper
- `knowledgeBaseApi.build(knowledgeBaseId, data)`

This stage only extends the client shape. UI migration can be done in a later focused pass.

## Error Handling

- `401`: missing, expired, or revoked system session.
- `404`: knowledge base or source binding is not accessible to the current user.
- `400`: empty question, empty search query, or invalid build payload.
- `502`: upstream Bilibili account data is incomplete or unusable.
- `500`: unexpected server-side failure.

Errors should avoid leaking cross-user resource existence.

## Tests

Add or extend tests for:

- Unauthenticated scoped endpoints return `401`.
- A user cannot access another user's knowledge base.
- Scoped search passes `workspace_id` and `knowledge_base_id` filters to RAG.
- Scoped chat uses scoped retrieval.
- Scoped build writes vectors with `workspace_id`, `knowledge_base_id`, and `source_binding_id`.
- Legacy endpoints remain importable and are not removed.

## Rollout

1. Implement scoped backend dependencies and endpoints.
2. Add focused backend tests.
3. Extend frontend API client.
4. Keep old endpoints documented as compatibility-only.
5. Defer UI migration and old-data migration to later phases.

## Open Risks

- Old Chroma vectors without scope metadata remain unsafe for multi-user retrieval.
- Current in-memory build tasks are acceptable locally but should move to a persisted queue before real multi-user deployment.
- SQLite remains acceptable for local development but should move to Postgres before external users rely on the system.
