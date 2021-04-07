import os
import shutil
from datetime import datetime, timezone

from PyQt5 import uic
from PyQt5.QtCore import QDate, QThreadPool
from PyQt5.QtWidgets import QDialog, QMessageBox

import algobot.helpers as helpers
from algobot.data import Data
from algobot.threads.downloadThread import DownloadThread
from algobot.threads.listThread import Worker

otherCommandsUi = os.path.join(helpers.ROOT_DIR, 'UI', 'otherCommands.ui')


class OtherCommands(QDialog):
    def __init__(self, parent=None):
        super(OtherCommands, self).__init__(parent)  # Initializing object
        uic.loadUi(otherCommandsUi, self)  # Loading the main UI
        self.parent = parent
        self.threadPool = QThreadPool()
        self.load_slots()
        self.csvThread = None
        self.setDateThread = None
        self.currentDateList = None

    def load_slots(self):
        """
        Loads all the slots for the GUI.
        """
        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)
        self.stopButton.clicked.connect(self.stop_csv_generation)
        self.csvGenerationTicker.currentTextChanged.connect(self.start_date_thread)

        # Purge
        self.purgeLogsButton.clicked.connect(lambda: self.purge('Logs'))
        self.purgeDatabasesButton.clicked.connect(lambda: self.purge('Databases'))
        self.purgeBacktestResultsButton.clicked.connect(lambda: self.purge('Backtest Results'))
        self.purgeConfigurationFilesButton.clicked.connect(lambda: self.purge('Configuration'))
        self.purgeCredentialsButton.clicked.connect(lambda: self.purge('Credentials'))
        self.purgeCSVFilesButton.clicked.connect(lambda: self.purge('CSV'))

    def purge(self, directory):
        path = os.path.join(helpers.ROOT_DIR, directory)
        if not os.path.exists(path):
            QMessageBox.about(self, 'Warning', f"No {directory.lower()} files detected.")
            return

        message = f'Are you sure you want to delete your {directory.lower()} files? You might not be able to undo ' \
                  f'this operation. \n\nThe following path will be deleted: \n{path}'
        qm = QMessageBox
        ret = qm.question(self, 'Warning', message, qm.Yes | qm.No)

        if ret == qm.Yes and os.path.exists(path):
            shutil.rmtree(path)
            self.infoLabel.setText(f'{directory.capitalize()} files have been successfully deleted.')

            if directory == 'Logs':
                self.parent.logger = helpers.get_logger(logFile='algobot', loggerName='algobot')

    def start_date_thread(self):
        self.csvGenerationStatus.setText("Searching for earliest start date..")
        self.csvGenerationProgressBar.setValue(0)
        self.setDateThread = Worker(self.get_start_date_for_csv)
        self.setDateThread.signals.finished.connect(self.set_start_date_for_csv)
        self.setDateThread.signals.started.connect(lambda: self.generateCSVButton.setEnabled(False))
        self.setDateThread.signals.restore.connect(self.restore_csv_state)
        self.threadPool.start(self.setDateThread)

    # noinspection PyProtectedMember
    def get_start_date_for_csv(self):
        symbol = self.csvGenerationTicker.currentText()
        interval = helpers.convert_long_interval(self.csvGenerationDataInterval.currentText())

        ts = Data(loadData=False, log=False).binanceClient._get_earliest_valid_timestamp(symbol, interval)
        startDate = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        qStart = QDate(startDate.year, startDate.month, startDate.day)

        endDate = datetime.now(tz=timezone.utc)
        qEnd = QDate(endDate.year, endDate.month, endDate.day)

        return [qStart, qEnd]

    def set_start_date_for_csv(self, startEndList):
        self.currentDateList = startEndList
        self.startDateCalendar.setDateRange(*startEndList)
        self.startDateCalendar.setSelectedDate(startEndList[0])
        self.csvGenerationStatus.setText("Setup filtered date successfully.")

    def initiate_csv_generation(self):
        """
        Starts download of data and CSV generation.
        """
        symbol = self.csvGenerationTicker.currentText()
        descending = self.descendingDateRadio.isChecked()
        armyTime = self.armyDateRadio.isChecked()
        interval = helpers.convert_long_interval(self.csvGenerationDataInterval.currentText())

        selectedDate = self.startDateCalendar.selectedDate().toPyDate()
        startDate = None if selectedDate == self.currentDateList[0] else selectedDate

        self.csvGenerationStatus.setText("Downloading data...")
        thread = DownloadThread(interval, symbol, descending, armyTime, startDate)
        thread.signals.locked.connect(lambda: self.stopButton.setEnabled(False))
        thread.signals.csv_finished.connect(self.end_csv_generation)
        thread.signals.error.connect(self.handle_csv_generation_error)
        thread.signals.restore.connect(self.restore_csv_state)
        thread.signals.progress.connect(self.progress_update)
        thread.signals.started.connect(self.disable_csv_state)
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
            helpers.open_file_or_folder(savedPath)

    def disable_csv_state(self):
        self.generateCSVButton.setEnabled(False)
        self.stopButton.setEnabled(True)

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
