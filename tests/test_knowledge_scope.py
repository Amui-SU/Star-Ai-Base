import pytest


@pytest.mark.asyncio
async def test_protected_knowledge_base_list_requires_login(client):
    response = await client.get("/knowledge-bases")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_can_create_and_list_own_knowledge_base(client):
    await client.post(
        "/system-auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery staple",
            "display_name": "Alice",
        },
    )

    create_response = await client.post(
        "/knowledge-bases",
        json={"name": "B 站学习库", "description": "课程和访谈"},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "B 站学习库"
    assert created["description"] == "课程和访谈"

    list_response = await client.get("/knowledge-bases")
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()] == ["B 站学习库"]
