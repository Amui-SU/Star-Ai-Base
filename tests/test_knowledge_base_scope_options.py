import pytest

from tests.test_knowledge_base_scoping import (
    create_knowledge_base,
    register_user,
    seed_scope_folder,
)


@pytest.mark.asyncio
async def test_scope_options_only_returns_current_knowledge_base(
    client,
    db_session_factory,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Alice KB")
    other_knowledge_base = await create_knowledge_base(client, "Other KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Current folder",
        videos=[("BV1CURRENT", "Current video")],
    )
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=other_knowledge_base,
        media_id=20,
        title="External folder",
        videos=[("BV2EXTERNAL", "External video")],
    )

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/scope-options"
    )

    assert response.status_code == 200
    assert response.json() == {
        "folders": [
            {
                "media_id": 10,
                "title": "Current folder",
                "video_count": 1,
                "videos": [
                    {"bvid": "BV1CURRENT", "title": "Current video"},
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_scope_options_requires_login(client):
    response = await client.get("/knowledge-bases/1/scope-options")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scope_options_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/scope-options")

    assert response.status_code == 404
