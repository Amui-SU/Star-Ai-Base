async def register_user(client, email: str, *, display_name: str = "Alice"):
    code_resp = await client.post("/system-auth/send-code", json={"email": email})
    assert code_resp.status_code == 200
    code = code_resp.json()["code"]

    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    return response.json()


async def create_knowledge_base(client, name: str, *, description: str | None = None):
    payload = {"name": name}
    if description is not None:
        payload["description"] = description

    response = await client.post("/knowledge-bases", json=payload)
    assert response.status_code == 200
    return response.json()
