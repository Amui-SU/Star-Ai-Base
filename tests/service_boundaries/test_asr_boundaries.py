from tests.service_boundaries.helpers import get_project_root


def test_asr_service_delegates_audio_preparation_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/asr_audio.py"
    asr_source = (project_root / "app/services/asr.py").read_text(encoding="utf-8")

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "prepare_recognition_input",
        "transcode_audio_to_pcm",
        "transcode_audio_to_wav",
    }:
        assert f"def {name}" in service_source

    assert "from app.services.asr_audio import" in asr_source
    assert "shutil.which" not in asr_source
    assert "subprocess.run" not in asr_source
    assert '"-f",\n            "s16le"' not in asr_source
    assert '"-vn",\n            wav_path' not in asr_source


def test_asr_service_delegates_transcription_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/asr_transcription.py"
    asr_source = (project_root / "app/services/asr.py").read_text(encoding="utf-8")

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in {
        "build_dashscope_api_url",
        "download_transcription_text",
        "fetch_transcription_task_restful",
        "submit_transcription_task_restful",
        "transcribe_sync_restful",
        "transcribe_sync_with_sdk",
    }:
        assert f"def {name}" in service_source

    assert "from app.services.asr_transcription import" in asr_source
    assert "import httpx" not in asr_source
    assert "from dashscope.audio.asr import Transcription" not in asr_source
    assert "default_headers" not in asr_source
    assert "join_url" not in asr_source
    assert "Transcription.async_call" not in asr_source
    assert "Transcription.fetch" not in asr_source
    assert "httpx.post" not in asr_source
    assert "httpx.get" not in asr_source
