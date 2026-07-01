import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import OAuthPendingState, SourceBinding, SourceCredential
from app.services.source_binding_services import generate_bilibili_binding_qrcode
from app.services.source_binding_services import poll_bilibili_binding_qrcode
from tests.source_binding_services.helpers import auth_objects
from tests.source_binding_services.helpers import register_user


class FakeQrService:
    closed_count = 0

    async def generate_qrcode(self):
        return {
            "qrcode_key": "service-qrcode",
            "qrcode_url": "https://passport.example/qrcode",
            "qrcode_image_base64": "base64",
        }

    async def close(self):
        type(self).closed_count += 1


class BrokenQrService:
    closed = False

    async def generate_qrcode(self):
        raise RuntimeError("upstream down")

    async def close(self):
        type(self).closed = True


@pytest.mark.asyncio
async def test_generate_bilibili_binding_qrcode_records_pending_state(
    client, db_session_factory
):
    auth = await register_user(client, "qr-generate-service@example.com")
    current_user, _ = auth_objects(auth)
    sessions = {}
    pending_calls = []
    FakeQrService.closed_count = 0

    async def create_pending_state(*args, **kwargs):
        pending_calls.append((args, kwargs))

    async with db_session_factory() as session:
        response = await generate_bilibili_binding_qrcode(
            current_user,
            session,
            service_class=FakeQrService,
            set_session=lambda key, payload, ttl: sessions.update(
                {key: {"payload": payload, "ttl": ttl}}
            ),
            create_pending_state=create_pending_state,
            qrcode_session_ttl=120,
        )

    assert response.qrcode_key == "service-qrcode"
    assert sessions["service-qrcode"]["payload"]["purpose"] == "source_binding"
    assert sessions["service-qrcode"]["ttl"] == 120
    assert pending_calls[0][1]["state_key"] == "service-qrcode"
    assert FakeQrService.closed_count == 1


@pytest.mark.asyncio
async def test_generate_bilibili_binding_qrcode_closes_service_on_failure(
    client, db_session_factory
):
    auth = await register_user(client, "qr-generate-fail-service@example.com")
    current_user, _ = auth_objects(auth)
    BrokenQrService.closed = False

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await generate_bilibili_binding_qrcode(
                current_user,
                session,
                service_class=BrokenQrService,
                set_session=lambda *_args: None,
                create_pending_state=lambda *_args, **_kwargs: None,
                qrcode_session_ttl=120,
            )

    assert exc_info.value.status_code == 502
    assert BrokenQrService.closed is True


@pytest.mark.asyncio
async def test_poll_bilibili_binding_qrcode_confirms_and_clears_pending(
    client, db_session_factory
):
    auth = await register_user(client, "qr-poll-confirm-service@example.com")
    current_user, current_workspace = auth_objects(auth)
    login_sessions = {"confirm-qrcode": {"purpose": "source_binding"}}
    deleted = []

    class PollService:
        def __init__(self, *args, **kwargs):
            self.dedeuserid = kwargs.get("dedeuserid")

        async def poll_qrcode_status(self, qrcode_key):
            assert qrcode_key == "confirm-qrcode"
            return {
                "status": "confirmed",
                "message": "ok",
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

    async def delete_pending_state(_db, qrcode_key):
        deleted.append(qrcode_key)

    async with db_session_factory() as session:
        response = await poll_bilibili_binding_qrcode(
            "confirm-qrcode",
            current_user,
            current_workspace,
            session,
            service_class=PollService,
            service_from_cookies=lambda cookies, service_class: service_class(
                dedeuserid=cookies["DedeUserID"]
            ),
            get_session=lambda _key: {
                "purpose": "source_binding",
                "user_id": current_user.id,
            },
            login_sessions=login_sessions,
            get_pending_state=lambda *_args, **_kwargs: None,
            delete_pending_state=delete_pending_state,
            encrypt_payload=lambda payload: payload,
        )

    assert response.status == "confirmed"
    assert response.user_info["mid"] == 4242
    assert response.session_id is not None
    assert "confirm-qrcode" not in login_sessions
    assert deleted == ["confirm-qrcode"]

    async with db_session_factory() as session:
        binding = (
            await session.execute(
                select(SourceBinding).where(
                    SourceBinding.id == int(response.session_id)
                )
            )
        ).scalar_one()
        credential = (
            await session.execute(
                select(SourceCredential).where(
                    SourceCredential.source_binding_id == binding.id
                )
            )
        ).scalar_one()

    assert binding.external_account_id == "4242"
    assert json.loads(credential.encrypted_payload)["SESSDATA"] == "sess"


@pytest.mark.asyncio
async def test_poll_bilibili_binding_qrcode_uses_persisted_pending_state(
    client, db_session_factory
):
    auth = await register_user(client, "qr-poll-wait-service@example.com")
    current_user, current_workspace = auth_objects(auth)

    class WaitingService:
        async def poll_qrcode_status(self, qrcode_key):
            assert qrcode_key == "waiting-qrcode"
            return {"status": "waiting", "message": "等待扫码"}

        async def close(self):
            pass

    async def get_pending_state(_db, **kwargs):
        return OAuthPendingState(
            state_key=kwargs["state_key"],
            purpose=kwargs["purpose"],
            user_id=kwargs["user_id"],
        )

    async with db_session_factory() as session:
        response = await poll_bilibili_binding_qrcode(
            "waiting-qrcode",
            current_user,
            current_workspace,
            session,
            service_class=WaitingService,
            service_from_cookies=lambda *_args: None,
            get_session=lambda _key: None,
            login_sessions={},
            get_pending_state=get_pending_state,
            delete_pending_state=lambda *_args: None,
        )

    assert response.status == "waiting"
    assert response.message == "等待扫码"
