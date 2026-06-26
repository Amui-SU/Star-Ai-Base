# Chat History Persistence Design

## Goal

Add durable chat history that survives refreshes and app restarts while keeping different users' histories isolated.

## Scope

- Hard access boundary: `user_id`. A user can only list, open, update, or delete their own conversations.
- Management metadata: `workspace_id`, `knowledge_base_id`, `folder_ids`, `bvids`, `web_search`, and `web_search_provider`.
- First UI slice: recent conversations, new conversation, open a conversation, continue chatting.
- Out of scope for this slice: full-text history search, automatic summaries, review cards, shared/team conversation history.

## Backend Shape

Create two SQLite-backed models:

- `ChatConversation`: owner user, optional workspace and knowledge base metadata, title, scope snapshot, web search snapshot, timestamps.
- `ChatMessage`: conversation owner, role, content, thinking, sources, web search status, sequence index, timestamps.

Expose an independent `/chat/conversations` router instead of nesting under `/knowledge-bases/{id}`. Knowledge bases remain a filter and restore context, not the primary security boundary.

## Frontend Shape

Add API methods under `chatHistoryApi`. `ChatPanel` keeps the current streaming behavior, then saves the completed message snapshot. Loading a conversation replaces in-memory messages and restores saved scope and web search options when available.

## Testing

- Backend tests first for login requirement, user isolation, create/list/detail/update/delete, and knowledge-base filtering.
- Frontend tests for loading recent conversations, opening history, creating a new conversation, and saving after a completed answer.
