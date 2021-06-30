"""
Initialization file.
"""

from algobot.helpers import get_current_version, get_latest_version, get_logger

MAIN_LOGGER = get_logger(log_file='algobot', logger_name='algobot')

CURRENT_VERSION = get_current_version()
LATEST_VERSION = get_latest_version()
