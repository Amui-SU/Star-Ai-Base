import pytest


@pytest.mark.asyncio
async def test_protected_knowledge_base_list_requires_login(client):
    response = await client.get("/knowledge-bases")
    assert response.status_code == 401
