import time

from datetime import timedelta
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
    def __init__(self, gui, logger):
        super(BacktestThread, self).__init__()
        self.gui = gui
        self.logger = logger
        self.running = True
        self.signals = BacktestSignals()

    def get_configuration_details_to_setup_backtest(self) -> dict:
        """
        Returns configuration details from GUI in a dictionary to setup backtest.
        :return: GUI configuration details in a dictionary.
        """
        gui = self.gui
        config = gui.configuration
        startDate, endDate = config.get_calendar_dates()
        lossDict = gui.get_loss_settings(BACKTEST)
        takeProfitDict = gui.configuration.get_take_profit_settings(BACKTEST)
        strategies = config.get_strategies(BACKTEST)

        return {
            'startingBalance': config.backtestStartingBalanceSpinBox.value(),
            'data': config.data,
            'startDate': startDate,
            'endDate': endDate,
            'takeProfitType': takeProfitDict['takeProfitType'],
            'takeProfitPercentage': takeProfitDict['takeProfitPercentage'],
            'lossStrategy': lossDict["lossType"],
            'lossPercentage': lossDict["lossPercentage"],
            'smartStopLossCounter': lossDict["smartStopLossCounter"],
            'dataType': config.dataType,
            'precision': config.backtestPrecisionSpinBox.value(),
            'outputTrades': config.backtestOutputTradesCheckBox.isChecked(),
            'marginEnabled': config.backtestMarginTradingCheckBox.isChecked(),
            'strategies': strategies,
            'strategyInterval': config.backtestStrategyIntervalCombobox.currentText()
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
            'symbol': f'{backtester.symbol}'
        }

        if 'movingAverage' in backtester.strategies:
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
        self.gui.backtester = Backtester(startingBalance=configDetails['startingBalance'],
                                         data=configDetails['data'],
                                         symbol=configDetails['dataType'],
                                         lossStrategy=configDetails['lossStrategy'],
                                         lossPercentage=configDetails['lossPercentage'],
                                         marginEnabled=configDetails['marginEnabled'],
                                         startDate=configDetails['startDate'],
                                         endDate=configDetails['endDate'],
                                         precision=configDetails['precision'],
                                         outputTrades=configDetails['outputTrades'],
                                         strategies=configDetails['strategies'],
                                         takeProfitType=configDetails['takeProfitType'],
                                         takeProfitPercentage=configDetails['takeProfitPercentage'],
                                         strategyInterval=configDetails['strategyInterval'])
        self.gui.backtester.set_stop_loss_counter(configDetails['smartStopLossCounter'])
        self.signals.started.emit(self.get_configuration_dictionary_for_gui())

    def stop(self):
        """
        Stops the backtest by setting the running flag to False.
        """
        self.running = False

    def backtest(self):
        """
        Performs a backtest with given configurations.
        """
        limit = 1000  # Data limit.
        backtester = self.gui.backtester
        backtester.startTime = time.time()
        seenData = backtester.data[:backtester.minPeriod][::-1]  # Start from minimum previous period data.
        strategyData = seenData if backtester.strategyIntervalMinutes == backtester.intervalMinutes else []
        nextInsertion = None
        backtestPeriod = backtester.data[backtester.startDateIndex: backtester.endDateIndex]
        testLength = len(backtestPeriod)
        divisor = testLength // 100
        if testLength % 100 != 0:
            divisor += 1

        for index, period in enumerate(backtestPeriod):
            if not self.running:
                raise RuntimeError("Backtest was canceled.")

            if len(seenData) >= limit:
                seenData = seenData[:limit // 2]
            if len(strategyData) >= limit:
                strategyData = strategyData[:limit // 2]

            seenData.insert(0, period)
            backtester.currentPeriod = period
            backtester.currentPrice = period['open']
            periodDate = period['date_utc']

            if len(seenData) > backtester.intervalGapMinutes and (nextInsertion is None or periodDate >= nextInsertion):
                nextInsertion = seenData[0]['date_utc'] + timedelta(minutes=backtester.strategyIntervalMinutes)
                gapData = backtester.get_gap_data(seenData, backtester.intervalGapMinutes)
                strategyData.insert(0, gapData)

            if len(backtester.strategies) > 0:
                backtester.main_logic()
            else:
                if not backtester.inLongPosition:
                    backtester.buy_long('Entered long because no strategies were found.')

            if backtester.get_net() <= 0:
                raise RuntimeError("Backtester ran out of money. Try changing your strategy or date interval.")

            if len(strategyData) >= backtester.minPeriod:
                tempData = [period] + strategyData
                for strategy in backtester.strategies.values():
                    strategy.get_trend(tempData)

            if index % divisor == 0:
                self.signals.activity.emit(self.get_activity_dictionary(period=period, index=index, length=testLength))

        if backtester.inShortPosition:
            backtester.buy_short('Exited short because of end of backtest.')
        elif backtester.inLongPosition:
            backtester.sell_long('Exiting long because of end of backtest.')

        self.signals.activity.emit(self.get_activity_dictionary(period=backtestPeriod[-1],  # Final backtest data.
                                                                index=testLength,
                                                                length=testLength))
        backtester.endTime = time.time()

    @pyqtSlot()
    def run(self):
        """
        Runs the backtest thread. It first sets up the bot, then it backtests. During the backtest, it also emits
        several signals for GUI to update itself.
        """
        try:
            self.setup_bot()
            self.backtest()
            self.signals.finished.emit()
        except Exception as e:
            self.logger.exception(repr(e))
            self.signals.error.emit(BACKTEST, repr(e))
        finally:
            self.signals.restore.emit()
