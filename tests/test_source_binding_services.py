from tests.service_boundaries.helpers import get_project_root


def test_source_binding_services_file_delegates_to_focused_files():
    project_root = get_project_root()
    focused_dir = project_root / "tests" / "source_binding_services"

    for file_name in [
        "test_binding_catalog.py",
        "test_binding_credentials.py",
        "test_bilibili_qrcode.py",
    ]:
        assert (focused_dir / file_name).exists()
