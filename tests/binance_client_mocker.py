"""
Mock the Binance client for tests.
"""
from typing import List, Dict


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
                    'tickSize': 1000
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
            ["03/06/2021 01:43 AM", 3.772, 3.776, 3.772, 3.776, 1640.75, 1614995039999.0, 6192.345082, 25.0, 1635.85]
        ]

    @staticmethod
    def get_all_tickers() -> List[Dict[str, str]]:
        """
        Mock the get all tickers function.
        :return: List of dictionaries with symbol information.
        """
        return [
            {"symbol": "BTCUSDT"},
            {"symbol": "ETHUSDT"},
            {"symbol": "YFIUSDT"},
            {"symbol": "LUNAUSDT"},
            {"symbol": "XRPUSDT"},
            {"symbol": "DOGEUSDT"},
        ]
