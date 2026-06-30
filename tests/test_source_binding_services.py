import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import SourceBinding, SourceCredential
from app.services.source_binding_services import get_bilibili_service_for_binding


async def _create_binding_and_credential(
    db_session_factory,
    auth,
    *,
    status: str = "active",
    encrypted_payload: str | None = "encrypted",
):
    async with db_session_factory() as session:
        binding = SourceBinding(
            user_id=auth["user"]["id"],
            workspace_id=auth["workspace"]["id"],
            source_type="bilibili",
            external_account_id="4242",
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
