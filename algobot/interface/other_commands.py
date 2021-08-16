"""
Other commands window.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List

import pandas as pd
from PyQt5 import QtGui, uic
from PyQt5.QtCore import QDate, QThreadPool
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox

import algobot
from algobot.helpers import ROOT_DIR, convert_long_interval, create_folder, get_logger, open_file_or_folder
from algobot.interface.utils import create_popup, open_from_msg_box
from algobot.threads.downloadThread import DownloadThread
from algobot.threads.volatilitySnooperThread import VolatilitySnooperThread
from algobot.threads.workerThread import Worker

if TYPE_CHECKING:
    from algobot.__main__ import Interface

otherCommandsUi = os.path.join(ROOT_DIR, 'UI', 'otherCommands.ui')


class OtherCommands(QDialog):
    """
    Other commands window.
    """
    def __init__(self, parent: Interface = None):
        """
        Initializer for other commands QDialog. This is the main QDialog that supports CSV creation and data purges.
        """
        super(OtherCommands, self).__init__(parent)  # Initializing object
        uic.loadUi(otherCommandsUi, self)  # Loading the main UI
        self.parent = parent
        self.threadPool = QThreadPool()
        self.load_slots()
        self.csvThread = None
        self.volatilityThread = None
        self.setDateThread = None
        self.currentDateList = None

    def mousePressEvent(self, a0: QtGui.QMouseEvent) -> None:
        """
        Overrides QDialog to detect click events. Used mainly to clear focus from QLineEdits.
        """
        # pylint: disable=c-extension-no-member, no-self-use
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QLineEdit):
            focused_widget.clearFocus()

    def load_slots(self):
        """
        Loads all the slots for the GUI.
        """
        # CSV generation slots.
        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)
        self.stopButton.clicked.connect(self.stop_csv_generation)
        self.csvGenerationTicker.editingFinished.connect(self.start_date_thread)

        # Volatility snooper slots.
        self.volatilityGenerateButton.clicked.connect(self.volatility_snooper)
        self.stopVolatilityButton.clicked.connect(self.stop_volatility_snooper)

        # Purge buttons.
        self.purgeLogsButton.clicked.connect(lambda: self.purge('Logs'))
        self.purgeDatabasesButton.clicked.connect(lambda: self.purge('Databases'))
        self.purgeBacktestResultsButton.clicked.connect(lambda: self.purge('Backtest Results'))
        self.purgeConfigurationFilesButton.clicked.connect(lambda: self.purge('Configuration'))
        self.purgeCredentialsButton.clicked.connect(lambda: self.purge('Credentials'))
        self.purgeCSVFilesButton.clicked.connect(lambda: self.purge('CSV'))

    def purge(self, directory: str):
        """
        Deletes directory provided.
        """
        path = os.path.join(ROOT_DIR, directory)
        if not os.path.exists(path):
            create_popup(self, f"No {directory.lower()} files detected.")
            return

        message = f'Are you sure you want to delete your {directory.lower()} files? You might not be able to undo ' \
                  f'this operation. \n\nThe following path will be deleted: \n{path}'
        qm = QMessageBox
        ret = qm.question(self, 'Warning', message, qm.Yes | qm.No)

        if ret == qm.Yes and os.path.exists(path):
            shutil.rmtree(path)
            self.infoLabel.setText(f'{directory.capitalize()} files have been successfully deleted.')

            if directory == 'Logs':  # Reinitialize log folder if old logs were purged.
                self.parent.logger = get_logger(log_file='algobot', logger_name='algobot')

    def start_date_thread(self):
        """
        Main thread for finding start dates when attempting to initiate a CSV generation.
        """
        self.csvGenerationTicker.clearFocus()  # Shift focus to next element.
        self.csvGenerationStatus.setText("Searching for earliest start date..")
        self.csvGenerationProgressBar.setValue(0)
        self.setDateThread = Worker(self.get_start_date_for_csv)
        self.setDateThread.signals.finished.connect(self.set_start_date_for_csv)
        self.setDateThread.signals.started.connect(lambda: self.generateCSVButton.setEnabled(False))
        self.setDateThread.signals.error.connect(self.error_handle_for_csv_start_date)
        self.threadPool.start(self.setDateThread)

    # noinspection PyProtectedMember
    def get_start_date_for_csv(self) -> List[QDate]:
        """
        Find start date by instantiating a Data object and fetching the Binance API.
        """
        symbol = self.csvGenerationTicker.text()
        interval = convert_long_interval(self.csvGenerationDataInterval.currentText())

        # pylint: disable=protected-access
        ts = algobot.BINANCE_CLIENT._get_earliest_valid_timestamp(symbol, interval)
        startDate = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        qStart = QDate(startDate.year, startDate.month, startDate.day)

        endDate = datetime.now(tz=timezone.utc)
        qEnd = QDate(endDate.year, endDate.month, endDate.day)
        return [qStart, qEnd]

    def set_start_date_for_csv(self, startEndList: List[QDate]):
        """
        Sets start date for CSV generation based on the parameters provided.
        """
        self.currentDateList = startEndList
        self.startDateCalendar.setDateRange(*startEndList)
        self.startDateCalendar.setSelectedDate(startEndList[0])
        self.csvGenerationStatus.setText("Setup filtered date successfully.")
        self.generateCSVButton.setEnabled(True)

    def error_handle_for_csv_start_date(self, error_message: str):
        """
        Error handling function when CSV start date can't be handled.
        """
        self.csvGenerationStatus.setText(error_message)
        self.generateCSVButton.setEnabled(False)

    def initiate_csv_generation(self):
        """
        Starts download of data and CSV generation.
        """
        symbol = self.csvGenerationTicker.text()
        descending = self.descendingDateRadio.isChecked()
        armyTime = self.armyDateRadio.isChecked()
        interval = convert_long_interval(self.csvGenerationDataInterval.currentText())

        selectedDate = self.startDateCalendar.selectedDate().toPyDate()
        startDate = None if selectedDate == self.currentDateList[0] else selectedDate

        self.csvGenerationStatus.setText("Downloading data...")
        thread = DownloadThread(interval, symbol, descending, armyTime, startDate, logger=self.parent.logger)
        thread.signals.locked.connect(lambda: self.stopButton.setEnabled(False))
        thread.signals.csv_finished.connect(self.end_csv_generation)
        thread.signals.error.connect(lambda e: self.csvGenerationStatus.setText(f"Download failed with error: {e}"))
        thread.signals.restore.connect(lambda: self.modify_csv_ui(running=False, reset=True))
        thread.signals.progress.connect(self.progress_update)
        thread.signals.started.connect(lambda: self.modify_csv_ui(running=True))
        self.csvThread = thread
        self.threadPool.start(thread)

    def progress_update(self, progress: int, message: str):
        """
        Updates progress bar and message label with values passed.
        :param progress: Progress value to set.
        :param message: Message to set in message label.
        """
        self.csvGenerationProgressBar.setValue(progress)
        self.csvGenerationStatus.setText(message)

    def end_csv_generation(self, savedPath: str):
        """
        After getting a successful end signal from thread, it modifies GUI to reflect this action. It also opens up a
        pop-up asking the user if they want to open the file right away.
        :param savedPath: Path where the file was saved.
        """
        msg = f"Successfully saved CSV data to {savedPath}."

        self.csvGenerationStatus.setText(msg)
        self.csvGenerationProgressBar.setValue(100)
        self.generateCSVButton.setEnabled(True)

        if open_from_msg_box(text=f"Successfully saved CSV data to {savedPath}.", title="Data saved successfully."):
            open_file_or_folder(savedPath)

    def modify_csv_ui(self, running: bool, reset: bool = False):
        """
        Modify CSV tab UI based on the running and reset boolean statuses'.
        :param running: Boolean whether CSV is being generated or not.
        :param reset: Flag for whether to kill the CSV thread.
        """
        self.generateCSVButton.setEnabled(not running)
        self.stopButton.setEnabled(running)

        if reset:
            self.csvThread = None

    def stop_csv_generation(self):
        """
        Stops download if download is in progress.
        """
        if self.csvThread:
            self.csvGenerationStatus.setText("Canceling download...")
            self.csvThread.stop()

    def end_snoop_generate_volatility_report(self, volatility_dict: Dict[str, Any], output_type: str):
        """
        End the snooping process and generate a volatility report.
        :param volatility_dict: Volatility dictionary containing snooped information.
        :param output_type: Output type in which to generate a report. (xlsx and csv supported)
        """
        self.volatilityStatus.setText("Finished snooping. Generating report...")
        self.volatilityProgressBar.setValue(100)
        folder_path = create_folder("Volatility Results")
        file_name = f'Volatility_Results_{datetime.now().strftime("%m_%d_%Y_%H_%M_%S")}.{output_type.lower()}'
        file_path = os.path.join(folder_path, file_name)

        df = pd.DataFrame(list(volatility_dict.items()), columns=['Ticker', 'Volatility'])
        if output_type.lower() == 'csv':
            df.to_csv(file_path, index=False)
        elif output_type.lower() == 'xlsx':
            df.to_excel(file_path, index=False)
        else:
            raise ValueError(f"Unknown type of output type: {output_type} provided.")

        self.volatilityStatus.setText(f"Generated report at {file_path}.")

        if open_from_msg_box(text='Do you want to open the volatility report?', title='Volatility Report'):
            open_file_or_folder(file_path)

    def stop_volatility_snooper(self):
        """
        Stop the snooping process.
        """
        if self.volatilityThread:
            self.volatilityStatus.setText("Stopping volatility snooper...")
            self.volatilityThread.stop()
            self.volatilityProgressBar.setValue(0)
            self.volatilityStatus.setText("Stopped volatility snooper.")
        else:
            self.volatilityStatus.setText("No volatility snooper running.")

    def modify_snooper_ui(self, running: bool):
        """
        Modify snooper UI's buttons based on running status.
        :param running: Boolean whether snooper is running or not.
        """
        self.volatilityGenerateButton.setEnabled(not running)
        self.stopVolatilityButton.setEnabled(running)

    def volatility_snooper(self):
        """
        Starts volatility snooper.
        """
        periods = self.volatilityPeriodsSpinBox.value()
        interval = self.volatilityDataInterval.currentText()
        volatility = self.volatilityComboBox.currentText()
        ticker_filter = self.volatilityFilter.text()
        progress_bar = self.volatilityProgressBar
        status = self.volatilityStatus
        output_type = self.volatilityFileType.currentText()

        self.volatilityThread = thread = VolatilitySnooperThread(periods=periods, interval=interval,
                                                                 volatility=volatility, tickers=self.parent.tickers,
                                                                 filter_word=ticker_filter)
        thread.signals.progress.connect(progress_bar.setValue)
        thread.signals.activity.connect(status.setText)
        thread.signals.error.connect(lambda x: status.setText(f'Error: {x}'))
        thread.signals.started.connect(lambda: self.modify_snooper_ui(running=True))
        thread.signals.restore.connect(lambda: self.modify_snooper_ui(running=False))
        thread.signals.finished.connect(lambda d: self.end_snoop_generate_volatility_report(d, output_type=output_type))
        self.threadPool.start(thread)
