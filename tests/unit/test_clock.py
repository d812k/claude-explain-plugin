"""SystemClock converts a seconds time source into integer epoch milliseconds."""

from explain_selection.adapters import SystemClock


def test_converts_seconds_to_milliseconds() -> None:
    assert SystemClock(lambda: 1_700_000_000.5).now_ms() == 1_700_000_000_500


def test_truncates_sub_millisecond_fractions() -> None:
    assert SystemClock(lambda: 12.3456).now_ms() == 12_345
