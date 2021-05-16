import os
from logging import Logger
from typing import List, Union

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QHBoxLayout, QLabel, QLayout,
                             QMainWindow, QScrollArea, QSpinBox, QTabWidget,
                             QVBoxLayout, QWidget)

import algobot.helpers as helpers
from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION, STOP, TRAILING
from algobot.graph_helpers import create_infinite_line
from algobot.interface.config_utils.calendar_utils import setup_calendar
from algobot.interface.config_utils.credential_utils import (
    load_credentials, save_credentials, test_binance_credentials)
from algobot.interface.config_utils.telegram_utils import (
    reset_telegram_state, test_telegram)
from algobot.interface.config_utils.user_config_utils import (
    copy_settings_to_backtest, copy_settings_to_simulation,
    load_backtest_settings, load_live_settings, load_simulation_settings,
    save_backtest_settings, save_live_settings, save_simulation_settings)
from algobot.interface.configuration_helpers import (
    add_strategy_buttons, add_strategy_inputs, create_inner_tab,
    create_strategy_inputs, delete_strategy_inputs, get_default_widget,
    get_input_widget_value, get_regular_groupbox_and_layout,
    get_strategies_dictionary, set_value)
# noinspection PyUnresolvedReferences
from algobot.strategies import *  # noqa: F403, F401
from algobot.strategies.strategy import Strategy
from algobot.threads import downloadThread

configurationUi = os.path.join(helpers.ROOT_DIR, 'UI', 'configuration.ui')


class Configuration(QDialog):
    def __init__(self, parent: QMainWindow, logger: Logger = None):
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
        self.lossOptimizerTypes = ('lossPercentage', 'stopLossCounter')
        self.takeProfitTypes = ('Stop',)
        self.takeProfitOptimizerTypes = ('takeProfitPercentage',)

        # Telegram
        self.tokenPass = False
        self.chatPass = False

        # Folders and files
        self.credentialsFolder = "Credentials"
        self.configFolder = 'Configuration'
        self.basicFilePath = os.path.join(helpers.ROOT_DIR, 'state.json')

        self.categoryTabs = [
            self.mainConfigurationTabWidget,
            self.simulationConfigurationTabWidget,
            self.backtestConfigurationTabWidget,
            self.optimizerConfigurationTabWidget
        ]

        self.strategies = get_strategies_dictionary(Strategy.__subclasses__())
        self.strategyDict = {}  # We will store all the strategy slot information in this dictionary.
        self.lossDict = {}  # We will store stop loss settings here.
        self.takeProfitDict = {}  # We will store take profit settings here.

        self.load_combo_boxes()  # Primarily used for backtest interval changer logic.
        self.load_slots()  # Loads stop loss, take profit, and strategies slots.
        load_credentials(self)  # Load credentials if they exist.

    def enable_disable_hover_line(self):
        """
        Enables or disables the hover line based on whether its checkmark is ticked or not.
        """
        enable = self.enableHoverLine.isChecked()
        if enable:
            for graphDict in self.parent.graphs:
                if len(graphDict['plots']) > 0:
                    create_infinite_line(gui=self.parent, graphDict=graphDict)
        else:
            for graphDict in self.parent.graphs:
                hoverLine = graphDict.get('line')
                self.parent.reset_backtest_cursor()
                if hoverLine:
                    graphDict['graph'].removeItem(hoverLine)
                    graphDict['line'] = None

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

    def load_loss_slots(self):
        """
        Loads slots for loss settings in GUI.
        """
        create_inner_tab(
            categoryTabs=self.categoryTabs,
            description="Configure your stop loss settings here.",
            tabName="Stop Loss",
            input_creator=self.create_loss_inputs,
            dictionary=self.lossDict,
            signalFunction=self.update_loss_settings,
            parent=self
        )

    def load_take_profit_slots(self):
        """
        Loads slots for take profit settings in GUI.
        """
        create_inner_tab(
            categoryTabs=self.categoryTabs,
            description="Configure your take profit settings here.",
            tabName="Take Profit",
            input_creator=self.create_take_profit_inputs,
            dictionary=self.takeProfitDict,
            signalFunction=self.update_take_profit_settings,
            parent=self
        )

    @staticmethod
    def helper_get_optimizer(tab, dictionary: dict, key: str, optimizerTypes: tuple, settings: dict):
        """
        Helper function to get optimizer settings based on the dictionary provided.
        """
        if dictionary[tab, 'groupBox'].isChecked():
            settings[key] = []
            for string, checkBox in dictionary['optimizerTypes']:
                if checkBox.isChecked():
                    settings[key].append(string)

            if len(settings[key]) > 0:
                for opt in optimizerTypes:
                    start, end, step = (dictionary[opt, 'start'].value(), dictionary[opt, 'end'].value(),
                                        dictionary[opt, 'step'].value())
                    settings[opt] = (start, end, step)
            else:
                del settings[key]

    def get_optimizer_settings(self) -> dict:
        """
        Returns optimizer configuration in a dictionary.
        """
        tab = self.get_category_tab(OPTIMIZER)
        settings = {}

        self.helper_get_optimizer(tab, self.lossDict, 'lossType', self.lossOptimizerTypes, settings)
        self.helper_get_optimizer(tab, self.takeProfitDict, 'takeProfitType', self.takeProfitOptimizerTypes, settings)

        settings['strategies'] = {}
        for strategy in self.strategies.values():
            temp = strategy()
            strategyName = temp.name
            parameters = temp.get_param_types()
            if self.strategyDict[tab, strategyName].isChecked():
                current = {}
                for index, parameter in enumerate(parameters, start=1):
                    if type(parameter) == tuple and parameter[1] in (int, float) or type(parameter) != tuple:
                        if type(parameter) == type:
                            key = strategyName.lower() + str(index)
                        else:
                            key = parameter[0]
                        current[key] = (
                            self.strategyDict[strategyName, index, 'start'].value(),
                            self.strategyDict[strategyName, index, 'end'].value(),
                            self.strategyDict[strategyName, index, 'step'].value(),
                        )
                    else:
                        current[parameter[0]] = []
                        for option in parameter[2]:
                            if self.strategyDict[strategyName, option].isChecked():
                                current[parameter[0]].append(option)
                settings['strategies'][strategyName] = current
        return settings

    @staticmethod
    def add_start_end_step_to_layout(layout: QLayout, msg: str, start: QWidget, end: QWidget, step: QWidget):
        """
        Adds start, end, and step rows to the layout provided.
        """
        layout.addRow(QLabel(f"{helpers.get_label_string(msg)} Optimization"))
        layout.addRow("Start", start)
        layout.addRow("End", end)
        layout.addRow("Step", step)

        start.valueChanged.connect(lambda: (end.setValue(start.value()), end.setMinimum(start.value())))

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
            for lossType in self.lossTypes:
                checkbox = QCheckBox(f'Enable {lossType.lower()} type of stop loss?')
                innerLayout.addRow(checkbox)
                self.lossDict['optimizerTypes'].append((lossType, checkbox))

            for optimizerType in self.lossOptimizerTypes:
                self.lossDict[optimizerType, 'start'] = start = get_default_widget(QSpinBox, 1, 0)
                self.lossDict[optimizerType, 'end'] = end = get_default_widget(QSpinBox, 1, 0)
                self.lossDict[optimizerType, 'step'] = step = get_default_widget(QSpinBox, 1)
                self.add_start_end_step_to_layout(innerLayout, optimizerType, start, end, step)
        else:
            self.lossDict[tab, "lossType"] = lossTypeComboBox = QComboBox()
            self.lossDict[tab, "lossPercentage"] = lossPercentage = QDoubleSpinBox()
            self.lossDict[tab, "smartStopLossCounter"] = smartStopLossCounter = QSpinBox()

            lossTypeComboBox.addItems(self.lossTypes)
            lossPercentage.setValue(5)

            innerLayout.addRow(QLabel("Loss Type"), lossTypeComboBox)
            innerLayout.addRow(QLabel("Loss Percentage"), lossPercentage)
            innerLayout.addRow(QLabel("Smart Stop Loss Counter"), smartStopLossCounter)

            if tab != self.backtestConfigurationTabWidget:
                self.lossDict[tab, "safetyTimer"] = safetyTimer = QSpinBox()
                safetyTimer.valueChanged.connect(lambda: self.update_loss_settings(tab))
                innerLayout.addRow(QLabel("Safety Timer"), safetyTimer)

            lossTypeComboBox.currentIndexChanged.connect(lambda: self.update_loss_settings(tab))
            lossPercentage.valueChanged.connect(lambda: self.update_loss_settings(tab))
            smartStopLossCounter.valueChanged.connect(lambda: self.update_loss_settings(tab))

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
            for takeProfitType in self.takeProfitTypes:
                checkbox = QCheckBox(f'Enable {takeProfitType} take profit?')
                innerLayout.addRow(checkbox)
                self.takeProfitDict['optimizerTypes'].append((takeProfitType, checkbox))

            for optimizerType in self.takeProfitOptimizerTypes:
                self.takeProfitDict[optimizerType, 'start'] = start = get_default_widget(QSpinBox, 1, 0)
                self.takeProfitDict[optimizerType, 'end'] = end = get_default_widget(QSpinBox, 1, 0)
                self.takeProfitDict[optimizerType, 'step'] = step = get_default_widget(QSpinBox, 1)
                self.add_start_end_step_to_layout(innerLayout, optimizerType, start, end, step)
        else:
            self.takeProfitDict[tab, 'takeProfitType'] = takeProfitTypeComboBox = QComboBox()
            self.takeProfitDict[tab, 'takeProfitPercentage'] = takeProfitPercentage = QDoubleSpinBox()

            takeProfitTypeComboBox.addItems(self.takeProfitTypes)
            takeProfitTypeComboBox.currentIndexChanged.connect(lambda: self.update_take_profit_settings(tab))
            takeProfitPercentage.setValue(5)
            takeProfitPercentage.valueChanged.connect(lambda: self.update_take_profit_settings(tab))

            innerLayout.addRow(QLabel("Take Profit Type"), takeProfitTypeComboBox)
            innerLayout.addRow(QLabel('Take Profit Percentage'), takeProfitPercentage)

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
                takeProfitType = TRAILING
            else:
                takeProfitType = STOP
        else:
            takeProfitType = None

        return {
            'takeProfitType': takeProfitType,
            'takeProfitTypeIndex': dictionary[tab, 'takeProfitType'].currentIndex(),
            'takeProfitPercentage': dictionary[tab, 'takeProfitPercentage'].value()
        }

    def update_loss_settings(self, tab: QTabWidget):
        caller = self.get_caller_based_on_tab(tab)
        trader = self.parent.get_trader(caller)

        if trader is not None and caller != BACKTEST:  # Skip backtester for now.
            settings = self.get_loss_settings(caller)
            trader.apply_loss_settings(settings)

    def update_take_profit_settings(self, tab: QTabWidget):
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
            lossType = TRAILING if dictionary[tab, "lossType"].currentText() == "Trailing" else STOP
        else:
            lossType = None

        lossSettings = {
            'lossType': lossType,
            'lossTypeIndex': dictionary[tab, "lossType"].currentIndex(),
            'lossPercentage': dictionary[tab, 'lossPercentage'].value(),
            'smartStopLossCounter': dictionary[tab, 'smartStopLossCounter'].value()
        }

        if tab != self.backtestConfigurationTabWidget:
            lossSettings['safetyTimer'] = dictionary[tab, 'safetyTimer'].value()

        return lossSettings

    def get_strategies(self, caller: int) -> List[tuple]:
        """
        Returns strategy information from GUI.
        :param caller: Caller that asked for strategy information.
        :return: List of strategy information.
        """
        strategies = []
        for strategyName, strategy in self.strategies.items():
            if self.strategy_enabled(strategyName, caller):
                values = self.get_strategy_values(strategyName, caller, verbose=True)
                strategyTuple = (strategy, values, strategyName)
                strategies.append(strategyTuple)

        return strategies

    def strategy_enabled(self, strategyName: str, caller: int) -> bool:
        """
        Returns a boolean whether a strategy is enabled or not.
        :param strategyName: Name of strategy to check if enabled.
        :param caller: Caller of the strategy.
        :return: Boolean whether strategy is enabled or not.
        """
        tab = self.get_category_tab(caller)
        return self.strategyDict[tab, strategyName, 'groupBox'].isChecked()

    def get_strategy_values(self, strategyName: str, caller: int, verbose: bool = False) -> List[int]:
        """
        This will return values from the strategy provided.
        :param verbose: If verbose, return value of widget when possible.
        :param strategyName: Name of strategy to get values from.
        :param caller: Caller that'll determine which tab object is used to get the strategy values.
        :return: List of strategy values.
        """
        tab = self.get_category_tab(caller)
        values = []
        for inputWidget in self.strategyDict[tab, strategyName, 'values']:
            values.append(get_input_widget_value(inputWidget, verbose=verbose))

        return values

    def load_strategy_slots(self):
        """
        This will initialize all the necessary strategy slots and add them to the configuration GUI. All the strategies
        are loaded from the self.strategies dictionary.
        :return: None
        """
        for strategy in self.strategies.values():
            temp = strategy()
            strategyName = temp.name
            parameters = temp.get_param_types()
            for tab in self.categoryTabs:
                self.strategyDict[tab, strategyName] = tabWidget = QTabWidget()
                descriptionLabel = QLabel(f'Strategy description: {temp.description}')
                descriptionLabel.setWordWrap(True)

                layout = QVBoxLayout()
                layout.addWidget(descriptionLabel)

                scroll = QScrollArea()  # Added a scroll area so user can scroll when additional slots are added.
                scroll.setWidgetResizable(True)

                if self.get_caller_based_on_tab(tab) == OPTIMIZER:
                    groupBox, groupBoxLayout = get_regular_groupbox_and_layout(f'Enable {strategyName} optimization?')
                    self.strategyDict[tab, strategyName] = groupBox
                    for index, parameter in enumerate(parameters, start=1):
                        # TODO: Refactor this logic.
                        if type(parameter) != tuple or type(parameter) == tuple and parameter[1] in [int, float]:
                            if type(parameter) == tuple:
                                widget = QSpinBox if parameter[1] == int else QDoubleSpinBox
                                step_val = 1 if widget == QSpinBox else 0.1
                            else:
                                widget = QSpinBox if parameter == int else QDoubleSpinBox
                                step_val = 1 if widget == QSpinBox else 0.1
                            self.strategyDict[strategyName, index, 'start'] = start = get_default_widget(widget, 1)
                            self.strategyDict[strategyName, index, 'end'] = end = get_default_widget(widget, 1)
                            self.strategyDict[strategyName, index, 'step'] = step = get_default_widget(widget, step_val)
                            if type(parameter) == tuple:
                                message = parameter[0]
                            else:
                                message = f"{strategyName} {index}"
                            self.add_start_end_step_to_layout(groupBoxLayout, message, start, end, step)
                        elif type(parameter) == tuple and parameter[1] == tuple:
                            groupBoxLayout.addRow(QLabel(parameter[0]))
                            for option in parameter[2]:
                                self.strategyDict[strategyName, option] = checkBox = QCheckBox(option)
                                groupBoxLayout.addRow(checkBox)
                        else:
                            raise ValueError("Invalid type of parameter type provided.")
                else:
                    groupBox, groupBoxLayout = get_regular_groupbox_and_layout(f"Enable {strategyName}?")
                    self.strategyDict[tab, strategyName, 'groupBox'] = groupBox

                    status = QLabel()
                    if temp.dynamic:
                        addButton, deleteButton = add_strategy_buttons(self.strategyDict, parameters, strategyName,
                                                                       groupBoxLayout, tab)
                        horizontalLayout = QHBoxLayout()
                        horizontalLayout.addWidget(addButton)
                        horizontalLayout.addWidget(deleteButton)
                        horizontalLayout.addWidget(status)
                        horizontalLayout.addStretch()
                        layout.addLayout(horizontalLayout)

                    values, labels = create_strategy_inputs(parameters, strategyName, groupBoxLayout)
                    self.strategyDict[tab, strategyName, 'values'] = values
                    self.strategyDict[tab, strategyName, 'labels'] = labels
                    self.strategyDict[tab, strategyName, 'parameters'] = parameters
                    self.strategyDict[tab, strategyName, 'layout'] = groupBoxLayout
                    self.strategyDict[tab, strategyName, 'status'] = status

                layout.addWidget(scroll)
                scroll.setWidget(groupBox)
                tabWidget.setLayout(layout)
                tab.addTab(tabWidget, strategyName)

    def create_appropriate_config_folders(self, folder: str) -> str:
        """
        Creates appropriate configuration folders. If a configuration folder doesn't exist, it'll create that. Next,
        it'll try to check if a type of configuration folder exists (e.g. Live, Simulation, Backtest). If it exists,
        it'll just return the path to it. If not, it'll create the folder then return the path to it.
        :param folder: Folder to create inside configuration folder.
        :return: Absolute path to new folder.
        """
        basePath = os.path.join(helpers.ROOT_DIR, self.configFolder)
        helpers.create_folder_if_needed(basePath)

        targetPath = os.path.join(basePath, folder)
        helpers.create_folder_if_needed(targetPath, basePath=basePath)

        return targetPath

    def load_state(self):
        """
        This function will attempt to load previous basic configuration settings from self.basicFilePath.
        :return: None
        """
        if os.path.exists(self.basicFilePath):
            try:
                config = helpers.load_json_file(self.basicFilePath)

                self.lightModeRadioButton.setChecked(config['lightTheme'])
                self.darkModeRadioButton.setChecked(config['darkTheme'])
                self.bloombergModeRadioButton.setChecked(config['bloombergTheme'])
                self.bullModeRadioButton.setChecked(config['bullTheme'])
                self.bearModeRadioButton.setChecked(config['bearTheme'])

                self.balanceColor.setCurrentIndex(config['balanceColor'])
                self.avg1Color.setCurrentIndex(config['avg1Color'])
                self.avg2Color.setCurrentIndex(config['avg2Color'])
                self.avg3Color.setCurrentIndex(config['avg3Color'])
                self.avg4Color.setCurrentIndex(config['avg4Color'])
                self.hoverLineColor.setCurrentIndex(config['lineColor'])

                self.graphIndicatorsCheckBox.setChecked(config['averagePlot'])
                self.failureLimitSpinBox.setValue(int(config['failureLimit']))
                self.failureSleepSpinBox.setValue(int(config['failureSleep']))

                if self.parent:
                    self.parent.add_to_live_activity_monitor('Loaded previous state successfully.')
            except Exception as e:
                self.logger.exception(str(e))

                if self.parent:
                    self.parent.add_to_live_activity_monitor('Failed to fully load previous state. Try restarting.')

    def save_state(self):
        """
        Saves bot configuration to a JSON file for next application run.
        """
        config = {
            'lightTheme': self.lightModeRadioButton.isChecked(),
            'darkTheme': self.darkModeRadioButton.isChecked(),
            'bloombergTheme': self.bloombergModeRadioButton.isChecked(),
            'bullTheme': self.bullModeRadioButton.isChecked(),
            'bearTheme': self.bearModeRadioButton.isChecked(),
            'balanceColor': self.balanceColor.currentIndex(),
            'avg1Color': self.avg1Color.currentIndex(),
            'avg2Color': self.avg2Color.currentIndex(),
            'avg3Color': self.avg3Color.currentIndex(),
            'avg4Color': self.avg4Color.currentIndex(),
            'lineColor': self.hoverLineColor.currentIndex(),
            'averagePlot': self.graphIndicatorsCheckBox.isChecked(),
            'failureLimit': self.failureLimitSpinBox.value(),
            'failureSleep': self.failureSleepSpinBox.value()
        }

        helpers.write_json_file(self.basicFilePath, **config)

    def import_data(self, caller: int = BACKTEST):
        """
        Imports CSV data and loads it.
        """
        self.optimizer_backtest_dict[caller]['infoLabel'].setText("Importing data...")
        filePath, _ = QFileDialog.getOpenFileName(self, 'Open file', helpers.ROOT_DIR, "CSV (*.csv)")
        if filePath == '':
            self.optimizer_backtest_dict[caller]['infoLabel'].setText("Data not imported.")
        else:
            self.optimizer_backtest_dict[caller]['data'] = helpers.load_from_csv(filePath, descending=False)
            self.optimizer_backtest_dict[caller]['dataType'] = "Imported"
            self.optimizer_backtest_dict[caller]['infoLabel'].setText("Imported data successfully.")
            self.optimizer_backtest_dict[caller]['dataLabel'].setText('Using imported data to conduct backtest.')
            setup_calendar(config_obj=self, caller=caller)

    def download_data(self, caller: int = BACKTEST):
        """
        Loads data from data object. If the data object is empty, it downloads it.
        """
        self.optimizer_backtest_dict[caller]['downloadButton'].setEnabled(False)
        self.optimizer_backtest_dict[caller]['importButton'].setEnabled(False)
        self.set_download_progress(progress=0, message="Attempting to download...", caller=caller, enableStop=False)

        symbol = self.optimizer_backtest_dict[caller]['tickers'].text()
        interval = helpers.convert_long_interval(self.optimizer_backtest_dict[caller]['intervals'].currentText())

        thread = downloadThread.DownloadThread(symbol=symbol, interval=interval, caller=caller, logger=self.logger)
        thread.signals.progress.connect(self.set_download_progress)
        thread.signals.finished.connect(self.set_downloaded_data)
        thread.signals.error.connect(self.handle_download_failure)
        thread.signals.restore.connect(self.restore_download_state)
        thread.signals.locked.connect(lambda:
                                      self.optimizer_backtest_dict[caller]['stopDownloadButton'].setEnabled(False))
        self.optimizer_backtest_dict[caller]['downloadThread'] = thread
        self.threadPool.start(thread)

    def stop_download(self, caller: int = BACKTEST):
        """
        Stops download if download is in progress.
        :param caller: Caller that'll determine who called this function -> OPTIMIZER or BACKTEST
        """
        if self.optimizer_backtest_dict[caller]['downloadThread'] is not None:
            self.optimizer_backtest_dict[caller]['downloadLabel'].setText("Canceling download...")
            self.optimizer_backtest_dict[caller]['downloadThread'].stop()

    def set_download_progress(self, progress: int, message: str, caller: int = BACKTEST, enableStop: bool = True):
        """
        Sets download progress and message with parameters passed.
        :param enableStop: Boolean that'll determine if download can be stopped or not.
        :param caller: Caller that'll determine which caller was used.
        :param progress: Progress value to set bar at.
        :param message: Message to display in label.
        """
        if enableStop:
            self.optimizer_backtest_dict[caller]['stopDownloadButton'].setEnabled(True)

        if progress != -1:
            self.optimizer_backtest_dict[caller]['downloadProgress'].setValue(progress)
        self.optimizer_backtest_dict[caller]['downloadLabel'].setText(message)

    def restore_download_state(self, caller: int = BACKTEST):
        """
        Restores GUI to normal state.
        """
        self.optimizer_backtest_dict[caller]['downloadThread'] = None
        self.optimizer_backtest_dict[caller]['stopDownloadButton'].setEnabled(False)
        self.optimizer_backtest_dict[caller]['importButton'].setEnabled(True)
        self.optimizer_backtest_dict[caller]['downloadButton'].setEnabled(True)

    def handle_download_failure(self, e, caller: int = BACKTEST):
        """
        If download fails for backtest data, then GUI gets updated.
        :param caller: Caller that'll determine which caller was used.
        :param e: Error for why download failed.
        """
        self.set_download_progress(progress=-1, message='Download failed.', caller=caller, enableStop=False)
        self.optimizer_backtest_dict[caller]['infoLabel'].setText(f"Error occurred during download: {e}")

    def set_downloaded_data(self, data, caller: int = BACKTEST):
        """
        If download is successful, the data passed is set to backtest data.
        :param caller: Caller that'll determine which caller was used.
        :param data: Data to be used for backtesting.
        """
        symbol = self.optimizer_backtest_dict[caller]['tickers'].text()
        interval = self.optimizer_backtest_dict[caller]['intervals'].currentText().lower()

        self.optimizer_backtest_dict[caller]['data'] = data
        self.optimizer_backtest_dict[caller]['dataType'] = symbol
        self.optimizer_backtest_dict[caller]['infoLabel'].setText(f"Downloaded {interval} {symbol} data successfully.")
        self.optimizer_backtest_dict[caller]['dataLabel'].setText(f'Using {interval} {symbol} data to run backtest.')
        setup_calendar(config_obj=self, caller=caller)

    def helper_save(self, caller: int, config: dict):
        """
        Helper function to save caller configuration from GUI.
        :param caller: Caller to save configuration of.
        :param config: Configuration dictionary to dump info to.
        :return: None
        """
        config.update(self.get_loss_settings(caller))
        config.update(self.get_take_profit_settings(caller))
        for strategyName in self.strategies.keys():
            self.add_strategy_to_config(caller, strategyName, config)

    def helper_get_save_file_path(self, name: str) -> Union[str]:
        """
        Does necessary folder creations and returns save file path based on name provided.
        :param name: Name to use for file name and folder creation.
        :return: Absolute path to file.
        """
        name = name.capitalize()
        targetPath = self.create_appropriate_config_folders(name)
        defaultPath = os.path.join(targetPath, f'{name.lower()}_configuration.json')
        filePath, _ = QFileDialog.getSaveFileName(self, f'Save {name} Configuration', defaultPath, 'JSON (*.json)')
        return filePath

    def helper_load(self, caller: int, config: dict):
        """
        Helper function to load caller configuration to GUI.
        :param caller: Caller to load configuration to.
        :param config: Configuration dictionary to get info from.
        :return: None
        """
        self.set_loss_settings(caller, config)
        self.set_take_profit_settings(caller, config)
        for strategyName in self.strategies.keys():
            self.load_strategy_from_config(caller, strategyName, config)

    def add_strategy_to_config(self, caller: int, strategyName: str, config: dict):
        """
        Adds strategy configuration to config dictionary provided.
        :param caller: Caller that'll determine which trader's strategy settings get added to the config dictionary.
        :param strategyName: Name of strategy to add.
        :param config: Dictionary to add strategy information to.
        :return: None
        """
        values = self.get_strategy_values(strategyName, caller)
        config[strategyName.lower()] = self.strategy_enabled(strategyName, caller)
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

        valueCount = config[key]
        tab = self.get_category_tab(caller)
        valueWidgets = self.strategyDict[tab, strategyName, 'values']
        parameters = self.strategyDict[tab, strategyName, 'parameters']
        groupBoxLayout = self.strategyDict[tab, strategyName, 'layout']

        self.strategyDict[tab, strategyName, 'groupBox'].setChecked(config[f'{strategyName.lower()}'])

        while valueCount > len(valueWidgets):
            add_strategy_inputs(self.strategyDict, parameters, strategyName, groupBoxLayout, tab)
        while valueCount < len(valueWidgets):
            delete_strategy_inputs(self.strategyDict, parameters, strategyName, tab)

        for index, widget in enumerate(valueWidgets, start=1):
            value = config[f'{strategyName.lower()}{index}']
            set_value(widget, value)

    def set_strategy_values(self, strategyName: str, caller: int, values):
        """
        Set GUI values for a strategy based on values passed.
        :param strategyName: Name of the strategy that'll have its values set.
        :param caller: Caller that'll determine which tab object gets returned.
        :param values: List of values to populate GUI with.
        :return: None
        """
        tab = self.get_category_tab(caller)
        targetValues = self.strategyDict[tab, strategyName, 'values']
        parameters = self.strategyDict[tab, strategyName, 'parameters']
        layout = self.strategyDict[tab, strategyName, 'layout']

        while len(values) < len(targetValues):
            delete_strategy_inputs(self.strategyDict, parameters, strategyName, tab)
        while len(values) > len(targetValues):
            add_strategy_inputs(self.strategyDict, parameters, strategyName, layout, tab)

        for index, widget in enumerate(targetValues):
            value = values[index]
            set_value(widget, value)

    def update_graph_speed(self):
        """
        Updates graph speed on main Algobot interface.
        """
        graphSpeed = self.graphPlotSpeedSpinBox.value()
        self.parent.graphUpdateSeconds = graphSpeed
        self.parent.add_to_live_activity_monitor(f"Updated graph plot speed to every {graphSpeed} seconds.")

    @staticmethod
    def reset_strategy_interval_comboBox(strategy_combobox: QComboBox, interval_combobox: QComboBox):
        """
        This function will reset the strategy combobox based on what interval is picked in the interval combobox.
        """
        childText = strategy_combobox.currentText()
        parentIndex = interval_combobox.currentIndex()
        intervals = helpers.get_interval_strings(startingIndex=parentIndex)
        strategy_combobox.clear()
        strategy_combobox.addItems(intervals)

        previousChildIndex = strategy_combobox.findText(childText)
        if previousChildIndex != -1:
            strategy_combobox.setCurrentIndex(previousChildIndex)

    def load_combo_boxes(self):
        """
        This function currently only handles combo boxes for backtester interval logic. It'll update the strategy
        interval combo-box depending on what the data interval combo-box has as its current value.
        """
        intervals = helpers.get_interval_strings(startingIndex=0)
        self.backtestStrategyIntervalCombobox.addItems(intervals)
        self.backtestIntervalComboBox.addItems(intervals)
        self.backtestIntervalComboBox.currentTextChanged.connect(lambda: self.reset_strategy_interval_comboBox(
            strategy_combobox=self.backtestStrategyIntervalCombobox,
            interval_combobox=self.backtestIntervalComboBox
        ))

        self.optimizerStrategyIntervalCombobox.addItems(intervals)
        self.optimizerIntervalComboBox.addItems(intervals)
        self.optimizerIntervalComboBox.currentTextChanged.connect(lambda: self.reset_strategy_interval_comboBox(
            strategy_combobox=self.optimizerStrategyIntervalCombobox,
            interval_combobox=self.optimizerIntervalComboBox
        ))

    def load_slots(self):
        """
        Loads all configuration interface slots.
        :return: None
        """
        self.simulationCopySettingsButton.clicked.connect(lambda: copy_settings_to_simulation(self))
        self.simulationSaveConfigurationButton.clicked.connect(lambda: save_simulation_settings(self))
        self.simulationLoadConfigurationButton.clicked.connect(lambda: load_simulation_settings(self))

        self.backtestCopySettingsButton.clicked.connect(lambda: copy_settings_to_backtest(self))
        self.backtestSaveConfigurationButton.clicked.connect(lambda: save_backtest_settings(self))
        self.backtestLoadConfigurationButton.clicked.connect(lambda: load_backtest_settings(self))
        self.backtestImportDataButton.clicked.connect(lambda: self.import_data(BACKTEST))
        self.backtestDownloadDataButton.clicked.connect(lambda: self.download_data(BACKTEST))
        self.backtestStopDownloadButton.clicked.connect(lambda: self.stop_download(BACKTEST))

        self.optimizerImportDataButton.clicked.connect(lambda: self.import_data(OPTIMIZER))
        self.optimizerDownloadDataButton.clicked.connect(lambda: self.download_data(OPTIMIZER))
        self.optimizerStopDownloadButton.clicked.connect(lambda: self.stop_download(OPTIMIZER))

        self.testCredentialsButton.clicked.connect(lambda: test_binance_credentials(self))
        self.saveCredentialsButton.clicked.connect(lambda: save_credentials(self))
        self.loadCredentialsButton.clicked.connect(lambda: load_credentials(config_obj=self, auto=False))

        self.testTelegramButton.clicked.connect(lambda: test_telegram(self))
        self.telegramApiKey.textChanged.connect(lambda: reset_telegram_state(self))
        self.telegramChatID.textChanged.connect(lambda: reset_telegram_state(self))

        self.saveConfigurationButton.clicked.connect(lambda: save_live_settings(self))
        self.loadConfigurationButton.clicked.connect(lambda: load_live_settings(self))
        self.graphPlotSpeedSpinBox.valueChanged.connect(self.update_graph_speed)
        self.enableHoverLine.stateChanged.connect(self.enable_disable_hover_line)

        self.load_loss_slots()  # These slots are based on the ordering.
        self.load_take_profit_slots()
        self.load_strategy_slots()
