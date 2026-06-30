import pytest
from sqlalchemy import select

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    KnowledgeBase,
    OAuthPendingState,
    SourceBinding,
    VideoTitleOverride,
)


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


async def _create_bound_video(
    db_session_factory,
    auth,
    *,
    bvid: str,
    existing_title: str | None = None,
):
    async with db_session_factory() as session:
        binding = SourceBinding(
            user_id=auth["user"]["id"],
            workspace_id=auth["workspace"]["id"],
            source_type="bilibili",
            external_account_id="4242",
            status="active",
        )
        knowledge_base = KnowledgeBase(
            workspace_id=auth["workspace"]["id"],
            name=f"{bvid} KB",
            created_by=auth["user"]["id"],
        )
        session.add_all([binding, knowledge_base])
        await session.flush()

        folder = FavoriteFolder(
            session_id=f"{bvid.lower()}-folder",
            workspace_id=auth["workspace"]["id"],
            knowledge_base_id=knowledge_base.id,
            source_binding_id=binding.id,
            media_id=8800 + binding.id,
            title=f"{bvid} folder",
        )
        session.add(folder)
        await session.flush()
        session.add(
            FavoriteVideo(
                folder_id=folder.id,
                bvid=bvid,
                workspace_id=auth["workspace"]["id"],
                knowledge_base_id=knowledge_base.id,
                source_binding_id=binding.id,
            )
        )
        if existing_title is not None:
            session.add(
                VideoTitleOverride(
                    workspace_id=auth["workspace"]["id"],
                    knowledge_base_id=knowledge_base.id,
                    source_binding_id=binding.id,
                    bvid=bvid,
                    custom_title=existing_title,
                    created_by=auth["user"]["id"],
                )
            )
        await session.commit()
        return binding.id, knowledge_base.id


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


@pytest.mark.asyncio
async def test_update_video_title_by_binding_writes_override(
    client, db_session_factory
):
    auth = await _register_user(client, "title-update@example.com")
    binding_id, knowledge_base_id = await _create_bound_video(
        db_session_factory, auth, bvid="BVTITLE1"
    )

    response = await client.put(
        f"/source-bindings/{binding_id}/videos/title",
        json={
            "bvid": "BVTITLE1",
            "title": "A better local title",
            "knowledge_base_id": knowledge_base_id,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "bvid": "BVTITLE1",
        "custom_title": "A better local title",
    }

    async with db_session_factory() as session:
        override = (
            await session.execute(
                select(VideoTitleOverride).where(
                    VideoTitleOverride.knowledge_base_id == knowledge_base_id
                )
            )
        ).scalar_one()

    assert override.bvid == "BVTITLE1"
    assert override.custom_title == "A better local title"


@pytest.mark.asyncio
async def test_update_video_title_by_binding_clears_override(
    client, db_session_factory
):
    auth = await _register_user(client, "title-clear@example.com")
    binding_id, knowledge_base_id = await _create_bound_video(
        db_session_factory,
        auth,
        bvid="BVTITLE2",
        existing_title="Existing custom title",
    )

    response = await client.put(
        f"/source-bindings/{binding_id}/videos/title",
        json={
            "bvid": "BVTITLE2",
            "title": "",
            "knowledge_base_id": knowledge_base_id,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "bvid": "BVTITLE2",
        "custom_title": None,
    }

    async with db_session_factory() as session:
        overrides = (
            (
                await session.execute(
                    select(VideoTitleOverride).where(
                        VideoTitleOverride.knowledge_base_id == knowledge_base_id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert overrides == []
