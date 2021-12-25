"""
Calendar helper functions for configuration.py can be found here.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional, Tuple

from dateutil import parser
from PyQt5.QtCore import QDate

from algobot.enums import BACKTEST

if TYPE_CHECKING:
    from algobot.interface.configuration import Configuration


def get_calendar_dates(config_obj: Configuration,
                       caller: str = BACKTEST) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
    """
    Returns start end end dates for backtest. If both are the same, returns None.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller object that called this function.
    :return: Start and end dates for backtest.
    """
    start_date = config_obj.optimizer_backtest_dict[caller]['startDate'].selectedDate().toPyDate()
    end_date = config_obj.optimizer_backtest_dict[caller]['endDate'].selectedDate().toPyDate()
    if start_date == end_date:
        return None, None
    return start_date, end_date


def setup_calendar(config_obj: Configuration, caller: str = BACKTEST):
    """
    Parses data if needed and then manipulates GUI elements with data timeframe.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller object that called this function.
    """
    data = config_obj.optimizer_backtest_dict[caller]['data']
    if isinstance(data[0]['date_utc'], str):
        start_date = parser.parse(data[0]['date_utc'])
        end_date = parser.parse(data[-1]['date_utc'])
    else:
        start_date = data[0]['date_utc']
        end_date = data[-1]['date_utc']

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    start_year, start_month, start_day = start_date.year, start_date.month, start_date.day
    q_start_date = QDate(start_year, start_month, start_day)

    end_year, end_month, end_day = end_date.year, end_date.month, end_date.day
    q_end_date = QDate(end_year, end_month, end_day)

    config_obj.optimizer_backtest_dict[caller]['startDate'].setEnabled(True)
    config_obj.optimizer_backtest_dict[caller]['startDate'].setDateRange(q_start_date, q_end_date)
    config_obj.optimizer_backtest_dict[caller]['startDate'].setSelectedDate(q_start_date)

    config_obj.optimizer_backtest_dict[caller]['endDate'].setEnabled(True)
    config_obj.optimizer_backtest_dict[caller]['endDate'].setDateRange(q_start_date, q_end_date)
    config_obj.optimizer_backtest_dict[caller]['endDate'].setSelectedDate(q_end_date)
