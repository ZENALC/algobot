"""
Configuration window.
"""

from __future__ import annotations

import os
from logging import Logger
from typing import TYPE_CHECKING

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QLabel, QLayout, QSpinBox, QTabWidget,
                             QWidget)

from algobot.enums import ALL_TRENDS, BACKTEST, LIVE, OPTIMIZER, SIMULATION, STOP, TRAILING
from algobot.graph_helpers import create_infinite_line
from algobot.helpers import ROOT_DIR
from algobot.interface.config_utils.credential_utils import load_credentials
from algobot.interface.config_utils.slot_utils import load_hide_show_strategies, load_slots
from algobot.interface.configuration_helpers import (add_start_end_step_to_layout, get_default_widget,
                                                     get_input_widget_value)
# noinspection PyUnresolvedReferences
from algobot.interface.utils import clear_layout, get_elements_from_combobox
from algobot.strategies import *  # noqa: F403, F401 pylint: disable=wildcard-import,unused-wildcard-import
from algobot.strategies.loader import get_json_strategies

if TYPE_CHECKING:
    from algobot.__main__ import Interface

configurationUi = os.path.join(ROOT_DIR, 'UI', 'configuration.ui')


class Configuration(QDialog):
    """
    Configuration window.
    """
    def __init__(self, parent: Interface, logger: Logger = None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.parent = parent
        self.thread_pool = QThreadPool()
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

        self.loss_types = ("Trailing", "Stop")
        self.take_profit_types = ('Stop',)
        self.loss_optimizer_types = ('lossPercentage', 'stopLossCounter')
        self.take_profit_optimizer_types = ('takeProfitPercentage',)

        # Telegram
        self.token_pass = False
        self.chat_pass = False

        # Folders and files
        self.credentials_folder = "Credentials"
        self.config_folder = 'Configuration'
        self.state_file_path = os.path.join(ROOT_DIR, 'state.json')

        self.category_tabs = [
            self.mainConfigurationTabWidget,
            self.simulationConfigurationTabWidget,
            self.backtestConfigurationTabWidget,
            self.optimizerConfigurationTabWidget
        ]

        self.json_strategies = get_json_strategies(self.parent.add_to_live_activity_monitor)

        # Hidden strategies dynamically populated.
        self.hidden_strategies = set(self.json_strategies)

        self.strategy_dict = {}  # We will store all the strategy slot information in this dictionary.
        self.loss_dict = {}  # We will store stop loss settings here.
        self.take_profit_dict = {}  # We will store take profit settings here.

        load_slots(self)  # Loads stop loss, take profit, and strategies slots.
        load_credentials(self)  # Load credentials if they exist.

    def reload_custom_strategies(self):
        """
        Reload custom strategies after creating a strategy.
        """
        self.json_strategies = get_json_strategies(self.parent.add_to_live_activity_monitor)
        self.hidden_strategies = set(self.json_strategies)

        clear_layout(self.hideStrategiesFormLayout)
        load_hide_show_strategies(self)

    def enable_disable_hover_line(self):
        """
        Enables or disables the hover line based on whether its checkmark is ticked or not.
        """
        enable = self.enableHoverLine.isChecked()
        if enable:
            for graph_dict in self.parent.graphs:
                if len(graph_dict['plots']) > 0:
                    create_infinite_line(gui=self.parent, graph_dict=graph_dict)
        else:
            for graph_dict in self.parent.graphs:
                hover_line = graph_dict.get('line')
                self.parent.reset_backtest_cursor()
                if hover_line:
                    graph_dict['graph'].removeItem(hover_line)
                    graph_dict['line'] = None

    def update_graph_speed(self):
        """
        Updates graph speed on main Algobot interface.
        """
        graph_speed = self.graphPlotSpeedSpinBox.value()
        self.parent.graph_update_seconds = graph_speed
        self.parent.add_to_live_activity_monitor(f"Updated graph plot speed to every {graph_speed} second(s).")

    def get_caller_based_on_tab(self, tab: QTabWidget) -> str:
        """
        This will return a caller based on the tab provided.
        :param tab: Tab for which the caller will be returned.
        :return: Caller for which this tab corresponds to.
        """
        if tab == self.category_tabs[2]:
            return BACKTEST
        elif tab == self.category_tabs[1]:
            return SIMULATION
        elif tab == self.category_tabs[0]:
            return LIVE
        elif tab == self.category_tabs[3]:
            return OPTIMIZER
        else:
            raise ValueError("Invalid tab provided. No known called associated with this tab.")

    def get_category_tab(self, caller: str) -> QTabWidget:
        """
        This will return the category tab (main, simulation, or live) based on the caller provided.
        :param caller: Caller argument to return the appropriate category tab.
        :return: Category tab widget object.
        """
        if caller == BACKTEST:
            return self.category_tabs[2]
        elif caller == SIMULATION:
            return self.category_tabs[1]
        elif caller == LIVE:
            return self.category_tabs[0]
        elif caller == OPTIMIZER:
            return self.category_tabs[3]
        else:
            raise ValueError("Invalid type of caller provided.")

    @staticmethod
    def helper_get_optimizer(optimizer_tab, dictionary: dict, key: str, optimizer_types: tuple, settings: dict):
        """
        Helper function to get optimizer settings and modify the settings dictionary based on the dictionary provided.
        :param optimizer_tab: Optimizer tab.
        :param dictionary: Specific dictionary that is either the loss dictionary or the take profit dictionary.
        :param key: Key to populate in the settings dictionary.
        :param optimizer_types: Optimizer types.
        :param settings: Dictionary to modify.
        """
        if dictionary[optimizer_tab, 'groupBox'].isChecked():
            settings[key] = []
            for string, check_box in dictionary['optimizerTypes']:
                if check_box.isChecked():
                    settings[key].append(string)

            if len(settings[key]) > 0:
                for opt in optimizer_types:
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

    def parse_optimizer_dict(self, settings: dict) -> dict:
        """
        Convert QT objects to their respective tests for optimizer.
        :param settings: Dictionary containing QT objects.
        :return: Converted dictionary with the values.
        """
        new_settings = {}
        for key, val in settings.items():
            if isinstance(val, dict):
                new_settings[key] = self.parse_optimizer_dict(val)
            elif isinstance(val, QWidget):
                if isinstance(val, QCheckBox) and not val.isChecked():
                    continue

                new_settings[key] = get_input_widget_value(val, verbose=True)
            elif isinstance(val, list):
                values = [get_input_widget_value(value, verbose=True) for value in val
                          if not isinstance(value, QCheckBox) or isinstance(value, QCheckBox) and value.isChecked()]
                new_settings[key] = values
            else:
                new_settings[key] = val

        for trend in ALL_TRENDS:  # We must remove unused trend indicator values if non-existent.
            if trend in new_settings and len(new_settings[trend]) == 0:
                del new_settings[trend]

        return new_settings

    def get_optimizer_settings(self) -> dict:
        """
        Returns optimizer configuration in a dictionary.
        """
        tab = self.get_category_tab(OPTIMIZER)
        settings = {}

        self.helper_get_optimizer(tab, self.loss_dict, 'lossType', self.loss_optimizer_types, settings)
        self.helper_get_optimizer(tab, self.take_profit_dict, 'takeProfitType', self.take_profit_optimizer_types,
                                  settings)
        self.get_strategy_intervals_for_optimizer(settings)

        settings['strategies'] = {}
        for strategy_name in self.json_strategies:
            if strategy_name in self.hidden_strategies or \
                    not self.strategy_dict[tab, strategy_name, 'groupBox'].isChecked():
                continue

            settings['strategies'][strategy_name] = self.parse_optimizer_dict(self.strategy_dict[tab, strategy_name])

        return settings

    def create_loss_inputs(self, tab: QTabWidget, inner_layout: QLayout, is_optimizer: bool = False):
        """
        Creates inputs for loss settings in GUI.
        :param tab: Tab to create inputs for - simulation, live, or backtest.
        :param inner_layout: Inner layout to place input widgets on.
        :param is_optimizer: Boolean for whether optimizer method called this function.
        """
        if is_optimizer:
            self.loss_dict['optimizerTypes'] = []
            inner_layout.addRow(QLabel("Loss Types"))
            for loss_type in self.loss_types:
                checkbox = QCheckBox(f'Enable {loss_type.lower()} type of stop loss?')
                inner_layout.addRow(checkbox)
                self.loss_dict['optimizerTypes'].append((loss_type, checkbox))

            for optimizer_type in self.loss_optimizer_types:
                self.loss_dict[optimizer_type, 'start'] = start = get_default_widget(QSpinBox, 1, 0)
                self.loss_dict[optimizer_type, 'end'] = end = get_default_widget(QSpinBox, 1, 0)
                self.loss_dict[optimizer_type, 'step'] = step = get_default_widget(QSpinBox, 1)
                add_start_end_step_to_layout(inner_layout, optimizer_type, start, end, step)
        else:
            self.loss_dict[tab, "lossType"] = loss_type_combo_box = QComboBox()
            self.loss_dict[tab, "lossPercentage"] = loss_percentage = QDoubleSpinBox()
            self.loss_dict[tab, "smartStopLossCounter"] = smart_stop_loss_counter = QSpinBox()

            loss_type_combo_box.addItems(self.loss_types)
            loss_percentage.setValue(5)

            inner_layout.addRow(QLabel("Loss Type"), loss_type_combo_box)
            inner_layout.addRow(QLabel("Loss Percentage"), loss_percentage)
            inner_layout.addRow(QLabel("Smart Stop Loss Counter"), smart_stop_loss_counter)

            if tab != self.backtestConfigurationTabWidget:
                self.loss_dict[tab, "safetyTimer"] = safety_timer = QSpinBox()
                safety_timer.valueChanged.connect(lambda: self.update_loss_settings(tab))
                inner_layout.addRow(QLabel("Safety Timer"), safety_timer)

            loss_type_combo_box.currentIndexChanged.connect(lambda: self.update_loss_settings(tab))
            loss_percentage.valueChanged.connect(lambda: self.update_loss_settings(tab))
            smart_stop_loss_counter.valueChanged.connect(lambda: self.update_loss_settings(tab))

    def create_take_profit_inputs(self, tab: QTabWidget, inner_layout: QLayout, is_optimizer: bool = False):
        """
        Creates inputs for take profit settings in GUI.
        :param tab: Tab to create inputs for - simulation, live, or backtest.
        :param inner_layout: Inner layout to place input widgets on.
        :param is_optimizer: Boolean for whether optimizer method called this function.
        """
        if is_optimizer:
            self.take_profit_dict['optimizerTypes'] = []
            inner_layout.addRow(QLabel("Take Profit Types"))
            for take_profit_type in self.take_profit_types:
                checkbox = QCheckBox(f'Enable {take_profit_type} take profit?')
                inner_layout.addRow(checkbox)
                self.take_profit_dict['optimizerTypes'].append((take_profit_type, checkbox))

            for optimizer_type in self.take_profit_optimizer_types:
                self.take_profit_dict[optimizer_type, 'start'] = start = get_default_widget(QSpinBox, 1, 0)
                self.take_profit_dict[optimizer_type, 'end'] = end = get_default_widget(QSpinBox, 1, 0)
                self.take_profit_dict[optimizer_type, 'step'] = step = get_default_widget(QSpinBox, 1)
                add_start_end_step_to_layout(inner_layout, optimizer_type, start, end, step)
        else:
            self.take_profit_dict[tab, 'takeProfitType'] = take_profit_type_combo_box = QComboBox()
            self.take_profit_dict[tab, 'takeProfitPercentage'] = take_profit_percentage = QDoubleSpinBox()

            take_profit_type_combo_box.addItems(self.take_profit_types)
            take_profit_type_combo_box.currentIndexChanged.connect(lambda: self.update_take_profit_settings(tab))
            take_profit_percentage.setValue(5)
            take_profit_percentage.valueChanged.connect(lambda: self.update_take_profit_settings(tab))

            inner_layout.addRow(QLabel("Take Profit Type"), take_profit_type_combo_box)
            inner_layout.addRow(QLabel('Take Profit Percentage'), take_profit_percentage)

    def set_loss_settings(self, caller: str, config: dict):
        """
        Sets loss settings to GUI from configuration dictionary provided.
        :param caller: This caller's tab's GUI will be modified by this function.
        :param config: Configuration dictionary from which to get loss settings.
        """
        if "lossTypeIndex" not in config:  # We don't have this data in config, so just return.
            return

        tab = self.get_category_tab(caller)
        self.loss_dict[tab, "lossType"].setCurrentIndex(config["lossTypeIndex"])
        self.loss_dict[tab, "lossPercentage"].setValue(config["lossPercentage"])
        self.loss_dict[tab, "smartStopLossCounter"].setValue(config["smartStopLossCounter"])

        if tab != self.backtestConfigurationTabWidget:
            self.loss_dict[tab, 'safetyTimer'].setValue(config["safetyTimer"])

    def set_take_profit_settings(self, caller: str, config: dict):
        """
        Sets take profit settings to GUI from configuration dictionary provided.
        :param caller: This caller's tab's GUI will be modified by this function.
        :param config: Configuration dictionary from which to get take profit settings.
        """
        if "takeProfitTypeIndex" not in config:  # We don't have this data in config, so just return.
            return

        tab = self.get_category_tab(caller)
        self.take_profit_dict[tab, 'takeProfitType'].setCurrentIndex(config["takeProfitTypeIndex"])
        self.take_profit_dict[tab, 'takeProfitPercentage'].setValue(config["takeProfitPercentage"])

    def get_take_profit_settings(self, caller) -> dict:
        """
        Returns take profit settings from GUI.
        :param caller: Caller that'll determine which take profit settings get returned.
        :return: Dictionary including take profit settings.
        """
        tab = self.get_category_tab(caller)
        dictionary = self.take_profit_dict
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

    def get_loss_settings(self, caller: str) -> dict:
        """
        Returns loss settings from GUI.
        :param caller: Caller that'll determine which loss settings get returned.
        :return: Dictionary including loss settings.
        """
        tab = self.get_category_tab(caller)
        dictionary = self.loss_dict
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
