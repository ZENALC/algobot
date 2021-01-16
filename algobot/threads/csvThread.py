import traceback

from data import Data
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class CSVSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    restore = pyqtSignal()
    progress = pyqtSignal(int, str)
    locked = pyqtSignal()


class CSVGeneratingThread(QRunnable):
    def __init__(self, symbol, interval, descending, armyTime):
        super(CSVGeneratingThread, self).__init__()
        self.signals = CSVSignals()
        self.symbol = symbol
        self.interval = interval
        self.descending = descending
        self.armyTime = armyTime
        self.client: Data or None = None

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            self.client: Data = Data(interval=self.interval, symbol=self.symbol, updateData=False)
            data = self.client.custom_get_new_data(progress_callback=self.signals.progress, locked=self.signals.locked)
            if data:
                self.signals.progress.emit(100, "Creating CSV file...")
                savedPath = self.client.create_csv_file(descending=self.descending, armyTime=self.armyTime)
                self.signals.finished.emit(savedPath)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            self.signals.restore.emit()

    def stop(self):
        if self.client is not None:
            self.client.downloadLoop = False
