import pytest
from fastapi import HTTPException

from app.models import SourceBinding
from app.services.source_binding_services import (
    ensure_active_source_binding,
    list_source_bindings,
    revoke_source_binding,
)
from tests.source_binding_services.helpers import auth_objects
from tests.source_binding_services.helpers import create_binding_and_credential
from tests.source_binding_services.helpers import register_user


@pytest.mark.asyncio
async def test_list_source_bindings_returns_current_workspace_bindings_desc(
    client, db_session_factory
):
    auth = await register_user(client, "binding-list-service@example.com")
    current_user, current_workspace = auth_objects(auth)
    first_binding_id = await create_binding_and_credential(
        db_session_factory,
        auth,
        external_account_id="1111",
    )
    second_binding_id = await create_binding_and_credential(
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
    auth = await register_user(client, "binding-revoke-service@example.com")
    current_user, current_workspace = auth_objects(auth)
    binding_id = await create_binding_and_credential(db_session_factory, auth)

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
    auth = await register_user(client, "binding-revoke-missing-service@example.com")
    current_user, current_workspace = auth_objects(auth)

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
    auth = await register_user(client, "binding-active-service@example.com")
    current_user, current_workspace = auth_objects(auth)
    binding_id = await create_binding_and_credential(db_session_factory, auth)

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
    auth = await register_user(client, "binding-revoked-service@example.com")
    current_user, current_workspace = auth_objects(auth)
    binding_id = await create_binding_and_credential(
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
