import pytest
from pydantic import ValidationError

from app.config import Settings, settings


@pytest.mark.parametrize("version", ["development", "1" * 40])
def test_settings_accept_valid_build_versions(version):
    assert Settings(_env_file=None, app_version=version).app_version == version


def test_settings_rejects_invalid_production_build_version():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_version="latest")


@pytest.mark.asyncio
async def test_health_preserves_the_legacy_response_body(client, monkeypatch):
    version = "1" * 40
    monkeypatch.setattr(settings, "app_version", version)

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.text == '{"status":"healthy"}'


@pytest.mark.asyncio
async def test_health_version_reports_the_runtime_build_version(client, monkeypatch):
    version = "1" * 40
    monkeypatch.setattr(settings, "app_version", version)

    response = await client.get("/health/version")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": version}
