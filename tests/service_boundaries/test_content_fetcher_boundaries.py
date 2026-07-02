from tests.service_boundaries.helpers import get_project_root


def test_content_fetcher_delegates_ai_summary_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/content_summary.py"
    fetcher_source = (project_root / "app/services/content_fetcher.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "def parse_ai_summary_result" in service_source
    assert "def format_ai_summary_content" in service_source
    assert "from app.services.content_summary import" in fetcher_source
    assert 'model_result.get("outline"' not in fetcher_source
    assert 'for item in summary["outline"]' not in fetcher_source
    assert 'for point in item.get("part_outline"' not in fetcher_source


def test_content_fetcher_delegates_subtitle_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/content_subtitles.py"
    fetcher_source = (project_root / "app/services/content_fetcher.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "extract_subtitles",
        "extract_subtitle_url",
        "pick_preferred_subtitle",
        "try_bilibili_subtitle",
    }:
        assert f"def {name}" in service_source or f"async def {name}" in service_source

    assert "from app.services.content_subtitles import" in fetcher_source
    assert "def pick_subtitle(" not in fetcher_source
    assert "def extract_subtitles(" not in fetcher_source
    assert "def extract_url(" not in fetcher_source
    assert "download_subtitle(" not in fetcher_source
    assert "get_player_info(" not in fetcher_source


def test_content_fetcher_delegates_asr_audio_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/content_asr.py"
    local_audio_path = project_root / "app/services/content_audio_runtime.py"
    fetcher_source = (project_root / "app/services/content_fetcher.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "probe_audio_url",
        "try_asr_with_local_audio",
        "try_bilibili_asr",
    }:
        assert f"async def {name}" in service_source

    assert "from app.services.content_asr import" in fetcher_source
    assert "httpx.AsyncClient" not in fetcher_source
    assert "download_audio_to_file(" not in fetcher_source
    assert "transcribe_url(" not in fetcher_source
    assert "transcribe_local_file(" not in fetcher_source
    assert "def _probe_audio_url(" not in fetcher_source
    assert "def _try_asr_with_local_audio(" not in fetcher_source

    assert local_audio_path.exists()
    local_audio_source = local_audio_path.read_text(encoding="utf-8")
    for name in {
        "transcode_audio_to_wav",
        "get_audio_duration_sec",
        "split_audio_wav",
    }:
        assert f"def {name}" in local_audio_source
    assert "from app.services.content_audio_runtime import" in fetcher_source
    assert "shutil.which" not in fetcher_source
    assert "subprocess.run" not in fetcher_source
    assert "math.ceil" not in fetcher_source
    assert '"-ss",' not in fetcher_source
