import pytest

from app.schemas.content import ContentSource
from app.services.content_fetcher import ContentFetcher
from app.services.content_summary import (
    format_ai_summary_content,
    parse_ai_summary_result,
)


class FakeASR:
    def __init__(self, text=None):
        self.text = text
        self.calls = 0

    async def transcribe_url(self, audio_url):
        self.calls += 1
        return self.text

    async def transcribe_local_file(self, file_path):
        self.calls += 1
        return self.text


class FakeBilibili:
    def __init__(
        self,
        *,
        video_info=None,
        summary=None,
        subtitle_text=None,
        audio_url=None,
    ):
        self.video_info = video_info or {}
        self.summary = summary
        self.subtitle_text = subtitle_text
        self.audio_url = audio_url
        self.video_info_calls = 0

    def _get_cookies(self):
        return {"SESSDATA": "test"}

    async def get_video_info(self, bvid):
        self.video_info_calls += 1
        return self.video_info

    async def get_player_info(self, bvid, cid, aid=None):
        return self.video_info

    async def get_video_summary(self, bvid, cid, up_mid=None):
        return self.summary

    async def download_subtitle(self, subtitle_url):
        return self.subtitle_text or ""

    async def get_audio_url(self, bvid, cid):
        return self.audio_url

    async def download_audio_to_file(self, audio_url, file_path):
        return False


def test_content_summary_helpers_parse_and_format_ai_summary_payload():
    result = {
        "code": 0,
        "model_result": {
            "summary": "Summary text",
            "outline": [
                {
                    "title": "Part one",
                    "timestamp": 12,
                    "part_outline": [
                        {"content": "Point A", "timestamp": 18},
                        {"content": "", "timestamp": 19},
                    ],
                }
            ],
        },
    }

    summary = parse_ai_summary_result(result)

    assert summary == {
        "summary": "Summary text",
        "outline": [
            {
                "title": "Part one",
                "timestamp": 12,
                "points": [
                    {"content": "Point A", "timestamp": 18},
                    {"content": "", "timestamp": 19},
                ],
            }
        ],
    }
    assert format_ai_summary_content(summary) == (
        "AI 摘要：Summary text\n\n" "分段提纲：\n" "- Part one (12s)\n" "  - Point A"
    )


def test_content_summary_helpers_reject_unavailable_or_empty_summary():
    assert parse_ai_summary_result(None) is None
    assert parse_ai_summary_result({"code": -404}) is None
    assert parse_ai_summary_result({"code": 0, "model_result": {"summary": ""}}) is None


@pytest.mark.asyncio
async def test_fetch_content_uses_available_ai_summary_first():
    bili = FakeBilibili(
        video_info={"aid": 123, "cid": 456, "title": "Summary Video"},
        summary={
            "code": 0,
            "model_result": {
                "summary": "这是 AI 摘要内容。",
                "outline": [
                    {
                        "title": "第一段",
                        "timestamp": 12,
                        "part_outline": [{"content": "要点 A", "timestamp": 18}],
                    }
                ],
            },
        },
        subtitle_text="这是字幕内容。" * 20,
        audio_url="https://example.test/audio.m4s",
    )
    asr = FakeASR(text="这是 ASR 内容。" * 20)

    content = await ContentFetcher(bili, asr).fetch_content(
        "BV1SUMMARY", cid=456, title="Summary Video"
    )

    assert content.source == ContentSource.AI_SUMMARY
    assert "这是 AI 摘要内容。" in content.content
    assert "第一段" in content.content
    assert asr.calls == 0


@pytest.mark.asyncio
async def test_fetch_content_uses_available_subtitle_before_asr():
    subtitle = "这是字幕内容。" * 20
    bili = FakeBilibili(
        video_info={
            "aid": 123,
            "cid": 456,
            "title": "Subtitle Video",
            "subtitle": {
                "subtitles": [
                    {
                        "lan": "zh-CN",
                        "ai_status": 0,
                        "subtitle_url": "https://example.test/subtitle.json",
                    }
                ]
            },
        },
        subtitle_text=subtitle,
        audio_url="https://example.test/audio.m4s",
    )
    asr = FakeASR(text="这是 ASR 内容。" * 20)

    content = await ContentFetcher(bili, asr).fetch_content(
        "BV1SUBTITLE", cid=456, title="Subtitle Video"
    )

    assert content.source == ContentSource.SUBTITLE
    assert content.content == subtitle
    assert asr.calls == 0


@pytest.mark.asyncio
async def test_fetch_content_fetches_video_info_to_fill_basic_description():
    bili = FakeBilibili(
        video_info={
            "cid": 456,
            "title": "Description Video",
            "desc": "这是从视频详情接口补齐的简介。",
        }
    )

    content = await ContentFetcher(bili, FakeASR()).fetch_content(
        "BV1DESC", cid=456, title="Description Video"
    )

    assert content.source == ContentSource.BASIC_INFO
    assert "Description Video" in content.content
    assert "这是从视频详情接口补齐的简介。" in content.content
    assert bili.video_info_calls == 1
