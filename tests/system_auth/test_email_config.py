import pytest
from app.config import settings


@pytest.mark.asyncio
async def test_email_config_status_reports_debug_and_smtp(client, monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_password", "")

    response = await client.get("/system-auth/email/config")

    assert response.status_code == 200
    assert response.json() == {
        "debug": True,
        "smtp_configured": False,
        "email_login_available": True,
    }
