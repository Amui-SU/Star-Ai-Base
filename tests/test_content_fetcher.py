import pytest

from app.schemas.content import ContentSource
from app.services.content_asr import (
    probe_audio_url,
    try_asr_with_local_audio,
    try_bilibili_asr,
)
from app.services.content_fetcher import ContentFetcher
from app.services.content_subtitles import (
    extract_subtitle_url,
    extract_subtitles,
    pick_preferred_subtitle,
    try_bilibili_subtitle,
)
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
        self.last_url = audio_url
        return self.text

    async def transcribe_local_file(self, file_path):
        self.calls += 1
        self.last_file_path = file_path
        return self.text


class FakeBilibili:
    def __init__(
        self,
        *,
        video_info=None,
        summary=None,
        subtitle_text=None,
        audio_url=None,
        download_audio_ok=False,
    ):
        self.video_info = video_info or {}
        self.summary = summary
        self.subtitle_text = subtitle_text
        self.audio_url = audio_url
        self.download_audio_ok = download_audio_ok
        self.video_info_calls = 0
        self.downloaded_audio_path = None

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
        self.downloaded_audio_path = file_path
        return self.download_audio_ok


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


def test_content_subtitle_helpers_prefer_manual_chinese_subtitle():
    subtitles = [
        {"lan": "en-US", "ai_status": 0, "url": "https://example.test/en.json"},
        {
            "lan": "zh-CN",
            "ai_status": 1,
            "url": "https://example.test/auto-zh.json",
        },
        {
            "lan": "zh-Hans",
            "ai_status": 0,
            "subtitle_url": "https://example.test/manual-zh.json",
        },
    ]

    selected = pick_preferred_subtitle(subtitles)

    assert selected == subtitles[2]
    assert extract_subtitle_url(selected) == "https://example.test/manual-zh.json"


def test_content_subtitle_helpers_extract_player_and_view_lists():
    player_data = {"subtitle": {"subtitles": [{"lan": "zh-CN"}]}}
    view_data = {"subtitle": {"list": [{"lan": "zh-Hans"}]}}

    assert extract_subtitles(player_data) == [{"lan": "zh-CN"}]
    assert extract_subtitles(view_data) == [{"lan": "zh-Hans"}]


@pytest.mark.asyncio
async def test_try_bilibili_subtitle_falls_back_to_view_subtitles():
    subtitle = "这是 view 字幕兜底内容。" * 20
    bili = FakeBilibili(
        video_info={
            "aid": 123,
            "subtitle": {
                "list": [
                    {
                        "lan": "zh-CN",
                        "ai_status": 0,
                        "subtitle_url": "https://example.test/view-subtitle.json",
                    }
                ]
            },
        },
        subtitle_text=subtitle,
    )

    text = await try_bilibili_subtitle(
        bili,
        "BV1VIEW",
        456,
        video_info=bili.video_info,
    )

    assert text == subtitle


@pytest.mark.asyncio
async def test_try_bilibili_asr_uses_transcription_when_audio_url_is_reachable():
    text = "这是 ASR 转写内容。" * 20
    bili = FakeBilibili(audio_url="https://example.test/audio.m4s")
    asr = FakeASR(text=text)

    result = await try_bilibili_asr(
        bili,
        asr,
        "BV1ASR",
        456,
        probe_audio=lambda _bvid, _audio_url: 200,
    )

    assert result == text
    assert asr.calls == 1
    assert asr.last_url == "https://example.test/audio.m4s"
    assert bili.downloaded_audio_path is None


@pytest.mark.asyncio
async def test_try_bilibili_asr_uses_local_audio_when_remote_url_is_unreachable():
    text = "这是本地 Recognition 转写内容。" * 20
    bili = FakeBilibili(
        audio_url="https://example.test/audio.m4s",
        download_audio_ok=True,
    )
    asr = FakeASR(text=text)

    result = await try_bilibili_asr(
        bili,
        asr,
        "BV1LOCAL",
        456,
        probe_audio=lambda _bvid, _audio_url: 403,
        tmp_dir="data/test_asr_tmp",
        time_provider=lambda: 123456,
        path_exists=lambda _path: False,
        get_file_size=lambda _path: 2048,
        remove_file=lambda _path: None,
    )

    assert result == text
    assert asr.calls == 1
    assert asr.last_file_path.endswith("BV1LOCAL_456_123456.m4s")
    assert bili.downloaded_audio_path == asr.last_file_path


@pytest.mark.asyncio
async def test_try_bilibili_asr_rejects_short_transcripts():
    bili = FakeBilibili(audio_url="https://example.test/audio.m4s")
    asr = FakeASR(text="太短")

    result = await try_bilibili_asr(
        bili,
        asr,
        "BV1SHORT",
        456,
        probe_audio=lambda _bvid, _audio_url: 200,
    )

    assert result is None


@pytest.mark.asyncio
async def test_try_asr_with_local_audio_skips_tiny_downloaded_file():
    bili = FakeBilibili(
        audio_url="https://example.test/audio.m4s",
        download_audio_ok=True,
    )
    asr = FakeASR(text="不会被调用")
    removed = []

    result = await try_asr_with_local_audio(
        bili,
        asr,
        "BV1TINY",
        456,
        "https://example.test/audio.m4s",
        tmp_dir="data/test_asr_tmp",
        time_provider=lambda: 123456,
        path_exists=lambda _path: True,
        get_file_size=lambda _path: 512,
        remove_file=removed.append,
    )

    assert result is None
    assert asr.calls == 0
    assert removed == [bili.downloaded_audio_path]


@pytest.mark.asyncio
async def test_fetch_content_prefers_full_subtitle_over_ai_summary():
    subtitle = "这是字幕正文内容。" * 20
    bili = FakeBilibili(
        video_info={
            "aid": 123,
            "cid": 456,
            "title": "Summary Video",
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
        subtitle_text=subtitle,
        audio_url="https://example.test/audio.m4s",
    )
    asr = FakeASR(text="这是 ASR 内容。" * 20)

    content = await ContentFetcher(bili, asr).fetch_content(
        "BV1SUMMARY", cid=456, title="Summary Video"
    )

    assert content.source == ContentSource.SUBTITLE
    assert content.content == subtitle
    assert asr.calls == 0


@pytest.mark.asyncio
async def test_fetch_content_uses_ai_summary_when_full_text_is_unavailable():
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
    )
    asr = FakeASR(text=None)

    content = await ContentFetcher(bili, asr).fetch_content(
        "BV1SUMMARY", cid=456, title="Summary Video"
    )

    assert content.source == ContentSource.AI_SUMMARY
    assert "这是 AI 摘要内容。" in content.content
    assert "第一段" in content.content


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
