from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
FAST_WORKFLOW_ROOT = TESTS_ROOT / "fast_workflow"


def test_fast_workflow_contracts_stay_split_by_domain():
    legacy_monolith = TESTS_ROOT / "test_fast_workflow.py"
    focused_modules = list(FAST_WORKFLOW_ROOT.glob("test_*.py"))

    assert (
        not legacy_monolith.exists()
    ), "fast-workflow contracts must not return to one monolith"
    assert (
        len(focused_modules) >= 5
    ), "fast-workflow contracts need focused domain modules"

    module_sizes = {
        module.name: len(module.read_text(encoding="utf-8").splitlines())
        for module in focused_modules
    }
    oversized_modules = {
        name: size for name, size in module_sizes.items() if size > 600
    }
    assert (
        not oversized_modules
    ), f"split oversized fast-workflow modules: {oversized_modules}"

    support_files = [
        FAST_WORKFLOW_ROOT / "support.py",
        FAST_WORKFLOW_ROOT / "conftest.py",
    ]
    support_sizes = {
        support.name: len(support.read_text(encoding="utf-8").splitlines())
        for support in support_files
        if support.exists()
    }
    oversized_support = {
        name: size for name, size in support_sizes.items() if size > 350
    }
    assert (
        not oversized_support
    ), f"shrink fast-workflow support files: {oversized_support}"
