import traceback
import algobot

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot


class BacktestSignals(QObject):
    finished = pyqtSignal()
    updated = pyqtSignal()
    error = pyqtSignal(str)


class BacktestThread(QRunnable):
    def __init__(self, gui: algobot.Interface):
        super(BacktestThread, self).__init__()
        self.gui = gui
        self.signals = BacktestSignals()

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            caller = self.caller
            self.setup_bot(caller=caller)
            self.signals.started.emit(caller)
            self.trading_loop(caller)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(self.caller, str(e))
