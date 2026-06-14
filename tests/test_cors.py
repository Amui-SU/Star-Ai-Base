import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_mobile_webview_origin_can_preflight_delete():
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.options(
            "/knowledge-bases/1",
            headers={
                "Origin": "capacitor://localhost",
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "capacitor://localhost"
