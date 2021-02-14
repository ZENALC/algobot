import datetime
import os
import telegram
import helpers

from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox, QTabWidget, QFormLayout, QLabel, QSpinBox, \
    QGroupBox, QVBoxLayout, QDoubleSpinBox, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QFrame, QScrollArea
from PyQt5.QtCore import QDate, QThreadPool
from PyQt5 import uic
from binance.client import Client
from telegram.ext import Updater
from dateutil import parser
from threads import downloadThread
from typing import List, Tuple
from enums import SIMULATION, LIVE, BACKTEST
from strategies import StoicStrategy, ShrekStrategy, MovingAverageStrategy

configurationUi = os.path.join(helpers.ROOT_DIR, 'UI', 'configuration.ui')


class Configuration(QDialog):
    def __init__(self, parent=None, logger=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.parent = parent
        self.threadPool = QThreadPool()
        self.logger = logger
        self.data = None
        self.dataType = None
        self.downloadThread = None
        self.tokenPass = False
        self.chatPass = False
        self.credentialsFolder = "Credentials"
        self.configFolder = 'Configuration'
        self.basicFilePath = os.path.join(helpers.ROOT_DIR, 'state.json')

        self.categoryTabs = [self.mainConfigurationTabWidget,
                             self.simulationConfigurationTabWidget,
                             self.backtestConfigurationTabWidget,
                             ]
        self.strategies = {  # Add your strategy to this dictionary of strategies.
            'Stoic': StoicStrategy,
            'Shrek': ShrekStrategy,
            'Moving Average': MovingAverageStrategy,
        }
        self.strategyDict = {}  # We will store all the strategy slot information in this dictionary.

        self.load_slots()
        self.load_credentials()
        self.load_strategy_slots()

    def get_strategies(self, caller) -> List[tuple]:
        strategies = []
        for strategyName, strategy in self.strategies.items():
            if self.strategy_enabled(strategyName, caller):
                values = self.get_strategy_values(strategyName, caller, verbose=True)
                strategyTuple = (strategy, values, strategyName)
                strategies.append(strategyTuple)

        return strategies

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
        else:
            raise ValueError("Invalid type of caller provided.")

    def strategy_enabled(self, strategyName: str, caller: int) -> bool:
        """
        Returns a boolean whether a strategy is enabled or not.
        :param strategyName: Name of strategy to check if enabled.
        :param caller: Caller of the strategy.
        :return: Boolean whether strategy is enabled or not.
        """
        tab = self.get_category_tab(caller)
        return self.strategyDict[tab, strategyName, 'groupBox'].isChecked()

    @staticmethod
    def get_input_widget_value(inputWidget, verbose: bool = False):
        """
        This function will attempt to get the value of the inputWidget and return it.
        :param verbose: If verbose, return value of widget when possible.
        :param inputWidget: Input widget to try to get the value of.
        :return: Value of inputWidget object.
        """
        if isinstance(inputWidget, QSpinBox) or isinstance(inputWidget, QDoubleSpinBox):
            return inputWidget.value()
        elif isinstance(inputWidget, QLineEdit):
            return inputWidget.text()
        elif isinstance(inputWidget, QComboBox):
            if verbose:
                return inputWidget.currentText()
            else:
                return inputWidget.currentIndex()
        else:
            raise TypeError("Unknown type of instance provided. Please check load_strategy_slots() function.")

    @staticmethod
    def get_h_line() -> QFrame:
        """
        Returns a horizontal line object made using a QFrame object.
        :return: Horizontal line using a QFrame.
        """
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

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
            values.append(self.get_input_widget_value(inputWidget, verbose=verbose))

        return values

    def delete_strategy_inputs(self, parameters: list, strategyName: str, tab: QTabWidget):
        """
        Dynamically deletes strategy inputs.
        :param parameters: Parameters of the strategy.
        :param strategyName: Name of strategy to determine the dictionary.
        :param tab: Tab in which to delete strategy inputs.
        :return: None
        """
        values = self.strategyDict[tab, strategyName, 'values']
        labels = self.strategyDict[tab, strategyName, 'labels']
        if len(values) <= len(parameters):
            self.strategyDict[tab, strategyName, 'status'].setText("Can't delete additional slots.")
        else:
            for _ in range(len(parameters)):
                value = values.pop()
                value.setParent(None)

                label = labels.pop()
                label.setParent(None)

            labels.pop().setParent(None)  # Pop off the horizontal line from labels.
            self.strategyDict[tab, strategyName, 'status'].setText("Deleted additional slots.")

    def create_strategy_inputs(self, parameters: list, strategyName: str, groupBoxLayout) -> Tuple[list, list]:
        """
        This function will create strategy slots and labels based on the parameters provided to the layout.
        :param parameters: Parameters to add to strategy GUI slots.
        :param strategyName: Name of strategy.
        :param groupBoxLayout: Layout to add the slots to.
        :return: Tuple of labels and values lists.
        """
        labels = []
        values = []
        for paramIndex, parameter in enumerate(parameters):
            if type(parameter) == tuple:
                label = QLabel(parameter[0])
                parameter = parameter[1:]  # Set parameter to just the last element so we can use this later.
            elif parameter == int:
                label = QLabel(f'{strategyName} input {paramIndex + 1}')
                parameter = [parameter]
            else:
                raise TypeError("Please make sure your function get_param_types() only has ints or tuples.")

            if parameter[0] == int:
                value = QSpinBox()
                value.setRange(1, 500)
            elif parameter[0] == float:
                value = QDoubleSpinBox()
            elif parameter[0] == str:
                value = QLineEdit()
            elif parameter[0] == tuple:
                elements = parameter[1]
                value = QComboBox()
                value.addItems(elements)
            else:
                raise TypeError("Invalid type of parameter provided.")

            labels.append(label)
            values.append(value)
            groupBoxLayout.addRow(label, value)

        line = self.get_h_line()
        labels.append(line)
        groupBoxLayout.addWidget(line)

        return values, labels

    def add_strategy_inputs(self, parameters: list, strategyName: str, groupBoxLayout, tab: QTabWidget):
        """
        Adds strategy parameters to the layout provided.
        :param parameters: Parameters to add to the group box layout.
        :param strategyName: Name of strategy.
        :param groupBoxLayout: Layout to add parameters to.
        :param tab: Add which group box layout is in.
        :return: None
        """
        values, labels = self.create_strategy_inputs(parameters, strategyName, groupBoxLayout)
        self.strategyDict[tab, strategyName, 'labels'] += labels
        self.strategyDict[tab, strategyName, 'values'] += values
        self.strategyDict[tab, strategyName, 'status'].setText("Added additional slots.")

    def add_strategy_buttons(self, parameters, strategyName, groupBoxLayout, tab) -> Tuple[QPushButton, QPushButton]:
        """
        Adds add and delete buttons to strategy GUI.
        :param parameters: Parameters to pass to strategy inputs function.
        :param strategyName: Name of strategy.
        :param groupBoxLayout: Layout to add strategy buttons to.
        :param tab: Tab to modify GUI.
        :return: Tuple of add and delete buttons.
        """
        addButton = QPushButton("Add Extra")
        addButton.clicked.connect(lambda: self.add_strategy_inputs(parameters, strategyName, groupBoxLayout, tab))
        deleteButton = (QPushButton("Delete Extra"))
        deleteButton.clicked.connect(lambda: self.delete_strategy_inputs(parameters, strategyName, tab))

        return addButton, deleteButton

    def load_strategy_slots(self):
        """
        This will initialize all the necessary strategy slots and add them to the configuration GUI. All the strategies
        are loaded from the self.strategies dictionary. Make sure you add your strategy to that dictionary with the key
        as the strategy name and the value as the strategy class.
        :return: None
        """
        for strategy in self.strategies.values():
            temp = strategy()
            strategyName = temp.name
            parameters = temp.get_param_types()
            for tab in self.categoryTabs:
                self.strategyDict[tab, strategyName] = tabWidget = QTabWidget()
                self.strategyDict[tab, strategyName, 'groupBox'] = groupBox = QGroupBox(f"Enable {strategyName}?")

                layout = QVBoxLayout()
                descriptionLabel = QLabel(f'Strategy description: {temp.description}')
                descriptionLabel.setWordWrap(True)
                layout.addWidget(descriptionLabel)

                scroll = QScrollArea()  # Added a scroll area so user can scroll when additional slots are added.
                scroll.setWidget(groupBox)
                scroll.setWidgetResizable(True)

                groupBox.setCheckable(True)
                groupBox.setChecked(False)
                groupBoxLayout = QFormLayout()
                groupBox.setLayout(groupBoxLayout)

                status = QLabel()
                if temp.dynamic:
                    addButton, deleteButton = self.add_strategy_buttons(parameters, strategyName, groupBoxLayout, tab)
                    horizontalLayout = QHBoxLayout()
                    horizontalLayout.addWidget(addButton)
                    horizontalLayout.addWidget(deleteButton)
                    horizontalLayout.addWidget(status)
                    horizontalLayout.addStretch()
                    layout.addLayout(horizontalLayout)

                layout.addWidget(scroll)

                values, labels = self.create_strategy_inputs(parameters, strategyName, groupBoxLayout)
                self.strategyDict[tab, strategyName, 'values'] = values
                self.strategyDict[tab, strategyName, 'labels'] = labels
                self.strategyDict[tab, strategyName, 'parameters'] = parameters
                self.strategyDict[tab, strategyName, 'layout'] = groupBoxLayout
                self.strategyDict[tab, strategyName, 'status'] = status

                tabWidget.setLayout(layout)
                tab.addTab(tabWidget, strategyName)

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

    def reset_telegram_state(self):
        """
        Resets telegram state once something is changed in the Telegram configuration GUI.
        """
        self.chatPass = False
        self.tokenPass = False
        self.telegrationConnectionResult.setText("Telegram credentials not yet tested.")

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

    def load_credentials(self, auto=True):
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

    def get_calendar_dates(self) -> Tuple[datetime.date or None, datetime.date or None]:
        """
        Returns start end end dates for backtest. If both are the same, returns None.
        :return: Start and end dates for backtest.
        """
        startDate = self.backtestStartDate.selectedDate().toPyDate()
        endDate = self.backtestEndDate.selectedDate().toPyDate()
        if startDate == endDate:
            return None, None
        return startDate, endDate

    def setup_calendar(self):
        """
        Parses data if needed and then manipulates GUI elements with data timeframe.
        """
        data = self.data
        if type(data[0]['date_utc']) == str:
            startDate = parser.parse(data[0]['date_utc'])
            endDate = parser.parse(data[-1]['date_utc'])
        else:
            startDate = data[0]['date_utc']
            endDate = data[-1]['date_utc']

        startYear, startMonth, startDay = startDate.year, startDate.month, startDate.day
        qStartDate = QDate(startYear, startMonth, startDay)

        endYear, endMonth, endDay = endDate.year, endDate.month, endDate.day
        qEndDate = QDate(endYear, endMonth, endDay)

        self.backtestStartDate.setEnabled(True)
        self.backtestEndDate.setEnabled(True)
        self.backtestStartDate.setDateRange(qStartDate, qEndDate)
        self.backtestEndDate.setDateRange(qStartDate, qEndDate)

    def import_data(self):
        """
        Imports CSV data and loads it.
        """
        self.backtestInfoLabel.setText("Importing data...")
        filePath, _ = QFileDialog.getOpenFileName(self, 'Open file', helpers.ROOT_DIR, "CSV (*.csv)")
        if filePath == '':
            self.backtestInfoLabel.setText("Data not imported.")
            return
        self.data = helpers.load_from_csv(filePath, descending=False)
        self.dataType = "Imported"
        self.backtestInfoLabel.setText("Imported data successfully.")
        self.backtestDataLabel.setText('Currently using imported data to conduct backtest.')
        self.setup_calendar()

    def download_data(self):
        """
        Loads data from data object. If the data object is empty, it downloads it.
        """
        self.backtestDownloadDataButton.setEnabled(False)
        self.backtestImportDataButton.setEnabled(False)
        self.backtestStopDownloadButton.setEnabled(True)
        self.set_download_progress(progress=0, message="Downloading data...", caller=-1)

        symbol = self.backtestTickerComboBox.currentText()
        interval = helpers.convert_interval(self.backtestIntervalComboBox.currentText())

        thread = downloadThread.DownloadThread(symbol=symbol, interval=interval)
        thread.signals.progress.connect(self.set_download_progress)
        thread.signals.finished.connect(self.set_downloaded_data)
        thread.signals.error.connect(self.handle_download_failure)
        thread.signals.restore.connect(self.restore_download_state)
        thread.signals.locked.connect(lambda: self.backtestStopDownloadButton.setEnabled(False))
        self.downloadThread = thread
        self.threadPool.start(thread)

    def stop_download(self):
        """
        Stops download if download is in progress.
        """
        if self.downloadThread:
            self.backtestDownloadLabel.setText("Canceling download...")
            self.downloadThread.stop()

    def set_download_progress(self, progress, message, caller):
        """
        Sets download progress and message with parameters passed.
        :param caller: This is not used in this function.
        :param progress: Progress value to set bar at.
        :param message: Message to display in label.
        """
        assert caller == -1
        if progress != -1:
            self.backtestDownloadProgressBar.setValue(progress)
        self.backtestDownloadLabel.setText(message)

    def restore_download_state(self):
        """
        Restores GUI to normal state.
        """
        self.downloadThread = None
        self.backtestStopDownloadButton.setEnabled(False)
        self.backtestDownloadDataButton.setEnabled(True)
        self.backtestImportDataButton.setEnabled(True)

    def handle_download_failure(self, e):
        """
        If download fails for backtest data, then GUI gets updated.
        :param e: Error for why download failed.
        """
        self.backtestInfoLabel.setText(f"Error occurred during download: {e}.")

    def set_downloaded_data(self, data):
        """
        If download is successful, the data passed is set to backtest data.
        :param data: Data to be used for backtesting.
        """
        symbol = self.backtestTickerComboBox.currentText()
        interval = self.backtestIntervalComboBox.currentText().lower()

        self.data = data
        self.dataType = symbol
        self.backtestInfoLabel.setText(f"Downloaded {symbol} {interval} data successfully.")
        self.backtestDataLabel.setText(f'Currently using {symbol} in {interval} intervals to conduct backtest.')
        self.setup_calendar()

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

            # Loss
            'trailingLoss': self.backtestTrailingLossRadio.isChecked(),
            'stopLoss': self.backtestStopLossRadio.isChecked(),
            'lossPercentage': self.backtestLossPercentageSpinBox.value(),
            'smartStopLossCounter': self.backtestSmartStopLossSpinBox.value(),
        }

        for strategyName in self.strategies.keys():
            self.add_strategy_to_config(BACKTEST, strategyName, config)

        targetPath = self.create_appropriate_config_folders('Backtest')
        defaultPath = os.path.join(targetPath, 'backtest_configuration.json')
        filePath, _ = QFileDialog.getSaveFileName(self, 'Save Backtest Configuration', defaultPath, 'JSON (*.json)')
        filePath = filePath.strip()

        if filePath:
            helpers.write_json_file(filePath, **config)
            file = os.path.basename(filePath)
            self.backtestConfigurationResult.setText(f"Saved backtest configuration successfully to {file}.")
        else:
            self.backtestConfigurationResult.setText("Could not save backtest configuration.")

    def load_backtest_settings(self):
        """
        Loads backtest settings from JSON file and sets them to backtest settings.
        """
        targetPath = self.create_appropriate_config_folders('Backtest')
        filePath, _ = QFileDialog.getOpenFileName(self, 'Load Credentials', targetPath, "JSON (*.json)")
        try:
            config = helpers.load_json_file(filePath)
            if config['type'] != BACKTEST:
                QMessageBox.about(self, 'Warning', 'Incorrect type of non-backtest configuration provided.')
            else:
                self.backtestTickerComboBox.setCurrentIndex(config['ticker'])
                self.backtestIntervalComboBox.setCurrentIndex(config['interval'])
                self.backtestStartingBalanceSpinBox.setValue(config['startingBalance'])
                self.backtestPrecisionSpinBox.setValue(config['precision'])
                self.backtestMarginTradingCheckBox.setChecked(config['marginTrading'])

                self.backtestTrailingLossRadio.setChecked(config['trailingLoss'])
                self.backtestStopLossRadio.setChecked(config['stopLoss'])
                self.backtestLossPercentageSpinBox.setValue(config['lossPercentage'])
                self.backtestSmartStopLossSpinBox.setValue(config['smartStopLossCounter'])

                for strategyName in self.strategies.keys():
                    self.load_strategy_from_config(BACKTEST, strategyName, config)

                file = os.path.basename(filePath)
                self.backtestConfigurationResult.setText(f"Loaded backtest configuration successfully from {file}.")
        except Exception as e:
            self.logger.exception(str(e))
            self.backtestConfigurationResult.setText("Could not load backtest configuration.")

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

            # Loss
            'trailingLoss': self.simulationTrailingLossRadio.isChecked(),
            'stopLoss': self.simulationStopLossRadio.isChecked(),
            'lossPercentage': self.simulationLossPercentageSpinBox.value(),
            'smartStopLossCounter': self.simulationSmartStopLossSpinBox.value(),
            'safetyTimer': self.simulationSafetyTimerSpinBox.value(),
        }

        for strategyName in self.strategies.keys():
            self.add_strategy_to_config(SIMULATION, strategyName, config)

        targetPath = self.create_appropriate_config_folders('Simulation')
        defaultPath = os.path.join(targetPath, 'simulation.json')
        filePath, _ = QFileDialog.getSaveFileName(self, 'Save Simulation Configuration', defaultPath, 'JSON (*.json)')
        filePath = filePath.strip()

        if filePath:
            helpers.write_json_file(filePath, **config)
            file = os.path.basename(filePath)
            self.simulationConfigurationResult.setText(f"Saved simulation configuration successfully to {file}.")
        else:
            self.simulationConfigurationResult.setText("Could not save simulation configuration.")

    def load_simulation_settings(self):
        """
        Loads simulation settings from JSON file and sets it to simulation settings.
        """
        targetPath = self.create_appropriate_config_folders('Simulation')
        filePath, _ = QFileDialog.getOpenFileName(self, 'Load Credentials', targetPath, "JSON (*.json)")
        try:
            config = helpers.load_json_file(filePath)
            if config['type'] != SIMULATION:
                QMessageBox.about(self, 'Warning', 'Incorrect type of non-simulation configuration provided.')
            else:
                self.simulationTickerComboBox.setCurrentIndex(config['ticker'])
                self.simulationIntervalComboBox.setCurrentIndex(config['interval'])
                self.simulationStartingBalanceSpinBox.setValue(config['startingBalance'])
                self.simulationPrecisionSpinBox.setValue(config['precision'])
                self.lowerIntervalSimulationCheck.setChecked(config['lowerInterval'])

                self.simulationTrailingLossRadio.setChecked(config['trailingLoss'])
                self.simulationStopLossRadio.setChecked(config['stopLoss'])
                self.simulationLossPercentageSpinBox.setValue(config['lossPercentage'])
                self.simulationSmartStopLossSpinBox.setValue(config['smartStopLossCounter'])
                self.simulationSafetyTimerSpinBox.setValue(config['safetyTimer'])

                for strategyName in self.strategies.keys():
                    self.load_strategy_from_config(SIMULATION, strategyName, config)

                file = os.path.basename(filePath)
                self.simulationConfigurationResult.setText(f"Loaded simulation configuration successfully from {file}.")
        except Exception as e:
            self.logger.exception(str(e))
            self.simulationConfigurationResult.setText("Could not load simulation configuration.")

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

            # Loss
            'trailingLoss': self.trailingLossRadio.isChecked(),
            'stopLoss': self.stopLossRadio.isChecked(),
            'lossPercentage': self.lossPercentageSpinBox.value(),
            'smartStopLossCounter': self.smartStopLossSpinBox.value(),
            'safetyTimer': self.safetyTimerSpinBox.value(),
        }

        for strategyName in self.strategies.keys():
            self.add_strategy_to_config(LIVE, strategyName, config)

        targetPath = self.create_appropriate_config_folders('Live')
        defaultPath = os.path.join(targetPath, 'live_configuration.json')
        filePath, _ = QFileDialog.getSaveFileName(self, 'Save Live Configuration', defaultPath, 'JSON (*.json)')
        filePath = filePath.strip()

        if filePath:
            helpers.write_json_file(filePath, **config)
            file = os.path.basename(filePath)
            self.configurationResult.setText(f"Saved live configuration successfully to {file}.")
        else:
            self.configurationResult.setText("Could not save live configuration.")

    def load_live_settings(self):
        """
        Loads live settings from JSON file and sets it to live settings.
        """
        targetPath = self.create_appropriate_config_folders('Live')
        filePath, _ = QFileDialog.getOpenFileName(self, 'Load Credentials', targetPath, "JSON (*.json)")
        try:
            config = helpers.load_json_file(filePath)
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

                self.trailingLossRadio.setChecked(config['trailingLoss'])
                self.stopLossRadio.setChecked(config['stopLoss'])
                self.lossPercentageSpinBox.setValue(config['lossPercentage'])
                self.smartStopLossSpinBox.setValue(config['smartStopLossCounter'])
                self.safetyTimerSpinBox.setValue(config['safetyTimer'])

                for strategyName in self.strategies.keys():
                    self.load_strategy_from_config(LIVE, strategyName, config)

                file = os.path.basename(filePath)
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
        valueCount = config[f'{strategyName.lower()}Length']
        tab = self.get_category_tab(caller)
        valueWidgets = self.strategyDict[tab, strategyName, 'values']
        parameters = self.strategyDict[tab, strategyName, 'parameters']
        groupBoxLayout = self.strategyDict[tab, strategyName, 'layout']

        self.strategyDict[tab, strategyName, 'groupBox'].setChecked(config[f'{strategyName.lower()}'])

        while valueCount > len(valueWidgets):
            self.add_strategy_inputs(parameters, strategyName, groupBoxLayout, tab)
        while valueCount < len(valueWidgets):
            self.delete_strategy_inputs(parameters, strategyName, tab)

        for index, widget in enumerate(valueWidgets, start=1):
            value = config[f'{strategyName.lower()}{index}']
            self.set_value(widget, value)

    @staticmethod
    def set_value(widget, value):
        """
        Sets appropriate value to a widget depending on what it is.
        :param widget: Widget to alter.
        :param value: Value to modify widget with.
        :return: None
        """
        if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
            widget.setValue(value)
        elif isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, QComboBox):
            widget.setCurrentIndex(value)
        else:
            raise TypeError("Unknown type of instance provided. Please check load_strategy_slots() function.")

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
            self.delete_strategy_inputs(parameters, strategyName, tab)
        while len(values) > len(targetValues):
            self.add_strategy_inputs(parameters, strategyName, layout, tab)

        for index, widget in enumerate(targetValues):
            value = values[index]
            self.set_value(widget, value)

    def copy_strategy_settings(self, fromCaller, toCaller, strategyName):
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

    def copy_settings_to_simulation(self):
        """
        Copies parameters from main configuration to simulation configuration.
        :return: None
        """
        self.simulationIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.simulationTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())
        self.simulationPrecisionSpinBox.setValue(self.precisionSpinBox.value())

        self.simulationLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.simulationStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.simulationTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())
        self.simulationSmartStopLossSpinBox.setValue(self.smartStopLossSpinBox.value())
        self.simulationSafetyTimerSpinBox.setValue(self.safetyTimerSpinBox.value())

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

        self.backtestLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.backtestStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.backtestTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())
        self.backtestSmartStopLossSpinBox.setValue(self.smartStopLossSpinBox.value())

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

    def load_slots(self):
        """
        Loads all configuration interface slots.
        :return: None
        """
        self.simulationCopySettingsButton.clicked.connect(self.copy_settings_to_simulation)

        self.backtestCopySettingsButton.clicked.connect(self.copy_settings_to_backtest)
        self.backtestImportDataButton.clicked.connect(self.import_data)
        self.backtestDownloadDataButton.clicked.connect(self.download_data)
        self.backtestStopDownloadButton.clicked.connect(self.stop_download)

        self.testCredentialsButton.clicked.connect(self.test_binance_credentials)
        self.saveCredentialsButton.clicked.connect(self.save_credentials)
        self.loadCredentialsButton.clicked.connect(lambda: self.load_credentials(auto=False))
        self.testTelegramButton.clicked.connect(self.test_telegram)

        self.telegramApiKey.textChanged.connect(self.reset_telegram_state)
        self.telegramChatID.textChanged.connect(self.reset_telegram_state)

        self.simulationSaveConfigurationButton.clicked.connect(self.save_simulation_settings)
        self.simulationLoadConfigurationButton.clicked.connect(self.load_simulation_settings)
        self.saveConfigurationButton.clicked.connect(self.save_live_settings)
        self.loadConfigurationButton.clicked.connect(self.load_live_settings)
        self.backtestSaveConfigurationButton.clicked.connect(self.save_backtest_settings)
        self.backtestLoadConfigurationButton.clicked.connect(self.load_backtest_settings)

        self.graphPlotSpeedSpinBox.valueChanged.connect(self.update_graph_speed)
