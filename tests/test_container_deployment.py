from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def active_dockerfile_lines(relative_path: str) -> list[str]:
    return [
        line.strip()
        for line in read(relative_path).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def active_dockerignore_rules(relative_path: str) -> set[str]:
    rules = set()
    for line in read(relative_path).splitlines():
        rule = line.strip()
        if rule and not rule.startswith(("#", "!")):
            rules.add(rule)
    return rules


def test_backend_image_defines_healthcheck_contract():
    lines = active_dockerfile_lines("Dockerfile.backend")
    healthcheck = (
        "HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\"
    )
    command = (
        'CMD python -c "import urllib.request; '
        "urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()\""
    )

    healthcheck_index = lines.index(healthcheck)
    assert lines[healthcheck_index + 1] == command


def test_frontend_image_defines_api_url_and_healthcheck_contracts():
    lines = active_dockerfile_lines("frontend/Dockerfile")
    arg = "ARG NEXT_PUBLIC_API_URL=http://localhost:8000"
    env = "ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL"
    build = "RUN npm run build"
    healthcheck = (
        "HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\"
    )
    command = "CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1"

    assert lines.index(arg) < lines.index(build)
    assert lines.index(env) < lines.index(build)
    healthcheck_index = lines.index(healthcheck)
    assert lines[healthcheck_index + 1] == command


def test_root_dockerignore_excludes_runtime_and_production_files():
    rules = active_dockerignore_rules(".dockerignore")

    for entry in [".env*", "data/", "logs/", "deploy/.env.deploy"]:
        assert entry in rules


def test_frontend_dockerignore_excludes_local_build_and_environment_files():
    rules = active_dockerignore_rules("frontend/.dockerignore")

    for entry in [".env*", "node_modules/", ".next/", "out/"]:
        assert entry in rules
