import traceback
import os

from data import Data
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class Worker(QRunnable):
    """
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """

        # Retrieve args/kwargs here; and fire processing using them
        try:
            self.fn(*self.args, **self.kwargs)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(str(e))


class CSVSignals(QObject):
    started = pyqtSignal()
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


class CSVGeneratingThread(QRunnable):
    def __init__(self, symbol, interval, descending):
        super(CSVGeneratingThread, self).__init__()
        self.signals = CSVSignals()
        self.symbol = symbol
        self.interval = interval
        self.descending = descending

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            savedPath = Data(interval=self.interval, symbol=self.symbol).get_csv_file(descending=self.descending)
            self.signals.finished.emit(savedPath)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.singals.error.emit(str(e))

