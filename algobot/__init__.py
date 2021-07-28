"""
Initialization file.
"""
from binance import Client

from algobot.helpers import get_current_version, get_latest_version, get_logger

MAIN_LOGGER = get_logger(log_file='algobot', logger_name='algobot')

CURRENT_VERSION = get_current_version()
LATEST_VERSION = get_latest_version()

try:
    BINANCE_CLIENT = Client()
except Exception as e:
    MAIN_LOGGER.exception(repr(e))
    BINANCE_CLIENT = None
