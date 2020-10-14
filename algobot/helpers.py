import logging
import time
import os
from datetime import datetime


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
    logging.basicConfig(filename=f'{logFileName}', level=logging.INFO, format='%(message)s')
    os.chdir(curPath)
