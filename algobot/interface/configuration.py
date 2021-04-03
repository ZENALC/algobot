import datetime
import os
from typing import List, Tuple, Union

import telegram
from binance.client import Client
from dateutil import parser
from PyQt5 import uic
from PyQt5.QtCore import QDate, QThreadPool
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QHBoxLayout, QLabel, QLayout,
                             QMessageBox, QScrollArea, QSpinBox, QTabWidget,
                             QVBoxLayout)
from telegram.ext import Updater

import algobot.helpers as helpers
from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION, STOP, TRAILING
from algobot.interface.configuration_helpers import (
    add_strategy_buttons, add_strategy_inputs, create_inner_tab,
    create_strategy_inputs, delete_strategy_inputs, get_input_widget_value,
    get_regular_groupbox_and_layout, get_strategies_dictionary, set_value)
# noinspection PyUnresolvedReferences
from algobot.strategies import *  # noqa: F403, F401
from algobot.strategies.strategy import Strategy
from algobot.threads import downloadThread

configurationUi = os.path.join(helpers.ROOT_DIR, 'UI', 'configuration.ui')


class Configuration(QDialog):
    def __init__(self, parent, logger=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.parent = parent
        self.threadPool = QThreadPool()
        self.logger = logger

        self.optimizer_backtest_dict = {
            BACKTEST: {
                'startDate': self.backtestStartDate,
                'endDate': self.backtestEndDate,
                'tickers': self.backtestTickerComboBox,
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
                'tickers': self.optimizerTickerComboBox,
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
        self.load_credentials()  # Load credentials if they exist.

    def enable_disable_hover_line(self):
        """
        Enables or disables the hover line based on whether its checkmark is ticked or not.
        """
        enable = self.enableHoverLine.isChecked()
        if enable:
            for graphDict in self.parent.graphs:
                if len(graphDict['plots']) > 0:
                    self.parent.create_infinite_line(graphDict)
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
    def add_start_end_step_to_layout(layout, msg, start, end, step):
        layout.addRow(QLabel(f"{helpers.get_label_string(msg)} Optimization"))
        layout.addRow("Start", start)
        layout.addRow("End", end)
        layout.addRow("Step", step)

    def create_loss_inputs(self, tab: QTabWidget, innerLayout: QLayout, isOptimizer: bool = False):
        """
        Creates inputs for loss settings in GUI.
        :param tab: Tab to create inputs for - simulation, live, or backtest.
        :param innerLayout: Inner layout to place input widgets on.
        :param isOptimizer: Boolean for whether optimizer method called this function.
        """
        lossTypes = ("Trailing", "Stop")
        if isOptimizer:
            self.lossDict['optimizerTypes'] = []
            for lossType in lossTypes:
                checkbox = QCheckBox(f'Enable {lossType.lower()} type of stop loss?')
                innerLayout.addRow(checkbox)
                self.lossDict['optimizerTypes'].append((lossType, checkbox))

            optimizerTypes = ('lossPercentage', 'stopLossCounter')
            for optimizerType in optimizerTypes:
                self.lossDict[optimizerType, 'start'] = start = QSpinBox()
                self.lossDict[optimizerType, 'end'] = end = QSpinBox()
                self.lossDict[optimizerType, 'step'] = step = QSpinBox()
                self.add_start_end_step_to_layout(innerLayout, optimizerType, start, end, step)
        else:
            self.lossDict[tab, "lossType"] = lossTypeComboBox = QComboBox()
            self.lossDict[tab, "lossPercentage"] = lossPercentage = QDoubleSpinBox()
            self.lossDict[tab, "smartStopLossCounter"] = smartStopLossCounter = QSpinBox()

            lossTypeComboBox.addItems(lossTypes)
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
        takeProfitTypes = ('Stop', 'Trailing')
        if isOptimizer:
            self.takeProfitDict['optimizerTypes'] = []
            for takeProfitType in takeProfitTypes:
                checkbox = QCheckBox(f'Enable {takeProfitType} take profit?')
                innerLayout.addRow(checkbox)
                self.takeProfitDict['optimizerTypes'].append((takeProfitType, checkbox))

            self.takeProfitDict['optimizerStart'] = start = QSpinBox()
            self.takeProfitDict['optimizerEnd'] = end = QSpinBox()
            self.takeProfitDict['optimizerStep'] = step = QSpinBox()
            self.add_start_end_step_to_layout(innerLayout, 'takeProfitPercentage', start, end, step)
        else:
            self.takeProfitDict[tab, 'takeProfitType'] = takeProfitTypeComboBox = QComboBox()
            self.takeProfitDict[tab, 'takeProfitPercentage'] = takeProfitPercentage = QDoubleSpinBox()

            takeProfitTypeComboBox.addItems(takeProfitTypes)
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
                    self.strategyDict[tab, f'{strategyName}Optimization'] = groupBox
                    for index, parameter in enumerate(parameters, start=1):
                        if type(parameter) == tuple and parameter[1] == int or type(parameter) != tuple:
                            self.strategyDict[strategyName, index, 'start'] = start = QSpinBox()
                            self.strategyDict[strategyName, index, 'end'] = end = QSpinBox()
                            self.strategyDict[strategyName, index, 'step'] = step = QSpinBox()
                            if type(parameter) == tuple:
                                message = parameter[0]
                            else:
                                message = f"{strategyName} {index}"
                            self.add_start_end_step_to_layout(groupBoxLayout, message, start, end, step)
                        elif type(parameter) == tuple and parameter[1] == tuple:
                            groupBoxLayout.addRow(QLabel(parameter[0]))
                            for option in parameter[2]:
                                groupBoxLayout.addRow(QCheckBox(option))
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

    def reset_telegram_state(self):
        """
        Resets telegram state once something is changed in the Telegram configuration GUI.
        """
        self.chatPass = False
        self.tokenPass = False
        self.telegrationConnectionResult.setText("Telegram credentials not yet tested.")

    def test_telegram(self):
        """
        Tests Telegram connection and updates respective GUI elements.
        """
        tokenPass = chatPass = False
        message = error = ''

        try:
            telegramApikey = self.telegramApiKey.text()
            chatID = self.telegramChatID.text()
            Updater(telegramApikey, use_context=True)
            tokenPass = True
            telegram.Bot(token=telegramApikey).send_message(chat_id=chatID, text='Testing connection with Chat ID.')
            chatPass = True
        except Exception as e:
            error = repr(e)
            if 'ConnectionError' in error:
                error = 'There was a connection error. Please check your connection.'

        if tokenPass:
            if 'Unauthorized' in error:
                message = 'Token authorization was unsuccessful. Please recheck your token.'
            else:
                message += "Token authorization was successful. "
                if chatPass:
                    message += "Chat ID checked and connected to successfully. "
                else:
                    if 'Chat not found' in error:
                        message += "However, the specified chat ID is invalid."
                    else:
                        message += f'However, chat ID error occurred: "{error}".'
        else:
            message = f'Error: {error}'

        self.telegrationConnectionResult.setText(message)
        self.chatPass = chatPass
        self.tokenPass = tokenPass

    def test_binance_credentials(self):
        """
        Tests Binance credentials provided in configuration.
        """
        apiKey = self.binanceApiKey.text()
        apiSecret = self.binanceApiSecret.text()
        try:
            Client(apiKey, apiSecret).get_account()
            self.credentialResult.setText('Connected successfully.')
        except Exception as e:
            stringError = repr(e)
            if '1000ms' in stringError:
                self.credentialResult.setText('Time not synchronized. Please synchronize your time.')
            else:
                self.credentialResult.setText(stringError)

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

                if self.parent:
                    self.parent.add_to_live_activity_monitor('Loaded previous state successfully.')
            except Exception as e:
                self.logger.exception(str(e))

                if self.parent:
                    self.parent.add_to_live_activity_monitor('Failed to load previous state.')

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
        }

        helpers.write_json_file(self.basicFilePath, **config)

    def load_credentials(self, auto: bool = True):
        """
        Attempts to load credentials automatically from path program regularly stores credentials in if auto is True.
        """
        targetFolder = os.path.join(helpers.ROOT_DIR, self.credentialsFolder)
        if helpers.create_folder_if_needed(targetFolder):
            self.credentialResult.setText('No credentials found.')
            return

        if not auto:
            filePath, _ = QFileDialog.getOpenFileName(self, 'Load Credentials', targetFolder, "JSON (*.json)")
        else:
            filePath = os.path.join(targetFolder, 'default.json')

        try:
            credentials = helpers.load_json_file(jsonfile=filePath)
            self.binanceApiKey.setText(credentials['apiKey'])
            self.binanceApiSecret.setText(credentials['apiSecret'])
            self.telegramApiKey.setText(credentials['telegramApiKey'])
            self.telegramChatID.setText(credentials['chatID'])
            self.credentialResult.setText(f'Credentials loaded successfully from {os.path.basename(filePath)}.')
        except FileNotFoundError:
            self.credentialResult.setText('Could not load credentials.')
        except Exception as e:
            self.credentialResult.setText(str(e))

    def save_credentials(self):
        """
        Function that saves credentials to base path in a JSON format. Obviously not very secure, but temp fix.
        """
        targetFolder = os.path.join(helpers.ROOT_DIR, self.credentialsFolder)
        helpers.create_folder_if_needed(targetFolder)

        apiKey = self.binanceApiKey.text()
        apiSecret = self.binanceApiSecret.text()
        telegramApiKey = self.telegramApiKey.text()
        telegramChatId = self.telegramChatID.text()

        defaultPath = os.path.join(targetFolder, 'default.json')
        filePath, _ = QFileDialog.getSaveFileName(self, 'Save Credentials', defaultPath, 'JSON (*.json)')
        filePath = filePath.strip()

        if filePath:
            helpers.write_json_file(filePath=filePath, apiKey=apiKey, apiSecret=apiSecret,
                                    telegramApiKey=telegramApiKey, chatID=telegramChatId)
            self.credentialResult.setText(f'Credentials saved successfully to {os.path.basename(filePath)}.')
        else:
            self.credentialResult.setText('Credentials could not be saved.')

    def get_calendar_dates(self, caller: int = BACKTEST) -> Tuple[datetime.date or None, datetime.date or None]:
        """
        Returns start end end dates for backtest. If both are the same, returns None.
        :return: Start and end dates for backtest.
        """
        startDate = self.optimizer_backtest_dict[caller]['startDate'].selectedDate().toPyDate()
        endDate = self.optimizer_backtest_dict[caller]['startDate'].selectedDate().toPyDate()
        if startDate == endDate:
            return None, None
        return startDate, endDate

    def setup_calendar(self, caller: int = BACKTEST):
        """
        Parses data if needed and then manipulates GUI elements with data timeframe.
        """
        data = self.optimizer_backtest_dict[caller]['data']
        if type(data[0]['date_utc']) == str:
            startDate = parser.parse(data[0]['date_utc'])
            endDate = parser.parse(data[-1]['date_utc'])
        else:
            startDate = data[0]['date_utc']
            endDate = data[-1]['date_utc']

        if startDate > endDate:
            startDate, endDate = endDate, startDate

        startYear, startMonth, startDay = startDate.year, startDate.month, startDate.day
        qStartDate = QDate(startYear, startMonth, startDay)

        endYear, endMonth, endDay = endDate.year, endDate.month, endDate.day
        qEndDate = QDate(endYear, endMonth, endDay)

        self.optimizer_backtest_dict[caller]['startDate'].setEnabled(True)
        self.optimizer_backtest_dict[caller]['startDate'].setDateRange(qStartDate, qEndDate)
        self.optimizer_backtest_dict[caller]['startDate'].setSelectedDate(qStartDate)

        self.optimizer_backtest_dict[caller]['endDate'].setEnabled(True)
        self.optimizer_backtest_dict[caller]['endDate'].setDateRange(qStartDate, qEndDate)
        self.optimizer_backtest_dict[caller]['endDate'].setSelectedDate(qEndDate)

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
            self.setup_calendar(caller=caller)

    def download_data(self, caller: int = BACKTEST):
        """
        Loads data from data object. If the data object is empty, it downloads it.
        """
        self.optimizer_backtest_dict[caller]['downloadButton'].setEnabled(False)
        self.optimizer_backtest_dict[caller]['importButton'].setEnabled(False)
        self.set_download_progress(progress=0, message="Attempting to download...", caller=caller, enableStop=False)

        symbol = self.optimizer_backtest_dict[caller]['tickers'].currentText()
        interval = helpers.convert_long_interval(self.optimizer_backtest_dict[caller]['intervals'].currentText())

        thread = downloadThread.DownloadThread(symbol=symbol, interval=interval, caller=caller)
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
        self.optimizer_backtest_dict[caller]['infoLabel'].setText(f"Error occurred during download: {e}.")

    def set_downloaded_data(self, data, caller: int = BACKTEST):
        """
        If download is successful, the data passed is set to backtest data.
        :param caller: Caller that'll determine which caller was used.
        :param data: Data to be used for backtesting.
        """
        symbol = self.optimizer_backtest_dict[caller]['tickers'].currentText()
        interval = self.optimizer_backtest_dict[caller]['intervals'].currentText().lower()

        self.optimizer_backtest_dict[caller]['data'] = data
        self.optimizer_backtest_dict[caller]['dataType'] = symbol
        self.optimizer_backtest_dict[caller]['infoLabel'].setText(f"Downloaded {interval} {symbol} data successfully.")
        self.optimizer_backtest_dict[caller]['dataLabel'].setText(f'Using {interval} {symbol} data to run backtest.')
        self.setup_calendar(caller=caller)

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

    def save_backtest_settings(self):
        """
        Saves backtest settings to JSON file.
        """
        config = {
            # General
            'type': BACKTEST,
            'ticker': self.backtestTickerComboBox.currentIndex(),
            'interval': self.backtestIntervalComboBox.currentIndex(),
            'startingBalance': self.backtestStartingBalanceSpinBox.value(),
            'precision': self.backtestPrecisionSpinBox.value(),
            'marginTrading': self.backtestMarginTradingCheckBox.isChecked(),
        }

        self.helper_save(BACKTEST, config)
        filePath = self.helper_get_save_file_path("Backtest")

        if filePath:
            helpers.write_json_file(filePath, **config)
            file = os.path.basename(filePath)
            self.backtestConfigurationResult.setText(f"Saved backtest configuration successfully to {file}.")
        else:
            self.backtestConfigurationResult.setText("Could not save backtest configuration.")

    def save_simulation_settings(self):
        """
        Saves simulation settings to JSON file.
        """
        config = {
            # General
            'type': SIMULATION,
            'ticker': self.simulationTickerComboBox.currentIndex(),
            'interval': self.simulationIntervalComboBox.currentIndex(),
            'startingBalance': self.simulationStartingBalanceSpinBox.value(),
            'precision': self.simulationPrecisionSpinBox.value(),
            'lowerInterval': self.lowerIntervalSimulationCheck.isChecked(),
        }

        self.helper_save(SIMULATION, config)
        filePath = self.helper_get_save_file_path("Simulation")

        if filePath:
            helpers.write_json_file(filePath, **config)
            file = os.path.basename(filePath)
            self.simulationConfigurationResult.setText(f"Saved simulation configuration successfully to {file}.")
        else:
            self.simulationConfigurationResult.setText("Could not save simulation configuration.")

    def save_live_settings(self):
        """
        Saves live settings to JSON file.
        """
        config = {
            # General
            'type': LIVE,
            'ticker': self.tickerComboBox.currentIndex(),
            'interval': self.intervalComboBox.currentIndex(),
            'precision': self.precisionSpinBox.value(),
            'usRegion': self.usRegionRadio.isChecked(),
            'otherRegion': self.otherRegionRadio.isChecked(),
            'isolatedMargin': self.isolatedMarginAccountRadio.isChecked(),
            'crossMargin': self.crossMarginAccountRadio.isChecked(),
            'lowerInterval': self.lowerIntervalCheck.isChecked(),
        }

        self.helper_save(LIVE, config)
        filePath = self.helper_get_save_file_path("Live")

        if filePath:
            helpers.write_json_file(filePath, **config)
            file = os.path.basename(filePath)
            self.configurationResult.setText(f"Saved live configuration successfully to {file}.")
        else:
            self.configurationResult.setText("Could not save live configuration.")

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

    def load_backtest_settings(self):
        """
        Loads backtest settings from JSON file and sets them to backtest settings.
        """
        targetPath = self.create_appropriate_config_folders('Backtest')
        filePath, _ = QFileDialog.getOpenFileName(self, 'Load Credentials', targetPath, "JSON (*.json)")
        try:
            config = helpers.load_json_file(filePath)
            file = os.path.basename(filePath)
            if config['type'] != BACKTEST:
                QMessageBox.about(self, 'Warning', 'Incorrect type of non-backtest configuration provided.')
            else:
                self.backtestTickerComboBox.setCurrentIndex(config['ticker'])
                self.backtestIntervalComboBox.setCurrentIndex(config['interval'])
                self.backtestStartingBalanceSpinBox.setValue(config['startingBalance'])
                self.backtestPrecisionSpinBox.setValue(config['precision'])
                self.backtestMarginTradingCheckBox.setChecked(config['marginTrading'])
                self.helper_load(BACKTEST, config)
                self.backtestConfigurationResult.setText(f"Loaded backtest configuration successfully from {file}.")
        except Exception as e:
            self.logger.exception(str(e))
            self.backtestConfigurationResult.setText("Could not load backtest configuration.")

    def load_simulation_settings(self):
        """
        Loads simulation settings from JSON file and sets it to simulation settings.
        """
        targetPath = self.create_appropriate_config_folders('Simulation')
        filePath, _ = QFileDialog.getOpenFileName(self, 'Load Credentials', targetPath, "JSON (*.json)")
        try:
            config = helpers.load_json_file(filePath)
            file = os.path.basename(filePath)
            if config['type'] != SIMULATION:
                QMessageBox.about(self, 'Warning', 'Incorrect type of non-simulation configuration provided.')
            else:
                self.simulationTickerComboBox.setCurrentIndex(config['ticker'])
                self.simulationIntervalComboBox.setCurrentIndex(config['interval'])
                self.simulationStartingBalanceSpinBox.setValue(config['startingBalance'])
                self.simulationPrecisionSpinBox.setValue(config['precision'])
                self.lowerIntervalSimulationCheck.setChecked(config['lowerInterval'])
                self.helper_load(SIMULATION, config)
                self.simulationConfigurationResult.setText(f"Loaded simulation configuration successfully from {file}.")
        except Exception as e:
            self.logger.exception(str(e))
            self.simulationConfigurationResult.setText("Could not load simulation configuration.")

    def load_live_settings(self):
        """
        Loads live settings from JSON file and sets it to live settings.
        """
        targetPath = self.create_appropriate_config_folders('Live')
        filePath, _ = QFileDialog.getOpenFileName(self, 'Load Credentials', targetPath, "JSON (*.json)")
        try:
            config = helpers.load_json_file(filePath)
            file = os.path.basename(filePath)
            if config['type'] != LIVE:
                QMessageBox.about(self, 'Warning', 'Incorrect type of non-live configuration provided.')
            else:
                self.tickerComboBox.setCurrentIndex(config['ticker'])
                self.intervalComboBox.setCurrentIndex(config['interval'])
                self.precisionSpinBox.setValue(config['precision'])
                self.usRegionRadio.setChecked(config['usRegion'])
                self.otherRegionRadio.setChecked(config['otherRegion'])
                self.isolatedMarginAccountRadio.setChecked(config['isolatedMargin'])
                self.crossMarginAccountRadio.setChecked(config['crossMargin'])
                self.lowerIntervalCheck.setChecked(config['lowerInterval'])
                self.helper_load(LIVE, config)
                self.configurationResult.setText(f"Loaded live configuration successfully from {file}.")
        except Exception as e:
            self.logger.exception(str(e))
            self.configurationResult.setText("Could not load live configuration.")

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

    def copy_strategy_settings(self, fromCaller: int, toCaller: int, strategyName: str):
        """
        Copies strategy settings from caller provided and sets it to caller provided based on strategy name.
        :param fromCaller: Function will copy settings from this caller.
        :param toCaller: Function will copy settings to this caller.
        :param strategyName: This strategy's settings will be copied.
        :return: None
        """
        fromCallerTab = self.get_category_tab(fromCaller)
        toCallerTab = self.get_category_tab(toCaller)

        fromCallerGroupBox = self.strategyDict[fromCallerTab, strategyName, 'groupBox']
        self.strategyDict[toCallerTab, strategyName, 'groupBox'].setChecked(fromCallerGroupBox.isChecked())
        self.set_strategy_values(strategyName, toCaller, self.get_strategy_values(strategyName, fromCaller))

    def copy_loss_settings(self, fromCaller: int, toCaller: int):
        """
        Copies loss settings from one caller to another.
        :param fromCaller: Loss settings will be copied from this trader.
        :param toCaller: Loss settings will be copied to this trader.
        :return: None
        """
        fromTab = self.get_category_tab(fromCaller)
        toTab = self.get_category_tab(toCaller)

        self.lossDict[toTab, "lossType"].setCurrentIndex(self.lossDict[fromTab, "lossType"].currentIndex())
        self.lossDict[toTab, "lossPercentage"].setValue(self.lossDict[fromTab, "lossPercentage"].value())
        self.lossDict[toTab, "smartStopLossCounter"].setValue(self.lossDict[fromTab, "smartStopLossCounter"].value())

        if toTab != self.backtestConfigurationTabWidget:
            self.lossDict[toTab, "safetyTimer"].setValue(self.lossDict[fromTab, "safetyTimer"].value())

    def copy_settings_to_simulation(self):
        """
        Copies parameters from main configuration to simulation configuration.
        :return: None
        """
        self.simulationIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.simulationTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())
        self.simulationPrecisionSpinBox.setValue(self.precisionSpinBox.value())
        self.copy_loss_settings(LIVE, SIMULATION)

        for strategyName in self.strategies.keys():
            self.copy_strategy_settings(LIVE, SIMULATION, strategyName)

        self.simulationCopyLabel.setText("Copied all viable settings from main to simulation settings successfully.")

    def copy_settings_to_backtest(self):
        """
        Copies parameters from main configuration to backtest configuration.
        :return: None
        """
        self.backtestIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.backtestTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())
        self.backtestPrecisionSpinBox.setValue(self.precisionSpinBox.value())
        self.copy_loss_settings(LIVE, BACKTEST)

        for strategyName in self.strategies.keys():
            self.copy_strategy_settings(LIVE, BACKTEST, strategyName)

        self.backtestCopyLabel.setText("Copied all viable settings from main to backtest settings successfully.")

    def update_graph_speed(self):
        """
        Updates graph speed on main Algobot interface.
        :return: None
        """
        graphSpeed = self.graphPlotSpeedSpinBox.value()
        self.parent.graphUpdateSeconds = graphSpeed
        self.parent.add_to_live_activity_monitor(f"Updated graph plot speed to every {graphSpeed} seconds.")

    @staticmethod
    def reset_strategy_interval_comboBox(strategy_combobox, interval_combobox):
        """
        This function will reset the strategy interval combo-box.
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
        self.simulationCopySettingsButton.clicked.connect(self.copy_settings_to_simulation)
        self.simulationSaveConfigurationButton.clicked.connect(self.save_simulation_settings)
        self.simulationLoadConfigurationButton.clicked.connect(self.load_simulation_settings)

        self.backtestCopySettingsButton.clicked.connect(self.copy_settings_to_backtest)
        self.backtestSaveConfigurationButton.clicked.connect(self.save_backtest_settings)
        self.backtestLoadConfigurationButton.clicked.connect(self.load_backtest_settings)
        self.backtestImportDataButton.clicked.connect(lambda: self.import_data(BACKTEST))
        self.backtestDownloadDataButton.clicked.connect(lambda: self.download_data(BACKTEST))
        self.backtestStopDownloadButton.clicked.connect(lambda: self.stop_download(BACKTEST))

        self.optimizerImportDataButton.clicked.connect(lambda: self.import_data(OPTIMIZER))
        self.optimizerDownloadDataButton.clicked.connect(lambda: self.download_data(OPTIMIZER))
        self.optimizerStopDownloadButton.clicked.connect(lambda: self.stop_download(OPTIMIZER))

        self.testCredentialsButton.clicked.connect(self.test_binance_credentials)
        self.saveCredentialsButton.clicked.connect(self.save_credentials)
        self.loadCredentialsButton.clicked.connect(lambda: self.load_credentials(auto=False))

        self.testTelegramButton.clicked.connect(self.test_telegram)
        self.telegramApiKey.textChanged.connect(self.reset_telegram_state)
        self.telegramChatID.textChanged.connect(self.reset_telegram_state)

        self.saveConfigurationButton.clicked.connect(self.save_live_settings)
        self.loadConfigurationButton.clicked.connect(self.load_live_settings)
        self.graphPlotSpeedSpinBox.valueChanged.connect(self.update_graph_speed)
        self.enableHoverLine.stateChanged.connect(self.enable_disable_hover_line)

        self.load_loss_slots()  # These slots are based on the ordering.
        self.load_take_profit_slots()
        self.load_strategy_slots()
