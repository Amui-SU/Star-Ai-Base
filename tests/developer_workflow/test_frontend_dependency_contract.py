import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
NODE_VERSION = "22.13.1"
PACKAGE_MANAGER = "npm@10.9.2"
OPTIONAL_DEPENDENCIES = {
    "@emnapi/runtime": "1.11.1",
    "@img/sharp-wasm32": "0.35.3",
    "@tybys/wasm-util": "0.10.2",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_frontend_toolchain_baseline_is_shared_by_manifest_and_ci():
    assert (PROJECT_ROOT / ".nvmrc").read_text(encoding="utf-8").strip() == NODE_VERSION

    manifest = load_json(FRONTEND_ROOT / "package.json")
    assert manifest["packageManager"] == PACKAGE_MANAGER

    workflow = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'node-version-file: ".nvmrc"' in workflow
    assert 'node-version: "22"' not in workflow


def test_optional_dependency_workarounds_are_exact_and_locked():
    manifest = load_json(FRONTEND_ROOT / "package.json")
    lockfile = load_json(FRONTEND_ROOT / "package-lock.json")

    assert manifest["optionalDependencies"] == OPTIONAL_DEPENDENCIES
    assert lockfile["packages"][""]["optionalDependencies"] == OPTIONAL_DEPENDENCIES

    for name, version in OPTIONAL_DEPENDENCIES.items():
        assert lockfile["packages"][f"node_modules/{name}"]["version"] == version
