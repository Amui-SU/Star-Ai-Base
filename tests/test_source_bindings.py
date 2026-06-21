import pytest


async def _register_user(client, email: str = "alice@example.com"):
    code_resp = await client.post("/system-auth/send-code", json={"email": email})
    assert code_resp.status_code == 200
    code = code_resp.json()["code"]

    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Alice",
            "code": code,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_source_bindings_require_login(client):
    response = await client.get("/source-bindings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_new_user_has_empty_source_binding_list(client):
    await _register_user(client)

    response = await client.get("/source-bindings")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_bilibili_qrcode_requires_system_login(client):
    response = await client.get("/source-bindings/bilibili/qrcode")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bilibili_qrcode_upstream_error_returns_readable_502(client, monkeypatch):
    await _register_user(client, "qrcode@example.com")

    class BrokenBilibiliService:
        async def generate_qrcode(self):
            raise Exception("连接 B站二维码接口超时或网络异常，请稍后重试")

        async def close(self):
            pass

    monkeypatch.setattr(
        "app.routers.source_bindings.BilibiliService",
        BrokenBilibiliService,
    )

    response = await client.get("/source-bindings/bilibili/qrcode")

    assert response.status_code == 502
    assert response.json()["detail"] == "连接 B站二维码接口超时或网络异常，请稍后重试"
