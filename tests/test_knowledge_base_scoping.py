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
