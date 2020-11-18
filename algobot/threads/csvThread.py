import traceback

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
from data import Data


class CSVSignals(QObject):
    started = pyqtSignal()
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


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
            savedPath = Data(interval=self.interval, symbol=self.symbol, log=False).create_csv_file(
                descending=self.descending, armyTime=self.armyTime)
            self.signals.finished.emit(savedPath)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(str(e))
