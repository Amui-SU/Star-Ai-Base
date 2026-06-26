from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.time_utils import as_aware_utc, utc_now, utc_now_naive


def test_as_aware_utc_adds_timezone_to_naive_datetime():
    value = datetime(2026, 6, 26, 12, 30, 0)

    result = as_aware_utc(value)

    assert result == datetime(2026, 6, 26, 12, 30, 0, tzinfo=timezone.utc)


def test_as_aware_utc_converts_aware_datetime_to_utc():
    source_tz = timezone(timedelta(hours=8))
    value = datetime(2026, 6, 26, 20, 30, 0, tzinfo=source_tz)

    result = as_aware_utc(value)

    assert result == datetime(2026, 6, 26, 12, 30, 0, tzinfo=timezone.utc)


def test_utc_now_helpers_return_expected_timezone_shapes():
    assert utc_now().tzinfo is not None
    assert utc_now_naive().tzinfo is None


def test_business_code_uses_central_utc_helpers():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in sorted(app_dir.rglob("*.py")):
        if path.name == "time_utils.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "datetime.now(timezone.utc)" in text:
            offenders.append(path.relative_to(app_dir).as_posix())

    assert offenders == []
