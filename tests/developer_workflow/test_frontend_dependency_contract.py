import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
NODE_VERSION = "22.13.1"
PACKAGE_MANAGER = "npm@10.9.2"
OPTIONAL_DEPENDENCIES = {
    "@emnapi/runtime": "1.11.3",
    "@img/sharp-wasm32": "0.35.4",
    "@tybys/wasm-util": "0.10.2",
}
SECURITY_PINNED_DEV_DEPENDENCIES = {
    "yaml": "2.9.0",
    "eslint-config-next": "16.3.4",
    "vitest": "4.1.11",
}
SECURITY_PINNED_TRANSITIVE_DEPENDENCIES = {
    "@xmldom/xmldom": "0.9.12",
    "browserslist": "4.28.8",
    "sharp": "0.35.4",
    "js-yaml": "4.3.2",
    "vite": "8.0.16",
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


def test_security_pinned_dev_dependencies_are_exact_and_locked():
    manifest = load_json(FRONTEND_ROOT / "package.json")
    lockfile = load_json(FRONTEND_ROOT / "package-lock.json")

    for name, version in SECURITY_PINNED_DEV_DEPENDENCIES.items():
        assert manifest["devDependencies"][name] == version
        assert lockfile["packages"][""]["devDependencies"][name] == version
        assert lockfile["packages"][f"node_modules/{name}"]["version"] == version


def test_security_pinned_transitive_dependencies_are_exact_and_locked():
    manifest = load_json(FRONTEND_ROOT / "package.json")
    lockfile = load_json(FRONTEND_ROOT / "package-lock.json")

    for name, version in SECURITY_PINNED_TRANSITIVE_DEPENDENCIES.items():
        assert manifest["overrides"][name] == version
        assert lockfile["packages"][f"node_modules/{name}"]["version"] == version


@pytest.mark.parametrize(
    ("name", "version"),
    [
        ("next", "16.3.4"),
        ("sharp", "0.35.4"),
        ("vitest", "4.1.11"),
        ("@vitest/mocker", "4.1.11"),
        ("js-yaml", "4.3.2"),
    ],
)
def test_security_remediation_covers_every_locked_copy(name: str, version: str):
    lockfile = load_json(FRONTEND_ROOT / "package-lock.json")
    copies = {
        path: package["version"]
        for path, package in lockfile["packages"].items()
        if path == f"node_modules/{name}" or path.endswith(f"/node_modules/{name}")
    }
    assert copies, f"Missing locked dependency: {name}"
    assert set(copies.values()) == {version}, copies
    if name == "next":
        manifest = load_json(FRONTEND_ROOT / "package.json")
        assert manifest["dependencies"][name] == version
        assert lockfile["packages"][""]["dependencies"][name] == version
