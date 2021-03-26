from datetime import datetime
from typing import Any, Dict

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from algobot.enums import BACKTEST, TRAILING
from algobot.traders.backtester import Backtester


class BacktestSignals(QObject):
    """
    Possible signals to emit in backtest thread.
    """
    finished = pyqtSignal()
    message = pyqtSignal(str)
    activity = pyqtSignal(dict)
    started = pyqtSignal(dict)
    error = pyqtSignal(int, str)
    restore = pyqtSignal()
    updateGraphLimits = pyqtSignal(int)


class BacktestThread(QRunnable):
    def __init__(self, gui, logger):
        super(BacktestThread, self).__init__()
        self.signals = BacktestSignals()
        self.gui = gui
        self.logger = logger
        self.running = True

    def get_configuration_details_to_setup_backtest(self) -> Dict[str, Any]:
        """
        Returns configuration details from GUI in a dictionary to setup backtest.
        :return: GUI configuration details in a dictionary.
        """
        config = self.gui.configuration
        startDate, endDate = config.get_calendar_dates()

        return {
            'startingBalance': config.backtestStartingBalanceSpinBox.value(),
            'data': config.data,
            'startDate': startDate,
            'endDate': endDate,
            'dataType': config.dataType,
            'precision': config.backtestPrecisionSpinBox.value(),
            'outputTrades': config.backtestOutputTradesCheckBox.isChecked(),
            'marginEnabled': config.backtestMarginTradingCheckBox.isChecked(),
            'strategies': config.get_strategies(BACKTEST),
            'strategyInterval': config.backtestStrategyIntervalCombobox.currentText()
        }

    def get_configuration_dictionary_for_gui(self) -> Dict[str, str]:
        """
        Returns backtest configuration details to update GUI.
        :return: Dictionary containing backtest configuration details.
        """
        backtester = self.gui.backtester
        d = {
            'startingBalance': f'${backtester.startingBalance}',
            'interval': backtester.interval,
            'marginEnabled': f'{backtester.marginEnabled}',
            'stopLossPercentage': f'{backtester.lossPercentageDecimal * 100}%',
            'stopLossStrategy': f'{"Trailing Loss" if backtester.lossStrategy == TRAILING else "Stop Loss"}',
            'startPeriod': f'{backtester.data[backtester.startDateIndex]["date_utc"].strftime("%m/%d/%Y, %H:%M:%S")}',
            'endPeriod': f'{backtester.data[backtester.endDateIndex]["date_utc"].strftime("%m/%d/%Y, %H:%M:%S")}',
            'symbol': f'{backtester.symbol}'
        }

        if 'movingAverage' in backtester.strategies:
            d['options'] = [opt.get_pretty_option() for opt in backtester.strategies['movingAverage'].get_params()]

        return d

    def get_activity_dictionary(self, period: Dict[str, datetime], index: int, length: int) -> dict:
        """
        Returns activity dictionary based on current backtest period values.
        :param period: Current period used to update graphs and GUI with.
        :param index: Current index from period data. Used to calculate percentage of backtest conducted.
        :param length: Current length of backtest periods. Used with index to calculate percentage of backtest done.
        :return: Dictionary containing period activity.
        """
        backtester = self.gui.backtester
        net = backtester.get_net()
        profit = net - backtester.startingBalance
        if profit < 0:
            profitPercentage = round(100 - net / backtester.startingBalance * 100, 2)
        else:
            profitPercentage = round(net / backtester.startingBalance * 100 - 100, 2)

        activity = {
            'net': round(net, backtester.precision),
            'netString': f'${round(net, backtester.precision)}',
            'balance': f'${round(backtester.balance, backtester.precision)}',
            'commissionsPaid': f'${round(backtester.commissionsPaid, backtester.precision)}',
            'tradesMade': str(len(backtester.trades)),
            'profit': f'${abs(round(profit, backtester.precision))}',
            'profitPercentage': f'{profitPercentage}%',
            'currentPeriod': period['date_utc'].strftime("%m/%d/%Y, %H:%M:%S"),
            'utc': period['date_utc'].timestamp(),
            'percentage': int(index / length * 100)
        }

        backtester.pastActivity.append(activity)
        return activity

    def setup_bot(self):
        """
        Sets up initial backtester and then emits parameters to GUI.
        """
        configDetails = self.get_configuration_details_to_setup_backtest()
        self.gui.backtester = Backtester(startingBalance=configDetails['startingBalance'],
                                         data=configDetails['data'],
                                         symbol=configDetails['dataType'],
                                         marginEnabled=configDetails['marginEnabled'],
                                         startDate=configDetails['startDate'],
                                         endDate=configDetails['endDate'],
                                         precision=configDetails['precision'],
                                         outputTrades=configDetails['outputTrades'],
                                         strategies=configDetails['strategies'],
                                         strategyInterval=configDetails['strategyInterval'])
        self.gui.backtester.apply_take_profit_settings(self.gui.configuration.get_take_profit_settings(BACKTEST))
        self.gui.backtester.apply_loss_settings(self.gui.get_loss_settings(BACKTEST))
        self.signals.started.emit(self.get_configuration_dictionary_for_gui())

    def stop(self):
        """
        Stops the backtest by setting the running flag to False.
        """
        self.running = False

    def run_backtest(self):
        """
        Performs a backtest with given configurations.
        """
        backtester = self.gui.backtester
        backtester.start_backtest(thread=self)
        self.signals.activity.emit(self.get_activity_dictionary(period=backtester.data[backtester.endDateIndex],
                                                                index=1,
                                                                length=1))

    @pyqtSlot()
    def run(self):
        """
        Runs the backtest thread. It first sets up the bot, then it backtests. During the backtest, it also emits
        several signals for GUI to update itself.
        """
        try:
            self.setup_bot()
            self.run_backtest()
            self.signals.finished.emit()
        except Exception as e:
            self.logger.exception(repr(e))
            self.signals.error.emit(BACKTEST, str(e))
        finally:
            self.signals.restore.emit()
