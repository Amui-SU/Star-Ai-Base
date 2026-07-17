from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_backend_image_defines_healthcheck_contract():
    dockerfile = read("Dockerfile.backend")

    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/health" in dockerfile
    assert "urllib.request" in dockerfile


def test_frontend_image_defines_api_url_and_healthcheck_contracts():
    dockerfile = read("frontend/Dockerfile")

    assert "ARG NEXT_PUBLIC_API_URL" in dockerfile
    assert "ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1/" in dockerfile


def test_root_dockerignore_excludes_runtime_and_production_files():
    dockerignore = read(".dockerignore")

    for entry in [".env.production", "data/", "logs/", "deploy/.env.deploy"]:
        assert entry in dockerignore


def test_frontend_dockerignore_excludes_local_build_and_environment_files():
    dockerignore = read("frontend/.dockerignore")

    for entry in [".env.local", ".env.production", "node_modules/", ".next/", "out/"]:
        assert entry in dockerignore
