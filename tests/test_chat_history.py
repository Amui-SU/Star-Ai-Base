import pytest


async def _send_code(client, email: str) -> str:
    response = await client.post("/system-auth/send-code", json={"email": email})
    assert response.status_code == 200
    return response.json()["code"]


async def _register_user(client, email: str, display_name: str) -> dict:
    code = await _send_code(client, email)
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    return response.json()


async def _create_knowledge_base(client, name: str, headers: dict) -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_chat_history_requires_login(client):
    response = await client.get("/chat/conversations")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_can_create_list_and_open_chat_conversation(client):
    auth = await _register_user(client, "history-owner@example.com", "History Owner")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    kb = await _create_knowledge_base(client, "History KB", headers)

    created = await client.post(
        "/chat/conversations",
        json={
            "title": "RAG follow-up",
            "workspace_id": auth["workspace"]["id"],
            "knowledge_base_id": kb["id"],
            "scope": {"folder_ids": [10], "bvids": ["BV1ABC"]},
            "web_search": True,
            "web_search_provider": "tavily",
            "messages": [
                {"role": "user", "content": "Explain RAG"},
                {
                    "role": "assistant",
                    "content": "RAG combines retrieval and generation.",
                    "thinking": "Need concise answer",
                    "sources": [
                        {
                            "type": "knowledge",
                            "title": "RAG 入门",
                            "url": "https://www.bilibili.com/video/BV1ABC",
                            "bvid": "BV1ABC",
                        }
                    ],
                    "web_search": {"status": "success", "message": "used web"},
                },
            ],
        },
        headers=headers,
    )

    assert created.status_code == 200
    conversation = created.json()
    assert conversation["title"] == "RAG follow-up"
    assert conversation["user_id"] == auth["user"]["id"]
    assert conversation["knowledge_base_id"] == kb["id"]
    assert conversation["scope"] == {"folder_ids": [10], "bvids": ["BV1ABC"]}
    assert conversation["web_search"] is True
    assert conversation["web_search_provider"] == "tavily"
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][1]["sources"][0]["bvid"] == "BV1ABC"

    listing = await client.get("/chat/conversations", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == conversation["id"]
    assert "messages" not in listing.json()["items"][0]

    opened = await client.get(
        f"/chat/conversations/{conversation['id']}",
        headers=headers,
    )
    assert opened.status_code == 200
    assert opened.json()["messages"][1]["content"] == (
        "RAG combines retrieval and generation."
    )


@pytest.mark.asyncio
async def test_chat_conversations_are_isolated_by_user(client):
    alice = await _register_user(client, "alice-history@example.com", "Alice")
    bob = await _register_user(client, "bob-history@example.com", "Bob")
    client.cookies.clear()
    alice_headers = {"Authorization": f"Bearer {alice['session_token']}"}
    bob_headers = {"Authorization": f"Bearer {bob['session_token']}"}

    created = await client.post(
        "/chat/conversations",
        json={
            "title": "Alice private chat",
            "messages": [{"role": "user", "content": "private"}],
        },
        headers=alice_headers,
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    bob_list = await client.get("/chat/conversations", headers=bob_headers)
    assert bob_list.status_code == 200
    assert bob_list.json()["items"] == []

    bob_open = await client.get(
        f"/chat/conversations/{conversation_id}",
        headers=bob_headers,
    )
    assert bob_open.status_code == 404

    bob_delete = await client.delete(
        f"/chat/conversations/{conversation_id}",
        headers=bob_headers,
    )
    assert bob_delete.status_code == 404


@pytest.mark.asyncio
async def test_chat_conversations_can_be_filtered_by_knowledge_base(client):
    auth = await _register_user(client, "history-filter@example.com", "History Filter")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    first_kb = await _create_knowledge_base(client, "First KB", headers)
    second_kb = await _create_knowledge_base(client, "Second KB", headers)

    for title, kb_id in [("first", first_kb["id"]), ("second", second_kb["id"])]:
        response = await client.post(
            "/chat/conversations",
            json={
                "title": title,
                "knowledge_base_id": kb_id,
                "messages": [{"role": "user", "content": title}],
            },
            headers=headers,
        )
        assert response.status_code == 200

    filtered = await client.get(
        f"/chat/conversations?knowledge_base_id={first_kb['id']}",
        headers=headers,
    )

    assert filtered.status_code == 200
    assert [item["title"] for item in filtered.json()["items"]] == ["first"]


@pytest.mark.asyncio
async def test_user_can_update_and_delete_own_chat_conversation(client):
    auth = await _register_user(client, "history-update@example.com", "History Update")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    created = await client.post(
        "/chat/conversations",
        json={
            "title": "Draft",
            "messages": [{"role": "user", "content": "old"}],
        },
        headers=headers,
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    updated = await client.put(
        f"/chat/conversations/{conversation_id}",
        json={
            "title": "Updated",
            "scope": {"folder_ids": [], "bvids": ["BVNEW"]},
            "messages": [
                {"role": "user", "content": "new question"},
                {"role": "assistant", "content": "new answer"},
            ],
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert updated.json()["scope"] == {"folder_ids": [], "bvids": ["BVNEW"]}
    assert [m["content"] for m in updated.json()["messages"]] == [
        "new question",
        "new answer",
    ]

    deleted = await client.delete(
        f"/chat/conversations/{conversation_id}",
        headers=headers,
    )
    assert deleted.status_code == 204

    opened = await client.get(
        f"/chat/conversations/{conversation_id}",
        headers=headers,
    )
    assert opened.status_code == 404
