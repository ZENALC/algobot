"""
Test helper functions.
"""

import time
from typing import Any, Dict

import pytest

from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION
from algobot.helpers import (convert_long_interval, convert_small_interval,
                             get_caller_string, get_data_from_parameter,
                             get_elapsed_time, get_label_string,
                             get_normalized_data, get_ups_and_downs,
                             parse_strategy_name)


@pytest.mark.parametrize(
    'interval, expected',
    [
        ("1m", "1 Minute"),
        ("8h", "8 Hours")
    ]
)
def test_convert_small_interval(interval: str, expected: str):
    """
    Test conversions from small interval to big interval.
    :param interval: Small interval.
    :param expected: Converted big interval.
    """
    assert convert_small_interval(interval) == expected, f"Expected converted interval to be: {expected}."


@pytest.mark.parametrize(
    'interval, expected',
    [
        ("1 Minute", "1m"),
        ("8 Hours", "8h")
    ]
)
def test_convert_long_interval(interval: str, expected: str):
    """
    Test conversions from big interval to small interval.
    :param interval: Big interval.
    :param expected: Converted small interval.
    """
    assert convert_long_interval(interval) == expected, f"Expected converted interval to be: {expected}."


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
    """
    Test get label string functionality.
    :param label: Label to convert.
    :param expected: Expected converted label.
    """
    assert get_label_string(label) == expected, f"Expected label string to be: {expected}."


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
    """
    Test get caller string functionality.
    :param caller: Caller int.
    :param expected: Expected caller string.
    """
    assert get_caller_string(caller) == expected, f"Expected caller string to be: {expected}."


@pytest.mark.parametrize(
    'data, parameter, expected',
    [
        ({"high": 5, "low": 3}, 'high/low', 4),
        ({'open': 5, 'close': 5}, 'open/close', 5),
        ({'high': 5}, 'high', 5)
    ]
)
def test_get_data_from_parameter(data: Dict[str, Any], parameter: str, expected: float):
    """
    Test get data from parameter functionality.
    :param data: Data dictionary to use.
    :param parameter: Parameter from data dictionary.
    :param expected: Expected data.
    """
    assert get_data_from_parameter(data, parameter) == expected, f"Expected data to be: {expected}."


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
    """
    Test get normalized data functionality.
    """
    assert get_normalized_data(data, date_in_utc) == expected, f"Expected normalized data to be: {expected}."


@pytest.mark.parametrize(
    'data, parameter, expected',
    [
        (
            [{'high': 5}, {'high': 4}, {'high': 8}, {'high': 6}, {'high': 9}, {'high': 10}], 'high',
            ([0, 0, 4, 0, 3, 1], [0, 1, 0, 2, 0, 0])
        )
    ]
)
def test_get_ups_and_downs(data, parameter, expected):
    """
    Test get ups and down functionality.
    """
    assert get_ups_and_downs(data, parameter) == expected, f"Expected ups and downs to be: {expected}."


@pytest.mark.parametrize(
    'elapsed, expected',
    [
        (time.time() - 30, ("30 seconds", "31 seconds", "32 seconds")),
        (time.time() - 60, ("60 seconds", "1m 1s", "1m 2s")),
        (time.time() - 3600, ("60m 0s", "1h 0m 1s", "1h 0m 2s")),
        (time.time() - 3601, ("1h 0m 1s", "1h 0m 2s", "1h 0m 3s"))
    ]
)
def test_get_elapsed_time(elapsed, expected):
    """
    Test get elapsed time functionality.
    :param elapsed: Elapsed time.
    :param expected: Expected parsed elapsed time.
    """
    assert get_elapsed_time(elapsed) in expected, f"Expected elapsed time to be in: {expected}."


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Camel Case Strategy", "camelCaseStrategy"),
        ("strategy", "strategy"),
        ("Moving Average Strategy", "movingAverageStrategy")
    ]
)
def test_parse_strategy_name(name, expected):
    """
    Test parse strategy name functionality.
    :param name: Strategy name.
    :param expected: Parsed strategy name to be expected.
    """
    assert parse_strategy_name(name) == expected, f"Expected parsed strategy to be: {expected}."
