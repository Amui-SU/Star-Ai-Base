from types import SimpleNamespace

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
