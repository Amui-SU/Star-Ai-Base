"""测试视频笔记 AI 功能改进"""

import pytest
from app.services.video_note_ai_suggestions import (
    _timestamp_items,
    _message_for,
    EMPTY_TIMESTAMPS_MESSAGE,
)
from app.services.video_note_ai import build_ai_edit_messages
from app.models import VideoNote
from app.schemas.video_notes import VideoNoteAiEditRequest
from app.services.video_note_presenters import VideoNoteSource


def test_timestamp_smart_fallback():
    """测试时间戳智能降级：当没有具体时间戳但有内容时，应根据视频时长智能分配"""
    source = VideoNoteSource(
        bvid="BV1234567890",
        cid=12345,
        title="测试视频",
        original_title="测试视频",
        folder_title="测试收藏夹",
        owner_name="测试UP主",
        duration=600,  # 10分钟视频
        pic_url=None,
        description=None,
        source_binding_id=1,
        content="这是一个测试视频的内容",
        outline=[
            {"title": "开头介绍", "timestamp": 0},
            {"title": "核心内容", "timestamp": 0},
            {"title": "结尾总结", "timestamp": 0},
        ],
    )

    items = _timestamp_items(source, ai_payload=None, bilibili_timestamps=None)

    # 应该生成时间戳
    assert len(items) > 0
    # 时间戳应该分布在整个视频时长中
    assert items[0]["time"] == 0
    if len(items) > 1:
        assert items[-1]["time"] > 0
        assert items[-1]["time"] <= source.duration


def test_timestamp_with_bilibili_official():
    """测试 B 站官方时间戳优先级最高"""
    source = VideoNoteSource(
        bvid="BV1234567890",
        cid=12345,
        title="测试视频",
        original_title="测试视频",
        folder_title="测试收藏夹",
        owner_name="测试UP主",
        duration=600,
        pic_url=None,
        description=None,
        source_binding_id=1,
        content="测试内容",
        outline=[],
    )

    bilibili_timestamps = [
        {"time": 0, "text": "开头"},
        {"time": 120, "text": "中间"},
        {"time": 480, "text": "结尾"},
    ]

    items = _timestamp_items(
        source, ai_payload=None, bilibili_timestamps=bilibili_timestamps
    )

    # 应该使用 B 站官方时间戳
    assert len(items) == 3
    assert items[0]["time"] == 0
    assert items[1]["time"] == 120
    assert items[2]["time"] == 480


def test_timestamp_with_ai_payload():
    """测试 AI 生成的时间戳"""
    source = VideoNoteSource(
        bvid="BV1234567890",
        cid=12345,
        title="测试视频",
        original_title="测试视频",
        folder_title="测试收藏夹",
        owner_name="测试UP主",
        duration=600,
        pic_url=None,
        description=None,
        source_binding_id=1,
        content="测试内容",
        outline=[],
    )

    ai_payload = {
        "timestamps": [
            {"time": 0, "text": "AI 生成的开头"},
            {"time": 200, "text": "AI 生成的中间"},
            {"time": 500, "text": "AI 生成的结尾"},
        ]
    }

    items = _timestamp_items(source, ai_payload=ai_payload, bilibili_timestamps=None)

    # 应该使用 AI 生成的时间戳
    assert len(items) == 3
    assert items[0]["time"] == 0
    assert items[1]["time"] == 200
    assert items[2]["time"] == 500


def test_message_for_different_statuses():
    """测试不同状态的消息提示"""
    # 官方数据
    msg = _message_for("timestamps", "official")
    assert "B 站官方章节" in msg
    assert "✓" in msg

    # AI 生成
    msg = _message_for("timestamps", "generated")
    assert "AI" in msg
    assert "✓" in msg

    # 生成失败
    msg = _message_for("timestamps", "failed")
    assert "失败" in msg
    assert "⚠" in msg

    # 未连接
    msg = _message_for("timestamps", "unavailable")
    assert "未连接" in msg
    assert "ℹ" in msg


def test_empty_timestamps_message():
    """测试空时间戳消息"""
    assert "框架" in EMPTY_TIMESTAMPS_MESSAGE
    assert "ℹ" in EMPTY_TIMESTAMPS_MESSAGE


def test_generate_timestamps_prompt_uses_part_relative_seconds():
    """分P视频的 AI 时间戳必须要求使用当前分P内秒数。"""
    source = VideoNoteSource(
        bvid="BV1234567890",
        cid=222,
        title="合集视频 P2/4: 第二讲",
        original_title="合集视频",
        folder_title="测试收藏夹",
        owner_name="测试UP主",
        duration=540,
        pic_url=None,
        description=None,
        source_binding_id=1,
        content="这是第二讲的字幕内容",
        outline=[],
        page_number=2,
        part_title="第二讲",
        total_parts=4,
    )

    messages = build_ai_edit_messages(
        VideoNote(blocks_json=[]),
        VideoNoteAiEditRequest(
            action="generate_timestamps",
            instruction="生成时间戳",
            selected_block_ids=[],
        ),
        source,
    )

    prompt = messages[-1]["content"]
    assert "当前分P：P2/4" in prompt
    assert "time 必须是当前分P内的秒数" in prompt
    assert "不要累计前面分P的时长" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
