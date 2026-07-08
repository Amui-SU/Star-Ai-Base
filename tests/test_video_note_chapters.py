import pytest

from app.services.video_note_chapters import (
    extract_bilibili_view_point_timestamps,
    fetch_bilibili_view_point_timestamps,
)
from app.services.video_note_presenters import VideoNoteSource


def _source(**overrides) -> VideoNoteSource:
    values = {
        "bvid": "BVNOTE123",
        "cid": 456,
        "title": "AI 视频学习法",
        "original_title": "AI 视频学习法",
        "folder_title": "学习收藏夹",
        "owner_name": "知识区 UP",
        "duration": 360,
        "pic_url": "https://example.com/cover.jpg",
        "description": "介绍如何用 AI 做学习复盘",
        "source_binding_id": None,
        "content": "这是已有的视频摘要内容。",
        "outline": None,
    }
    values.update(overrides)
    return VideoNoteSource(**values)


def test_extract_bilibili_view_point_timestamps_normalizes_player_view_points():
    items = extract_bilibili_view_point_timestamps(
        {
            "view_points": [
                {"from": 0, "to": 24, "content": "开场介绍"},
                {"from": 64.8, "to": 120, "content": "拆解核心流程"},
                {"from": 64, "content": "拆解核心流程"},
                {"from": 180, "title": "总结与行动"},
                {"from": 240, "content": "   "},
            ]
        }
    )

    assert items == [
        {"time": 0, "text": "开场介绍"},
        {"time": 64, "text": "拆解核心流程"},
        {"time": 180, "text": "总结与行动"},
    ]


def test_extract_bilibili_view_point_timestamps_parses_time_strings():
    items = extract_bilibili_view_point_timestamps(
        {
            "view_points": [
                {"from": "00:00", "content": "开场介绍"},
                {"from": "01:04", "content": "拆解核心流程"},
                {"from": "01:02:03", "content": "总结与行动"},
            ]
        }
    )

    assert items == [
        {"time": 0, "text": "开场介绍"},
        {"time": 64, "text": "拆解核心流程"},
        {"time": 3723, "text": "总结与行动"},
    ]


@pytest.mark.asyncio
async def test_fetch_bilibili_view_point_timestamps_uses_video_cid_and_closes_service():
    class FakeBilibiliService:
        instances = []

        def __init__(self):
            self.closed = False
            self.calls = []
            FakeBilibiliService.instances.append(self)

        async def get_player_info(self, bvid, cid, aid=None):
            self.calls.append((bvid, cid, aid))
            return {
                "view_points": [
                    {"from": 15, "content": "进入案例"},
                    {"from": 96, "content": "关键步骤"},
                ]
            }

        async def close(self):
            self.closed = True

    items = await fetch_bilibili_view_point_timestamps(
        None,
        user=None,
        workspace=None,
        source=_source(),
        service_class=FakeBilibiliService,
    )

    assert items == [
        {"time": 15, "text": "进入案例"},
        {"time": 96, "text": "关键步骤"},
    ]
    service = FakeBilibiliService.instances[0]
    assert service.calls == [("BVNOTE123", 456, None)]
    assert service.closed is True


@pytest.mark.asyncio
async def test_fetch_bilibili_timestamps_resolves_missing_cid_and_uses_summary_outline():
    class FakeBilibiliService:
        instances = []

        def __init__(self):
            self.closed = False
            self.video_info_calls = []
            self.player_info_calls = []
            self.summary_calls = []
            FakeBilibiliService.instances.append(self)

        async def get_video_info(self, bvid):
            self.video_info_calls.append(bvid)
            return {
                "aid": 123,
                "cid": 789,
                "owner": {"mid": 456},
            }

        async def get_player_info(self, bvid, cid, aid=None):
            self.player_info_calls.append((bvid, cid, aid))
            return {"view_points": []}

        async def get_video_summary(self, bvid, cid, up_mid=None):
            self.summary_calls.append((bvid, cid, up_mid))
            return {
                "code": 0,
                "model_result": {
                    "summary": "B 站 AI 总结",
                    "outline": [
                        {
                            "title": "问题背景",
                            "timestamp": 31,
                            "part_outline": [
                                {"content": "拆解操作步骤", "timestamp": 45}
                            ],
                        }
                    ],
                },
            }

        async def close(self):
            self.closed = True

    items = await fetch_bilibili_view_point_timestamps(
        None,
        user=None,
        workspace=None,
        source=_source(cid=None),
        service_class=FakeBilibiliService,
    )

    assert items == [
        {"time": 31, "text": "问题背景"},
        {"time": 45, "text": "拆解操作步骤"},
    ]
    service = FakeBilibiliService.instances[0]
    assert service.video_info_calls == ["BVNOTE123"]
    assert service.player_info_calls == [("BVNOTE123", 789, 123)]
    assert service.summary_calls == [("BVNOTE123", 789, 456)]
    assert service.closed is True
