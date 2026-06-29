from app.routers.system_auth import OAUTH_STATE_COOKIE_NAME


def set_oauth_nonce_cookie(client, nonce: str) -> None:
    client.cookies.set(
        OAUTH_STATE_COOKIE_NAME,
        nonce,
        domain="testserver.local",
        path="/system-auth",
    )


def has_oauth_nonce_clear_cookie(response) -> bool:
    return any(
        cookie.startswith(f"{OAUTH_STATE_COOKIE_NAME}=") and "Max-Age=0" in cookie
        for cookie in response.headers.get_list("set-cookie")
    )


async def send_code(client, email: str) -> str | None:
    """Send a debug verification code for the auth flow."""
    resp = await client.post("/system-auth/send-code", json={"email": email})
    if resp.status_code != 200:
        return None
    return resp.json().get("code")


async def register_user(
    client,
    email: str,
    *,
    password: str = "correct horse battery staple",
    display_name: str = "Test User",
) -> dict:
    code = await send_code(client, email)
    assert code is not None
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    return response.json()
