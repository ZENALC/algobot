import time
import traceback

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot
from backtest import Backtester
from enums import BACKTEST


class BacktestSignals(QObject):
    finished = pyqtSignal(str)
    activity = pyqtSignal(int, tuple)
    started = pyqtSignal()
    error = pyqtSignal(int, str)


class BacktestThread(QRunnable):
    def __init__(self, gui):
        super(BacktestThread, self).__init__()
        self.gui = gui
        self.signals = BacktestSignals()

    def backtest(self):
        self.signals.started.emit()
        backtester = self.gui.backtester
        backtester.movingAverageTestStartTime = time.time()
        seenData = backtester.data[:backtester.minPeriod][::-1]  # Start from minimum previous period data.
        backtestPeriod = backtester.data[backtester.startDateIndex:backtester.endDateIndex]
        nets = []
        utcList = []
        previousIndex = 0
        for index, period in enumerate(backtestPeriod):
            seenData.insert(0, period)
            backtester.currentPeriod = period
            backtester.currentPrice = period['open']
            backtester.main_logic()
            backtester.check_trend(seenData)
            utc = period['date_utc'].timestamp()
            nets.append(backtester.get_net())
            utcList.append(utc)
            if index / len(backtestPeriod) >= 0.25:
                self.signals.activity.emit(25, (nets[previousIndex:index], utcList[previousIndex:index]))
                previousIndex = index
            elif index / len(backtestPeriod) >= 0.5:
                self.signals.activity.emit(50, (nets[previousIndex:index], utcList[previousIndex:index]))
                previousIndex = index
            elif index / len(backtestPeriod) >= 0.75:
                self.signals.activity.emit(75, (nets[previousIndex:index], utcList[previousIndex:index]))
                previousIndex = index

            # self.signals.activity.emit(backtester.get_net(), utc)

        if backtester.inShortPosition:
            backtester.exit_short('Exited short because of end of backtest.')
        elif backtester.inLongPosition:
            backtester.exit_long('Exiting long because of end of backtest.')

        backtester.movingAverageTestEndTime = time.time()

    def setup_bot(self):
        gui = self.gui
        startingBalance = gui.configuration.backtestStartingBalanceSpinBox.value()
        data = gui.configuration.data
        marginEnabled = gui.configuration.backtestMarginTradingCheckBox.isChecked()
        lossStrategy, lossPercentageDecimal = gui.get_loss_settings(BACKTEST)
        options = gui.get_trading_options(BACKTEST)
        gui.backtester = Backtester(startingBalance=startingBalance,
                                    data=data,
                                    lossStrategy=lossStrategy,
                                    lossPercentage=lossPercentageDecimal * 100,
                                    options=options,
                                    marginEnabled=marginEnabled)

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            self.setup_bot()
            self.backtest()
            path = self.gui.backtester.write_results()
            self.signals.finished.emit(path)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(BACKTEST, str(e))
