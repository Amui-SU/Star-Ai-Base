import pytest

from app.models import VideoNote
from app.services.video_note_markdown import (
    _format_timestamp,
    render_video_note_markdown,
)
from app.services.video_note_presenters import VideoNoteSource


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (204, "03:24"),
        (204.9, "03:24"),
        (3723, "01:02:03"),
        (360000.9, "100:00:00"),
        (-1, "00:00"),
        ("invalid", "00:00"),
        ("204", "00:00"),
        (True, "00:00"),
        (float("nan"), "00:00"),
        (float("inf"), "00:00"),
        (float("-inf"), "00:00"),
        (None, "00:00"),
    ],
)
def test_format_timestamp_uses_adaptive_time_segments(value, expected):
    assert _format_timestamp(value) == expected


def test_render_markdown_normalizes_timestamp_labels_and_links_together():
    values = ["invalid", "204", True, float("nan"), float("inf"), float("-inf")]
    note = VideoNote(
        title="Timestamp boundaries",
        bvid="BV1timestamp",
        knowledge_base_id=1,
        tags_json=[],
        blocks_json=[
            {
                "type": "timestamp_outline",
                "items": [
                    {"time": value, "text": f"Invalid {index}"}
                    for index, value in enumerate(values)
                ],
            }
        ],
    )
    source = VideoNoteSource(
        bvid="BV1timestamp",
        cid=None,
        title="Timestamp boundaries",
        original_title="Timestamp boundaries",
        folder_title=None,
        owner_name=None,
        duration=None,
        pic_url=None,
        description=None,
        source_binding_id=None,
        content=None,
        outline=None,
    )

    markdown = render_video_note_markdown(note, source)

    for index in range(len(values)):
        assert f"- [00:00]({source.url}?t=0) Invalid {index}" in markdown
