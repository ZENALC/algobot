import logging
import time
import os
from datetime import datetime


def initialize_logger():
    """Initializes logger"""
    if not os.path.exists('Logs'):
        os.mkdir('Logs')

    previousPath = os.getcwd()
    os.chdir('Logs')

    todayDate = datetime.today().strftime('%Y-%m-%d')

    if not os.path.exists(todayDate):
        os.mkdir(todayDate)

    os.chdir(previousPath)

    logFileName = f'{datetime.now().strftime("%H-%M-%S")}.log'
    logging.basicConfig(filename=f'Logs/{todayDate}/{logFileName}', level=logging.INFO, format='%(message)s')
