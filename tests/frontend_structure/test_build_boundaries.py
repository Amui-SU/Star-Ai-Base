import json

from .helpers import get_project_root


def test_frontend_build_cleans_next_dev_type_cache():
    project_root = get_project_root()
    package_json = json.loads(
        (project_root / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    cleanup_script = project_root / "frontend" / "scripts" / "clean-next-dev-types.mjs"

    assert (
        package_json["scripts"]["prebuild"] == "node scripts/clean-next-dev-types.mjs"
    )
    assert cleanup_script.exists()
    cleanup_source = cleanup_script.read_text(encoding="utf-8")
    assert ".next/dev/types" in cleanup_source
    assert "rmdirSync" in cleanup_source
