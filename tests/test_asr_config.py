import json
from types import SimpleNamespace

import pytest

from app.services.asr import ASRService


def test_asr_uses_dedicated_dashscope_api_key(monkeypatch):
    fake_settings = SimpleNamespace(
        dashscope_api_key="dashscope-key",
        openai_api_key="chat-key",
        dashscope_base_url="https://dashscope.aliyuncs.com/api/v1",
        asr_model="paraformer-v2",
        asr_timeout=600,
        asr_model_local="paraformer-realtime-v2",
        asr_input_format="pcm",
    )
    monkeypatch.setattr("app.services.asr.settings", fake_settings)

    service = ASRService()

    assert service.api_key == "dashscope-key"


class FakeUrlResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_asr_download_transcription_collects_text_and_sentence_variants(monkeypatch):
    payload = {
        "transcripts": [
            {"text": "第一段"},
            {"sentences": [{"text": "第二段"}, {"text": ""}, {"text": "第三段"}]},
        ]
    }
    monkeypatch.setattr(
        "app.services.asr.urlrequest.urlopen",
        lambda url: FakeUrlResponse(payload),
    )

    text = ASRService(api_key="dashscope-key")._download_transcription(
        "https://example.test/result.json"
    )

    assert text == "第一段\n第二段\n第三段"


def test_asr_download_transcription_uses_top_level_text(monkeypatch):
    monkeypatch.setattr(
        "app.services.asr.urlrequest.urlopen",
        lambda url: FakeUrlResponse({"text": "完整转写"}),
    )

    text = ASRService(api_key="dashscope-key")._download_transcription(
        "https://example.test/result.json"
    )

    assert text == "完整转写"


def test_asr_build_api_url_uses_configured_base_url():
    service = ASRService(
        api_key="dashscope-key",
        base_url="https://dashscope.example/api/v1/",
    )

    assert (
        service._build_api_url("tasks", "task-1")
        == "https://dashscope.example/api/v1/tasks/task-1"
    )


def test_asr_prepare_recognition_input_uses_configured_format(monkeypatch):
    service = ASRService(api_key="dashscope-key")
    calls = []

    monkeypatch.setattr(
        service,
        "_transcode_audio_to_wav",
        lambda file_path: calls.append(("wav", file_path)) or "audio.wav",
    )
    monkeypatch.setattr(
        service,
        "_transcode_audio_to_pcm",
        lambda file_path: calls.append(("pcm", file_path)) or "audio.pcm",
    )

    service.input_format = "wav"
    assert service._prepare_recognition_input("audio.mp4") == "audio.wav"
    service.input_format = "pcm"
    assert service._prepare_recognition_input("audio.mp4") == "audio.pcm"

    assert calls == [("wav", "audio.mp4"), ("pcm", "audio.mp4")]


def test_asr_transcribe_sync_with_model_restores_original_model(monkeypatch):
    service = ASRService(api_key="dashscope-key", model="default-model")

    def fail_transcribe(audio_url):
        assert audio_url == "https://example.test/audio.wav"
        assert service.model == "temporary-model"
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "_transcribe_sync", fail_transcribe)

    with pytest.raises(RuntimeError):
        service._transcribe_sync_with_model(
            "https://example.test/audio.wav",
            "temporary-model",
        )

    assert service.model == "default-model"
