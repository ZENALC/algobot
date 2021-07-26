"""
File containing utility functions for the GUI.
"""

from datetime import datetime
from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QDialog, QMessageBox, QTableWidget, QTableWidgetItem


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
    msgBox = QMessageBox()
    msgBox.setIcon(QMessageBox.Information)
    msgBox.setText(text)
    msgBox.setWindowTitle(title)
    msgBox.setStandardButtons(QMessageBox.Open | QMessageBox.Close)
    return msgBox.exec_() == QMessageBox.Open


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


def add_to_table(table: QTableWidget, data: list, insertDate=True):
    """
    Function that will add specified data to a provided table.
    :param insertDate: Boolean to add date to 0th index of data or not.
    :param table: Table we will add data to.
    :param data: Data we will add to table.
    """
    row_position = table.rowCount()
    columns = table.columnCount()

    if insertDate:
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
