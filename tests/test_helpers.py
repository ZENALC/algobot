"""
Test helper functions.
"""
import os
from typing import Any, Dict, List, Union
from unittest import mock

import pytest

from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION
from algobot.helpers import (ROOT_DIR, convert_long_interval, convert_small_interval, get_caller_string,
                             get_data_from_parameter, get_label_string, get_normalized_data, get_ups_and_downs,
                             load_from_csv, parse_precision, parse_strategy_name)
from tests.binance_client_mocker import BinanceMockClient


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
def test_get_caller_string(caller: str, expected: str):
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
    'data, expected',
    [
        (['01/01/21', 5, 15, 3, 8, 9, 10, 15, 9, 15], {
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
        (['January 1st 2021', 5, 15, 3, 8, 9, 10, 15, 9, 15], {
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
def test_get_normalized_data(data, expected):
    """
    Test get normalized data functionality.
    """
    assert get_normalized_data(data) == expected, f"Expected normalized data to be: {expected}."


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


def helper_for_test_load_from_csv(descending: bool) -> List[Dict[str, Union[str, float]]]:
    """
    Helper function for testing load from CSV.
    :param descending: Boolean whether data is to be returned in descending format or not.
    :return: List of dictionaries containing sample data.
    """
    data = [
        {
            'date_utc': '03/06/2021 01:39 AM',
            'open': 3.7667,
            'close': 3.7754,
            'high': 3.7754,
            'low': 3.7657,
            'number_of_trades': 7788.621466,
            'quote_asset_volume': 1614994799999.0,
            'taker_buy_base_asset': 28.0,
            'taker_buy_quote_asset': 716.76,
            'volume': 2067.17
        },
        {
            'date_utc': '03/06/2021 01:40 AM',
            'open': 3.7751,
            'close': 3.7751,
            'high': 3.7754,
            'low': 3.7751,
            'number_of_trades': 806.036601,
            'quote_asset_volume': 1614994859999.0,
            'taker_buy_base_asset': 3.0,
            'taker_buy_quote_asset': 213.51,
            'volume': 213.51
        },
        {
            'date_utc': '03/06/2021 01:41 AM',
            'open': 3.7749,
            'close': 3.774,
            'high': 3.7753,
            'low': 3.774,
            'number_of_trades': 1297.482873,
            'quote_asset_volume': 1614994919999.0,
            'taker_buy_base_asset': 15.0,
            'taker_buy_quote_asset': 343.73,
            'volume': 343.73
        },
        {
            'date_utc': '03/06/2021 01:42 AM',
            'open': 3.774,
            'close': 3.7732,
            'high': 3.775,
            'low': 3.7688,
            'number_of_trades': 8544.069182,
            'quote_asset_volume': 1614994979999.0,
            'taker_buy_base_asset': 33.0,
            'taker_buy_quote_asset': 360.2,
            'volume': 2263.93
        },
        {
            'date_utc': '03/06/2021 01:43 AM',
            'open': 3.7729,
            'close': 3.7763,
            'high': 3.7763,
            'low': 3.7729,
            'number_of_trades': 6192.345082,
            'quote_asset_volume': 1614995039999.0,
            'taker_buy_base_asset': 25.0,
            'taker_buy_quote_asset': 1635.85,
            'volume': 1640.75
        }
    ]

    return data[::-1] if descending else data


@pytest.mark.parametrize(
    'descending, expected',
    [
        (True, helper_for_test_load_from_csv(descending=True)),
        (False, helper_for_test_load_from_csv(descending=False))
    ]
)
def test_load_from_csv(descending: bool, expected: List[Dict[str, Union[str, float]]]):
    """
    Test load from CSV function works as intended.
    :param descending: Boolean whether data is in descending format or not.
    :param expected: Expected data to return from function.
    """
    data_path = os.path.join(ROOT_DIR, 'tests', 'data/small_csv_data.csv')
    loaded_data = load_from_csv(data_path, descending=descending)

    assert loaded_data == expected, f"Expected: {expected} Got: {loaded_data}"


@pytest.mark.parametrize(
    'precision, expected',
    [
        ('Auto', 3),
        (5, 5),
        (5.1, 5),
        (-5, -5)
    ]
)
def test_parse_precision(precision: Union[str, float, int], expected: int):
    """
    Test parse precision functionality.
    """
    with mock.patch('algobot.BINANCE_CLIENT', BinanceMockClient):
        result = parse_precision(precision=precision, symbol="some_symbol")
        assert result == expected, f"Expected: {expected} | Got: {result}."
