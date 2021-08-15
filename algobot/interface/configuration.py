"""
Configuration window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from algobot.__main__ import Interface

import os
from logging import Logger

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QLabel, QLayout, QSpinBox, QTabWidget

from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION, STOP, TRAILING
from algobot.graph_helpers import create_infinite_line
from algobot.helpers import ROOT_DIR
from algobot.interface.config_utils.credential_utils import load_credentials
from algobot.interface.config_utils.slot_utils import load_slots
from algobot.interface.config_utils.strategy_utils import (add_strategy_inputs, delete_strategy_inputs,
                                                           get_strategies_dictionary, get_strategy_values,
                                                           strategy_enabled)
from algobot.interface.configuration_helpers import add_start_end_step_to_layout, get_default_widget, set_value
# noinspection PyUnresolvedReferences
from algobot.interface.utils import get_elements_from_combobox
from algobot.strategies import *  # noqa: F403, F401 pylint: disable=wildcard-import,unused-wildcard-import
from algobot.strategies.strategy import Strategy

configurationUi = os.path.join(ROOT_DIR, 'UI', 'configuration.ui')


class Configuration(QDialog):
    """
    Configuration window.
    """
    def __init__(self, parent: Interface, logger: Logger = None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.parent = parent
        self.threadPool = QThreadPool()
        self.logger = logger

        self.optimizer_backtest_dict = {
            BACKTEST: {
                'startDate': self.backtestStartDate,
                'endDate': self.backtestEndDate,
                'tickers': self.backtestTickerLineEdit,
                'intervals': self.backtestIntervalComboBox,
                'data': None,
                'dataIntervalComboBox': self.backtestIntervalComboBox,
                'dataInterval': None,
                'dataType': None,
                'infoLabel': self.backtestInfoLabel,
                'dataLabel': self.backtestDataLabel,
                'downloadThread': None,
                'downloadLabel': self.backtestDownloadLabel,
                'downloadButton': self.backtestDownloadDataButton,
                'stopDownloadButton': self.backtestStopDownloadButton,
                'importButton': self.backtestImportDataButton,
                'downloadProgress': self.backtestDownloadProgressBar
            },
            OPTIMIZER: {
                'startDate': self.optimizerStartDate,
                'endDate': self.optimizerEndDate,
                'tickers': self.optimizerTickerLineEdit,
                'intervals': self.optimizerIntervalComboBox,
                'data': None,
                'dataIntervalComboBox': self.optimizerIntervalComboBox,
                'dataInterval': None,
                'dataType': None,
                'infoLabel': self.optimizerInfoLabel,
                'dataLabel': self.optimizerDataLabel,
                'downloadThread': None,
                'downloadLabel': self.optimizerDownloadLabel,
                'downloadButton': self.optimizerDownloadDataButton,
                'stopDownloadButton': self.optimizerStopDownloadButton,
                'importButton': self.optimizerImportDataButton,
                'downloadProgress': self.optimizerDownloadProgressBar
            }
        }

        self.lossTypes = ("Trailing", "Stop")
        self.takeProfitTypes = ('Stop',)
        self.lossOptimizerTypes = ('lossPercentage', 'stopLossCounter')
        self.takeProfitOptimizerTypes = ('takeProfitPercentage',)

        # Telegram
        self.tokenPass = False
        self.chatPass = False

        # Folders and files
        self.credentialsFolder = "Credentials"
        self.configFolder = 'Configuration'
        self.stateFilePath = os.path.join(ROOT_DIR, 'state.json')

        self.categoryTabs = [
            self.mainConfigurationTabWidget,
            self.simulationConfigurationTabWidget,
            self.backtestConfigurationTabWidget,
            self.optimizerConfigurationTabWidget
        ]

        self.strategies = get_strategies_dictionary(Strategy.__subclasses__())
        self.hiddenStrategies = set(self.strategies)  # Hidden strategies dynamically populated.
        self.strategyDict = {}  # We will store all the strategy slot information in this dictionary.
        self.lossDict = {}  # We will store stop loss settings here.
        self.takeProfitDict = {}  # We will store take profit settings here.

        load_slots(self)  # Loads stop loss, take profit, and strategies slots.
        load_credentials(self)  # Load credentials if they exist.

    def enable_disable_hover_line(self):
        """
        Enables or disables the hover line based on whether its checkmark is ticked or not.
        """
        enable = self.enableHoverLine.isChecked()
        if enable:
            for graph_dict in self.parent.graphs:
                if len(graph_dict['plots']) > 0:
                    create_infinite_line(gui=self.parent, graphDict=graph_dict)
        else:
            for graph_dict in self.parent.graphs:
                hoverLine = graph_dict.get('line')
                self.parent.reset_backtest_cursor()
                if hoverLine:
                    graph_dict['graph'].removeItem(hoverLine)
                    graph_dict['line'] = None

    def update_graph_speed(self):
        """
        Updates graph speed on main Algobot interface.
        """
        graph_speed = self.graphPlotSpeedSpinBox.value()
        self.parent.graphUpdateSeconds = graph_speed
        self.parent.add_to_live_activity_monitor(f"Updated graph plot speed to every {graph_speed} second(s).")

    def get_caller_based_on_tab(self, tab: QTabWidget) -> int:
        """
        This will return a caller based on the tab provided.
        :param tab: Tab for which the caller will be returned.
        :return: Caller for which this tab corresponds to.
        """
        if tab == self.categoryTabs[2]:
            return BACKTEST
        elif tab == self.categoryTabs[1]:
            return SIMULATION
        elif tab == self.categoryTabs[0]:
            return LIVE
        elif tab == self.categoryTabs[3]:
            return OPTIMIZER
        else:
            raise ValueError("Invalid tab provided. No known called associated with this tab.")

    def get_category_tab(self, caller: int) -> QTabWidget:
        """
        This will return the category tab (main, simulation, or live) based on the caller provided.
        :param caller: Caller argument to return the appropriate category tab.
        :return: Category tab widget object.
        """
        if caller == BACKTEST:
            return self.categoryTabs[2]
        elif caller == SIMULATION:
            return self.categoryTabs[1]
        elif caller == LIVE:
            return self.categoryTabs[0]
        elif caller == OPTIMIZER:
            return self.categoryTabs[3]
        else:
            raise ValueError("Invalid type of caller provided.")

    @staticmethod
    def helper_get_optimizer(optimizer_tab, dictionary: dict, key: str, optimizerTypes: tuple, settings: dict):
        """
        Helper function to get optimizer settings and modify the settings dictionary based on the dictionary provided.
        :param optimizer_tab: Optimizer tab.
        :param dictionary: Specific dictionary that is either the loss dictionary or the take profit dictionary.
        :param key: Key to populate in the settings dictionary.
        :param optimizerTypes: Optimizer types.
        :param settings: Dictionary to modify.
        """
        if dictionary[optimizer_tab, 'groupBox'].isChecked():
            settings[key] = []
            for string, check_box in dictionary['optimizerTypes']:
                if check_box.isChecked():
                    settings[key].append(string)

            if len(settings[key]) > 0:
                for opt in optimizerTypes:
                    start, end, step = (dictionary[opt, 'start'].value(), dictionary[opt, 'end'].value(),
                                        dictionary[opt, 'step'].value())
                    settings[opt] = (start, end, step)
            else:
                del settings[key]

    def get_strategy_intervals_for_optimizer(self, settings: dict):
        """
        This will return the strategy intervals for the optimizer to leverage.
        :param settings: Settings dictionary to populate.
        :return: None
        """
        combobox = self.optimizerStrategyIntervalEndCombobox
        intervals = get_elements_from_combobox(combobox)
        end_index = intervals.index(combobox.currentText())

        settings['strategyIntervals'] = intervals[:end_index + 1]

    def get_optimizer_settings(self) -> dict:
        """
        Returns optimizer configuration in a dictionary.
        """
        tab = self.get_category_tab(OPTIMIZER)
        settings = {}

        self.helper_get_optimizer(tab, self.lossDict, 'lossType', self.lossOptimizerTypes, settings)
        self.helper_get_optimizer(tab, self.takeProfitDict, 'takeProfitType', self.takeProfitOptimizerTypes, settings)
        self.get_strategy_intervals_for_optimizer(settings)

        settings['strategies'] = {}
        # TODO: Refactor so it's not as nested and remove pylint disable below.
        # pylint: disable=too-many-nested-blocks
        for strategy in self.strategies.values():
            temp = strategy()
            strategy_name = temp.name
            parameters = temp.get_param_types()
            if strategy_name not in self.hiddenStrategies and self.strategyDict[tab, strategy_name].isChecked():
                current = {}
                for index, parameter in enumerate(parameters, start=1):
                    if isinstance(parameter, tuple) and parameter[1] in (int, float) or \
                            not isinstance(parameter, tuple):
                        if not isinstance(parameter, tuple):
                            key = strategy_name.lower() + str(index)
                        else:
                            key = parameter[0]
                        current[key] = (
                            self.strategyDict[strategy_name, index, 'start'].value(),
                            self.strategyDict[strategy_name, index, 'end'].value(),
                            self.strategyDict[strategy_name, index, 'step'].value(),
                        )
                    else:
                        current[parameter[0]] = []
                        for option in parameter[2]:
                            if self.strategyDict[strategy_name, option].isChecked():
                                current[parameter[0]].append(option)
                settings['strategies'][strategy_name] = current
        return settings

    def create_loss_inputs(self, tab: QTabWidget, innerLayout: QLayout, isOptimizer: bool = False):
        """
        Creates inputs for loss settings in GUI.
        :param tab: Tab to create inputs for - simulation, live, or backtest.
        :param innerLayout: Inner layout to place input widgets on.
        :param isOptimizer: Boolean for whether optimizer method called this function.
        """
        if isOptimizer:
            self.lossDict['optimizerTypes'] = []
            innerLayout.addRow(QLabel("Loss Types"))
            for loss_type in self.lossTypes:
                checkbox = QCheckBox(f'Enable {loss_type.lower()} type of stop loss?')
                innerLayout.addRow(checkbox)
                self.lossDict['optimizerTypes'].append((loss_type, checkbox))

            for optimizer_type in self.lossOptimizerTypes:
                self.lossDict[optimizer_type, 'start'] = start = get_default_widget(QSpinBox, 1, 0)
                self.lossDict[optimizer_type, 'end'] = end = get_default_widget(QSpinBox, 1, 0)
                self.lossDict[optimizer_type, 'step'] = step = get_default_widget(QSpinBox, 1)
                add_start_end_step_to_layout(innerLayout, optimizer_type, start, end, step)
        else:
            self.lossDict[tab, "lossType"] = loss_type_combo_box = QComboBox()
            self.lossDict[tab, "lossPercentage"] = loss_percentage = QDoubleSpinBox()
            self.lossDict[tab, "smartStopLossCounter"] = smart_stop_loss_counter = QSpinBox()

            loss_type_combo_box.addItems(self.lossTypes)
            loss_percentage.setValue(5)

            innerLayout.addRow(QLabel("Loss Type"), loss_type_combo_box)
            innerLayout.addRow(QLabel("Loss Percentage"), loss_percentage)
            innerLayout.addRow(QLabel("Smart Stop Loss Counter"), smart_stop_loss_counter)

            if tab != self.backtestConfigurationTabWidget:
                self.lossDict[tab, "safetyTimer"] = safetyTimer = QSpinBox()
                safetyTimer.valueChanged.connect(lambda: self.update_loss_settings(tab))
                innerLayout.addRow(QLabel("Safety Timer"), safetyTimer)

            loss_type_combo_box.currentIndexChanged.connect(lambda: self.update_loss_settings(tab))
            loss_percentage.valueChanged.connect(lambda: self.update_loss_settings(tab))
            smart_stop_loss_counter.valueChanged.connect(lambda: self.update_loss_settings(tab))

    def create_take_profit_inputs(self, tab: QTabWidget, innerLayout: QLayout, isOptimizer: bool = False):
        """
        Creates inputs for take profit settings in GUI.
        :param tab: Tab to create inputs for - simulation, live, or backtest.
        :param innerLayout: Inner layout to place input widgets on.
        :param isOptimizer: Boolean for whether optimizer method called this function.
        """
        if isOptimizer:
            self.takeProfitDict['optimizerTypes'] = []
            innerLayout.addRow(QLabel("Take Profit Types"))
            for take_profit_type in self.takeProfitTypes:
                checkbox = QCheckBox(f'Enable {take_profit_type} take profit?')
                innerLayout.addRow(checkbox)
                self.takeProfitDict['optimizerTypes'].append((take_profit_type, checkbox))

            for optimizer_type in self.takeProfitOptimizerTypes:
                self.takeProfitDict[optimizer_type, 'start'] = start = get_default_widget(QSpinBox, 1, 0)
                self.takeProfitDict[optimizer_type, 'end'] = end = get_default_widget(QSpinBox, 1, 0)
                self.takeProfitDict[optimizer_type, 'step'] = step = get_default_widget(QSpinBox, 1)
                add_start_end_step_to_layout(innerLayout, optimizer_type, start, end, step)
        else:
            self.takeProfitDict[tab, 'takeProfitType'] = take_profit_type_combo_box = QComboBox()
            self.takeProfitDict[tab, 'takeProfitPercentage'] = take_profit_percentage = QDoubleSpinBox()

            take_profit_type_combo_box.addItems(self.takeProfitTypes)
            take_profit_type_combo_box.currentIndexChanged.connect(lambda: self.update_take_profit_settings(tab))
            take_profit_percentage.setValue(5)
            take_profit_percentage.valueChanged.connect(lambda: self.update_take_profit_settings(tab))

            innerLayout.addRow(QLabel("Take Profit Type"), take_profit_type_combo_box)
            innerLayout.addRow(QLabel('Take Profit Percentage'), take_profit_percentage)

    def set_loss_settings(self, caller: int, config: dict):
        """
        Sets loss settings to GUI from configuration dictionary provided.
        :param caller: This caller's tab's GUI will be modified by this function.
        :param config: Configuration dictionary from which to get loss settings.
        """
        if "lossTypeIndex" not in config:  # We don't have this data in config, so just return.
            return

        tab = self.get_category_tab(caller)
        self.lossDict[tab, "lossType"].setCurrentIndex(config["lossTypeIndex"])
        self.lossDict[tab, "lossPercentage"].setValue(config["lossPercentage"])
        self.lossDict[tab, "smartStopLossCounter"].setValue(config["smartStopLossCounter"])

        if tab != self.backtestConfigurationTabWidget:
            self.lossDict[tab, 'safetyTimer'].setValue(config["safetyTimer"])

    def set_take_profit_settings(self, caller: int, config: dict):
        """
        Sets take profit settings to GUI from configuration dictionary provided.
        :param caller: This caller's tab's GUI will be modified by this function.
        :param config: Configuration dictionary from which to get take profit settings.
        """
        if "takeProfitTypeIndex" not in config:  # We don't have this data in config, so just return.
            return

        tab = self.get_category_tab(caller)
        self.takeProfitDict[tab, 'takeProfitType'].setCurrentIndex(config["takeProfitTypeIndex"])
        self.takeProfitDict[tab, 'takeProfitPercentage'].setValue(config["takeProfitPercentage"])

    def get_take_profit_settings(self, caller) -> dict:
        """
        Returns take profit settings from GUI.
        :param caller: Caller that'll determine which take profit settings get returned.
        :return: Dictionary including take profit settings.
        """
        tab = self.get_category_tab(caller)
        dictionary = self.takeProfitDict
        if dictionary[tab, 'groupBox'].isChecked():
            if dictionary[tab, 'takeProfitType'].currentText() == "Trailing":
                take_profit_type = TRAILING
            else:
                take_profit_type = STOP
        else:
            take_profit_type = None

        return {
            'takeProfitType': take_profit_type,
            'takeProfitTypeIndex': dictionary[tab, 'takeProfitType'].currentIndex(),
            'takeProfitPercentage': dictionary[tab, 'takeProfitPercentage'].value()
        }

    def update_loss_settings(self, tab: QTabWidget):
        """
        Update loss settings based on the tab provided.
        :param tab: Tab to update loss settings for.
        """
        caller = self.get_caller_based_on_tab(tab)
        trader = self.parent.get_trader(caller)

        if trader is not None and caller != BACKTEST:  # Skip backtester for now.
            settings = self.get_loss_settings(caller)
            trader.apply_loss_settings(settings)

    def update_take_profit_settings(self, tab: QTabWidget):
        """
        Update take profit settings based on the tab provided.
        :param tab: Tab to update take profit settings for.
        """
        caller = self.get_caller_based_on_tab(tab)
        trader = self.parent.get_trader(caller)

        if trader is not None and caller != BACKTEST:  # Skip backtester for now.
            settings = self.get_take_profit_settings(caller)
            trader.apply_take_profit_settings(settings)

    def get_loss_settings(self, caller: int) -> dict:
        """
        Returns loss settings from GUI.
        :param caller: Caller that'll determine which loss settings get returned.
        :return: Dictionary including loss settings.
        """
        tab = self.get_category_tab(caller)
        dictionary = self.lossDict
        if dictionary[tab, 'groupBox'].isChecked():
            loss_type = TRAILING if dictionary[tab, "lossType"].currentText() == "Trailing" else STOP
        else:
            loss_type = None

        loss_settings = {
            'lossType': loss_type,
            'lossTypeIndex': dictionary[tab, "lossType"].currentIndex(),
            'lossPercentage': dictionary[tab, 'lossPercentage'].value(),
            'smartStopLossCounter': dictionary[tab, 'smartStopLossCounter'].value()
        }

        if tab != self.backtestConfigurationTabWidget:
            loss_settings['safetyTimer'] = dictionary[tab, 'safetyTimer'].value()

        return loss_settings

    def add_strategy_to_config(self, caller: int, strategyName: str, config: dict):
        """
        Adds strategy configuration to config dictionary provided.
        :param caller: Caller that'll determine which trader's strategy settings get added to the config dictionary.
        :param strategyName: Name of strategy to add.
        :param config: Dictionary to add strategy information to.
        :return: None
        """
        values = get_strategy_values(self, strategyName, caller)
        config[strategyName.lower()] = strategy_enabled(self, strategyName, caller)
        config[f'{strategyName.lower()}Length'] = len(values)
        for index, value in enumerate(values, start=1):
            config[f'{strategyName.lower()}{index}'] = value

    def load_strategy_from_config(self, caller: int, strategyName: str, config: dict):
        """
        This function will load the strategy from the config dictionary provided.
        :param caller: Caller to manipulate.
        :param strategyName: Name of strategy to load.
        :param config: Configuration dictionary to load.
        :return: None
        """
        key = f'{strategyName.lower()}Length'
        if key not in config:
            return

        value_count = config[key]
        tab = self.get_category_tab(caller)
        value_widgets = self.strategyDict[tab, strategyName, 'values']
        parameters = self.strategyDict[tab, strategyName, 'parameters']
        group_box_layout = self.strategyDict[tab, strategyName, 'layout']

        self.strategyDict[tab, strategyName, 'groupBox'].setChecked(config[f'{strategyName.lower()}'])

        while value_count > len(value_widgets):
            add_strategy_inputs(self.strategyDict, parameters, strategyName, group_box_layout, tab)
        while value_count < len(value_widgets):
            delete_strategy_inputs(self.strategyDict, parameters, strategyName, tab)

        for index, widget in enumerate(value_widgets, start=1):
            value = config[f'{strategyName.lower()}{index}']
            set_value(widget, value)
