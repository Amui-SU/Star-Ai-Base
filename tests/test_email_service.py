import pytest
from email import message_from_string

from app.config import settings
from app.services.email import send_verification_email


def _html_payload(raw_message: str) -> str:
    parsed = message_from_string(raw_message)
    for part in parsed.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            return payload.decode(part.get_content_charset() or "utf-8")
    return ""


@pytest.mark.asyncio
async def test_send_verification_email_skips_when_smtp_missing(monkeypatch):
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_password", "")

    assert await send_verification_email("user@example.com", "123456") is False


@pytest.mark.asyncio
async def test_send_verification_email_uses_starttls(monkeypatch):
    calls: list[tuple] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("SMTP", host, port, timeout))

        def starttls(self):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def sendmail(self, from_addr, to_addrs, message):
            calls.append(("sendmail", from_addr, to_addrs, _html_payload(message)))

        def quit(self):
            calls.append(("quit",))

    monkeypatch.setattr(settings, "smtp_user", "smtp-user")
    monkeypatch.setattr(settings, "smtp_password", "smtp-password")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)

    assert await send_verification_email("user@example.com", "123456") is True
    assert calls[:3] == [
        ("SMTP", "smtp.example.com", 587, 15),
        ("starttls",),
        ("login", "smtp-user", "smtp-password"),
    ]
    assert calls[3][0:3] == ("sendmail", "noreply@example.com", ["user@example.com"])
    assert "123456" in calls[3][3]
    assert calls[4] == ("quit",)


@pytest.mark.asyncio
async def test_send_verification_email_uses_smtp_ssl(monkeypatch):
    calls: list[tuple] = []

    class FakeSMTPSSL:
        def __init__(self, host, port, timeout):
            calls.append(("SMTP_SSL", host, port, timeout))

        def login(self, user, password):
            calls.append(("login", user, password))

        def sendmail(self, from_addr, to_addrs, message):
            calls.append(("sendmail", from_addr, to_addrs, _html_payload(message)))

        def quit(self):
            calls.append(("quit",))

    monkeypatch.setattr(settings, "smtp_user", "smtp-user")
    monkeypatch.setattr(settings, "smtp_password", "smtp-password")
    monkeypatch.setattr(settings, "smtp_from", "")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 465)
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTPSSL)

    assert await send_verification_email("user@example.com", "654321") is True
    assert calls[:2] == [
        ("SMTP_SSL", "smtp.example.com", 465, 15),
        ("login", "smtp-user", "smtp-password"),
    ]
    assert calls[2][0:3] == ("sendmail", "smtp-user", ["user@example.com"])
    assert "654321" in calls[2][3]
    assert calls[3] == ("quit",)
