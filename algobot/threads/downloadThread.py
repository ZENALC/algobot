import traceback

from data import Data
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class DownloadSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    restore = pyqtSignal()
    progress = pyqtSignal(int, str)
    locked = pyqtSignal()


class DownloadThread(QRunnable):
    def __init__(self, interval, symbol):
        super(DownloadThread, self).__init__()
        self.interval = interval
        self.symbol = symbol
        self.signals = DownloadSignals()
        self.client: Data or None = None

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            self.client = Data(interval=self.interval, symbol=self.symbol, updateData=False)
            data = self.client.custom_get_new_data(progress_callback=self.signals.progress, locked=self.signals.locked)
            if data:
                self.signals.finished.emit(data)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            self.signals.restore.emit()

    def stop(self):
        if self.client is not None:
            self.client.downloadLoop = False
