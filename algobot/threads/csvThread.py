import traceback

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
from data import Data


class CSVSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    restore = pyqtSignal()


class CSVGeneratingThread(QRunnable):
    def __init__(self, symbol, interval, descending, armyTime):
        super(CSVGeneratingThread, self).__init__()
        self.signals = CSVSignals()
        self.symbol = symbol
        self.interval = interval
        self.descending = descending
        self.armyTime = armyTime

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            client = Data(interval=self.interval, symbol=self.symbol, updateData=False)
            data = client.custom_get_new_data(progress_callback=self.signals.progress)
            if data:
                self.signals.progress.emit(100, "Creating CSV file...")
                savedPath = client.create_csv_file(descending=self.descending, armyTime=self.armyTime)
                self.signals.finished.emit(savedPath)
            else:
                pass
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            self.signals.restore.emit()
