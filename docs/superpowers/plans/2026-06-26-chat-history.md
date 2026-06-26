# Chat History Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist chat conversations per user and allow reopening recent conversations from the chat UI.

**Architecture:** Store conversations and messages in SQLite through SQLAlchemy models, expose independent `/chat/conversations` endpoints, and let the frontend save completed message snapshots after streaming. User ownership is the hard security boundary; knowledge base and scope metadata are filters and restore hints.

**Tech Stack:** FastAPI, SQLAlchemy async, SQLite, Pydantic, Next.js/React, Vitest, Pytest.

---

### Task 1: Backend Conversation API

**Files:**

- Modify: `app/models.py`
- Modify: `app/database.py`
- Create: `app/routers/chat_history.py`
- Modify: `app/main.py`
- Test: `tests/test_chat_history.py`

- [x] Write failing API tests for login requirement and user isolation.
- [x] Add `ChatConversation` and `ChatMessage` models plus Pydantic request/response models.
- [x] Add SQLite legacy column/table handling for local databases.
- [x] Implement `/chat/conversations` list/create/detail/update/delete endpoints.
- [x] Register the router in `app/main.py`.
- [x] Run `python -m pytest tests/test_chat_history.py -q`.

### Task 2: Frontend API and Chat State Persistence

**Files:**

- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/chat/types.ts`
- Modify: `frontend/components/chat/useChatStreaming.ts`
- Modify: `frontend/components/ChatPanel.tsx`
- Test: `frontend/components/ChatPanel.test.tsx`

- [x] Write failing frontend tests for recent conversation loading and opening a saved conversation.
- [x] Add `chatHistoryApi` types and methods.
- [x] Expose completed-message callback from `useChatStreaming`.
- [x] Add current conversation state in `ChatPanel`.
- [x] Save completed message snapshots after an answer finishes.
- [x] Restore messages, scope, and web search options when a conversation opens.
- [x] Run `cd frontend; npm test -- ChatPanel.test.tsx`.

### Task 3: Verification and Docs

**Files:**

- Modify: `docs/大版本完善执行方案.md`

- [x] Run backend chat history tests.
- [x] Run full backend tests if backend changes are stable.
- [x] Run frontend targeted tests.
- [x] Run `cd frontend; npm test`.
- [x] Run `cd frontend; npm run lint`.
- [x] Run `cd frontend; npm run build`.
- [x] Record commands and results in the execution plan.

**Execution Notes:**

- TDD red confirmed: `cd frontend; npm test -- ChatPanel.test.tsx` failed with 3 new history tests before implementation.
- Backend verification: `python -m pytest tests/test_chat_history.py -q` passed with 5 tests.
- Frontend targeted verification: `cd frontend; npm test -- ChatPanel.test.tsx` passed with 27 tests.
- Full frontend verification: `cd frontend; npm test` passed with 23 files / 133 tests.
- Frontend quality gates: `cd frontend; npm run lint` and `cd frontend; npm run build` passed.
- Full backend verification: `python -m pytest -q` passed with 220 tests.
