import os
import telegram
import helpers

from PyQt5.QtCore import QDate, QThreadPool
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox
from binance.client import Client
from telegram.ext import Updater
from dateutil import parser
from threads import downloadThread
from enums import SIMULATION, LIVE, BACKTEST

configurationUi = os.path.join(helpers.ROOT_DIR, 'UI', 'configuration.ui')


class Configuration(QDialog):
    def __init__(self, parent=None, logger=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.threadPool = QThreadPool()
        self.logger = logger
        self.data = None
        self.dataType = None
        self.downloadThread = None
        self.tokenPass = False
        self.chatPass = False
        self.credentialsFolder = "Credentials"
        self.configFolder = 'Configuration'

        self.load_slots()
        self.load_credentials()

    def test_telegram(self):
        """
        Tests Telegram connection and updates respective GUI elements.
        """
        tokenPass = False
        chatPass = False
        message = ""
        error = ''

        try:
            telegramApikey = self.telegramApiKey.text()
            chatID = self.telegramChatID.text()
            Updater(telegramApikey, use_context=True)
            tokenPass = True
            telegram.Bot(token=telegramApikey).send_message(chat_id=chatID, text='Testing connection with Chat ID.')
            chatPass = True
        except Exception as e:
            error = str(e)
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
            stringError = str(e)
            if '1000ms' in stringError:
                self.credentialResult.setText('Time not synchronized. Please synchronize your time.')
            else:
                self.credentialResult.setText(stringError)

    @staticmethod
    def create_folder_if_needed(targetPath, basePath=None):
        if not basePath:
            basePath = helpers.ROOT_DIR

        if not os.path.exists(targetPath):
            folder = os.path.basename(targetPath)
            cur_path = os.getcwd()
            os.chdir(basePath)
            os.mkdir(folder)
            os.chdir(cur_path)
            return True
        return False

    def load_credentials(self, auto=True):
        """
        Attempts to load credentials automatically from path program regularly stores credentials in if auto is True.
        """
        targetFolder = os.path.join(helpers.ROOT_DIR, self.credentialsFolder)
        if self.create_folder_if_needed(targetFolder):
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
        self.create_folder_if_needed(targetFolder)

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
            # QMessageBox.about(self, 'Info', 'Credentials have successfully been overwritten.')
        else:
            self.credentialResult.setText('Credentials could not be saved.')

    def get_calendar_dates(self):
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

    def create_appropriate_config_folders(self, folder):
        basePath = os.path.join(helpers.ROOT_DIR, self.configFolder)
        self.create_folder_if_needed(basePath)

        targetPath = os.path.join(basePath, folder)
        self.create_folder_if_needed(targetPath, basePath=basePath)

        return targetPath

    # noinspection DuplicatedCode
    def save_backtest_settings(self):
        config = {
            # General
            'type': BACKTEST,
            'ticker': self.backtestTickerComboBox.currentIndex(),
            'interval': self.backtestIntervalComboBox.currentIndex(),
            'startingBalance': self.backtestStartingBalanceSpinBox.value(),
            'precision': self.backtestPrecisionSpinBox.value(),
            'marginTrading': self.backtestMarginTradingCheckBox.isChecked(),

            # Averages
            'averageType': self.backtestAverageTypeComboBox.currentIndex(),
            'parameter': self.backtestParameterComboBox.currentIndex(),
            'initialValue': self.backtestInitialValueSpinBox.value(),
            'finalValue': self.backtestFinalValueSpinBox.value(),
            'doubleCross': self.backtestDoubleCrossCheckMark.isChecked(),
            'averageType2': self.backtestDoubleAverageComboBox.currentIndex(),
            'parameter2': self.backtestDoubleParameterComboBox.currentIndex(),
            'initialValue2': self.backtestDoubleInitialValueSpinBox.value(),
            'finalValue2': self.backtestDoubleFinalValueSpinBox.value(),

            # Stoics
            'stoic': self.backtestStoicCheckMark.isChecked(),
            'stoic1': self.backtestStoicSpinBox1.value(),
            'stoic2': self.backtestStoicSpinBox2.value(),
            'stoic3': self.backtestStoicSpinBox3.value(),

            # Shrek
            'shrek': self.backtestShrekCheckMark.isChecked(),
            'shrek1': self.backtestShrekSpinBox1.value(),
            'shrek2': self.backtestShrekSpinBox2.value(),
            'shrek3': self.backtestShrekSpinBox3.value(),
            'shrek4': self.backtestShrekSpinBox4.value(),

            # Loss
            'trailingLoss': self.backtestTrailingLossRadio.isChecked(),
            'stopLoss': self.backtestStopLossRadio.isChecked(),
            'lossPercentage': self.backtestLossPercentageSpinBox.value(),
            'smartStopLossCounter': self.backtestSmartStopLossSpinBox.value(),
        }

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

    # noinspection DuplicatedCode
    def load_backtest_settings(self):
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

                self.backtestAverageTypeComboBox.setCurrentIndex(config['averageType'])
                self.backtestParameterComboBox.setCurrentIndex(config['parameter'])
                self.backtestInitialValueSpinBox.setValue(config['initialValue'])
                self.backtestFinalValueSpinBox.setValue(config['finalValue'])
                self.backtestDoubleCrossCheckMark.setChecked(config['doubleCross'])
                self.backtestDoubleAverageComboBox.setCurrentIndex(config['averageType2'])
                self.backtestDoubleParameterComboBox.setCurrentIndex(config['parameter2'])
                self.backtestDoubleInitialValueSpinBox.setValue(config['initialValue2'])
                self.backtestDoubleFinalValueSpinBox.setValue(config['finalValue2'])

                self.backtestStoicCheckMark.setChecked(config['stoic'])
                self.backtestStoicSpinBox1.setValue(config['stoic1'])
                self.backtestStoicSpinBox2.setValue(config['stoic2'])
                self.backtestStoicSpinBox3.setValue(config['stoic3'])

                self.backtestShrekCheckMark.setChecked(config['shrek'])
                self.backtestShrekSpinBox1.setValue(config['shrek1'])
                self.backtestShrekSpinBox2.setValue(config['shrek2'])
                self.backtestShrekSpinBox3.setValue(config['shrek3'])
                self.backtestShrekSpinBox4.setValue(config['shrek4'])

                self.backtestTrailingLossRadio.setChecked(config['trailingLoss'])
                self.backtestStopLossRadio.setChecked(config['stopLoss'])
                self.backtestLossPercentageSpinBox.setValue(config['lossPercentage'])
                self.backtestSmartStopLossSpinBox.setValue(config['smartStopLossCounter'])

                file = os.path.basename(filePath)
                self.backtestConfigurationResult.setText(f"Loaded backtest configuration successfully from {file}.")
        except Exception as e:
            print(str(e))
            self.logger.exception(str(e))
            self.backtestConfigurationResult.setText("Could not load backtest configuration.")

    # noinspection DuplicatedCode
    def save_simulation_settings(self):
        config = {
            # General
            'type': SIMULATION,
            'ticker': self.simulationTickerComboBox.currentIndex(),
            'interval': self.simulationIntervalComboBox.currentIndex(),
            'startingBalance': self.simulationStartingBalanceSpinBox.value(),
            'precision': self.simulationPrecisionSpinBox.value(),
            'lowerInterval': self.lowerIntervalSimulationCheck.isChecked(),

            # Averages
            'averageType': self.simulationAverageTypeComboBox.currentIndex(),
            'parameter': self.simulationParameterComboBox.currentIndex(),
            'initialValue': self.simulationInitialValueSpinBox.value(),
            'finalValue': self.simulationFinalValueSpinBox.value(),
            'doubleCross': self.simulationDoubleCrossCheckMark.isChecked(),
            'averageType2': self.simulationDoubleAverageComboBox.currentIndex(),
            'parameter2': self.simulationDoubleParameterComboBox.currentIndex(),
            'initialValue2': self.simulationDoubleInitialValueSpinBox.value(),
            'finalValue2': self.simulationDoubleFinalValueSpinBox.value(),

            # Stoics
            'stoic': self.simulationStoicCheckMark.isChecked(),
            'stoic1': self.simulationStoicSpinBox1.value(),
            'stoic2': self.simulationStoicSpinBox2.value(),
            'stoic3': self.simulationStoicSpinBox3.value(),

            # Shrek
            'shrek': self.simulationShrekCheckMark.isChecked(),
            'shrek1': self.simulationShrekSpinBox1.value(),
            'shrek2': self.simulationShrekSpinBox2.value(),
            'shrek3': self.simulationShrekSpinBox3.value(),
            'shrek4': self.simulationShrekSpinBox4.value(),

            # Loss
            'trailingLoss': self.simulationTrailingLossRadio.isChecked(),
            'stopLoss': self.simulationStopLossRadio.isChecked(),
            'lossPercentage': self.simulationLossPercentageSpinBox.value(),
            'smartStopLossCounter': self.simulationSmartStopLossSpinBox.value(),
            'safetyTimer': self.simulationSafetyTimerSpinBox.value(),
        }

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

    # noinspection DuplicatedCode
    def load_simulation_settings(self):
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

                self.simulationAverageTypeComboBox.setCurrentIndex(config['averageType'])
                self.simulationParameterComboBox.setCurrentIndex(config['parameter'])
                self.simulationInitialValueSpinBox.setValue(config['initialValue'])
                self.simulationFinalValueSpinBox.setValue(config['finalValue'])
                self.simulationDoubleCrossCheckMark.setChecked(config['doubleCross'])
                self.simulationDoubleAverageComboBox.setCurrentIndex(config['averageType2'])
                self.simulationDoubleParameterComboBox.setCurrentIndex(config['parameter2'])
                self.simulationDoubleInitialValueSpinBox.setValue(config['initialValue2'])
                self.simulationDoubleFinalValueSpinBox.setValue(config['finalValue2'])

                self.simulationStoicCheckMark.setChecked(config['stoic'])
                self.simulationStoicSpinBox1.setValue(config['stoic1'])
                self.simulationStoicSpinBox2.setValue(config['stoic2'])
                self.simulationStoicSpinBox3.setValue(config['stoic3'])

                self.simulationShrekCheckMark.setChecked(config['shrek'])
                self.simulationShrekSpinBox1.setValue(config['shrek1'])
                self.simulationShrekSpinBox2.setValue(config['shrek2'])
                self.simulationShrekSpinBox3.setValue(config['shrek3'])
                self.simulationShrekSpinBox4.setValue(config['shrek4'])

                self.simulationTrailingLossRadio.setChecked(config['trailingLoss'])
                self.simulationStopLossRadio.setChecked(config['stopLoss'])
                self.simulationLossPercentageSpinBox.setValue(config['lossPercentage'])
                self.simulationSmartStopLossSpinBox.setValue(config['smartStopLossCounter'])
                self.simulationSafetyTimerSpinBox.setValue(config['safetyTimer'])

                file = os.path.basename(filePath)
                self.simulationConfigurationResult.setText(f"Loaded simulation configuration successfully from {file}.")
        except Exception as e:
            print(str(e))
            self.logger.exception(str(e))
            self.simulationConfigurationResult.setText("Could not load simulation configuration.")

    # noinspection DuplicatedCode
    def save_live_settings(self):
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

            # Averages
            'averageType': self.averageTypeComboBox.currentIndex(),
            'parameter': self.parameterComboBox.currentIndex(),
            'initialValue': self.initialValueSpinBox.value(),
            'finalValue': self.finalValueSpinBox.value(),
            'doubleCross': self.doubleCrossCheckMark.isChecked(),
            'averageType2': self.doubleAverageComboBox.currentIndex(),
            'parameter2': self.doubleParameterComboBox.currentIndex(),
            'initialValue2': self.doubleInitialValueSpinBox.value(),
            'finalValue2': self.doubleFinalValueSpinBox.value(),

            # Stoics
            'stoic': self.stoicCheckMark.isChecked(),
            'stoic1': self.stoicSpinBox1.value(),
            'stoic2': self.stoicSpinBox2.value(),
            'stoic3': self.stoicSpinBox3.value(),

            # Shrek
            'shrek': self.shrekCheckMark.isChecked(),
            'shrek1': self.shrekSpinBox1.value(),
            'shrek2': self.shrekSpinBox2.value(),
            'shrek3': self.shrekSpinBox3.value(),
            'shrek4': self.shrekSpinBox4.value(),

            # Loss
            'trailingLoss': self.trailingLossRadio.isChecked(),
            'stopLoss': self.stopLossRadio.isChecked(),
            'lossPercentage': self.lossPercentageSpinBox.value(),
            'smartStopLossCounter': self.smartStopLossSpinBox.value(),
            'safetyTimer': self.safetyTimerSpinBox.value(),
        }

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

    # noinspection DuplicatedCode
    def load_live_settings(self):
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

                self.averageTypeComboBox.setCurrentIndex(config['averageType'])
                self.parameterComboBox.setCurrentIndex(config['parameter'])
                self.initialValueSpinBox.setValue(config['initialValue'])
                self.finalValueSpinBox.setValue(config['finalValue'])
                self.doubleCrossCheckMark.setChecked(config['doubleCross'])
                self.doubleAverageComboBox.setCurrentIndex(config['averageType2'])
                self.doubleParameterComboBox.setCurrentIndex(config['parameter2'])
                self.doubleInitialValueSpinBox.setValue(config['initialValue2'])
                self.doubleFinalValueSpinBox.setValue(config['finalValue2'])

                self.stoicCheckMark.setChecked(config['stoic'])
                self.stoicSpinBox1.setValue(config['stoic1'])
                self.stoicSpinBox2.setValue(config['stoic2'])
                self.stoicSpinBox3.setValue(config['stoic3'])

                self.shrekCheckMark.setChecked(config['shrek'])
                self.shrekSpinBox1.setValue(config['shrek1'])
                self.shrekSpinBox2.setValue(config['shrek2'])
                self.shrekSpinBox3.setValue(config['shrek3'])
                self.shrekSpinBox4.setValue(config['shrek4'])

                self.trailingLossRadio.setChecked(config['trailingLoss'])
                self.stopLossRadio.setChecked(config['stopLoss'])
                self.lossPercentageSpinBox.setValue(config['lossPercentage'])
                self.smartStopLossSpinBox.setValue(config['smartStopLossCounter'])
                self.safetyTimerSpinBox.setValue(config['safetyTimer'])

                file = os.path.basename(filePath)
                self.configurationResult.setText(f"Loaded live configuration successfully from {file}.")
        except Exception as e:
            self.logger.exception(str(e))
            self.configurationResult.setText("Could not load live configuration.")

    # noinspection DuplicatedCode
    def copy_settings_to_simulation(self):
        """
        Copies parameters from main configuration to simulation configuration.
        """
        self.simulationIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.simulationTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())
        self.simulationPrecisionSpinBox.setValue(self.precisionSpinBox.value())

        self.simulationAverageTypeComboBox.setCurrentIndex(self.averageTypeComboBox.currentIndex())
        self.simulationParameterComboBox.setCurrentIndex(self.parameterComboBox.currentIndex())
        self.simulationInitialValueSpinBox.setValue(self.initialValueSpinBox.value())
        self.simulationFinalValueSpinBox.setValue(self.finalValueSpinBox.value())

        self.simulationDoubleCrossCheckMark.setChecked(self.doubleCrossCheckMark.isChecked())
        self.simulationDoubleAverageComboBox.setCurrentIndex(self.doubleAverageComboBox.currentIndex())
        self.simulationDoubleParameterComboBox.setCurrentIndex(self.doubleParameterComboBox.currentIndex())
        self.simulationDoubleInitialValueSpinBox.setValue(self.doubleInitialValueSpinBox.value())
        self.simulationDoubleFinalValueSpinBox.setValue(self.doubleFinalValueSpinBox.value())

        self.simulationLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.simulationStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.simulationTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())
        self.simulationSmartStopLossSpinBox.setValue(self.smartStopLossSpinBox.value())
        self.simulationSafetyTimerSpinBox.setValue(self.safetyTimerSpinBox.value())

        self.simulationStoicCheckMark.setChecked(self.stoicCheckMark.isChecked())
        self.simulationStoicSpinBox1.setValue(self.stoicSpinBox1.value())
        self.simulationStoicSpinBox2.setValue(self.stoicSpinBox2.value())
        self.simulationStoicSpinBox3.setValue(self.stoicSpinBox3.value())

        self.simulationShrekCheckMark.setChecked(self.shrekCheckMark.isChecked())
        self.simulationShrekSpinBox1.setValue(self.shrekSpinBox1.value())
        self.simulationShrekSpinBox2.setValue(self.shrekSpinBox2.value())
        self.simulationShrekSpinBox3.setValue(self.shrekSpinBox3.value())
        self.simulationShrekSpinBox4.setValue(self.shrekSpinBox4.value())

        self.simulationCopyLabel.setText("Copied all viable settings from main to simulation settings successfully.")

    # noinspection DuplicatedCode
    def copy_settings_to_backtest(self):
        """
        Copies parameters from main configuration to backtest configuration.
        """
        self.backtestIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.backtestTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())
        self.backtestPrecisionSpinBox.setValue(self.precisionSpinBox.value())

        self.backtestAverageTypeComboBox.setCurrentIndex(self.averageTypeComboBox.currentIndex())
        self.backtestParameterComboBox.setCurrentIndex(self.parameterComboBox.currentIndex())
        self.backtestInitialValueSpinBox.setValue(self.initialValueSpinBox.value())
        self.backtestFinalValueSpinBox.setValue(self.finalValueSpinBox.value())

        self.backtestDoubleCrossCheckMark.setChecked(self.doubleCrossCheckMark.isChecked())
        self.backtestDoubleAverageComboBox.setCurrentIndex(self.doubleAverageComboBox.currentIndex())
        self.backtestDoubleParameterComboBox.setCurrentIndex(self.doubleParameterComboBox.currentIndex())
        self.backtestDoubleInitialValueSpinBox.setValue(self.doubleInitialValueSpinBox.value())
        self.backtestDoubleFinalValueSpinBox.setValue(self.doubleFinalValueSpinBox.value())

        self.backtestLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.backtestStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.backtestTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())
        self.backtestSmartStopLossSpinBox.setValue(self.smartStopLossSpinBox.value())

        self.backtestStoicCheckMark.setChecked(self.stoicCheckMark.isChecked())
        self.backtestStoicSpinBox1.setValue(self.stoicSpinBox1.value())
        self.backtestStoicSpinBox2.setValue(self.stoicSpinBox2.value())
        self.backtestStoicSpinBox3.setValue(self.stoicSpinBox3.value())

        self.backtestShrekCheckMark.setChecked(self.shrekCheckMark.isChecked())
        self.backtestShrekSpinBox1.setValue(self.shrekSpinBox1.value())
        self.backtestShrekSpinBox2.setValue(self.shrekSpinBox2.value())
        self.backtestShrekSpinBox3.setValue(self.shrekSpinBox3.value())
        self.backtestShrekSpinBox4.setValue(self.shrekSpinBox4.value())

        self.backtestCopyLabel.setText("Copied all viable settings from main to backtest settings successfully.")

    def toggle_double_cross_groupbox(self):
        self.toggle_groupbox(self.doubleCrossCheckMark, self.doubleCrossGroupBox)

    def toggle_simulation_double_cross_groupbox(self):
        self.toggle_groupbox(self.simulationDoubleCrossCheckMark, self.simulationDoubleCrossGroupBox)

    def toggle_backtest_double_cross_groupbox(self):
        self.toggle_groupbox(self.backtestDoubleCrossCheckMark, self.backtestDoubleCrossGroupBox)

    def toggle_backtest_stoic_groupbox(self):
        self.toggle_groupbox(self.backtestStoicCheckMark, self.backtestStoicGroupBox)

    def toggle_simulation_stoic_groupbox(self):
        self.toggle_groupbox(self.simulationStoicCheckMark, self.simulationStoicGroupBox)

    def toggle_stoic_groupbox(self):
        self.toggle_groupbox(self.stoicCheckMark, self.stoicGroupBox)

    @staticmethod
    def toggle_groupbox(checkMark, groupBox):
        groupBox.setEnabled(checkMark.isChecked())

    def load_slots(self):
        """
        Loads all configuration interface slots.
        """
        self.doubleCrossCheckMark.toggled.connect(self.toggle_double_cross_groupbox)
        self.simulationDoubleCrossCheckMark.toggled.connect(self.toggle_simulation_double_cross_groupbox)
        self.backtestDoubleCrossCheckMark.toggled.connect(self.toggle_backtest_double_cross_groupbox)

        self.stoicCheckMark.toggled.connect(self.toggle_stoic_groupbox)
        self.simulationStoicCheckMark.toggled.connect(self.toggle_simulation_stoic_groupbox)
        self.backtestStoicCheckMark.toggled.connect(self.toggle_backtest_stoic_groupbox)

        self.shrekCheckMark.toggled.connect(lambda: self.toggle_groupbox(self.shrekCheckMark, self.shrekGroupBox))
        self.simulationShrekCheckMark.toggled.connect(lambda: self.toggle_groupbox(self.simulationShrekCheckMark,
                                                                                   self.simulationShrekGroupBox))
        self.backtestShrekCheckMark.toggled.connect(lambda: self.toggle_groupbox(self.backtestShrekCheckMark,
                                                                                 self.backtestShrekGroupBox))

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
