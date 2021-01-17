import logging
import platform
import subprocess
import os
import json
import time
from datetime import datetime
from typing import Tuple

from dateutil import parser

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(BASE_DIR)
LOG_FOLDER = 'Logs'


def open_file_or_folder(targetPath):
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


def setup_and_return_log_path(fileName):
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
    logger = logging.getLogger(loggerName)
    logger.setLevel(logging.INFO)

    c_formatter = logging.Formatter('%(message)s')
    f_handler = logging.FileHandler(filename=setup_and_return_log_path(fileName=logFile), delay=True)
    # f_handler.setLevel(logging.INFO)
    f_handler.setFormatter(c_formatter)

    logger.addHandler(f_handler)
    return logger


def initialize_logger():
    """Initializes logger"""
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


def convert_interval(interval):
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


def convert_interval_to_string(interval):
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


def get_elapsed_time(previousTime):
    seconds = int(time.time() - previousTime)
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


def load_from_csv(path, descending=True):
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


def write_credentials(**kwargs):
    with open('secret.json', 'w') as f:
        json.dump(kwargs, f)


def load_credentials(jsonfile='secret.json'):
    with open(jsonfile) as f:
        return json.load(f)
