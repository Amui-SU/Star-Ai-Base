import json
from http import HTTPStatus
from types import SimpleNamespace

from app.services.asr_transcription import (
    build_dashscope_api_url,
    download_transcription_text,
    submit_transcription_task_restful,
    transcribe_sync_with_sdk,
)


class FakeUrlResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeHttpResponse:
    def __init__(self, payload, status_code=HTTPStatus.OK, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self.payload


def test_download_transcription_text_collects_text_and_sentence_variants():
    payload = {
        "transcripts": [
            {"text": "第一段"},
            {"sentences": [{"text": "第二段"}, {"text": ""}, {"text": "第三段"}]},
        ]
    }

    text = download_transcription_text(
        "https://example.test/result.json",
        open_url=lambda _url: FakeUrlResponse(payload),
    )

    assert text == "第一段\n第二段\n第三段"


def test_download_transcription_text_uses_top_level_text():
    text = download_transcription_text(
        "https://example.test/result.json",
        open_url=lambda _url: FakeUrlResponse({"text": "完整转写"}),
    )

    assert text == "完整转写"


def test_build_dashscope_api_url_uses_configured_base_url():
    assert (
        build_dashscope_api_url(
            "tasks",
            "task-1",
            base_url="https://dashscope.example/api/v1/",
        )
        == "https://dashscope.example/api/v1/tasks/task-1"
    )


def test_submit_transcription_task_restful_builds_paraformer_payload():
    calls = []

    task_id = submit_transcription_task_restful(
        "https://example.test/audio.wav",
        "paraformer-v2",
        api_key="dashscope-key",
        build_api_url=lambda *parts: "/".join(parts),
        default_headers_factory=lambda key: {"Authorization": f"Bearer {key}"},
        post_json=lambda url, json, headers, timeout: calls.append(
            (url, json, headers, timeout)
        )
        or FakeHttpResponse({"output": {"task_id": "task-1"}}),
    )

    assert task_id == "task-1"
    assert calls == [
        (
            "services/audio/asr/transcription",
            {
                "model": "paraformer-v2",
                "input": {"file_urls": ["https://example.test/audio.wav"]},
                "parameters": {"language_hints": ["zh", "en"]},
            },
            {
                "Authorization": "Bearer dashscope-key",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            },
            30.0,
        )
    ]


def test_transcribe_sync_with_sdk_polls_until_success_and_downloads_result():
    calls = []

    class FakeTranscription:
        @staticmethod
        def async_call(**kwargs):
            calls.append(("async_call", kwargs))
            return SimpleNamespace(
                output={"task_id": "task-1", "task_status": "RUNNING"},
                status_code=HTTPStatus.OK,
            )

        @staticmethod
        def fetch(task):
            calls.append(("fetch", task))
            return SimpleNamespace(
                output={
                    "task_id": task,
                    "task_status": "SUCCEEDED",
                    "results": [
                        {
                            "subtask_status": "SUCCEEDED",
                            "transcription_url": "https://example.test/result.json",
                        }
                    ],
                },
                status_code=HTTPStatus.OK,
            )

    text = transcribe_sync_with_sdk(
        "https://example.test/audio.wav",
        model="paraformer-v2",
        timeout=30,
        transcription=FakeTranscription,
        get_output_value=lambda output, key, default=None: (
            output.get(key, default) if isinstance(output, dict) else default
        ),
        download_transcription=lambda url: f"text from {url}",
        sleep=lambda _seconds: None,
        now=iter([0, 1]).__next__,
    )

    assert text == "text from https://example.test/result.json"
    assert calls == [
        (
            "async_call",
            {
                "model": "paraformer-v2",
                "file_urls": ["https://example.test/audio.wav"],
                "language_hints": ["zh", "en"],
            },
        ),
        ("fetch", "task-1"),
    ]
