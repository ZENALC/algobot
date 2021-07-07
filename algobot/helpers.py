import json
import logging
import math
import os
import platform
import random
import re
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Tuple, Union

import requests
from appdirs import AppDirs
from dateutil import parser

import algobot
from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION
from algobot.typing_hints import DICT_TYPE

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(BASE_DIR)

APP_NAME = "algobot"
APP_AUTHOR = "ZENALC"


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


class Paths:

    def __init__(self, app_dirs):
        self.app_dirs = app_dirs

    def get_log_dir(self) -> str:
        return os.path.join(self.app_dirs.user_log_dir, 'Logs')

    def get_database_dir(self) -> str:
        return os.path.join(self.app_dirs.user_data_dir, 'Databases')

    def get_state_path(self) -> str:
        return os.path.join(self.app_dirs.user_data_dir, 'state.json')


PATHS = Paths(AppDirs(APP_NAME, APP_AUTHOR))


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
        with open(version_file) as f:
            version = f.read().strip()

    return version


def is_debug() -> bool:
    return os.getenv('DEBUG') is not None


def get_random_color() -> str:
    """
    Returns a random HEX color string.
    :return: HEX color string.
    """
    def r():
        randomInt = random.randint(0, 255)
        return format(randomInt, '02x')

    return r() + r() + r()


def open_folder(folder: str):
    """
    This will open a folder even if it doesn't exist. It'll create one if it doesn't exist.
    """
    targetPath = create_folder(folder)
    open_file_or_folder(targetPath)


def create_folder(folder: str):
    """
    This will create a folder if needed in the root directory.
    """
    targetPath = os.path.join(ROOT_DIR, folder)
    create_folder_if_needed(targetPath)

    return targetPath


def create_folder_if_needed(targetPath: str, basePath: str = ROOT_DIR) -> bool:
    """
    This function will create the appropriate folders in the root folder if needed.
    :param targetPath: Target path to have exist.
    :param basePath: Base path to start from. By default, it'll be the root directory.
    :return: Boolean whether folder was created or not.
    """
    if not os.path.exists(targetPath):
        folder = os.path.basename(targetPath)
        os.mkdir(os.path.join(basePath, folder))
        return True
    return False


def open_file_or_folder(targetPath: str):
    """
    Opens a file or folder based on targetPath.
    :param targetPath: File or folder to open with system defaults.
    """
    if platform.system() == "Windows":
        os.startfile(targetPath)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", targetPath])
    else:
        subprocess.Popen(["xdg-open", targetPath])


def setup_and_return_log_path(filename: str) -> str:
    """
    Creates folders (if needed) and returns default log path.
    :param filename: Log filename to be created.
    :return: Absolute path to log file.
    """
    log_dir = PATHS.get_log_dir()
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    today_date = datetime.today().strftime('%Y-%m-%d')
    log_date_folder = os.path.join(log_dir, today_date)
    if not os.path.exists(log_date_folder):
        os.mkdir(log_date_folder)

    log_file_name = f'{datetime.now().strftime("%H-%M-%S")}-{filename}.log'
    full_path = os.path.join(log_date_folder, log_file_name)
    return full_path


def get_logger(log_file: str, logger_name: str) -> logging.Logger:
    """
    Returns a logger object with loggerName provided and that'll log to logFile.
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
    handler = logging.FileHandler(filename=setup_and_return_log_path(filename=log_file), delay=True)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


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


def get_elapsed_time(startingTime: float) -> str:
    """
    Returns elapsed time in human readable format subtracted from starting time.
    :param startingTime: Starting time to subtract from current time.
    :return: Human readable string representing elapsed time.
    """
    seconds = int(time.time() - startingTime)
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


def get_data_from_parameter(data: DICT_TYPE, parameter: str) -> float:
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


def get_caller_string(caller: int):
    """
    Returns the string of the caller provided. This should be changed to enums soon.
    :param caller: Caller enum.
    """
    if caller == LIVE:
        return 'live'
    elif caller == SIMULATION:
        return 'simulation'
    elif caller == BACKTEST:
        return 'backtest'
    elif caller == OPTIMIZER:
        return 'optimizer'
    else:
        raise ValueError("Invalid type of caller specified.")


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


def get_interval_minutes(interval: str) -> int:
    """
    Returns amount of minutes from interval provided.
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
    return intervals[interval]


def get_interval_strings(startingIndex: int = 0) -> List[str]:
    """
    Returns interval strings in a sorted format.
    :param startingIndex: Index to start getting interval strings from.
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
            '3 Days'][startingIndex:]


def parse_strategy_name(name: str) -> str:
    """
    Parses strategy name to camelCase for use with strategies.
    :param name: Name of strategy to be parsed.
    :return: Parsed strategy name.
    """
    parsed_name, *remaining = name.split()
    parsed_name = parsed_name.lower()
    for name in remaining:
        parsed_name += name.capitalize()

    return parsed_name


def get_normalized_data(data: List[str], date_in_utc: Union[str, datetime] = None) -> Dict[str, Union[str, float]]:
    """
    Normalize data provided and return as an appropriate dictionary.
    :param data: Data to normalize into a dictionary.
    :param date_in_utc: Optional date to use (if provided). If not provided, it'll use the first element from data.
    """
    return {
        'date_utc': date_in_utc if date_in_utc is not None else data[0],
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


def load_from_csv(path: str, descending: bool = True) -> list:
    """
    Returns data from CSV.
    :param path: Path to CSV file.
    :param descending: Boolean representing where data is return in descending or ascending format.
    :return: List of data.
    """
    with open(path) as f:
        data = []
        readLines = f.readlines()
        headers = list(map(str.lower, readLines[0].rstrip().split(', ')))
        for line in readLines[1:]:
            line = line.rstrip()  # strip newline character
            splitLine = line.split(',')
            splitLine = [line.strip() for line in splitLine]
            data.append({
                headers[0]: splitLine[0],  # date in UTC
                headers[1]: float(splitLine[1]),  # open
                headers[2]: float(splitLine[2]),  # high
                headers[3]: float(splitLine[3]),  # low
                headers[4]: float(splitLine[4]),  # close
                headers[5]: float(splitLine[5]),  # volume
            })
        firstDate = parser.parse(data[0]['date_utc'])  # Retrieve first date from CSV data.
        lastDate = parser.parse(data[-1]['date_utc'])  # Retrieve last date from CSV data.
        if descending:
            if firstDate < lastDate:
                return data[::-1]
            return data
        else:  # This assumes the sort is ascending.
            if firstDate > lastDate:
                return data[::-1]
            return data


def parse_precision(precision: str, symbol: str) -> int:
    if precision == "Auto":
        symbol_info = algobot.BINANCE_CLIENT.get_symbol_info(symbol)
        tickSize = float(symbol_info['filters'][0]['tickSize'])
        precision = abs(round(math.log(tickSize, 10)))
    return int(precision)


def write_json_file(filePath: str = 'secret.json', **kwargs):
    """
    Writes JSON file with **kwargs provided.
    :param filePath: Path to write **kwargs data to.
    :param kwargs: Dictionary to dump to JSON file.
    """
    with open(filePath, 'w') as f:
        json.dump(kwargs, f, indent=4)


def load_json_file(jsonfile: str) -> dict:
    """
    Loads JSON file passed and returns dictionary.
    :param jsonfile: File to read dictionary from.
    :return: Dictionary with credentials.
    """
    with open(jsonfile) as f:
        return json.load(f)
