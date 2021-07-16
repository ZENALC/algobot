"""
Download thread used for downloads.
"""

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

import algobot
from algobot.data import Data


class DownloadSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    # pylint: disable=too-few-public-methods
    started = pyqtSignal()
    csv_finished = pyqtSignal(str)
    finished = pyqtSignal(list, int)
    error = pyqtSignal(str, int)
    restore = pyqtSignal(int)
    progress = pyqtSignal(int, str, int)
    locked = pyqtSignal()


class DownloadThread(QRunnable):
    """
    Thread to use for downloads.
    """
    def __init__(self, interval, symbol, descending=None, armyTime=None, startDate=None, caller=None, logger=None):
        super(DownloadThread, self).__init__()
        self.caller = caller
        self.signals = DownloadSignals()
        self.symbol = symbol
        self.interval = interval
        self.descending = descending
        self.armyTime = armyTime
        self.startDate = startDate
        self.logger = logger
        self.client: Data or None = None

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        self.signals.started.emit()
        try:
            self.client = Data(interval=self.interval, symbol=self.symbol, updateData=False)
            data = self.client.custom_get_new_data(progress_callback=self.signals.progress, locked=self.signals.locked,
                                                   caller=self.caller)
            if data:
                if self.descending is None and self.armyTime is None:
                    self.signals.finished.emit(data, self.caller)
                else:  # This means the CSV generator called this thread.
                    self.signals.progress.emit(100, "Creating CSV file...", -1)
                    savedPath = self.client.create_csv_file(descending=self.descending, armyTime=self.armyTime,
                                                            startDate=self.startDate)
                    self.signals.csv_finished.emit(savedPath)
        except Exception as e:
            algobot.MAIN_LOGGER.exception(repr(e))
            self.signals.error.emit(str(e), self.caller)
        finally:
            self.signals.restore.emit(self.caller)

    def stop(self):
        """
        Stop the download loop if it's running.
        """
        if self.client is not None:
            self.client.downloadLoop = False
