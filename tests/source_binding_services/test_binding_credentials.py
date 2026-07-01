import json

import pytest
from fastapi import HTTPException

from app.services.source_binding_services import get_bilibili_service_for_binding
from tests.source_binding_services.helpers import auth_objects
from tests.source_binding_services.helpers import create_binding_and_credential
from tests.source_binding_services.helpers import register_user


@pytest.mark.asyncio
async def test_get_bilibili_service_for_binding_builds_service_from_credentials(
    client, db_session_factory
):
    auth = await register_user(client, "binding-service@example.com")
    binding_id = await create_binding_and_credential(db_session_factory, auth)
    captured = {}
    fake_service = object()
    current_user, current_workspace = auth_objects(auth)

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
    auth = await register_user(client, "missing-binding-service@example.com")
    current_user, current_workspace = auth_objects(auth)

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
    auth = await register_user(client, "missing-credential-service@example.com")
    binding_id = await create_binding_and_credential(
        db_session_factory,
        auth,
        encrypted_payload=None,
    )
    current_user, current_workspace = auth_objects(auth)

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
    auth = await register_user(client, "broken-credential-service@example.com")
    binding_id = await create_binding_and_credential(db_session_factory, auth)
    current_user, current_workspace = auth_objects(auth)

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
