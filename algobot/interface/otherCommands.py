import os
import helpers

from PyQt5 import uic
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QDialog, QMessageBox
from threads.downloadThread import DownloadThread

otherCommandsUi = os.path.join(helpers.ROOT_DIR, 'UI', 'otherCommands.ui')


class OtherCommands(QDialog):
    def __init__(self, parent=None):
        super(OtherCommands, self).__init__(parent)  # Initializing object
        uic.loadUi(otherCommandsUi, self)  # Loading the main UI
        self.threadPool = QThreadPool()
        self.load_slots()
        self.csvThread = None

    def load_slots(self):
        """
        Loads all the slots for the GUI.
        """
        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)
        self.stopButton.clicked.connect(self.stop_csv_generation)

    def initiate_csv_generation(self):
        """
        Starts download of data and CSV generation.
        """
        self.generateCSVButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.csvGenerationStatus.setText("Downloading data...")

        symbol = self.csvGenerationTicker.currentText()
        descending = self.descendingDateRadio.isChecked()
        armyTime = self.armyDateRadio.isChecked()
        interval = helpers.convert_interval(self.csvGenerationDataInterval.currentText())

        thread = DownloadThread(symbol=symbol, interval=interval, descending=descending, armyTime=armyTime)
        thread.signals.progress.connect(self.progress_update)
        thread.signals.csv_finished.connect(self.end_csv_generation)
        thread.signals.error.connect(self.handle_csv_generation_error)
        thread.signals.restore.connect(self.restore_csv_state)
        thread.signals.locked.connect(lambda: self.stopButton.setEnabled(False))
        self.csvThread = thread
        self.threadPool.start(thread)

    def progress_update(self, progress, message):
        """
        Updates progress bar and message label with values passed.
        :param progress: Progress value to set.
        :param message: Message to set in message label.
        """
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
        """
        Restores GUI state once CSV generation process is finished.
        :return:
        """
        self.generateCSVButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.csvThread = None

    def stop_csv_generation(self):
        """
        Stops download if download is in progress.
        """
        if self.csvThread:
            self.csvGenerationStatus.setText("Canceling download...")
            self.csvThread.stop()

    def handle_csv_generation_error(self, e):
        """
        In the event that thread fails, it modifies the GUI with the error message passed to function.
        :param e: Error message.
        """
        self.csvGenerationStatus.setText(f"Download failed because of error: {e}.")
