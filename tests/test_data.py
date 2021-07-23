"""
Test data object.
"""

import os
import re
from typing import Callable
from unittest import mock

import pytest

from algobot.data import Data
from algobot.helpers import ROOT_DIR, SHORT_INTERVAL_MAP
from tests.binance_client_mocker import BinanceMockClient
from tests.utils_for_tests import does_not_raise

INTERVAL = '1h'
ALGOBOT_TICKER = "ALGOBOTUSDT"

DATABASE_FILE = "ALGOBOTUSDT.db"
DATABASE_FILE_PATH = os.path.join(ROOT_DIR, "Databases", DATABASE_FILE)


def setup_module():
    """
    Setup module for testing by removing the test DB file.
    """
    if os.path.isfile(DATABASE_FILE_PATH):
        os.remove(DATABASE_FILE_PATH)


# def teardown_module():
#     """
#     Teardown module by removing the test DB file.
#     """
#     if os.path.isfile(DATABASE_FILE_PATH):
#         os.remove(DATABASE_FILE_PATH)


@pytest.fixture(name="data_object")
def get_data_object() -> Data:
    """
    Fixture to get a data object with a mocked Binance client.
    :return: Data object.
    """
    with mock.patch('binance.client.Client', BinanceMockClient):
        return Data(interval=INTERVAL, symbol=ALGOBOT_TICKER, load_data=False)


def test_initialization(data_object: Data):
    """
    Test data object initialization.
    :param data_object: Data object to check if initialized properly.
    """
    assert data_object.data is not None, "Data was not initialized properly."
    assert data_object.databaseFile == DATABASE_FILE_PATH
    assert data_object.databaseTable == 'data_1h'


@pytest.mark.parametrize(
    'interval, expectation',
    [
        ['15m', does_not_raise()],
        ['30m', does_not_raise()],
        ['51m', pytest.raises(ValueError, match=re.escape(f'Invalid interval 51m given. Available intervals are: '
                                                          f'\n{SHORT_INTERVAL_MAP.keys()}'))]
    ]
)
def test_validate_interval(data_object: Data, interval: str, expectation: Callable):
    """
    Test validate interval function.
    :param data_object: Data object to leverage to check interval validation.
    :param interval: Interval to check if function handles correctly.
    :param expectation: Expectation of function.
    """
    with expectation:
        data_object.validate_interval(interval)


@pytest.mark.parametrize(
    'symbol, expectation',
    [
        ['BTCUSDT', does_not_raise()],
        ['YFIUSDT', does_not_raise()],
        ['   ', pytest.raises(ValueError, match="No symbol/ticker found.")],
        ['BAD', pytest.raises(ValueError, match="Invalid symbol/ticker BAD provided.")]
    ]
)
def test_validate_symbol(data_object: Data, symbol: str, expectation: Callable):
    """
    Test validate symbol function.
    :param data_object: Data object to leverage to check symbol validation.
    :param symbol: Symbol to check if function handles correctly.
    :param expectation: Expectation of function.
    """
    with expectation:
        data_object.validate_symbol(symbol)


@pytest.mark.parametrize(
    'symbol, expected',
    [
        ('BTCUSDT', True),
        ('DOGEUSDT', True),
        ('BANANAUSDT', False)
    ]
)
def test_is_valid_symbol(data_object: Data, symbol: str, expected: bool):
    """
    Test to ensure is_valid_symbol works as intended.
    :param data_object: Data object to leverage to check symbol validation.
    :param symbol: Symbol value.
    :param expected: Expected value.
    """
    result = data_object.is_valid_symbol(symbol)
    assert result is expected, f"Expected: {expected} | Got: {result}"


def test_get_database_file(data_object: Data):
    """
    Test to ensure get database file works as intended.
    :param data_object: Data object to leverage to test get database file.
    """
    result = data_object.get_database_file()
    assert result == DATABASE_FILE_PATH, f"Expected: {DATABASE_FILE_PATH}. Got: {result}"
