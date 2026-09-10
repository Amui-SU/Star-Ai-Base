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


@pytest.mark.asyncio
async def test_fetch_bilibili_timestamps_normalizes_cumulative_multi_part_summary():
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
                "cid": 111,
                "owner": {"mid": 456},
                "pages": [
                    {"page": 1, "cid": 111, "duration": 1200},
                    {"page": 2, "cid": 222, "duration": 540},
                    {"page": 3, "cid": 333, "duration": 300},
                ],
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
                            "title": "第二讲问题背景",
                            "timestamp": 1283,
                            "part_outline": [
                                {"content": "第二讲操作步骤", "timestamp": 1320}
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
        source=_source(
            cid=222,
            duration=540,
            page_number=2,
            part_title="第二讲",
            total_parts=3,
        ),
        service_class=FakeBilibiliService,
    )

    assert items == [
        {"time": 83, "text": "第二讲问题背景"},
        {"time": 120, "text": "第二讲操作步骤"},
    ]
    service = FakeBilibiliService.instances[0]
    assert service.video_info_calls == ["BVNOTE123"]
    assert service.player_info_calls == [("BVNOTE123", 222, 123)]
    assert service.summary_calls == [("BVNOTE123", 222, 456)]
    assert service.closed is True


def test_normalize_shifts_short_cumulative_chapters_for_later_parts():
    """P2+ 的章节即使未超过分P时长，只要都落在累计区间起点之后也应换算"""
    from app.services.video_note_chapters import _normalize_part_relative_timestamps

    source = _source(page_number=2, total_parts=3, duration=300)
    video_info = {
        "pages": [
            {"page": 1, "cid": 111, "duration": 400},
            {"page": 2, "cid": 456, "duration": 300},
            {"page": 3, "cid": 333, "duration": 200},
        ]
    }
    # 累计秒（400 起）但都 <= 400+300，旧启发式会漏判
    items = [
        {"time": 400, "text": "开场"},
        {"time": 520, "text": "重点"},
        {"time": 690, "text": "总结"},
    ]

    normalized = _normalize_part_relative_timestamps(items, source, video_info)

    assert [item["time"] for item in normalized] == [0, 120, 290]


def test_normalize_drops_items_outside_part_instead_of_falling_back():
    """换算后全部越界时返回空列表，而不是回退成错误的累计秒数"""
    from app.services.video_note_chapters import _normalize_part_relative_timestamps

    source = _source(page_number=2, total_parts=2, duration=100)
    video_info = {
        "pages": [
            {"page": 1, "cid": 111, "duration": 100},
            {"page": 2, "cid": 456, "duration": 100},
        ]
    }
    # 全部超出 P2 的累计区间（100-200）
    items = [
        {"time": 500, "text": "不属于当前分P"},
        {"time": 700, "text": "同上"},
    ]

    normalized = _normalize_part_relative_timestamps(items, source, video_info)

    assert normalized == []


def test_normalize_keeps_part_relative_times_untouched():
    """已是分P内秒数（从 0 附近开始）时不做换算"""
    from app.services.video_note_chapters import _normalize_part_relative_timestamps

    source = _source(page_number=2, total_parts=2, duration=300)
    video_info = {
        "pages": [
            {"page": 1, "cid": 111, "duration": 400},
            {"page": 2, "cid": 456, "duration": 300},
        ]
    }
    items = [
        {"time": 0, "text": "开场"},
        {"time": 150, "text": "重点"},
    ]

    normalized = _normalize_part_relative_timestamps(items, source, video_info)

    assert normalized == items


def test_normalize_matches_part_by_storage_id_when_page_number_missing():
    """page_number 为空时通过分P存储ID（bvid_p{n}）匹配分P"""
    from app.services.video_note_chapters import _normalize_part_relative_timestamps

    source = _source(
        bvid="BVNOTE123_p2",
        cid=None,
        page_number=None,
        total_parts=2,
        duration=300,
    )
    video_info = {
        "pages": [
            {"page": 1, "cid": 111, "duration": 400},
            {"page": 2, "cid": 456, "duration": 300},
        ]
    }
    items = [{"time": 450, "text": "重点"}]

    normalized = _normalize_part_relative_timestamps(items, source, video_info)

    assert normalized == [{"time": 50, "text": "重点"}]


@pytest.mark.asyncio
async def test_fetch_bilibili_timestamps_caches_results_per_storage_id():
    """同一存储ID一小时内重复生成时间戳不再重复调 B 站接口"""
    from app.services.video_note_chapters import fetch_bilibili_view_point_timestamps

    class FakeBilibiliService:
        instances = []

        def __init__(self):
            self.calls = 0
            FakeBilibiliService.instances.append(self)

        async def get_player_info(self, bvid, cid, aid=None):
            self.calls += 1
            return {
                "view_points": [
                    {"from": 15, "to": 60, "content": "进入案例"},
                ]
            }

        async def get_video_summary(self, bvid, cid, up_mid=None):
            return None

        async def close(self):
            pass

    source = _source()
    first = await fetch_bilibili_view_point_timestamps(
        None,
        user=None,
        workspace=None,
        source=source,
        service_class=FakeBilibiliService,
    )
    second = await fetch_bilibili_view_point_timestamps(
        None,
        user=None,
        workspace=None,
        source=source,
        service_class=FakeBilibiliService,
    )

    assert first == [{"time": 15, "text": "进入案例"}]
    assert second == first
    # 第二次命中缓存，不再创建服务、不再请求接口
    assert len(FakeBilibiliService.instances) == 1
    assert FakeBilibiliService.instances[0].calls == 1
