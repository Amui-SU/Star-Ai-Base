import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from sqlalchemy import select

from app.models import OAuthPendingState, SourceBinding, SourceCredential
from app.services.source_binding_services import (
    ensure_active_source_binding,
    generate_bilibili_binding_qrcode,
    get_bilibili_service_for_binding,
    list_source_bindings,
    poll_bilibili_binding_qrcode,
    revoke_source_binding,
)


async def _create_binding_and_credential(
    db_session_factory,
    auth,
    *,
    status: str = "active",
    encrypted_payload: str | None = "encrypted",
    external_account_id: str = "4242",
):
    async with db_session_factory() as session:
        binding = SourceBinding(
            user_id=auth["user"]["id"],
            workspace_id=auth["workspace"]["id"],
            source_type="bilibili",
            external_account_id=external_account_id,
            status=status,
        )
        session.add(binding)
        await session.flush()
        if encrypted_payload is not None:
            session.add(
                SourceCredential(
                    user_id=auth["user"]["id"],
                    source_binding_id=binding.id,
                    encrypted_payload=encrypted_payload,
                )
            )
        await session.commit()
        return binding.id


async def _register_user(client, email: str):
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


def _auth_objects(auth):
    return (
        SimpleNamespace(id=auth["user"]["id"]),
        SimpleNamespace(id=auth["workspace"]["id"]),
    )


@pytest.mark.asyncio
async def test_list_source_bindings_returns_current_workspace_bindings_desc(
    client, db_session_factory
):
    auth = await _register_user(client, "binding-list-service@example.com")
    current_user, current_workspace = _auth_objects(auth)
    first_binding_id = await _create_binding_and_credential(
        db_session_factory,
        auth,
        external_account_id="1111",
    )
    second_binding_id = await _create_binding_and_credential(
        db_session_factory,
        auth,
        external_account_id="2222",
    )

    async with db_session_factory() as session:
        bindings = await list_source_bindings(current_user, current_workspace, session)

    assert [binding.id for binding in bindings] == [second_binding_id, first_binding_id]
    assert [binding.external_account_id for binding in bindings] == ["2222", "1111"]


@pytest.mark.asyncio
async def test_revoke_source_binding_marks_owned_workspace_binding_revoked(
    client, db_session_factory
):
    auth = await _register_user(client, "binding-revoke-service@example.com")
    current_user, current_workspace = _auth_objects(auth)
    binding_id = await _create_binding_and_credential(db_session_factory, auth)

    async with db_session_factory() as session:
        result = await revoke_source_binding(
            binding_id,
            current_user,
            current_workspace,
            session,
        )

    assert result == {"ok": True}
    async with db_session_factory() as session:
        binding = await session.get(SourceBinding, binding_id)
    assert binding.status == "revoked"


@pytest.mark.asyncio
async def test_revoke_source_binding_rejects_missing_or_foreign_binding(
    client, db_session_factory
):
    auth = await _register_user(client, "binding-revoke-missing-service@example.com")
    current_user, current_workspace = _auth_objects(auth)

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await revoke_source_binding(
                99999,
                current_user,
                current_workspace,
                session,
            )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_ensure_active_source_binding_returns_owned_active_binding(
    client, db_session_factory
):
    auth = await _register_user(client, "binding-active-service@example.com")
    current_user, current_workspace = _auth_objects(auth)
    binding_id = await _create_binding_and_credential(db_session_factory, auth)

    async with db_session_factory() as session:
        binding = await ensure_active_source_binding(
            binding_id,
            current_user,
            current_workspace,
            session,
        )

    assert binding.id == binding_id
    assert binding.status == "active"


@pytest.mark.asyncio
async def test_ensure_active_source_binding_rejects_revoked_binding(
    client, db_session_factory
):
    auth = await _register_user(client, "binding-revoked-service@example.com")
    current_user, current_workspace = _auth_objects(auth)
    binding_id = await _create_binding_and_credential(
        db_session_factory,
        auth,
        status="revoked",
    )

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await ensure_active_source_binding(
                binding_id,
                current_user,
                current_workspace,
                session,
            )

    assert exc_info.value.status_code == 404


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
async def test_get_bilibili_service_for_binding_builds_service_from_credentials(
    client, db_session_factory
):
    auth = await _register_user(client, "binding-service@example.com")
    binding_id = await _create_binding_and_credential(db_session_factory, auth)
    captured = {}
    fake_service = object()
    current_user, current_workspace = _auth_objects(auth)

    async with db_session_factory() as session:
        service = await get_bilibili_service_for_binding(
            binding_id,
            current_user,
            current_workspace,
            session,
            service_class=object,
            service_from_cookies=lambda payload, service_class: captured.update(
                {"payload": payload, "service_class": service_class}
            )
            or fake_service,
            decrypt_payload=lambda encrypted: json.dumps(
                {"SESSDATA": encrypted, "DedeUserID": "4242"}
            ),
        )

    assert service is fake_service
    assert captured == {
        "payload": {"SESSDATA": "encrypted", "DedeUserID": "4242"},
        "service_class": object,
    }


@pytest.mark.asyncio
async def test_get_bilibili_service_for_binding_rejects_missing_binding(
    client, db_session_factory
):
    auth = await _register_user(client, "missing-binding-service@example.com")
    current_user, current_workspace = _auth_objects(auth)

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_bilibili_service_for_binding(
                99999,
                current_user,
                current_workspace,
                session,
            )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_bilibili_service_for_binding_rejects_missing_credentials(
    client, db_session_factory
):
    auth = await _register_user(client, "missing-credential-service@example.com")
    binding_id = await _create_binding_and_credential(
        db_session_factory,
        auth,
        encrypted_payload=None,
    )
    current_user, current_workspace = _auth_objects(auth)

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_bilibili_service_for_binding(
                binding_id,
                current_user,
                current_workspace,
                session,
            )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_bilibili_service_for_binding_wraps_decrypt_errors(
    client, db_session_factory
):
    auth = await _register_user(client, "broken-credential-service@example.com")
    binding_id = await _create_binding_and_credential(db_session_factory, auth)
    current_user, current_workspace = _auth_objects(auth)

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_bilibili_service_for_binding(
                binding_id,
                current_user,
                current_workspace,
                session,
                decrypt_payload=lambda _encrypted: (_ for _ in ()).throw(
                    RuntimeError("broken")
                ),
            )

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_generate_bilibili_binding_qrcode_records_pending_state(
    client, db_session_factory
):
    auth = await _register_user(client, "qr-generate-service@example.com")
    current_user, _ = _auth_objects(auth)
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
    auth = await _register_user(client, "qr-generate-fail-service@example.com")
    current_user, _ = _auth_objects(auth)
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
    auth = await _register_user(client, "qr-poll-confirm-service@example.com")
    current_user, current_workspace = _auth_objects(auth)
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
    auth = await _register_user(client, "qr-poll-wait-service@example.com")
    current_user, current_workspace = _auth_objects(auth)

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
