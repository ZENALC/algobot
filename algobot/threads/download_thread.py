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
    started = pyqtSignal()
    csv_finished = pyqtSignal(str)
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str, str)
    restore = pyqtSignal(str)
    progress = pyqtSignal(int, str, str)
    locked = pyqtSignal()


class DownloadThread(QRunnable):
    """
    Thread to use for downloads.
    """
    def __init__(self, interval, symbol, descending=None, army_time=None, start_date=None, caller=None, logger=None):
        super(DownloadThread, self).__init__()
        self.caller = caller
        self.signals = DownloadSignals()
        self.symbol = symbol
        self.interval = interval
        self.descending = descending
        self.army_time = army_time
        self.start_date = start_date
        self.logger = logger
        self.client: Data or None = None

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        self.signals.started.emit()
        try:
            self.client = Data(interval=self.interval, symbol=self.symbol, update=False)
            data = self.client.custom_get_new_data(progress_callback=self.signals.progress, locked=self.signals.locked,
                                                   caller=self.caller)
            if data:
                if self.descending is None and self.army_time is None:
                    self.signals.finished.emit(data, self.caller)
                else:  # This means the CSV generator called this thread.
                    self.signals.progress.emit(100, "Creating CSV file...", '')
                    saved_path = self.client.create_csv_file(descending=self.descending, army_time=self.army_time,
                                                             start_date=self.start_date)
                    self.signals.csv_finished.emit(saved_path)
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
            self.client.download_loop = False
