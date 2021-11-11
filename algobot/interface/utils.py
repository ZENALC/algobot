"""
File containing utility functions for the GUI.
"""

from datetime import datetime
from typing import List, Union

import talib
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QLineEdit, QMessageBox, QSizePolicy, QSpacerItem,
                             QSpinBox, QTableWidget, QTableWidgetItem)

from algobot.interface.configuration_helpers import get_default_widget

# TALIB sets moving averages by numbers. This is not very appealing in the frontend, so we'll map it to its
#  appropriate moving average.
MOVING_AVERAGE_TYPES_BY_NUM = vars(talib.MA_Type)['_lookup']
MOVING_AVERAGE_TYPES_BY_NAME = {v: k for k, v in MOVING_AVERAGE_TYPES_BY_NUM.items()}

# Mappings from TALIB parameters to better display names.
PARAMETER_MAP = {
    'acceleration': 'Acceleration',
    'accelerationinitlong': 'Acceleration Init Long',
    'accelerationinitshort': 'Acceleration Init Short',
    'accelerationlong': 'Acceleration Long',
    'accelerationmaxlong': 'Acceleration Max Long',
    'accelerationmaxshort': 'Acceleration Max Short',
    'accelerationshort': "Acceleration Short",
    'fastd_matype': "Fast D MA Type",
    'fastd_period': "Fast D Period",
    'fastk_period': "Fast K Period",  # noqa
    'fastlimit': "Fast Limit",  # noqa
    'fastmatype': "Fast MA Type",
    'fastperiod': 'Fast Period',
    'matype': "MA Type",
    'maximum': "Maximum",
    'maxperiod': "Max Period",  # noqa
    'minperiod': 'Min Period',  # noqa
    'nbdev': 'NB Dev',  # noqa
    'nbdevdn': 'NB Dev Down',
    'nbdevup': 'NB Dev Up',
    'offsetonreverse': "Offset On Reverse",  # noqa
    'penetration': 'Penetration',
    'signalmatype': 'Signal MA Type',
    'signalperiod': 'Signal Period',  # noqa
    'slowd_matype': 'Slow D MA Type',  # noqa
    'slowd_period': 'Slow D Period',  # noqa
    'slowk_matype': 'Slow K MA Type',  # noqa
    'slowk_period': 'Slow K Period',  # noqa
    'slowlimit': "Slow Limit",  # noqa
    'slowmatype': "Slow MA Type",
    'slowperiod': "Slow Period",
    'startvalue': 'Start Value',  # noqa
    'timeperiod': "Time Period",
    'timeperiod1': "Time Period 1",
    'timeperiod2': 'Time Period 2',
    'timeperiod3': "Time Period 3",
    'vfactor': 'V Factor'
}


def get_param_obj(default_value: Union[float, int, str], param_name: str):
    """
    Get param widget based on param and param_name provided.
    :param default_value: Param type.
    :param param_name: Name of the parameter (e.g. matype)
    :return: Parameter object.
    """
    if isinstance(default_value, int):
        # TALIB stores MA types as ints. So, we must see what that num maps to.
        if 'matype' in param_name:
            default_moving_average = MOVING_AVERAGE_TYPES_BY_NUM[default_value]
            moving_averages = list(MOVING_AVERAGE_TYPES_BY_NAME.keys())

            input_obj = QComboBox()
            input_obj.addItems(moving_averages)
            input_obj.setCurrentIndex(moving_averages.index(default_moving_average))
            return input_obj
        else:
            return get_default_widget(QSpinBox, default_value, None, None)

    elif isinstance(default_value, float):
        return get_default_widget(QDoubleSpinBox, default_value, None, None)
    elif isinstance(default_value, str):
        return QLineEdit()
    else:
        raise ValueError("Unknown type of data encountered.")


def get_bold_font() -> QFont:
    """
    Returns a bold font.
    :return: Bold font.
    """
    bold_font = QFont()
    bold_font.setBold(True)

    return bold_font


def get_v_spacer() -> QSpacerItem:
    """
    Get a vertical spacer.
    :return: Vertical spacer.
    """
    return QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)


def create_popup(parent, msg: str, title='Warning'):
    """
    Creates a popup with message provided.
    :param parent: Parent object to create popup on.
    :param title: Title for message box. By default, it is warning.
    :param msg: Message provided.
    """
    QMessageBox.about(parent, title, msg)


def open_from_msg_box(text: str, title: str):
    """
    Create a message box with an open/close dialog with text and title provided and return true or false depending
    on whether the user wants to open it or not.
    :param text: Text to put in message box.
    :param title: Title to put in message box.
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setText(text)
    msg_box.setWindowTitle(title)
    msg_box.setStandardButtons(QMessageBox.Open | QMessageBox.Close)
    return msg_box.exec_() == QMessageBox.Open


def get_elements_from_combobox(combobox: QComboBox) -> List[str]:
    """
    Returns all elements from combobox provided in a list.
    :param combobox: Combobox to get list of elements from.
    :return: List of elements from combobox.
    """
    return [combobox.itemText(i) for i in range(combobox.count())]


def show_and_bring_window_to_front(window: QDialog):
    """
    This will bring the window provided to the very front of the screen.
    :param window: Window object to bring to front.
    """
    window.show()
    window.activateWindow()
    window.raise_()


def add_to_table(table: QTableWidget, data: list, insert_date: bool = True):
    """
    Function that will add specified data to a provided table.
    :param insert_date: Boolean to add date to 0th index of data or not.
    :param table: Table we will add data to.
    :param data: Data we will add to table.
    """
    row_position = table.rowCount()
    columns = table.columnCount()

    if insert_date:
        data.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if len(data) != columns:
        raise ValueError('Data needs to have the same amount of columns as table.')

    table.insertRow(row_position)
    for column in range(0, columns):
        value = data[column]
        if type(value) not in (int, float):
            item = QTableWidgetItem(str(value))
        else:
            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, value)
        table.setItem(row_position, column, item)


def clear_table(table: QTableWidget):
    """
    Sets table row count to 0.
    :param table: Table which is to be cleared.
    """
    table.setRowCount(0)
