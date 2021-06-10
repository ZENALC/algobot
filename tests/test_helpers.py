import pytest

from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION
from algobot.helpers import (convert_long_interval, convert_small_interval,
                             get_caller_string, get_label_string)


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


@pytest.mark.parametrize(
    "label, expected",
    [
        ("helloWorld", "Hello World"),
        ("HELLO", "HELLO"),
        (150, "150"),
        ("Hello world", "Hello world"),
        ("testHelloWorld", "Test Hello World")
    ]
)
def test_get_label_string(label: str, expected: str):
    assert get_label_string(label) == expected


@pytest.mark.parametrize(
    'caller, expected',
    [
        (OPTIMIZER, "optimizer"),
        (SIMULATION, "simulation"),
        (BACKTEST, "backtest"),
        (LIVE, "live"),
    ]
)
def test_get_caller_string(caller: int, expected: str):
    assert get_caller_string(caller) == expected
