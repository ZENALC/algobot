"""
Calendar helper functions for configuration.py can be found here.
"""

import datetime
from typing import Tuple

from dateutil import parser
from PyQt5.QtCore import QDate

from algobot.enums import BACKTEST


def get_calendar_dates(config_obj, caller: int = BACKTEST) -> Tuple[datetime.date or None, datetime.date or None]:
    """
    Returns start end end dates for backtest. If both are the same, returns None.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller object that called this function.
    :return: Start and end dates for backtest.
    """
    startDate = config_obj.optimizer_backtest_dict[caller]['startDate'].selectedDate().toPyDate()
    endDate = config_obj.optimizer_backtest_dict[caller]['endDate'].selectedDate().toPyDate()
    if startDate == endDate:
        return None, None
    return startDate, endDate


def setup_calendar(config_obj, caller: int = BACKTEST):
    """
    Parses data if needed and then manipulates GUI elements with data timeframe.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller object that called this function.
    """
    data = config_obj.optimizer_backtest_dict[caller]['data']
    if type(data[0]['date_utc']) == str:
        startDate = parser.parse(data[0]['date_utc'])
        endDate = parser.parse(data[-1]['date_utc'])
    else:
        startDate = data[0]['date_utc']
        endDate = data[-1]['date_utc']

    if startDate > endDate:
        startDate, endDate = endDate, startDate

    startYear, startMonth, startDay = startDate.year, startDate.month, startDate.day
    qStartDate = QDate(startYear, startMonth, startDay)

    endYear, endMonth, endDay = endDate.year, endDate.month, endDate.day
    qEndDate = QDate(endYear, endMonth, endDay)

    config_obj.optimizer_backtest_dict[caller]['startDate'].setEnabled(True)
    config_obj.optimizer_backtest_dict[caller]['startDate'].setDateRange(qStartDate, qEndDate)
    config_obj.optimizer_backtest_dict[caller]['startDate'].setSelectedDate(qStartDate)

    config_obj.optimizer_backtest_dict[caller]['endDate'].setEnabled(True)
    config_obj.optimizer_backtest_dict[caller]['endDate'].setDateRange(qStartDate, qEndDate)
    config_obj.optimizer_backtest_dict[caller]['endDate'].setSelectedDate(qEndDate)
