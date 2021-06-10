import pytest

from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION
from algobot.helpers import (convert_long_interval, convert_small_interval,
                             get_caller_string, get_data_from_parameter,
                             get_label_string, get_normalized_data)


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


@pytest.mark.parametrize(
    'data, parameter, expected',
    [
        ({"high": 5, "low": 3}, 'high/low', 4),
        ({'open': 5, 'close': 5}, 'open/close', 5),
        ({'high': 5}, 'high', 5)
    ]
)
def test_get_data_from_parameter(data, parameter, expected):
    assert get_data_from_parameter(data, parameter) == expected


@pytest.mark.parametrize(
    'data, date_in_utc, expected',
    [
        (['01/01/21', 5, 15, 3, 8, 9, 10, 15, 9, 15], None, {
            'date_utc': '01/01/21',
            'open': 5,
            'high': 15,
            'low': 3,
            'close': 8,
            'volume': 9,
            'quote_asset_volume': 10,
            'number_of_trades': 15,
            'taker_buy_base_asset': 9,
            'taker_buy_quote_asset': 15
        }),
        (['01/01/21', 5, 15, 3, 8, 9, 10, 15, 9, 15], "January 1st 2021", {
            'date_utc': 'January 1st 2021',
            'open': 5.0,
            'high': 15.0,
            'low': 3.0,
            'close': 8.0,
            'volume': 9.0,
            'quote_asset_volume': 10.0,
            'number_of_trades': 15.0,
            'taker_buy_base_asset': 9.0,
            'taker_buy_quote_asset': 15.0
        }),
    ]
)
def test_get_normalized_data(data, date_in_utc, expected):
    assert get_normalized_data(data, date_in_utc) == expected
