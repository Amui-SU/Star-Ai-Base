from types import SimpleNamespace

from app.models import SourceBinding, SourceCredential


async def create_binding_and_credential(
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


async def register_user(client, email: str):
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


def auth_objects(auth):
    return (
        SimpleNamespace(id=auth["user"]["id"]),
        SimpleNamespace(id=auth["workspace"]["id"]),
    )
