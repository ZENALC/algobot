import os
import helpers

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QDialog, QMessageBox
from threadWorkers import Worker, CSVGeneratingThread
from data import Data

otherCommandsUi = os.path.join('../', 'UI', 'otherCommands.ui')


class OtherCommands(QDialog):
    def __init__(self, parent=None):
        super(OtherCommands, self).__init__(parent)  # Initializing object
        uic.loadUi(otherCommandsUi, self)  # Loading the main UI

        self.threadPool = QThreadPool()

        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)
        self.movingAverageMiscellaneousParameter.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousType.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousValue.valueChanged.connect(self.initiate_misc_get_moving_average)

    def initiate_misc_get_moving_average(self):
        thread = Worker(self.get_moving_average_miscellaneous)
        self.threadPool.start(thread)

    def get_moving_average_miscellaneous(self):
        self.movingAverageMiscellaneousResult.setText("Not yet implemented.")

    def initiate_csv_generation(self):
        self.generateCSVButton.setEnabled(False)
        self.csvGenerationStatus.setText("Downloading data...")
        symbol = self.csvGenerationTicker.currentText()
        interval = helpers.convert_interval(self.csvGenerationDataInterval.currentText())
        descending = self.descendingDateRadio.isChecked()
        thread = CSVGeneratingThread(symbol=symbol, interval=interval, descending=descending)
        self.threadPool.start(thread)
        thread.signals.finished.connect(self.end_csv_generation)

    def end_csv_generation(self, savedPath):
        msg = f"Successfully saved CSV data to {savedPath}."
        self.csvGenerationStatus.setText(msg)
        self.generateCSVButton.setEnabled(True)
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText(f"Successfully saved CSV data to {savedPath}.")
        msgBox.setWindowTitle("Data saved successfully.")
        msgBox.setStandardButtons(QMessageBox.Open | QMessageBox.Close)
        if msgBox.exec_() == QMessageBox.Open:
            os.startfile(savedPath)
