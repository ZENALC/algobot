"""
Backtester thread for Algobot GUI.
"""

from datetime import datetime
from typing import Any, Dict

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from algobot.enums import BACKTEST
from algobot.threads.thread_utils import get_config_helper
from algobot.traders.backtester import Backtester


class BacktestSignals(QObject):
    """
    Possible signals to emit in backtest thread.
    """
    finished = pyqtSignal()
    message = pyqtSignal(str)
    activity = pyqtSignal(dict)
    started = pyqtSignal(dict)
    error = pyqtSignal(str, str)
    restore = pyqtSignal()
    updateGraphLimits = pyqtSignal(int)


class BacktestThread(QRunnable):
    """
    Backtest thread used during backtests in the GUI.
    """
    def __init__(self, gui, logger):
        super(BacktestThread, self).__init__()
        self.signals = BacktestSignals()
        self.gui = gui
        self.logger = logger
        self.running = True
        self.caller = BACKTEST

    def get_configuration_details_to_setup_backtest(self) -> Dict[str, Any]:
        """
        Returns configuration details from GUI in a dictionary to setup backtest.
        :return: GUI configuration details in a dictionary.
        """
        return get_config_helper(self.gui, BACKTEST)

    def get_configuration_dictionary_for_gui(self) -> Dict[str, str]:
        """
        Returns backtest configuration details to update GUI.
        :return: Dictionary containing backtest configuration details.
        """
        backtester = self.gui.backtester
        if backtester.loss_strategy is not None:
            stop_loss_percentage_string = f'{backtester.loss_percentage_decimal * 100}%'
        else:
            stop_loss_percentage_string = 'Configuration Required'

        temp_dict = {
            'starting_balance': f'${backtester.starting_balance}',
            'interval': backtester.interval,
            'margin_enabled': f'{backtester.margin_enabled}',
            'stop_loss_percentage': stop_loss_percentage_string,
            'stop_loss_strategy': backtester.get_stop_loss_strategy_string(),
            'start_period':
                f'{backtester.data[backtester.start_date_index]["date_utc"].strftime("%m/%d/%Y, %H:%M:%S")}',
            'end_period': f'{backtester.data[backtester.end_date_index]["date_utc"].strftime("%m/%d/%Y, %H:%M:%S")}',
            'symbol': f'{backtester.symbol}'
        }

        if 'movingAverage' in backtester.strategies:
            temp_dict['options'] = [
                opt.get_pretty_option() for opt in backtester.strategies['movingAverage'].get_params()]
        else:
            temp_dict['options'] = [('Configuration Required', 'Configuration Required') for _ in range(2)]

        return temp_dict

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
        profit = net - backtester.starting_balance
        if profit < 0:
            profit_percentage = round(100 - net / backtester.starting_balance * 100, 2)
        else:
            profit_percentage = round(net / backtester.starting_balance * 100 - 100, 2)

        activity = {
            'price': backtester.get_safe_rounded_string(backtester.current_price),
            'net': round(net, backtester.precision),
            'netString': f'${round(net, backtester.precision)}',
            'balance': f'${round(backtester.balance, backtester.precision)}',
            'commissionsPaid': f'${round(backtester.commissions_paid, backtester.precision)}',
            'tradesMade': str(len(backtester.trades)),
            'profit': f'${abs(round(profit, backtester.precision))}',
            'profitPercentage': f'{profit_percentage}%',
            'currentPeriod': period['date_utc'].strftime("%m/%d/%Y, %H:%M:%S"),
            'utc': period['date_utc'].timestamp(),
            'percentage': int((index - backtester.start_date_index) / length * 100)
        }

        backtester.past_activity.append(activity)
        return activity

    def setup_bot(self):
        """
        Sets up initial backtester and then emits parameters to GUI.
        """
        self.gui.backtester = Backtester(**self.get_configuration_details_to_setup_backtest())
        self.gui.backtester.apply_take_profit_settings(self.gui.configuration.get_take_profit_settings(BACKTEST))
        self.gui.backtester.apply_loss_settings(self.gui.configuration.get_loss_settings(BACKTEST))
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
        self.signals.updateGraphLimits.emit(len(backtester.past_activity))
        self.signals.activity.emit(self.get_activity_dictionary(period=backtester.data[backtester.end_date_index],
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
