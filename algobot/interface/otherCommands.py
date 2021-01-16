import os
import helpers
from threads.csvThread import CSVGeneratingThread

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QDialog, QMessageBox

otherCommandsUi = os.path.join(helpers.ROOT_DIR, 'UI', 'otherCommands.ui')


class OtherCommands(QDialog):
    def __init__(self, parent=None):
        super(OtherCommands, self).__init__(parent)  # Initializing object
        uic.loadUi(otherCommandsUi, self)  # Loading the main UI
        self.threadPool = QThreadPool()
        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)

    def initiate_csv_generation(self):
        """
        Starts download of data and CSV generation.
        """
        self.generateCSVButton.setEnabled(False)
        self.csvGenerationStatus.setText("Downloading data...")

        symbol = self.csvGenerationTicker.currentText()
        interval = helpers.convert_interval(self.csvGenerationDataInterval.currentText())
        descending = self.descendingDateRadio.isChecked()
        armyTime = self.armyDateRadio.isChecked()

        thread = CSVGeneratingThread(symbol=symbol, interval=interval, descending=descending, armyTime=armyTime)
        thread.signals.progress.connect(self.progress_update)
        thread.signals.finished.connect(self.end_csv_generation)
        thread.signals.error.connect(self.handle_csv_generation_error)
        thread.signals.restore.connect(self.restore_csv_state)
        self.threadPool.start(thread)

    def progress_update(self, progress, message):
        self.csvGenerationProgressBar.setValue(progress)
        self.csvGenerationStatus.setText(message)

    def end_csv_generation(self, savedPath):
        """
        After getting a successful end signal from thread, it modifies GUI to reflect this action. It also opens up a
        pop-up asking the user if they want to open the file right away.
        :param savedPath: Path where the file was saved.
        """
        msg = f"Successfully saved CSV data to {savedPath}."

        self.csvGenerationStatus.setText(msg)
        self.csvGenerationProgressBar.setValue(100)
        self.generateCSVButton.setEnabled(True)

        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText(f"Successfully saved CSV data to {savedPath}.")
        msgBox.setWindowTitle("Data saved successfully.")
        msgBox.setStandardButtons(QMessageBox.Open | QMessageBox.Close)
        if msgBox.exec_() == QMessageBox.Open:
            os.startfile(savedPath)

    def restore_csv_state(self):
        self.generateCSVButton.setEnabled(True)

    def handle_csv_generation_error(self, e):
        """
        In the event that thread fails, it modifies the GUI with the error message passed to function.
        :param e: Error message.
        """
        self.csvGenerationStatus.setText(f"Downloading failed because of error: {e}.")
