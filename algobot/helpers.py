"""
Miscellaneous helper functions and constants.
"""

import json
import logging
import math
import os
import platform
import random
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
from dateutil import parser

import algobot
from algobot.typing_hints import DictType

LOG_FOLDER = 'Logs'
STRATEGIES_FOLDER = 'Strategies'

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(BASE_DIR)
STRATEGIES_DIR = os.path.join(ROOT_DIR, STRATEGIES_FOLDER)
LOG_DIR = os.path.join(ROOT_DIR, LOG_FOLDER)

SHORT_INTERVAL_MAP = {
    '1m': '1 Minute',
    '3m': '3 Minutes',
    '5m': '5 Minutes',
    '15m': '15 Minutes',
    '30m': '30 Minutes',
    '1h': '1 Hour',
    '2h': '2 Hours',
    '4h': '4 Hours',
    '6h': '6 Hours',
    '8h': '8 Hours',
    '12h': '12 Hours',
    '1d': '1 Day',
    '3d': '3 Days'
}

LONG_INTERVAL_MAP = {v: k for k, v in SHORT_INTERVAL_MAP.items()}


def get_latest_version() -> str:
    """
    Gets the latest Algobot version from GitHub.
    :return: Latest version.
    """
    url = 'https://raw.githubusercontent.com/ZENALC/algobot/master/version.txt'
    try:
        response = requests.get(url, timeout=3)
        version = response.content.decode().strip()
    except Exception as e:
        algobot.MAIN_LOGGER.exception(repr(e))
        version = 'unknown'
    return version


def get_current_version() -> str:
    """
    Reads version from version.txt and returns it.
    """
    version_file = os.path.join(ROOT_DIR, 'version.txt')

    if not os.path.isfile(version_file):
        version = 'not found'
    else:
        with open(version_file, encoding='utf-8') as f:
            version = f.read().strip()

    return version


def is_debug() -> bool:
    """
    Returns a boolean whether Algobot is running in debug mode or not.
    :return: Boolean whether in debug mode or not.
    """
    return os.getenv('DEBUG') is not None


def get_random_color() -> str:
    """
    Returns a random HEX color string.
    :return: HEX color string.
    """
    def random_integer():
        """
        Generates a random integer between 0 and 255 and returns in a hexadecimal format.
        :return: Hexadecimal between 0 and 255.
        """
        random_int = random.randint(0, 255)
        return format(random_int, '02x')

    return random_integer() + random_integer() + random_integer()


def open_folder(folder: str):
    """
    This will open a folder even if it doesn't exist. It'll create one if it doesn't exist.
    """
    target_path = create_folder(folder)
    open_file_or_folder(target_path)


def create_folder(folder: str) -> str:
    """
    This will create a folder if needed in the root directory and return the full path of the directory created.
    :param folder: Folder to create in the root directory.
    :return: Path to the directory.
    """
    target_path = os.path.join(ROOT_DIR, folder)
    create_folder_if_needed(target_path)

    return target_path


def create_folder_if_needed(target_path: str, base_path: str = ROOT_DIR) -> bool:
    """
    This function will create the appropriate folders in the root folder if needed.
    :param target_path: Target path to have exist.
    :param base_path: Base path to start from. By default, it'll be the root directory.
    :return: Boolean whether folder was created or not.
    """
    if not os.path.exists(target_path):
        folder = os.path.basename(target_path)
        os.mkdir(os.path.join(base_path, folder))
        return True
    return False


def open_file_or_folder(target_path: str):
    """
    Opens a file or folder based on targetPath.
    :param target_path: File or folder to open with system defaults.
    """
    # pylint: disable=consider-using-with, no-member
    if platform.system() == "Windows":
        os.startfile(target_path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", target_path])
    else:
        subprocess.Popen(["xdg-open", target_path])


def setup_and_return_log_path(file_name: str) -> str:
    """
    Creates folders (if needed) and returns default log path.
    :param file_name: Log filename to be created.
    :return: Absolute path to log file.
    """
    if not os.path.exists(LOG_DIR):
        os.mkdir(LOG_DIR)

    today_date = datetime.today().strftime('%Y-%m-%d')
    log_date_folder = os.path.join(LOG_DIR, today_date)
    if not os.path.exists(log_date_folder):
        os.mkdir(log_date_folder)

    log_file_name = f'{datetime.now().strftime("%H-%M-%S")}-{file_name}.log'
    return os.path.join(log_date_folder, log_file_name)


def get_logger(log_file: str, logger_name: str) -> logging.Logger:
    """
    Returns a logger object with loggerName provided and that'll log to log_file.
    :param log_file: File to log to.
    :param logger_name: Name logger will have.
    :return: A logger object.
    """
    logger = logging.getLogger(logger_name)
    log_level = logging.INFO

    if is_debug():
        log_level = logging.DEBUG

    logger.setLevel(log_level)
    formatter = logging.Formatter('%(message)s')
    handler = logging.FileHandler(filename=setup_and_return_log_path(file_name=log_file), delay=True)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logging_object(enable_logging: bool,
                       log_file: str,
                       logger_object: logging.Logger) -> Optional[logging.Logger]:
    """
    Returns a logger object.
    :param enable_logging: Boolean that determines whether logging is enabled or not.
    :param log_file: File to log to.
    :param logger_object: Logger object to return if there is one already specified.
    :return: Logger object or None.
    """
    if logger_object:
        return logger_object

    if enable_logging:
        return get_logger(log_file=log_file, logger_name=log_file)

    return None


def get_ups_and_downs(data: List[Dict[str, float]], parameter: str) -> Tuple[list, list]:
    """
    Returns lists of ups and downs from given data and parameter.
    :param data: List of dictionaries from which we get the ups and downs.
    :param parameter: Parameter from which data is retrieved.
    :return: Tuple of list of ups and downs.
    """
    ups = [0]
    downs = [0]
    previous = data[0]

    for period in data[1:]:
        if period[parameter] > previous[parameter]:
            ups.append(period[parameter] - previous[parameter])
            downs.append(0)
        else:
            ups.append(0)
            downs.append(previous[parameter] - period[parameter])
        previous = period

    return ups, downs


def get_elapsed_time(starting_time: float) -> str:
    """
    Returns elapsed time in human readable format subtracted from starting time.
    :param starting_time: Starting time to subtract from current time.
    :return: Human readable string representing elapsed time.
    """
    seconds = int(time.time() - starting_time)
    if seconds <= 60:
        return f'{seconds} seconds'
    elif seconds <= 3600:
        minutes = seconds // 60
        seconds = seconds % 60
        return f'{minutes}m {seconds}s'
    else:
        hours = seconds // 3600
        seconds = seconds % 3600
        minutes = seconds // 60
        seconds = seconds % 60
        return f'{hours}h {minutes}m {seconds}s'


def get_data_from_parameter(data: DictType, parameter: str) -> float:
    """
    Helper function for trading. Will return appropriate data from parameter passed in.
    :param data: Dictionary data with parameters.
    :param parameter: Data parameter to return.
    :return: Appropriate data to return.
    """
    if parameter == 'high/low':
        return (data['high'] + data['low']) / 2
    elif parameter == 'open/close':
        return (data['open'] + data['close']) / 2
    else:
        return data[parameter]


def get_caller_string(caller: str):
    """
    Returns the string of the caller provided. This should be changed to enums soon.
    :param caller: Caller enum.
    """
    return caller.lower()


def get_label_string(label: str) -> str:
    """
    Returns prettified string from a camel case formatted string.
    :param label: Potential string in camel case format.
    :return: Camel-case string.
    """
    label = str(label)

    if label.isupper():
        return label

    if not label[0].isupper():
        separated = re.sub('([A-Z][a-z]+)', r' \1', re.sub('([A-Z]+)', r' \1', label)).split()
        separated = list(map(lambda word: word.capitalize(), separated))
        label = ' '.join(separated)
    return label


def get_interval_minutes(interval: Union[int, str], reverse: bool = False) -> Union[int, str]:
    """
    Returns amount of minutes from interval provided.
    :param reverse: Reverse if you want interval from minutes instead.
    :param interval: Interval to get the amount of minutes of.
    """
    intervals = {
        '12 Hours': 720,
        '15 Minutes': 15,
        '1 Day': 1440,
        '1 Hour': 60,
        '1 Minute': 1,
        '2 Hours': 120,
        '30 Minutes': 30,
        '3 Days': 4320,
        '3 Minutes': 3,
        '4 Hours': 240,
        '5 Minutes': 5,
        '6 Hours': 360,
        '8 Hours': 480
    }

    if reverse:
        intervals = {v: k for k, v in intervals.items()}

    return intervals[interval]


def get_interval_strings(starting_index: int = 0) -> List[str]:
    """
    Returns interval strings in a sorted format.
    :param starting_index: Index to start getting interval strings from.
    :return: Strings in descending format.
    """
    return ['1 Minute',
            '3 Minutes',
            '5 Minutes',
            '15 Minutes',
            '30 Minutes',
            '1 Hour',
            '2 Hours',
            '4 Hours',
            '6 Hours',
            '8 Hours',
            '12 Hours',
            '1 Day',
            '3 Days'][starting_index:]


def parse_strategy_name(name: str) -> str:
    """
    Parses strategy name to camelCase for use with strategies.
    :param name: Name of strategy to be parsed.
    :return: Parsed strategy name.
    """
    parsed_name, *remaining = name.split()
    parsed_name = parsed_name.lower()
    for remaining_name in remaining:
        parsed_name += remaining_name.capitalize()

    return parsed_name


def convert_str_to_utc_datetime(str_datetime: str) -> datetime:
    """
    Convert string datetime to actual datetime object in UTC.
    :param str_datetime: Datetime in string.
    :return: Datetime object.
    """
    return parser.parse(str_datetime).replace(tzinfo=timezone.utc)


def get_normalized_data(data: List[str], parse_date: bool = False) -> Dict[str, Union[str, float]]:
    """
    Normalize data provided and return as an appropriate dictionary.
    :param data: Data to normalize into a dictionary.
    :param parse_date: Boolean whether to parse date or not if date in UTC is not provided.
    """
    date_in_utc = convert_str_to_utc_datetime(data[0]) if parse_date else data[0]
    return {
        'date_utc': date_in_utc,
        'open': float(data[1]),
        'high': float(data[2]),
        'low': float(data[3]),
        'close': float(data[4]),
        'volume': float(data[5]),
        'quote_asset_volume': float(data[6]),
        'number_of_trades': float(data[7]),
        'taker_buy_base_asset': float(data[8]),
        'taker_buy_quote_asset': float(data[9]),
    }


def convert_small_interval(interval: str) -> str:
    """
    Converts smaller interval string to longer interval string.
    :param interval: Small interval string.
    :return: Longer interval string.
    """
    return SHORT_INTERVAL_MAP[interval]


def convert_long_interval(interval: str) -> str:
    """
    Converts longer interval string to smaller interval string.
    :param interval: Long interval string.
    :return: Smaller interval string.
    """
    return LONG_INTERVAL_MAP[interval]


def convert_all_dates_to_datetime(data: List[Dict[str, Union[float, str, datetime]]]):
    """
    Converts all available dates in the data list of dictionaries to datetime objects.
    :param data: List of data in which to convert string dates to datetime objects.
    """
    if isinstance(data[0]['date_utc'], datetime):
        return

    for entry in data:
        entry['date_utc'] = parser.parse(entry['date_utc'])


def load_from_csv(path: str, descending: bool = True) -> List[Dict[str, Union[float, str]]]:
    """
    Returns data from CSV in a list of dictionaries.
    :param path: Path to CSV file.
    :param descending: Boolean representing whether data is returned in descending or ascending format by date.
    :return: List of dictionaries containing open, high, low, close, and date information.
    """
    df = pd.read_csv(path)
    df.columns = [col.lower().strip() for col in df.columns]  # To support backwards compatibility.
    data = df.to_dict('records')  # pylint: disable=no-member

    first_date = parser.parse(data[0]['date_utc'])  # Retrieve first date from CSV data.
    last_date = parser.parse(data[-1]['date_utc'])  # Retrieve last date from CSV data.

    if descending and first_date < last_date:
        return data[::-1]

    if not descending and first_date > last_date:
        return data[::-1]

    return data


def parse_precision(precision: str, symbol: str) -> int:
    """
    Parses precision based on the precision provided.
    :param precision: Precision string.
    :param symbol: Symbol to get precision of.
    :return: Precision in an integer format.
    """
    if precision == "Auto":
        symbol_info = algobot.BINANCE_CLIENT.get_symbol_info(symbol)
        tick_size = float(symbol_info['filters'][0]['tickSize'])
        precision = abs(round(math.log(tick_size, 10)))
    return int(precision)


def write_json_file(file_path: str = 'secret.json', **kwargs):
    """
    Writes JSON file with **kwargs provided.
    :param file_path: Path to write **kwargs data to.
    :param kwargs: Dictionary to dump to JSON file.
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(kwargs, f, indent=4)


def load_json_file(json_file: str) -> dict:
    """
    Loads JSON file passed and returns dictionary.
    :param json_file: File to read dictionary from.
    :return: Dictionary with credentials.
    """
    with open(json_file, encoding='utf-8') as f:
        return json.load(f)
