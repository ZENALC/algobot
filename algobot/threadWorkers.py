import traceback

import algobot
from data import Data
from enums import LIVE, SIMULATION
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
            savedPath = Data(interval=self.interval, symbol=self.symbol).create_csv_file(descending=self.descending)
            self.signals.finished.emit(savedPath)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(str(e))


class BotSignals(QObject):
    started = pyqtSignal(int)
    updated = pyqtSignal(int, dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)


class BotThread(QRunnable):
    def __init__(self, caller: int, gui: algobot.Interface):
        super(BotThread, self).__init__()
        self.signals = BotSignals()
        self.gui = gui
        self.caller = caller
        self.trader = None

    def setup_bot(self, caller):
        self.gui.create_trader(caller)
        self.gui.set_parameters(caller)
        self.trader = self.gui.trader if caller == LIVE else self.gui.simulationTrader

        if caller == LIVE:
            if self.gui.configuration.enableTelegramTrading.isChecked():
                self.gui.handle_telegram_bot()
            self.gui.runningLive = True
        elif caller == SIMULATION:
            self.gui.simulationRunningLive = True
        else:
            raise RuntimeError("Invalid type of caller specified.")

    def get_statistics(self):
        trader = self.trader
        net = trader.get_net()
        profit = trader.get_profit()
        stopLoss = trader.get_stop_loss()
        profitLabel = trader.get_profit_or_loss_string(profit=profit)
        percentage = trader.get_profit_percentage(trader.startingBalance, net)
        currentPriceString = f'${trader.dataView.get_current_price()}'
        percentageString = f'{round(percentage, 2)}%'
        profitString = f'${abs(round(profit, 2))}'
        netString = f'${round(net, 2)}'

        updateDict = {
            # Statistics window
            'net': net,
            'startingBalanceValue': f'${round(trader.startingBalance, 2)}',
            'currentBalanceValue': f'${round(trader.balance, 2)}',
            'netValue': netString,
            'profitLossLabel': profitLabel,
            'profitLossValue': profitString,
            'percentageValue': percentageString,
            'tradesMadeValue': str(len(trader.trades)),
            'coinOwnedLabel': f'{trader.coinName} Owned',
            'coinOwnedValue': f'{round(trader.coin, 6)}',
            'coinOwedLabel': f'{trader.coinName} Owed',
            'coinOwedValue': f'{round(trader.coinOwed, 6)}',
            'lossPointLabel': trader.get_stop_loss_strategy_string(),
            'lossPointValue': trader.get_safe_rounded_string(stopLoss),
            'customStopPointValue': trader.get_safe_rounded_string(trader.customStopLoss),
            'currentPositionValue': trader.get_position_string(),
            'autonomousValue': str(not trader.inHumanControl),
            'tickerLabel': trader.symbol,
            'tickerValue': currentPriceString
        }

        return updateDict

    def trading_loop(self, caller):
        lowerTrend = None
        runningLoop = self.gui.runningLive if caller == LIVE else self.gui.simulationRunningLive

        while runningLoop:
            self.gui.update_data(caller)
            self.gui.handle_logging(caller=caller)
            self.gui.handle_trailing_prices(caller=caller)
            self.gui.handle_trading(caller=caller)
            # crossNotification = self.handle_cross_notification(caller=caller, notification=crossNotification)
            lowerTrend = self.gui.handle_lower_interval_cross(caller, lowerTrend)
            statDict = self.get_statistics()
            self.signals.updated.emit(caller, statDict)
            runningLoop = self.gui.runningLive if caller == LIVE else self.gui.simulationRunningLive

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
            self.signals.error.emit(str(e))
