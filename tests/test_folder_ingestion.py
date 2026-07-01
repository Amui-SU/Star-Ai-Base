from tests.service_boundaries.helpers import get_project_root


def test_folder_ingestion_file_delegates_to_focused_files():
    focused_dir = get_project_root() / "tests" / "folder_ingestion"

    for file_name in [
        "test_helpers_and_records.py",
        "test_empty_and_partial_sync.py",
        "test_scoped_vector_rebuild.py",
    ]:
        assert (focused_dir / file_name).exists()
