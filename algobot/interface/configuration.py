import os
from logging import Logger

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QHBoxLayout, QLabel, QLayout, QMainWindow,
                             QScrollArea, QSpinBox, QTabWidget, QVBoxLayout)

import algobot.helpers as helpers
from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION, STOP, TRAILING
from algobot.graph_helpers import create_infinite_line
from algobot.interface.config_utils.credential_utils import (
    load_credentials, save_credentials, test_binance_credentials)
from algobot.interface.config_utils.data_utils import (download_data,
                                                       import_data,
                                                       stop_download)
from algobot.interface.config_utils.strategy_utils import (
    add_strategy_buttons, add_strategy_inputs, create_strategy_inputs,
    delete_strategy_inputs, get_strategies_dictionary, get_strategy_values,
    reset_strategy_interval_comboBox, strategy_enabled)
from algobot.interface.config_utils.telegram_utils import (
    reset_telegram_state, test_telegram)
from algobot.interface.config_utils.user_config_utils import (
    copy_settings_to_backtest, copy_settings_to_simulation,
    load_backtest_settings, load_live_settings, load_simulation_settings,
    save_backtest_settings, save_live_settings, save_simulation_settings)
from algobot.interface.configuration_helpers import (
    add_start_end_step_to_layout, create_inner_tab, get_default_widget,
    get_regular_groupbox_and_layout, set_value)
# noinspection PyUnresolvedReferences
from algobot.strategies import *  # noqa: F403, F401
from algobot.strategies.strategy import Strategy

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

    def update_graph_speed(self):
        """
        Updates graph speed on main Algobot interface.
        """
        graphSpeed = self.graphPlotSpeedSpinBox.value()
        self.parent.graphUpdateSeconds = graphSpeed
        self.parent.add_to_live_activity_monitor(f"Updated graph plot speed to every {graphSpeed} seconds.")

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
                            add_start_end_step_to_layout(groupBoxLayout, message, start, end, step)
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
                add_start_end_step_to_layout(innerLayout, optimizerType, start, end, step)
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
                add_start_end_step_to_layout(innerLayout, optimizerType, start, end, step)
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

    def load_combo_boxes(self):
        """
        This function currently only handles combo boxes for backtester interval logic. It'll update the strategy
        interval combo-box depending on what the data interval combo-box has as its current value.
        """
        intervals = helpers.get_interval_strings(startingIndex=0)
        self.backtestStrategyIntervalCombobox.addItems(intervals)
        self.backtestIntervalComboBox.addItems(intervals)
        self.backtestIntervalComboBox.currentTextChanged.connect(lambda: reset_strategy_interval_comboBox(
            strategy_combobox=self.backtestStrategyIntervalCombobox,
            interval_combobox=self.backtestIntervalComboBox
        ))

        self.optimizerStrategyIntervalCombobox.addItems(intervals)
        self.optimizerIntervalComboBox.addItems(intervals)
        self.optimizerIntervalComboBox.currentTextChanged.connect(lambda: reset_strategy_interval_comboBox(
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
        self.backtestImportDataButton.clicked.connect(lambda: import_data(self, BACKTEST))
        self.backtestDownloadDataButton.clicked.connect(lambda: download_data(self, BACKTEST))
        self.backtestStopDownloadButton.clicked.connect(lambda: stop_download(self, BACKTEST))

        self.optimizerImportDataButton.clicked.connect(lambda: import_data(self, OPTIMIZER))
        self.optimizerDownloadDataButton.clicked.connect(lambda: download_data(self, OPTIMIZER))
        self.optimizerStopDownloadButton.clicked.connect(lambda: stop_download(self, OPTIMIZER))

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
