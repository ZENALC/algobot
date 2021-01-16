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

configurationUi = os.path.join(helpers.ROOT_DIR, 'UI', 'configuration.ui')


class Configuration(QDialog):
    def __init__(self, parent=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.threadPool = QThreadPool()
        self.load_slots()
        self.load_credentials()
        self.data = None
        self.dataType = None
        self.downloadThread = None
        self.tokenPass = False
        self.chatPass = False

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
            telegram.Bot(token=telegramApikey).send_message(chat_id=chatID, text='TESTING CHAT ID CONNECTION')
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

    def load_credentials(self):
        """
        Attempts to load credentials automatically from path program regularly stores credentials in.
        """
        try:
            credentials = helpers.load_credentials()
            self.binanceApiKey.setText(credentials['apiKey'])
            self.binanceApiSecret.setText(credentials['apiSecret'])
            self.telegramApiKey.setText(credentials['telegramApiKey'])
            self.telegramChatID.setText(credentials['chatID'])
            self.credentialResult.setText('Credentials have been loaded successfully.')
        except FileNotFoundError:
            self.credentialResult.setText('Credentials not found. Please first save credentials to load them.')
        except Exception as e:
            self.credentialResult.setText(str(e))

    def save_credentials(self):
        """
        Function that saves credentials to base path in a JSON format. Obviously not very secure, but temp fix.
        """
        apiKey = self.binanceApiKey.text()
        apiSecret = self.binanceApiSecret.text()
        telegramApiKey = self.telegramApiKey.text()
        telegramChatId = self.telegramChatID.text()

        qm = QMessageBox
        warn = qm.warning(self, 'Close?',
                          f"Are you sure you want to save these credentials? All previous values will be overwritten!",
                          qm.Yes | qm.No)

        if warn == qm.Yes:
            helpers.write_credentials(apiKey=apiKey, apiSecret=apiSecret,
                                      telegramApiKey=telegramApiKey, chatID=telegramChatId)
            self.credentialResult.setText('Credentials have been saved successfully.')
            QMessageBox.about(self, 'Info', 'Credentials have successfully been overwritten.')
        else:
            self.credentialResult.setText('Credentials have not been saved.')

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
        self.set_download_progress(progress=0, message="Downloading data...")

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

    def set_download_progress(self, progress, message):
        """
        Sets download progress and message with parameters passed.
        :param progress: Progress value to set bar at.
        :param message: Message to display in label.
        """
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

    # noinspection DuplicatedCode
    def copy_settings_to_simulation(self):
        """
        Copies parameters from main configuration to simulation configuration.
        """
        self.simulationIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.simulationTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())

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

        self.simulationStoicCheckMark.setChecked(self.stoicCheckMark.isChecked())
        self.simulationStoicSpinBox1.setValue(self.stoicSpinBox1.value())
        self.simulationStoicSpinBox2.setValue(self.stoicSpinBox2.value())
        self.simulationStoicSpinBox3.setValue(self.stoicSpinBox3.value())

        self.simulationCopyLabel.setText("Copied all viable settings from main to simulation settings successfully.")

    # noinspection DuplicatedCode
    def copy_settings_to_backtest(self):
        """
        Copies parameters from main configuration to backtest configuration.
        """
        self.backtestIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.backtestTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())

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

        self.backtestStoicCheckMark.setChecked(self.stoicCheckMark.isChecked())
        self.backtestStoicSpinBox1.setValue(self.stoicSpinBox1.value())
        self.backtestStoicSpinBox2.setValue(self.stoicSpinBox2.value())
        self.backtestStoicSpinBox3.setValue(self.stoicSpinBox3.value())

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
        self.simulationCopySettingsButton.clicked.connect(self.copy_settings_to_simulation)

        self.backtestCopySettingsButton.clicked.connect(self.copy_settings_to_backtest)
        self.backtestImportDataButton.clicked.connect(self.import_data)
        self.backtestDownloadDataButton.clicked.connect(self.download_data)
        self.backtestStopDownloadButton.clicked.connect(self.stop_download)

        self.testCredentialsButton.clicked.connect(self.test_binance_credentials)
        self.saveCredentialsButton.clicked.connect(self.save_credentials)
        self.loadCredentialsButton.clicked.connect(self.load_credentials)
        self.testTelegramButton.clicked.connect(self.test_telegram)

        self.telegramApiKey.textChanged.connect(self.reset_telegram_state)
        self.telegramChatID.textChanged.connect(self.reset_telegram_state)
