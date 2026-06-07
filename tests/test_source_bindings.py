import pytest


@pytest.mark.asyncio
async def test_source_bindings_require_login(client):
    response = await client.get("/source-bindings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_new_user_has_empty_source_binding_list(client):
    await client.post(
        "/system-auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery staple",
            "display_name": "Alice",
        },
    )

    response = await client.get("/source-bindings")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_bilibili_qrcode_requires_system_login(client):
    response = await client.get("/source-bindings/bilibili/qrcode")
    assert response.status_code == 401
