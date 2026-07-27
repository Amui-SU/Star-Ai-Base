import pytest

from app.services.video_note_markdown import _format_timestamp


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (204, "03:24"),
        (3723, "01:02:03"),
        (-1, "00:00"),
        ("invalid", "00:00"),
        ("204", "00:00"),
        (True, "00:00"),
        (float("nan"), "00:00"),
        (None, "00:00"),
    ],
)
def test_format_timestamp_uses_adaptive_time_segments(value, expected):
    assert _format_timestamp(value) == expected
