import time
import traceback

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot
from backtester import Backtester
from enums import BACKTEST


class BacktestSignals(QObject):
    finished = pyqtSignal()
    activity = pyqtSignal(dict)
    started = pyqtSignal(dict)
    error = pyqtSignal(int, str)
    restore = pyqtSignal()


class BacktestThread(QRunnable):
    def __init__(self, gui):
        super(BacktestThread, self).__init__()
        self.gui = gui
        self.signals = BacktestSignals()

    def get_configuration_details_to_setup_backtest(self) -> dict:
        """
        Returns configuration details from GUI in a dictionary to setup backtest.
        :return: GUI configuration details in a dictionary.
        """
        gui = self.gui
        config = gui.configuration
        startDate, endDate = config.get_calendar_dates()
        lossStrategy, lossPercentageDecimal = gui.get_loss_settings(BACKTEST)
        stoicOptions = [config.backtestStoicSpinBox1.value(), config.backtestStoicSpinBox2.value(),
                        config.backtestStoicSpinBox3.value()]
        shrekOptions = [config.backtestShrekSpinBox1.value(), config.backtestShrekSpinBox2.value(),
                        config.backtestShrekSpinBox3.value(), config.backtestShrekSpinBox4.value()]

        return {
            'startingBalance': config.backtestStartingBalanceSpinBox.value(),
            'data': config.data,
            'marginEnabled': config.backtestMarginTradingCheckBox.isChecked(),
            'options': gui.get_trading_options(BACKTEST),
            'startDate': startDate,
            'endDate': endDate,
            'lossStrategy': lossStrategy,
            'lossPercentage': lossPercentageDecimal * 100,
            'dataType': config.dataType,
            'stoicEnabled': config.backtestStoicCheckMark.isChecked(),
            'stoicOptions': stoicOptions,
            'smartStopLossCounter': config.backtestSmartStopLossSpinBox.value(),
            'shrekEnabled': config.backtestShrekCheckMark.isChecked(),
            'shrekOptions': shrekOptions,
            'precision': config.backtestPrecisionSpinBox.value(),
            'movingAverageEnabled': config.backtestMovingAverageCheckMark.isChecked(),
        }

    def get_configuration_dictionary_for_gui(self) -> dict:
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
            'stopLossStrategy': f'{"Trailing Loss" if backtester.lossStrategy == 2 else "Stop Loss"}',
            'startPeriod': f'{backtester.data[backtester.startDateIndex]["date_utc"].strftime("%m/%d/%Y, %H:%M:%S")}',
            'endPeriod': f'{backtester.data[backtester.endDateIndex]["date_utc"].strftime("%m/%d/%Y, %H:%M:%S")}',
        }

        if backtester.movingAverageEnabled:
            d['options'] = [opt.get_pretty_option() for opt in backtester.strategies['movingAverage'].get_params()]

        return d

    def get_activity_dictionary(self, period: dict, index: int, length: int) -> dict:
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

        return {
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

    def setup_bot(self):
        """
        Sets up initial backtester and then emits parameters to GUI.
        """
        configDetails = self.get_configuration_details_to_setup_backtest()
        stoicOptions = configDetails['stoicOptions'] if configDetails['stoicEnabled'] else None
        shrekOptions = configDetails['shrekOptions'] if configDetails['shrekEnabled'] else None
        options = configDetails['options'] if configDetails['movingAverageEnabled'] else None
        self.gui.backtester = Backtester(startingBalance=configDetails['startingBalance'],
                                         data=configDetails['data'],
                                         symbol=configDetails['dataType'],
                                         lossStrategy=configDetails['lossStrategy'],
                                         lossPercentage=configDetails['lossPercentage'],
                                         marginEnabled=configDetails['marginEnabled'],
                                         startDate=configDetails['startDate'],
                                         endDate=configDetails['endDate'],
                                         precision=configDetails['precision'],
                                         options=options,
                                         stoicOptions=stoicOptions,
                                         shrekOptions=shrekOptions)
        self.gui.backtester.set_stop_loss_counter(configDetails['smartStopLossCounter'])
        self.signals.started.emit(self.get_configuration_dictionary_for_gui())

    def backtest(self):
        """
        Performs a moving average test with given configurations.
        """
        limit = 1000  # Data limit.
        backtester = self.gui.backtester
        backtester.movingAverageTestStartTime = time.time()
        seenData = backtester.data[:backtester.minPeriod][::-1]  # Start from minimum previous period data.
        backtestPeriod = backtester.data[backtester.startDateIndex: backtester.endDateIndex]
        testLength = len(backtestPeriod)
        divisor = testLength // 100
        if testLength % 100 != 0:
            divisor += 1

        for index, period in enumerate(backtestPeriod):
            if len(seenData) >= limit:
                seenData = seenData[:limit // 2]

            seenData.insert(0, period)
            backtester.currentPeriod = period
            backtester.currentPrice = period['open']
            backtester.main_logic()

            if backtester.movingAverageEnabled:
                backtester.strategies['movingAverage'].get_trend(seenData)
            if backtester.stoicEnabled:
                backtester.strategies['stoic'].get_trend(seenData)
            if backtester.shrekEnabled:
                backtester.strategies['shrek'].get_trend(seenData)

            if index % divisor == 0:
                self.signals.activity.emit(self.get_activity_dictionary(period=period, index=index, length=testLength))

        if backtester.inShortPosition:
            backtester.exit_short('Exited short because of end of backtest.')
        elif backtester.inLongPosition:
            backtester.exit_long('Exiting long because of end of backtest.')

        self.signals.activity.emit(self.get_activity_dictionary(period=backtestPeriod[-1],  # Final backtest data.
                                                                index=testLength,
                                                                length=testLength))
        backtester.movingAverageTestEndTime = time.time()

    @pyqtSlot()
    def run(self):
        """
        Runs the backtest thread. It first sets up the bot, then it backtests. During the backtest, it also emits
        several signals for GUI to update itself.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            self.setup_bot()
            self.backtest()
            self.signals.finished.emit()
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(BACKTEST, str(e))
        finally:
            self.signals.restore.emit()
