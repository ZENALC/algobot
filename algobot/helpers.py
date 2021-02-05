import logging
import platform
import subprocess
import os
import re
import json
import time

from datetime import datetime
from dateutil import parser
from typing import Tuple

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(BASE_DIR)
LOG_FOLDER = 'Logs'


def open_file_or_folder(targetPath):
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


def get_ups_and_downs(data, parameter) -> Tuple[list, list]:
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


def setup_and_return_log_path(fileName) -> str:
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


def get_logger(logFile, loggerName):
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


def convert_interval(interval) -> str:
    """
    Converts longer interval string to smaller interval string.
    :param interval: Long interval string.
    :return: Smaller interval string.
    """
    intervals = {
        '12 Hours': '12h',
        '15 Minutes': '15m',
        '1 Day': '1d',
        '1 Hour': '1h',
        '1 Minute': '1m',
        '2 Hours': '2h',
        '30 Minutes': '30m',
        '3 Days': '3d',
        '3 Minutes': '3m',
        '4 Hours': '4h',
        '5 Minutes': '5m',
        '6 Hours': '6h',
        '8 Hours': '8h'
    }
    return intervals[interval]


def get_label_string(label: str) -> str:
    """
    Returns prettified string from a camel case formatted string.
    :param label: Potential string in camel case format.
    :return: Prettified string.
    """
    label = str(label)
    if not label[0].isupper():
        separated = re.sub('([A-Z][a-z]+)', r' \1', re.sub('([A-Z]+)', r' \1', label)).split()
        separated = list(map(lambda word: word.capitalize(), separated))
        label = ' '.join(separated)
    return label


def convert_interval_to_string(interval) -> str:
    """
    Converts smaller interval string to longer interval string.
    :param interval: Small interval string.
    :return: Longer interval string.
    """
    intervals = {
        '12h': '12 Hours',
        '15m': '15 Minutes',
        '1d': '1 Day',
        '1h': '1 Hour',
        '1m': '1 Minute',
        '2h': '2 Hours',
        '30m': '30 Minutes',
        '3d': '3 Days',
        '3m': '3 Minutes',
        '4h': '4 Hours',
        '5m': '5 Minutes',
        '6h': '6 Hours',
        '8h': '8 Hours'
    }
    return intervals[interval]


def get_elapsed_time(startingTime) -> str:
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


def get_data_from_parameter(data, parameter) -> float:
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


def load_from_csv(path, descending=True) -> list:
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
        json.dump(kwargs, f)


def load_json_file(jsonfile) -> dict:
    """
    Loads JSON file passed and returns dictionary.
    :param jsonfile: File to read dictionary from.
    :return: Dictionary with credentials.
    """
    with open(jsonfile) as f:
        return json.load(f)
