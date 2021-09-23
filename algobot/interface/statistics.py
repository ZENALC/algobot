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
        :param inner_tabs: Inner tabs of tab to tbe modified. E.g. Simulation's inner tabs can be general, averages, etc.
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
    def set_profit_or_loss_label(valueDictionary: Dict[str, Any], innerTabs: Dict[str, Any]):
        """
        Sets the profit or loss label appropriately based on the value dictionary provided.
        :param valueDictionary: Dictionary with values to update profit or loss label.
        :param innerTabs: Main tab's inner tabs.
        """
        if 'general' in valueDictionary and 'profit' in valueDictionary['general']:
            tab = innerTabs['general']
            if 'profit' in tab:
                if valueDictionary['general']['profit'][1] == '-':
                    label = 'Loss'
                    valueDictionary['general']['profit'] = "$" + valueDictionary['general']['profit'][2:]
                else:
                    label = 'Profit'
                tab['profit']['label'].setText(label)

    def modify_tab(self, valueDictionary: Dict[str, Any], tabType: str):
        """
        Modifies tab.
        :param valueDictionary: Dictionary with values.
        :param tabType: Tab type to be modified.
        """
        inner_tabs = self.tabs[tabType]['innerTabs']  # live/widgets
        self.set_profit_or_loss_label(valueDictionary=valueDictionary, innerTabs=inner_tabs)

        for key in inner_tabs:  # If there's a change in the value dictionary, re-initialize the tab.
            if key not in valueDictionary:
                self.initialize_tab(value_dictionary=valueDictionary, tab_type=tabType)
                break

        for category_key in valueDictionary:
            if category_key not in inner_tabs:
                tab = self.tabs[tabType]['tab']
                self.add_category_and_children_keys(category_key, valueDictionary, inner_tabs, tab)
            else:
                inner_widgets = inner_tabs[category_key]  # live/widgets/general
                for mainKey, mainValue in valueDictionary[category_key].items():
                    if mainKey in inner_widgets:
                        inner_widgets[mainKey]['value'].setText(str(mainValue))
                    else:
                        label = QLabel(get_label_string(str(mainKey)))
                        value = QLabel(str(mainValue))
                        value.setAlignment(QtCore.Qt.AlignRight)

                        layout = inner_tabs[category_key]['tab'].layout()
                        layout.addRow(label, value)
                        inner_widgets[mainKey] = {'label': label, 'value': value}
