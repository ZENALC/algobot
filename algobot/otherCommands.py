import os
import helpers

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QDialog
from threadWorkers import Worker
from data import Data


otherCommandsUi = f'../UI{os.path.sep}otherCommands.ui'


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
        self.movingAverageMiscellaneousResult.setText("haha what did you expect?")

    def initiate_csv_generation(self):
        thread = Worker(self.generate_csv)
        self.threadPool.start(thread)

    def generate_csv(self):
        self.generateCSVButton.setEnabled(False)

        symbol = self.csvGenerationTicker.currentText()
        interval = helpers.convert_interval(self.csvGenerationDataInterval.currentText())
        self.csvGenerationStatus.setText("Downloading data...")
        savedPath = Data(loadData=False, interval=interval, symbol=symbol).get_csv_file()

        # messageBox = QMessageBox()
        # messageBox.setText(f"Successfully saved CSV data to {savedPath}.")
        # messageBox.setIcon(QMessageBox.Information)
        # messageBox.exec_()
        self.csvGenerationStatus.setText(f"Successfully saved CSV data to {savedPath}.")
        self.generateCSVButton.setEnabled(True)
