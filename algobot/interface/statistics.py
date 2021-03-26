import os

from PyQt5 import QtCore, uic
from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QTabWidget

from algobot.helpers import ROOT_DIR, get_label_string

statisticsUi = os.path.join(ROOT_DIR, 'UI', 'statistics.ui')


class Statistics(QDialog):
    def __init__(self, parent=None):
        super(Statistics, self).__init__(parent)  # Initializing object
        uic.loadUi(statisticsUi, self)  # Loading the main UI
        self.tabs = {}

    def remove_tab_if_needed(self, tabType):
        """
        Removes tab based on tabType provided (if it exists).
        :param tabType: Tab type to remove from list of statistics tabs.
        """
        if tabType in self.tabs:  # Delete previous tab if exists.
            tab = self.tabs[tabType]['tab']
            index = self.statisticsTabWidget.indexOf(tab)
            self.statisticsTabWidget.removeTab(index)

    def remove_old_tab(self, tabType):
        """
        Removes previous tab of the same tab type.
        :param tabType: Tab type to remove.
        """
        index = self.get_index_from_tab_type(tabType)
        self.statisticsTabWidget.removeTab(index)

    def initialize_tab(self, valueDictionary, tabType):
        """
        Initializes tab of tabType provided.
        :param valueDictionary: Dictionary with values to fill into the tab.
        :param tabType: Type of tab.
        """
        self.remove_old_tab(tabType)
        self.tabs[tabType] = {'tab': QTabWidget(), 'innerTabs': {}}  # Create new tab dictionary.

        tab = self.tabs[tabType]['tab']
        tab.setTabPosition(QTabWidget.West)

        index = self.get_index_from_tab_type(tabType)
        innerTabs = self.tabs[tabType]['innerTabs']

        for categoryKey in valueDictionary:
            self.add_category_and_children_keys(categoryKey, valueDictionary, innerTabs, tab)

        self.statisticsTabWidget.insertTab(index, tab, f"{tabType.capitalize()}")
        self.statisticsTabWidget.setCurrentIndex(index)

    @staticmethod
    def get_index_from_tab_type(tabType) -> int:
        """
        Returns index of type of tab.
        :param tabType: Type of tab to get index of.
        :return: Tab index of given tab type.
        """
        if 'sim' in tabType:
            return 1
        else:
            return 0

    @staticmethod
    def add_category_and_children_keys(categoryKey, valueDictionary, innerTabs, tab):
        """
        Modifies instance tabs variable with new values from valueDictionary.
        :param categoryKey: Category to modify.
        :param valueDictionary: Dictionary with values to put in.
        :param innerTabs: Inner tabs of tab to tbe modified. E.g. Simulation's inner tabs can be general, averages, etc.
        :param tab: Tab to be modified. For instance, this tab can be the simulation tab.
        """
        innerLayout = QFormLayout()
        innerTabs[categoryKey] = {'tab': QTabWidget()}

        for mainKey in valueDictionary[categoryKey]:
            label = QLabel(get_label_string(str(mainKey)))
            value = QLabel(str(valueDictionary[categoryKey][mainKey]))
            value.setAlignment(QtCore.Qt.AlignRight)

            innerLayout.addRow(label, value)
            innerTabs[categoryKey][mainKey] = {'label': label, 'value': value}

        innerTabs[categoryKey]['tab'].setLayout(innerLayout)
        tab.addTab(innerTabs[categoryKey]['tab'], get_label_string(categoryKey))

    @staticmethod
    def set_profit_or_loss_label(valueDictionary, innerTabs):
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

    def modify_tab(self, valueDictionary, tabType):
        """
        Modifies tab.
        :param valueDictionary: Dictionary with values.
        :param tabType: Tab type to be modified.
        """
        innerTabs = self.tabs[tabType]['innerTabs']  # live/widgets
        self.set_profit_or_loss_label(valueDictionary=valueDictionary, innerTabs=innerTabs)

        for key in innerTabs:  # If there's a change in the value dictionary, re-initialize the tab.
            if key not in valueDictionary:
                self.initialize_tab(valueDictionary=valueDictionary, tabType=tabType)
                break

        for categoryKey in valueDictionary:
            if categoryKey not in innerTabs:
                tab = self.tabs[tabType]['tab']
                self.add_category_and_children_keys(categoryKey, valueDictionary, innerTabs, tab)
            else:
                innerWidgets = innerTabs[categoryKey]  # live/widgets/general
                for mainKey in valueDictionary[categoryKey]:
                    if mainKey in innerWidgets:
                        innerWidgets[mainKey]['value'].setText(str(valueDictionary[categoryKey][mainKey]))
                    else:
                        label = QLabel(get_label_string(str(mainKey)))
                        value = QLabel(str(valueDictionary[categoryKey][mainKey]))
                        value.setAlignment(QtCore.Qt.AlignRight)

                        layout = innerTabs[categoryKey]['tab'].layout()
                        layout.addRow(label, value)
                        innerWidgets[mainKey] = {'label': label, 'value': value}
