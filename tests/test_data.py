"""
Test data object.
"""
import filecmp
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Callable, Dict, List, Union
from unittest import mock

import pytest
from dateutil import parser

from algobot.data import Data
from algobot.helpers import ROOT_DIR, SHORT_INTERVAL_MAP, convert_str_to_utc_datetime, get_normalized_data
from tests.binance_client_mocker import BinanceMockClient
from tests.utils_for_tests import does_not_raise

INTERVAL = '1h'
TICKER = 'ALGOBOTUSDT'

DATABASE_FILE = f'{TICKER}.db'
DATABASE_TABLE = "data_1h"
DATABASE_FILE_PATH = os.path.join(ROOT_DIR, "Databases", DATABASE_FILE)


def remove_test_data():
    """
    Remove test data.
    """
    if os.path.isfile(DATABASE_FILE_PATH):
        os.remove(DATABASE_FILE_PATH)


def get_csv_data(headers: bool = False) -> List[str]:
    """
    Open and get CSV data.
    :param headers: Boolean for whether you want the headers in the list of data or not.
    """
    data_file = os.path.join(ROOT_DIR, 'tests', 'data', 'small_csv_data.csv')
    with open(data_file, 'r', encoding='utf-8') as f:
        index = 0 if headers else 1
        return f.readlines()[index:]


def get_normalized_csv_data() -> List[Dict[str, Union[float, datetime]]]:
    """
    Get normalized CSV data in typical Algobot fashion.
    :return: Normalized list of dictionaries.
    """
    csv_data = get_csv_data(headers=False)
    normalized_data = []
    for data in csv_data:
        split_data = data.split(',')
        normalized_dict = get_normalized_data(split_data, parse_date=True)
        normalized_data.append(normalized_dict)

    return normalized_data


def insert_test_data_to_database():
    """
    Insert test data into the database.
    """
    total_data = get_csv_data()
    query = f'''INSERT INTO {DATABASE_TABLE} (
                date_utc,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                quote_asset_volume,
                number_of_trades,
                taker_buy_base_asset,
                taker_buy_quote_asset
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);'''

    with closing(sqlite3.connect(DATABASE_FILE_PATH)) as connection:
        with closing(connection.cursor()) as cursor:
            for data in total_data:
                cursor.execute(query, data.split(','))
        connection.commit()


def setup_module():
    """
    Setup module for testing by removing the test DB file.
    """
    remove_test_data()


# def teardown_module():
#     """
#     Teardown module by removing the test DB file.
#     """
#     remove_test_data()


@pytest.fixture(name="data_object", scope="function")
def get_data_object() -> Data:
    """
    Fixture to get a data object with a mocked Binance client.
    :return: Data object.
    """
    with mock.patch('binance.client.Client', BinanceMockClient):
        return Data(interval=INTERVAL, symbol=TICKER, load_data=False)


def test_initialization(data_object: Data):
    """
    Test data object initialization.
    :param data_object: Data object to check if initialized properly.
    """
    assert data_object.data is not None, "Data was not initialized properly."
    assert data_object.database_file == DATABASE_FILE_PATH
    assert data_object.database_table == DATABASE_TABLE


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


def test_create_table(data_object: Data):
    """
    Test to ensure create table works as intended.
    """
    remove_test_data()
    assert os.path.exists(DATABASE_FILE_PATH) is False, f"Expected {DATABASE_FILE_PATH} to not exist for testing."

    data_object.create_table()
    with closing(sqlite3.connect(data_object.database_file)) as connection:
        with closing(connection.cursor()) as cursor:
            table_info = cursor.execute(f'PRAGMA TABLE_INFO({data_object.database_table})').fetchall()

    # Each tuple in table_info contains one column's information like this: (0, 'date_utc', 'TEXT', 0, None, 1)
    expected_columns = {
        'date_utc',
        'open_price',
        'high_price',
        'low_price',
        'close_price',
        'volume',
        'quote_asset_volume',
        'number_of_trades',
        'taker_buy_base_asset',
        'taker_buy_quote_asset'
    }

    table_columns = {col[1] for col in table_info}
    assert table_columns == expected_columns, f"Expected: {expected_columns}. Got: {table_columns}"
    assert all(col[2] == 'TEXT' for col in table_info), "Expected all columns to have the TEXT data type."


def test_get_latest_database_row(data_object: Data):
    """
    Test get latest database row functionality.
    :param data_object: Data object to leverage to test this function.
    """
    data_object.create_table()
    result = data_object.get_latest_database_row()
    assert result == {}, "Expected an empty dictionary."

    insert_test_data_to_database()
    result = data_object.get_latest_database_row()
    expected = {
        'close': 3.7763,
        'date_utc': convert_str_to_utc_datetime('03/06/2021 01:43 AM'),
        'high': 3.7763,
        'low': 3.7729,
        'number_of_trades': 6192.345082,
        'open': 3.7729,
        'quote_asset_volume': 1614995039999.0,
        'taker_buy_base_asset': 25.0,
        'taker_buy_quote_asset': 1635.85,
        'volume': 1640.75
    }
    assert result == expected, f'Expected: {expected}. Got: {result}'


def test_dump_to_table(data_object: Data):
    """
    Testing dumping to table functionality.
    :param data_object: Data object to leverage to test this function.
    """
    remove_test_data()
    data_object.create_table()

    normalized_csv_data = get_normalized_csv_data()
    result = data_object.dump_to_table(normalized_csv_data)
    assert result is True, "Expected all data to dump successfully."

    def get_rows():
        with closing(sqlite3.connect(DATABASE_FILE_PATH)) as connection:
            with closing(connection.cursor()) as cursor:
                db_rows = cursor.execute(f"SELECT * FROM {DATABASE_TABLE} ORDER BY date_utc").fetchall()
                return [get_normalized_data(row, parse_date=True) for row in db_rows]

    rows = get_rows()
    assert normalized_csv_data == rows, "Values entered are not equal."

    # Dumping several, duplicate values multiple times. Nothing should be dumped due to duplicates.
    data_object.dump_to_table(normalized_csv_data)
    data_object.dump_to_table(normalized_csv_data)

    assert len(rows) == len(get_rows()), "Expected count of data to be the same."


def test_get_data_from_database(data_object: Data):
    """
    Test to ensure get data from database works appropriately.
    :param data_object: Data object to leverage to test this function.
    """
    normalized_csv_data = get_normalized_csv_data()

    remove_test_data()
    data_object.create_table()
    data_object.dump_to_table(normalized_csv_data)
    result = data_object.get_data_from_database()

    # Reverse because data is in ascending order whereas CSV data is not.
    assert normalized_csv_data == result, "Expected data to equal."


@pytest.mark.parametrize(
    'data, expected',
    [
        ([], []),
        ([{'date_utc': 1}, {'date_utc': 1}, {'date_utc': 5}], [{'date_utc': 1}]),
        ([{'date_utc': 1}, {'date_utc': 5}], [])
    ]
)
def test_verify_integrity(data_object: Data, data, expected: List[Dict[str, float]]):
    """
    Test verify integrity functionality.
    :param data_object: Data object to leverage to test this function.
    :param data: Data to use to check integrity.
    :param expected: Errored data.
    """
    result = data_object.verify_integrity(data)
    assert result == expected, f"Expected: {expected}. Got: {result}."


@pytest.mark.parametrize(
    'descending, army_time, start_date, expected_file_to_match',
    [
        (False, False, '03/06/2021', 'asc_non_army_middle.csv'),
        (True, False, '03/05/2021', 'desc_non_army_middle.csv'),
    ]
)
def test_create_csv_file(data_object: Data, descending, army_time, start_date, expected_file_to_match):
    """
    Test create CSV file functionality.
    :param data_object: Data object to leverage to test this function.
    :param descending: Boolean that decides whether values in CSV are in descending format or not.
    :param army_time: Boolean that dictates whether dates will be written in army-time format or not.
    :param start_date: Date to have CSV data from.
    """
    remove_test_data()
    data_object.create_table()

    insert_test_data_to_database()
    data_object.data = data_object.get_data_from_database()

    start_date = parser.parse(start_date).date()

    path = data_object.create_csv_file(descending=descending, army_time=army_time, start_date=start_date)
    path_to_equal = os.path.join(ROOT_DIR, 'tests', 'data', 'test_create_csv_file_data', expected_file_to_match)

    assert filecmp.cmp(path, path_to_equal)
