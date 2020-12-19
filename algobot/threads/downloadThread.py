import traceback

from data import Data
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class DownloadSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = pyqtSignal(list)
    error = pyqtSignal(str)


class DownloadThread(QRunnable):
    def __init__(self, interval, symbol):
        super(DownloadThread, self).__init__()
        self.interval = interval
        self.symbol = symbol
        self.signals = DownloadSignals()

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            data = Data(interval=self.interval, symbol=self.symbol).data
            self.signals.finished.emit(data)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(str(e))
