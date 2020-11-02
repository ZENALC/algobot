import os
import helpers

from PyQt5.QtCore import QDate, QThreadPool
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QFileDialog
from binance.client import Client
from telegram.ext import Updater
from dateutil import parser
from threads import downloadThread

configurationUi = os.path.join('../', 'UI', 'configuration.ui')


class Configuration(QDialog):
    def __init__(self, parent=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.threadPool = QThreadPool()
        self.load_slots()
        self.load_credentials()
        self.downloadedData = None

    def load_slots(self):
        """
        Loads all configuration interface slots.
        """
        self.doubleCrossCheckMark.toggled.connect(self.toggle_double_cross_groupbox)
        self.simulationDoubleCrossCheckMark.toggled.connect(self.toggle_simulation_double_cross_groupbox)
        self.backtestDoubleCrossCheckMark.toggled.connect(self.toggle_backtest_double_cross_groupbox)

        self.simulationCopySettingsButton.clicked.connect(self.copy_settings_to_simulation)

        self.backtestCopySettingsButton.clicked.connect(self.copy_settings_to_backtest)
        self.backtestImportDataButton.clicked.connect(self.import_data)
        self.backtestDownloadDataButton.clicked.connect(self.download_data)

        self.testCredentialsButton.clicked.connect(self.test_binance_credentials)
        self.saveCredentialsButton.clicked.connect(self.save_credentials)
        self.loadCredentialsButton.clicked.connect(self.load_credentials)
        self.testTelegramButton.clicked.connect(self.test_telegram)

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
        Attempts to load credentials automatically from path Program stores credentials in.
        :return:
        """
        try:
            credentials = helpers.load_credentials()
            self.binanceApiKey.setText(credentials['apiKey'])
            self.binanceApiSecret.setText(credentials['apiSecret'])
            self.telegramApiKey.setText(credentials['telegramApiKey'])
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
        if len(apiKey) == 0:
            self.credentialResult.setText('Please fill in Binance API key details.')
            return

        apiSecret = self.binanceApiSecret.text()
        if len(apiSecret) == 0:
            self.credentialResult.setText('Please fill in Binance API secret details.')
            return

        telegramApiKey = self.telegramApiKey.text()
        helpers.write_credentials(apiKey=apiKey, apiSecret=apiSecret, telegramApiKey=telegramApiKey)
        self.credentialResult.setText('Credentials have been saved successfully.')

    def test_telegram(self):
        """
        Tests Telegram connection.
        """
        try:
            telegramApikey = self.telegramApiKey.text()
            Updater(telegramApikey, use_context=True)
            self.telegrationConnectionResult.setText('Connected successfully.')
        except Exception as e:
            self.telegrationConnectionResult.setText(str(e))

    def get_calendar_dates(self):
        startDate = self.backtestStartDate.selectedDate().toPyDate()
        endDate = self.backtestStartDate.selectedDate().toPyDate()
        return startDate, endDate

    def download_data(self):
        # startDate = self.backtestStartDate.selectedDate().toPyDate()
        # endDate = self.backtestStartDate.selectedDate().toPyDate()
        self.backtestInfoLabel.setText("Downloading data...")
        symbol = self.backtestTickerComboBox.currentText()
        interval = helpers.convert_interval(self.backtestIntervalComboBox.currentText())
        thread = downloadThread.DownloadThread(symbol=symbol, interval=interval)
        thread.signals.finished.connect(self.get_downloaded_data)
        thread.signals.error.connect(lambda e: self.backtestInfoLabel.setText(e))
        self.threadPool.start(thread)

    def get_downloaded_data(self, data):
        self.downloadedData = data
        self.backtestInfoLabel.setText("Downloaded data successfully.")

    def import_data(self):
        self.backtestInfoLabel.setText("Importing data...")
        filePath, _ = QFileDialog.getOpenFileName(self, 'Open file', os.path.join(os.getcwd(), '../'), "CSV (*.csv)")
        if filePath == '':
            self.backtestInfoLabel.setText("Data not imported.")
            return
        data = helpers.load_from_csv(filePath, descending=False)
        self.backtestInfoLabel.setText("Imported data successfully.")

        startDate = parser.parse(data[0]['date_utc'])
        startYear, startMonth, startDay = startDate.year, startDate.month, startDate.day
        qStartDate = QDate(startYear, startMonth, startDay)

        endDate = parser.parse(data[-1]['date_utc'])
        endYear, endMonth, endDay = endDate.year, endDate.month, endDate.day
        qEndDate = QDate(endYear, endMonth, endDay)

        self.backtestStartDate.setDateRange(qStartDate, qEndDate)
        self.backtestEndDate.setDateRange(qStartDate, qEndDate)

    def copy_settings_to_simulation(self):
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
        self.simulationPriceLimitSpinBox.setValue(self.priceLimitSpinBox.value())
        self.simulationStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.simulationTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())

    def copy_settings_to_backtest(self):
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

    def toggle_double_cross_groupbox(self):
        self.toggle_groupbox(self.doubleCrossCheckMark, self.doubleCrossGroupBox)

    def toggle_simulation_double_cross_groupbox(self):
        self.toggle_groupbox(self.simulationDoubleCrossCheckMark, self.simulationDoubleCrossGroupBox)

    def toggle_backtest_double_cross_groupbox(self):
        self.toggle_groupbox(self.backtestDoubleCrossCheckMark, self.backtestDoubleCrossGroupBox)

    @staticmethod
    def toggle_groupbox(checkMark, groupBox):
        groupBox.setEnabled(checkMark.isChecked())
