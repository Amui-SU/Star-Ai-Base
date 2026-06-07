import pytest


@pytest.mark.asyncio
async def test_source_bindings_require_login(client):
    response = await client.get("/source-bindings")
    assert response.status_code == 401
