"""
Test data object.

TODO: Write more tests.
"""
import pytest
import pytest_socket

from algobot.data import Data
from tests.utils_for_tests import does_not_raise


@pytest.fixture(name="data_object")
def get_data_object() -> Data:
    """
    TODO: Remove the enable socket() and mock connection.
    Fixture to get the data object.
    :return: Data object.
    """
    pytest_socket.enable_socket()
    return Data(interval='1h', symbol='YFIUSDT', loadData=True)


def test_initialization(data_object: Data):
    """
    TODO: Actually test it. This is doing nothing.

    Test data object initialization.
    :param data_object: Data object to check if initialized properly.
    """
    assert data_object.data is not None, "Data was not initialized properly."


@pytest.mark.parametrize(
    'interval, expectation',
    [
        ['15m', does_not_raise()],
        ['30m', does_not_raise()],
        ['51m', pytest.raises(ValueError)]
    ]
)
def test_validate_interval(data_object: Data, interval: str, expectation):
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
        ['BAD', pytest.raises(ValueError)]
    ]
)
def test_validate_symbol(data_object: Data, symbol: str, expectation):
    """
    Test validate symbol function.
    :param data_object: Data object to leverage to check symbol validation.
    :param symbol: Symbol to check if function handles correctly.
    :param expectation: Expectation of function.
    """
    with expectation:
        data_object.validate_symbol(symbol)
