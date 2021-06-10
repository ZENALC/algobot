import pytest

from algobot.helpers import convert_long_interval, convert_small_interval


@pytest.mark.parametrize(
    'interval, expected',
    [
        ("1m", "1 Minute"),
        ("8h", "8 Hours")
    ]
)
def test_convert_small_interval(interval: str, expected: str):
    assert convert_small_interval(interval) == expected


@pytest.mark.parametrize(
    'interval, expected',
    [
        ("1 Minute", "1m"),
        ("8 Hours", "8h")
    ]
)
def test_convert_long_interval(interval: str, expected: str):
    assert convert_long_interval(interval) == expected
