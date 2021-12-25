"""
File for the statistics window.
"""

import os
from typing import Any, Dict

from PyQt5 import QtCore, uic
from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QMainWindow, QTabWidget

from algobot.helpers import ROOT_DIR, get_label_string

statisticsUi = os.path.join(ROOT_DIR, 'UI', 'statistics.ui')


class Statistics(QDialog):
    """
    Class for statistics window.
    """
    def __init__(self, parent: QMainWindow = None):
        super(Statistics, self).__init__(parent)  # Initializing object
        uic.loadUi(statisticsUi, self)  # Loading the main UI
        self.tabs = {}

    def remove_tab_if_needed(self, tab_type: str):
        """
        Removes tab based on tabType provided (if it exists).
        :param tab_type: Tab type to remove from list of statistics tabs.
        """
        if tab_type in self.tabs:  # Delete previous tab if exists.
            tab = self.tabs[tab_type]['tab']
            index = self.statisticsTabWidget.indexOf(tab)
            self.statisticsTabWidget.removeTab(index)

    def remove_old_tab(self, tab_type: str):
        """
        Removes previous tab of the same tab type.
        :param tab_type: Tab type to remove.
        """
        index = self.get_index_from_tab_type(tab_type)
        self.statisticsTabWidget.removeTab(index)

    def initialize_tab(self, value_dictionary: Dict[str, Any], tab_type: str):
        """
        Initializes tab of tabType provided.
        :param value_dictionary: Dictionary with values to fill into the tab.
        :param tab_type: Type of tab.
        """
        self.remove_old_tab(tab_type)
        self.tabs[tab_type] = {'tab': QTabWidget(), 'innerTabs': {}}  # Create new tab dictionary.

        tab = self.tabs[tab_type]['tab']
        tab.setTabPosition(QTabWidget.West)

        index = self.get_index_from_tab_type(tab_type)
        inner_tabs = self.tabs[tab_type]['innerTabs']

        for category_key in value_dictionary:
            self.add_category_and_children_keys(category_key, value_dictionary, inner_tabs, tab)

        self.statisticsTabWidget.insertTab(index, tab, f"{tab_type.capitalize()}")
        self.statisticsTabWidget.setCurrentIndex(index)

    @staticmethod
    def get_index_from_tab_type(tab_type: str) -> int:
        """
        Returns index of type of tab.
        :param tab_type: Type of tab to get index of.
        :return: Tab index of given tab type.
        """
        return 1 if 'sim' in tab_type else 0

    @staticmethod
    def add_category_and_children_keys(category_key: str,
                                       value_dictionary: Dict[str, Any],
                                       inner_tabs: Dict[str, Any],
                                       tab: QTabWidget):
        """
        Modifies instance tabs variable with new values from value_dictionary.
        :param category_key: Category to modify.
        :param value_dictionary: Dictionary with values to put in.
        :param inner_tabs: Inner tabs of tab to tbe modified. E.g. Simulation's inner tabs can be general,
        averages, etc.
        :param tab: Tab to be modified. For instance, this tab can be the simulation tab.
        """
        inner_layout = QFormLayout()
        inner_tabs[category_key] = {'tab': QTabWidget()}

        for main_key, main_value in value_dictionary[category_key].items():
            label = QLabel(get_label_string(str(main_key)))
            value = QLabel(str(main_value))
            value.setAlignment(QtCore.Qt.AlignRight)

            inner_layout.addRow(label, value)
            inner_tabs[category_key][main_key] = {'label': label, 'value': value}

        inner_tabs[category_key]['tab'].setLayout(inner_layout)
        tab.addTab(inner_tabs[category_key]['tab'], get_label_string(category_key))

    @staticmethod
    def set_profit_or_loss_label(value_dictionary: Dict[str, Any], inner_tabs: Dict[str, Any]):
        """
        Sets the profit or loss label appropriately based on the value dictionary provided.
        :param value_dictionary: Dictionary with values to update profit or loss label.
        :param inner_tabs: Main tab's inner tabs.
        """
        if 'general' in value_dictionary and 'profit' in value_dictionary['general']:
            tab = inner_tabs['general']
            if 'profit' in tab:
                if value_dictionary['general']['profit'][1] == '-':
                    label = 'Loss'
                    value_dictionary['general']['profit'] = "$" + value_dictionary['general']['profit'][2:]
                else:
                    label = 'Profit'
                tab['profit']['label'].setText(label)

    def modify_tab(self, value_dictionary: Dict[str, Any], tab_type: str):
        """
        Modifies tab.
        :param value_dictionary: Dictionary with values.
        :param tab_type: Tab type to be modified.
        """
        inner_tabs = self.tabs[tab_type]['innerTabs']  # live/widgets
        self.set_profit_or_loss_label(value_dictionary=value_dictionary, inner_tabs=inner_tabs)

        for key in inner_tabs:  # If there's a change in the value dictionary, re-initialize the tab.
            if key not in value_dictionary:
                self.initialize_tab(value_dictionary=value_dictionary, tab_type=tab_type)
                break

        for category_key in value_dictionary:
            if category_key not in inner_tabs:
                tab = self.tabs[tab_type]['tab']
                self.add_category_and_children_keys(category_key, value_dictionary, inner_tabs, tab)
            else:
                inner_widgets = inner_tabs[category_key]  # live/widgets/general
                for main_key, main_value in value_dictionary[category_key].items():
                    if main_key in inner_widgets:
                        inner_widgets[main_key]['value'].setText(str(main_value))
                    else:
                        label = QLabel(get_label_string(str(main_key)))
                        value = QLabel(str(main_value))
                        value.setAlignment(QtCore.Qt.AlignRight)

                        layout = inner_tabs[category_key]['tab'].layout()
                        layout.addRow(label, value)
                        inner_widgets[main_key] = {'label': label, 'value': value}
