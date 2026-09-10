from app.models import VideoNote
from app.schemas.video_notes import VideoNoteAiEditRequest
from app.services.video_note_ai_suggestions import (
    build_ai_edit_suggestions,
    build_summary_suggestions,
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
        "outline": [
            {
                "title": "开场",
                "timestamp": 12,
                "points": [{"content": "介绍学习目标", "timestamp": 24}],
            }
        ],
    }
    values.update(overrides)
    return VideoNoteSource(**values)


def _operations(response) -> list[dict]:
    return [
        operation.model_dump(exclude_none=True) for operation in response.operations
    ]


def test_summary_suggestions_clean_ai_payload_and_keep_generated_message():
    response = build_summary_suggestions(
        VideoNote(blocks_json=[]),
        _source(),
        ai_payload={
            "summary": "  模型生成的摘要强调先提炼目标，再用问题驱动复盘。  ",
            "key_points": [
                "建立复盘闭环",
                {"text": "建立复盘闭环"},
                {"content": "把结论转为下一步行动"},
                "生成摘要",
            ],
            "tags": ["AI", "ai", "复盘", "  "],
        },
        ai_status="generated",
    )

    assert response.result_source == "ai"
    assert response.message == "✓ AI 已重新生成摘要和关键观点"
    assert response.tag_suggestions == ["AI", "复盘"]
    operations = _operations(response)
    assert operations[0]["block"]["text"] == (
        "模型生成的摘要强调先提炼目标，再用问题驱动复盘。"
    )
    assert operations[1]["block"]["items"] == [
        {"text": "建立复盘闭环"},
        {"text": "把结论转为下一步行动"},
    ]


def test_ai_edit_suggestions_fall_back_to_source_outline_for_timestamps():
    response = build_ai_edit_suggestions(
        VideoNote(blocks_json=[]),
        VideoNoteAiEditRequest(
            action="generate_timestamps",
            instruction="生成时间戳",
            selected_block_ids=[],
        ),
        _source(),
    )

    assert response.result_source == "fallback"
    assert response.message == (
        "ℹ AI 模型未连接，已根据入库内容提供基础建议；配置模型后可获得更好效果"
    )
    assert _operations(response) == [
        {
            "kind": "replace_or_insert_block",
            "target_block_id": "timestamp-outline",
            "block": {
                "id": "timestamp-outline",
                "type": "timestamp_outline",
                "items": [
                    {"time": 12, "text": "开场"},
                    {"time": 24, "text": "介绍学习目标"},
                ],
            },
        }
    ]


def test_ai_edit_suggestions_prefer_bilibili_timestamps_for_timestamp_generation():
    response = build_ai_edit_suggestions(
        VideoNote(blocks_json=[]),
        VideoNoteAiEditRequest(
            action="generate_timestamps",
            instruction="生成时间戳",
            selected_block_ids=[],
        ),
        _source(outline=None),
        bilibili_timestamps=[
            {"time": 32, "text": "官方章节开场"},
            {"time": 118, "text": "官方章节演示"},
        ],
        ai_status="official",
    )

    assert response.result_source == "official"
    assert response.message == "✓ 已根据 B 站官方章节生成时间戳提纲"
    assert _operations(response)[0]["block"]["items"] == [
        {"time": 32, "text": "官方章节开场"},
        {"time": 118, "text": "官方章节演示"},
    ]


def test_ai_edit_suggestions_parse_common_timestamp_aliases_from_ai_payload():
    response = build_ai_edit_suggestions(
        VideoNote(blocks_json=[]),
        VideoNoteAiEditRequest(
            action="generate_timestamps",
            instruction="生成时间戳",
            selected_block_ids=[],
        ),
        _source(outline=[]),
        ai_payload={
            "timestamps": [
                {"start": "01:04", "text": "拆解核心流程"},
                {"from": 118, "title": "总结行动"},
                {"start_time": "00:02:45", "content": "复盘问题"},
            ]
        },
        ai_status="generated",
    )

    assert _operations(response)[0]["block"]["items"] == [
        {"time": 64, "text": "拆解核心流程"},
        {"time": 118, "text": "总结行动"},
        {"time": 165, "text": "复盘问题"},
    ]


def test_ai_edit_suggestions_reject_single_zero_second_timestamp_summary():
    response = build_ai_edit_suggestions(
        VideoNote(blocks_json=[]),
        VideoNoteAiEditRequest(
            action="generate_timestamps",
            instruction="生成时间戳",
            selected_block_ids=[],
        ),
        _source(outline=[]),
        ai_payload={
            "timestamps": [
                {
                    "time": 0,
                    "text": "本视频围绕 CAD 零基础教学梳理核心学习路径",
                }
            ]
        },
        ai_status="generated",
    )

    assert response.message == "ℹ 当前视频暂无可用时间点数据，已生成基础框架"
    assert _operations(response)[0]["block"]["items"] == []


def test_failed_ai_edit_suggestions_report_fallback_result_source():
    response = build_ai_edit_suggestions(
        VideoNote(blocks_json=[]),
        VideoNoteAiEditRequest(
            action="custom_edit",
            instruction="Add a follow-up note",
            selected_block_ids=[],
        ),
        _source(),
        ai_status="failed",
    )

    assert response.result_source == "fallback"
