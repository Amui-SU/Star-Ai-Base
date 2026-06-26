import pytest
from sqlalchemy import select

from app.models import OAuthPendingState


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


@pytest.mark.asyncio
async def test_bilibili_qrcode_poll_survives_empty_memory_cache(client, monkeypatch):
    await _register_user(client, "binding-pending@example.com")

    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()

    class FakeBilibiliService:
        async def generate_qrcode(self):
            return {
                "qrcode_key": "persistent-binding-qrcode",
                "qrcode_url": "https://passport.bilibili.com/qrcode",
                "qrcode_image_base64": "base64-image",
            }

        async def poll_qrcode_status(self, qrcode_key):
            assert qrcode_key == "persistent-binding-qrcode"
            return {"status": "waiting", "message": "等待扫码"}

        async def close(self):
            pass

    monkeypatch.setattr(
        "app.routers.source_bindings.BilibiliService",
        FakeBilibiliService,
    )

    response = await client.get("/source-bindings/bilibili/qrcode")
    assert response.status_code == 200

    auth_router.login_sessions.clear()

    poll_response = await client.get(
        "/source-bindings/bilibili/qrcode/poll/persistent-binding-qrcode"
    )

    assert poll_response.status_code == 200
    assert poll_response.json()["status"] == "waiting"


@pytest.mark.asyncio
async def test_bilibili_qrcode_confirm_clears_persisted_pending_state(
    client, db_session_factory, monkeypatch
):
    await _register_user(client, "binding-confirm@example.com")

    class FakeBilibiliService:
        def __init__(self, *args, **kwargs):
            self.dedeuserid = kwargs.get("dedeuserid")

        async def generate_qrcode(self):
            return {
                "qrcode_key": "confirm-binding-qrcode",
                "qrcode_url": "https://passport.bilibili.com/qrcode",
                "qrcode_image_base64": "base64-image",
            }

        async def poll_qrcode_status(self, qrcode_key):
            assert qrcode_key == "confirm-binding-qrcode"
            return {
                "status": "confirmed",
                "message": "登录成功",
                "cookies": {
                    "SESSDATA": "sess",
                    "bili_jct": "csrf",
                    "DedeUserID": "4242",
                },
            }

        async def get_user_info(self):
            return {
                "mid": int(self.dedeuserid),
                "uname": "Binding User",
                "face": "https://example.com/avatar.png",
            }

        async def close(self):
            pass

    monkeypatch.setattr(
        "app.routers.source_bindings.BilibiliService",
        FakeBilibiliService,
    )

    response = await client.get("/source-bindings/bilibili/qrcode")
    assert response.status_code == 200

    poll_response = await client.get(
        "/source-bindings/bilibili/qrcode/poll/confirm-binding-qrcode"
    )

    assert poll_response.status_code == 200
    assert poll_response.json()["status"] == "confirmed"
    async with db_session_factory() as session:
        pending = (
            await session.execute(
                select(OAuthPendingState).where(
                    OAuthPendingState.state_key == "confirm-binding-qrcode"
                )
            )
        ).scalar_one_or_none()

    assert pending is None
