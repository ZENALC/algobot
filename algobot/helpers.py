import logging
import os
import json
import time
from datetime import datetime
from dateutil import parser


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
        return f'{hours}h {minutes}m {seconds} s'


def load_from_csv(path, descending=True):
    with open(path) as f:
        data = []
        readLines = f.readlines()
        headers = list(map(str.lower, readLines[0].rstrip().split(', ')))
        for line in readLines[1:]:
            line = line.rstrip()  # strip newline character
            splitLine = line.split(', ')
            data.append({
                headers[-1]: float(splitLine[-1]),  # close
                headers[-2]: float(splitLine[-2]),  # low
                headers[-3]: float(splitLine[-3]),  # high
                headers[-4]: float(splitLine[-4]),  # open
                headers[-5]: ' '.join(splitLine[0: -4])  # date in UTC
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
