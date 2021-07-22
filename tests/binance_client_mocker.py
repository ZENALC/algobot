"""
Mock the Binance client for tests.
"""
from typing import Dict, List, Union


class BinanceMockClient:
    """
    Binance client mocker class.
    """

    @staticmethod
    def get_symbol_info(symbol: str):
        """
        Mock symbol info in Binance client.
        :param symbol: Symbol for which to get information.
        :return: Dictionary with symbol information.
        """
        return {
            'symbol': symbol,
            'filters': [
                {
                    'tickSize': '0.001000000'
                }
            ]
        }

    @staticmethod
    def get_klines(**_):
        """
        Mock the get_klines function in Binance client.
        :return: List containing the klines information.
        """
        return [
            ['03/06/2021 01:43 AM', '3.772', '3.776', '3.772', '3.776', '1640.75', '1614995039999.0',
             '6192.345082', '25.0', '1635.85']
        ]

    @staticmethod
    def get_all_tickers() -> List[Dict[str, str]]:
        """
        Mock the get all tickers function.
        :return: List of dictionaries with symbol information.
        """
        return [
            {"symbol": "BTCUSDT", "price": '31123.78'},
            {"symbol": "ETHUSDT", "price": '1994.75'},
            {"symbol": "YFIUSDT", "price": '28286.15'},
            {"symbol": "LUNAUSDT", "price": '6.940'},
            {"symbol": "XRPUSDT", "price": '0.5710'},
            {"symbol": "DOGEUSDT", "price": '0.19326'},
        ]

    def get_symbol_ticker(self, symbol: str = None) -> Union[Dict[str, str], List[Dict[str, str]]]:
        """
        Mock the get symbol ticker function.
        :param symbol: Symbol to get information of.
        :return: List of symbol information if no symbol is provider or symbol information if symbol is provided.
        """
        symbols = self.get_all_tickers()

        if symbol is None:
            return symbols

        for sym in symbols:
            if sym['symbol'] == symbol:
                return sym

        raise ValueError("Invalid symbol.")

    @staticmethod
    def _get_earliest_valid_timestamp(**_) -> int:
        """
        Mock the get earliest valid timestamp function and return some arbitrary big number.
        :return: Arbitrary timestamp.
        """
        return 1502942400000
