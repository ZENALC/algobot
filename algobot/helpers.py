import json
import logging
import os
import platform
import re
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Tuple, Union

from dateutil import parser

from algobot.option import Option
from algobot.typeHints import DICT_TYPE

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(BASE_DIR)
LOG_FOLDER = 'Logs'


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


def setup_and_return_log_path(fileName: str) -> str:
    """
    Creates folders (if needed) and returns default log path.
    :param fileName: Log filename to be created.
    :return: Absolute path to log file.
    """
    previousPath = os.getcwd()
    os.chdir(ROOT_DIR)

    if not os.path.exists(LOG_FOLDER):
        os.mkdir(LOG_FOLDER)
    os.chdir(LOG_FOLDER)

    todayDate = datetime.today().strftime('%Y-%m-%d')
    if not os.path.exists(todayDate):
        os.mkdir(todayDate)
    os.chdir(todayDate)

    logFileName = f'{datetime.now().strftime("%H-%M-%S")}-{fileName}.log'
    fullPath = os.path.join(os.getcwd(), logFileName)
    # print(fullPath)
    os.chdir(previousPath)
    return fullPath


def get_logger(logFile: str, loggerName: str) -> logging.Logger:
    """
    Returns a logger object with loggerName provided and that'll log to logFile.
    :param logFile: File to log to.
    :param loggerName: Name logger will have.
    :return: A logger object.
    """
    logger = logging.getLogger(loggerName)
    logger.setLevel(logging.INFO)

    c_formatter = logging.Formatter('%(message)s')
    f_handler = logging.FileHandler(filename=setup_and_return_log_path(fileName=logFile), delay=True)
    # f_handler.setLevel(logging.INFO)
    f_handler.setFormatter(c_formatter)

    logger.addHandler(f_handler)
    return logger


def initialize_logger():
    """
    Initializes logger. THIS FUNCTION IS OFFICIALLY DEPRECATED.
    """
    curPath = os.getcwd()
    os.chdir('../')
    if not os.path.exists('Logs'):
        os.mkdir('Logs')

    os.chdir('Logs')
    todayDate = datetime.today().strftime('%Y-%m-%d')

    if not os.path.exists(todayDate):
        os.mkdir(todayDate)

    os.chdir(todayDate)

    logFileName = f'{datetime.now().strftime("%H-%M-%S")}.log'
    logging.basicConfig(filename=logFileName, level=logging.INFO, format='%(message)s')
    os.chdir(curPath)


def parse_strategy_name(name: str) -> str:
    """
    Parses strategy name for use with strategies.
    :param name: Name of strategy to be parsed.
    :return: Parsed strategy name.
    """
    nameList = name.split()
    remainingList = nameList[1:]

    nameList = [nameList[0].lower()]
    for name in remainingList:
        nameList.append(name.capitalize())

    return ''.join(nameList)


def set_up_strategies(trader, strategies: List[tuple]):
    for strategyTuple in strategies:
        strategyClass = strategyTuple[0]
        values = strategyTuple[1]
        name = parse_strategy_name(strategyTuple[2])

        if name != 'movingAverage':
            trader.strategies[name] = strategyClass(trader, inputs=values, precision=trader.precision)
        else:
            values = [Option(*values[x:x + 4]) for x in range(0, len(values), 4)]
            trader.strategies[name] = strategyClass(trader, inputs=values, precision=trader.precision)
            trader.minPeriod = trader.strategies[name].get_min_option_period()


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


def convert_small_interval(interval: str) -> str:
    """
    Converts smaller interval string to longer interval string.
    :param interval: Small interval string.
    :return: Longer interval string.
    """
    intervals = {
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
        '3d': '3 Days',
    }
    return intervals[interval]


def convert_long_interval(interval: str) -> str:
    """
    Converts longer interval string to smaller interval string.
    :param interval: Long interval string.
    :return: Smaller interval string.
    """
    intervals = {
        '1 Minute': '1m',
        '3 Minutes': '3m',
        '5 Minutes': '5m',
        '15 Minutes': '15m',
        '30 Minutes': '30m',
        '1 Hour': '1h',
        '2 Hours': '2h',
        '4 Hours': '4h',
        '6 Hours': '6h',
        '8 Hours': '8h',
        '12 Hours': '12h',
        '1 Day': '1d',
        '3 Days': '3d',
    }
    return intervals[interval]


def convert_all_dates_to_datetime(data: List[Dict[str, Union[float, str, datetime]]]):
    """
    Converts all available dates in the data list of dictionaries to datetime objects.
    :param data: List of data in which to convert string dates to datetime objects.
    """
    if isinstance(data[0]['date_utc'], datetime):
        return

    for entry in data:
        entry['date_utc'] = parser.parse(entry['date_utc'])


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


def create_folder_if_needed(targetPath: str, basePath: str = None) -> bool:
    """
    This function will create the appropriate folders in the root folder if needed.
    :param targetPath: Target path to have exist.
    :param basePath: Base path to start from. If none, it'll be the root directory.
    :return: Boolean whether folder was created or not.
    """
    if not basePath:
        basePath = ROOT_DIR

    if not os.path.exists(targetPath):
        folder = os.path.basename(targetPath)
        cur_path = os.getcwd()
        os.chdir(basePath)
        os.mkdir(folder)
        os.chdir(cur_path)
        return True
    return False


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
