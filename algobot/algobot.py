import assets
import sys
import helpers
import os

from data import Data
from datetime import datetime
from threadWorkers import Worker
from interface.palettes import *
from telegramBot import TelegramBot
from telegram.error import InvalidToken
from realtrader import RealTrader
from simulationtrader import SimulationTrader
from option import Option
from enums import *
from interface.configuration import Configuration
from interface.otherCommands import OtherCommands
from interface.about import About
from interface.statistics import Statistics

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import QThreadPool
from PyQt5.QtGui import QIcon
from pyqtgraph import DateAxisItem, mkPen, PlotWidget

app = QApplication(sys.argv)

mainUi = os.path.join('../', 'UI', 'algobot.ui')


class Interface(QMainWindow):
    def __init__(self, parent=None):
        assets.qInitResources()
        super(Interface, self).__init__(parent)  # Initializing object
        uic.loadUi(mainUi, self)  # Loading the main UI
        self.configuration = Configuration()  # Loading configuration
        self.otherCommands = OtherCommands()  # Loading other commands
        self.about = About()  # Loading about information
        self.statistics = Statistics()  # Loading statistics
        self.threadPool = QThreadPool()  # Initiating threading pool
        self.graphs = (
            {'graph': self.simulationGraph, 'plots': []},
            {'graph': self.backtestGraph, 'plots': []},
            {'graph': self.realGraph, 'plots': []},
            {'graph': self.avgGraph, 'plots': []},
            {'graph': self.simulationAvgGraph, 'plots': []},
        )
        self.setup_graphs()  # Setting up graphs
        self.initiate_slots()  # Initiating slots
        self.threadPool.start(Worker(self.load_tickers))  # Load tickers

        self.advancedLogging = True
        self.runningLive = False
        self.simulationRunningLive = False
        self.backtestRunningLive = False
        self.trader: RealTrader or None = None
        self.simulationTrader: SimulationTrader or None = None
        self.traderType = None
        self.simulationLowerIntervalData: Data or None = None
        self.lowerIntervalData: Data or None = None
        self.telegramBot = None
        self.add_to_activity_monitor('Initialized interface.')

    # TO FIX
    def initiate_bot_thread(self, caller):
        worker = Worker(lambda: self.run_bot(caller))
        worker.signals.error.connect(self.end_bot_and_create_popup)
        # worker.signals.result.connect(lambda: print("lol"))
        self.threadPool.start(worker)

    # TO FIX
    def end_bot_and_create_popup(self, msg):
        # self.disable_interface(False)
        self.endBotButton.setEnabled(False)
        self.endSimulationButton.setEnabled(False)
        # self.timestamp_message('Ended bot because of an error.')
        self.create_popup(msg)

    def update_data(self, caller):
        """
        Updates data if updated data exists for caller object.
        :param caller: Object type that will be updated.
        """
        if caller == LIVE and not self.trader.dataView.data_is_updated():
            self.add_to_activity_monitor('New data found. Updating...')
            self.trader.dataView.update_data()
        elif caller == SIMULATION and not self.simulationTrader.dataView.data_is_updated():
            self.add_to_simulation_activity_monitor('New data found. Updating...')
            self.simulationTrader.dataView.update_data()

    def handle_logging(self, caller):
        """
        Handles logging type for caller object.
        :param caller: Object those logging will be performed.
        """
        if caller == LIVE:
            if self.advancedLogging:
                self.trader.output_basic_information()
        elif caller == SIMULATION:
            if self.advancedLogging:
                self.simulationTrader.output_basic_information()

    def handle_position_buttons(self, caller):
        """
        Handles interface position buttons based on caller.
        :param caller: Caller object for whose interface buttons will be affected.
        """
        if caller == LIVE:
            if self.trader.get_position() is None:
                self.exitPositionButton.setEnabled(False)
                self.waitOverrideButton.setEnabled(False)
            else:
                self.exitPositionButton.setEnabled(True)
                self.waitOverrideButton.setEnabled(True)

            if self.trader.get_position() == LONG:
                self.forceLongButton.setEnabled(False)
                self.forceShortButton.setEnabled(True)

            if self.trader.get_position() == SHORT:
                self.forceLongButton.setEnabled(True)
                self.forceShortButton.setEnabled(False)

        elif caller == SIMULATION:
            if self.simulationTrader.get_position() is None:
                self.exitPositionSimulationButton.setEnabled(False)
                self.waitOverrideSimulationButton.setEnabled(False)
            else:
                self.exitPositionSimulationButton.setEnabled(True)
                self.waitOverrideSimulationButton.setEnabled(True)

            if self.simulationTrader.get_position() == LONG:
                self.forceLongSimulationButton.setEnabled(False)
                self.forceShortSimulationButton.setEnabled(True)

            if self.simulationTrader.get_position() == SHORT:
                self.forceLongSimulationButton.setEnabled(True)
                self.forceShortSimulationButton.setEnabled(False)

    def handle_trailing_prices(self, caller):
        """
        Handles trailing prices for caller object.
        :param caller: Trailing prices for what caller to be handled for.
        """
        if caller == SIMULATION:
            trader = self.simulationTrader
        elif caller == LIVE:
            trader = self.trader
        else:
            raise ValueError("Invalid caller type specified.")

        trader.currentPrice = trader.dataView.get_current_price()
        if trader.longTrailingPrice is not None and trader.currentPrice > trader.longTrailingPrice:
            trader.longTrailingPrice = trader.currentPrice
        if trader.shortTrailingPrice is not None and trader.currentPrice < trader.shortTrailingPrice:
            trader.shortTrailingPrice = trader.currentPrice

    def handle_trading(self, caller):
        """
        Handles trading by checking if automation mode is on or manual.
        :param caller: Object for which function will handle trading.
        """
        if caller == SIMULATION:
            trader = self.simulationTrader
        elif caller == LIVE:
            trader = self.trader
        else:
            raise ValueError('Invalid caller type specified.')

        if not trader.inHumanControl:
            trader.main_logic()

    def handle_cross_notification(self, caller, notification):
        """
        Handles cross notifications.
        :param caller: Caller object for whom function will handle cross notifications/
        :param notification: Notification boolean whether it is time to notify or not.
        :return: Boolean whether cross should be notified on next function call.
        """
        if caller == SIMULATION:
            if self.simulationTrader.currentPosition is not None:
                return True
            else:
                if not notification and not self.simulationTrader.inHumanControl:
                    self.add_to_simulation_activity_monitor("Waiting for a cross.")
                    return False
        elif caller == LIVE:
            if self.trader.currentPosition is not None:
                return True
            else:
                if not notification and not self.trader.inHumanControl:
                    self.add_to_activity_monitor("Waiting for a cross.")
                    return False
        else:
            raise ValueError("Invalid type of caller or cross notification specified.")

    def handle_lower_interval_cross(self, caller, previousLowerTrend) -> bool:
        """
        Handles logic and notifications for lower interval cross data.
        :param previousLowerTrend: Previous lower trend. Used to check if notification is necessary.
        :param caller: Caller for which we will check lower interval cross data.
        """
        if caller == SIMULATION:
            trader = self.simulationTrader
            lowerData = self.simulationLowerIntervalData
        elif caller == LIVE:
            trader = self.trader
            lowerData = self.lowerIntervalData
        else:
            raise ValueError("Invalid caller specified.")

        lowerTrend = trader.get_trend(dataObject=lowerData)
        trend = trader.trend
        if previousLowerTrend == lowerTrend or lowerTrend == trend:
            return lowerTrend
        else:
            trends = {BEARISH: 'Bearish', BULLISH: 'Bullish', None: 'No'}
            if caller == LIVE:
                self.add_to_activity_monitor(f'{trends[lowerTrend]} trend detected on lower interval data.')
            elif caller == SIMULATION:
                self.add_to_simulation_activity_monitor(f'{trends[lowerTrend]} trend detected on lower interval data.')
            return lowerTrend

    def handle_telegram_bot(self):
        """
        Attempts to initiate Telegram bot.
        """
        try:
            if self.telegramBot is None:
                apiKey = self.configuration.telegramApiKey.text()
                self.telegramBot = TelegramBot(gui=self, apiKey=apiKey)
            self.telegramBot.start()
            self.add_to_activity_monitor('Started Telegram bot.')
        except InvalidToken:
            self.add_to_activity_monitor('Invalid token for Telegram. Please recheck credentials in settings.')

    def automate_trading(self, caller):
        """
        Main function to automate trading.
        :param caller: Caller object to automate trading for.
        """
        crossNotification = False
        lowerTrend = None
        while self.simulationRunningLive:
            try:
                self.update_data(caller=caller)
                self.update_simulation_info()
                self.update_trades_table_and_activity_monitor(caller=caller)
                self.handle_logging(caller=caller)
                self.handle_position_buttons(caller=caller)
                self.handle_trailing_prices(caller=caller)
                self.handle_trading(caller=caller)
                crossNotification = self.handle_cross_notification(caller=caller, notification=crossNotification)
                lowerTrend = self.handle_lower_interval_cross(caller, lowerTrend)

            except Exception as e:
                raise e

    def run_bot(self, caller):
        """
        Runs bot with caller specified.
        :param caller: Type of bot to run - Simulation or LIVE.
        """
        self.create_trader(caller)
        self.disable_interface(True, caller)
        self.set_parameters(caller)
        self.enable_override(caller)

        if caller == LIVE:
            if self.configuration.enableTelegramTrading.isChecked():
                self.handle_telegram_bot()
            self.clear_table(self.historyTable)
            self.runningLive = True
            self.setup_graph_plots(self.realGraph, self.trader, NET_GRAPH)
            self.setup_graph_plots(self.avgGraph, self.trader, AVG_GRAPH)
            self.automate_trading(caller)
        elif caller == SIMULATION:
            self.clear_table(self.simulationHistoryTable)
            self.simulationRunningLive = True
            self.setup_graph_plots(self.simulationGraph, self.simulationTrader, NET_GRAPH)
            self.setup_graph_plots(self.simulationAvgGraph, self.simulationTrader, AVG_GRAPH)
            self.automate_trading(caller)

    def end_bot(self, caller):
        if caller == SIMULATION:
            self.simulationRunningLive = False
            self.simulationTrader.get_simulation_result()
            self.endSimulationButton.setEnabled(False)
            self.add_to_simulation_activity_monitor("Ended Simulation")
            self.runSimulationButton.setEnabled(True)
            tempTrader = self.simulationTrader
        else:
            self.runningLive = False
            self.endBotButton.setEnabled(False)
            self.telegramBot.stop()
            self.add_to_activity_monitor('Killed Telegram bot.')
            self.add_to_activity_monitor("Killed bot.")
            self.runBotButton.setEnabled(True)
            tempTrader = self.trader
        tempTrader.log_trades()
        self.disable_override(caller)
        self.update_trades_table_and_activity_monitor(caller)
        self.disable_interface(False, caller=caller)
        tempTrader.dataView.dump_to_table()
        # if self.lowerIntervalData is not None:
        #     self.lowerIntervalData.dump_to_table()
        #     self.lowerIntervalData = None
        self.destroy_trader(caller)

    def destroy_trader(self, caller):
        if caller == SIMULATION:
            self.simulationTrader = None
        elif caller == LIVE:
            self.trader = None
        elif caller == BACKTEST:
            pass
        else:
            raise ValueError("invalid caller type specified.")

    def create_trader(self, caller):
        if caller == SIMULATION:
            symbol = self.configuration.simulationTickerComboBox.currentText()
            interval = helpers.convert_interval(self.configuration.simulationIntervalComboBox.currentText())
            startingBalance = self.configuration.simulationStartingBalanceSpinBox.value()
            self.add_to_simulation_activity_monitor(f"Retrieving data for interval {interval}...")
            self.simulationTrader = SimulationTrader(startingBalance=startingBalance,
                                                     symbol=symbol,
                                                     interval=interval,
                                                     loadData=True)
        elif caller == LIVE:
            symbol = self.configuration.tickerComboBox.currentText()
            interval = helpers.convert_interval(self.configuration.intervalComboBox.currentText())
            apiSecret = self.configuration.binanceApiSecret.text()
            apiKey = self.configuration.binanceApiKey.text()
            if len(apiSecret) == 0:
                raise ValueError('Please specify an API secret key. No API secret key found.')
            elif len(apiKey) == 0:
                raise ValueError("Please specify an API key. No API key found.")
            self.add_to_activity_monitor(f"Retrieving data for interval {interval}...")
            self.trader = RealTrader(apiSecret=apiSecret, apiKey=apiKey, interval=interval, symbol=symbol)
        else:
            raise ValueError("Invalid caller.")

        self.initialize_lower_interval_trading(caller=caller, interval=interval)
        # self.trader.dataView.get_data_from_database()
        # if not self.trader.dataView.database_is_updated():
        #     self.timestamp_message("Updating data...")
        #     self.trader.dataView.update_database()
        # else:
        #     self.timestamp_message("Data is up-to-date.")

    def initialize_lower_interval_trading(self, caller, interval):
        sortedIntervals = ('1m', '3m', '5m', '15m', '30m', '1h', '2h', '12h', '4h', '6h', '8h', '1d', '3d')
        if interval != '1m':
            lowerInterval = sortedIntervals[sortedIntervals.index(interval) - 1]
            if caller == LIVE:
                self.add_to_activity_monitor(f'Retrieving data for lower interval {lowerInterval}...')
                self.lowerIntervalData = Data(lowerInterval)
            else:
                self.add_to_simulation_activity_monitor(f'Retrieving data for lower interval {lowerInterval}...')
                self.simulationLowerIntervalData = Data(lowerInterval)

    def set_parameters(self, caller):
        if caller == LIVE:
            self.trader.lossStrategy, self.trader.lossPercentageDecimal = self.get_loss_settings(caller)
            self.trader.tradingOptions = self.get_trading_options(caller)
        elif caller == SIMULATION:
            self.simulationTrader.lossStrategy, self.simulationTrader.lossPercentageDecimal = self.get_loss_settings(
                caller)
            self.simulationTrader.tradingOptions = self.get_trading_options(caller)
        else:
            raise ValueError('Invalid caller.')

    def set_advanced_logging(self, boolean):
        if self.advancedLogging:
            self.add_to_activity_monitor(f'Logging method has been changed to advanced.')
        else:
            self.add_to_activity_monitor(f'Logging method has been changed to simple.')
        self.advancedLogging = boolean

    def disable_interface(self, boolean, caller):
        boolean = not boolean
        if caller == BACKTEST:
            self.configuration.backtestConfigurationTabWidget.setEnabled(boolean)
            self.runBacktestButton.setEnabled(boolean)
            self.endBacktestButton.setEnabled(not boolean)
        elif caller == SIMULATION:
            self.configuration.simulationConfigurationTabWidget.setEnabled(boolean)
            self.runSimulationButton.setEnabled(boolean)
            self.endSimulationButton.setEnabled(not boolean)
        elif caller == LIVE:
            self.configuration.mainConfigurationTabWidget.setEnabled(boolean)
            self.runBotButton.setEnabled(boolean)
            self.endBotBUtton.setEnabled(not boolean)
        else:
            raise ValueError('Invalid caller specified.')

    def update_trades_to_list_view(self):
        widgetCount = self.tradesListWidget.count()
        tradeCount = len(self.trader.trades)

        if widgetCount < tradeCount:
            remaining = tradeCount - widgetCount
            for trade in self.trader.trades[-remaining:]:
                self.add_trade_to_list_view(f'{trade["action"]}')
                self.timestamp_message(f'{trade["action"]}')

    def add_trade_to_list_view(self, msg):
        self.tradesListWidget.addItem(msg)

    def update_simulation_info(self):
        trader = self.simulationTrader
        self.statistics.simulationCurrentBalanceValue.setText(f'${round(trader.get_net(), 2)}')
        self.statistics.simulationStartingBalanceValue.setText(f'${round(trader.startingBalance, 2)}')
        self.statistics.simulationAutonomousValue.setText(str(not trader.inHumanControl))

        if trader.get_profit() < 0:
            self.statistics.simulationProfitLossLabel.setText("Loss")
            self.statistics.simulationProfitLossValue.setText(f'${-round(trader.get_profit(), 2)}')
        else:
            self.statistics.simulationProfitLossLabel.setText("Gain")
            self.statistics.simulationProfitLossValue.setText(f'${round(trader.get_profit(), 2)}')

        position = trader.get_position()
        if position == LONG:
            self.statistics.simulationCurrentPositionValue.setText('Long')
        elif position == SHORT:
            self.statistics.simulationCurrentPositionValue.setText('Short')
        else:
            self.statistics.simulationCurrentPositionValue.setText('None')

        self.statistics.simulationCurrentBtcLabel.setText(f'{trader.coinName} Owned')
        self.statistics.simulationCurrentBtcValue.setText(f'{round(trader.coin, 6)}')
        self.statistics.simulationBtcOwedLabel.setText(f'{trader.coinName} Owed')
        self.statistics.simulationBtcOwedValue.setText(f'{round(trader.coinOwed, 6)}')
        self.statistics.simulationTradesMadeValue.setText(str(len(trader.trades)))
        self.statistics.simulationCurrentTickerLabel.setText(str(trader.dataView.symbol))
        self.statistics.simulationCurrentTickerValue.setText(f'${trader.dataView.get_current_price()}')

        if trader.get_stop_loss() is not None:
            if trader.lossStrategy == STOP_LOSS:
                self.statistics.simulationLossPointLabel.setText('Stop Loss')
            else:
                self.statistics.simulationLossPointLabel.setText('Trailing Loss')
            self.statistics.simulationLossPointValue.setText(f'${round(trader.get_stop_loss(), 2)}')
        else:
            self.statistics.simulationLossPointValue.setText('None')

        currentUTC = datetime.utcnow().timestamp()
        initialNet = self.simulationTrader.startingBalance
        netTotal = trader.get_net()
        profit = netTotal - initialNet
        percentage = self.simulationTrader.get_profit_percentage(initialNet, netTotal)

        if profit > 0:
            self.simulationProfitLabel.setText('Profit')
        else:
            self.simulationProfitLabel.setText('Loss')

        self.simulationNetTotalValue.setText(f'${round(netTotal, 2)}')
        self.simulationProfitValue.setText(f'${round(profit, 2)}')
        self.simulationPercentageValue.setText(f'{round(percentage, 2)}%')
        self.simulationTickerValue.setText(self.simulationTrader.symbol)
        self.add_data_to_plot(self.simulationGraph, 0, currentUTC, netTotal)

        for index, option in enumerate(trader.tradingOptions):
            initialAverage, finalAverage, initialAverageLabel, finalAverageLabel = self.get_option_info(option, trader)
            self.add_data_to_plot(self.simulationAvgGraph, index * 2, currentUTC, initialAverage)
            self.add_data_to_plot(self.simulationAvgGraph, index * 2 + 1, currentUTC, finalAverage)

            if index == 0:
                self.statistics.simulationBaseInitialMovingAverageLabel.setText(initialAverageLabel)
                self.statistics.simulationBaseInitialMovingAverageValue.setText(f'${initialAverage}')
                self.statistics.simulationBaseFinalMovingAverageLabel.setText(finalAverageLabel)
                self.statistics.simulationBaseFinalMovingAverageValue.setText(f'${finalAverage}')
                if len(trader.tradingOptions) == 1:
                    self.statistics.simulationNextInitialMovingAverageLabel.hide()
                    self.statistics.simulationNextInitialMovingAverageValue.hide()
                    self.statistics.simulationNextFinalMovingAverageLabel.hide()
                    self.statistics.simulationNextFinalMovingAverageValue.hide()

            if index > 0:
                self.statistics.simulationNextInitialMovingAverageLabel.show()
                self.statistics.simulationNextInitialMovingAverageValue.show()
                self.statistics.simulationNextFinalMovingAverageLabel.show()
                self.statistics.simulationNextFinalMovingAverageValue.show()

                self.statistics.simulationNextInitialMovingAverageLabel.setText(initialAverageLabel)
                self.statistics.simulationNextInitialMovingAverageValue.setText(f'${initialAverage}')
                self.statistics.simulationNextFinalMovingAverageLabel.setText(finalAverageLabel)
                self.statistics.nextFinalMovingAverageValue.setText(f'${finalAverage}')

    def update_info(self):
        self.statistics.currentBalanceValue.setText(f'${round(self.trader.get_net(), 2)}')
        self.statistics.startingBalanceValue.setText(f'${round(self.trader.startingBalance, 2)}')
        self.statistics.autonomousValue.setText(str(not self.trader.inHumanControl))

        if self.trader.inHumanControl:
            self.autonomousStateLabel.setText('WARNING: IN HUMAN CONTROL')
        else:
            self.autonomousStateLabel.setText('INFO: IN AUTONOMOUS MODE')

        if self.trader.get_profit() < 0:
            self.statistics.profitLossLabel.setText("Loss")
            self.statistics.profitLossValue.setText(f'${-round(self.trader.get_profit(), 2)}')
        else:
            self.statistics.profitLossLabel.setText("Gain")
            self.statistics.profitLossValue.setText(f'${round(self.trader.get_profit(), 2)}')

        position = self.trader.get_position()

        if position == LONG:
            self.statistics.currentPositionValue.setText('Long')
        elif position == SHORT:
            self.statistics.currentPositionValue.setText('Short')
        else:
            self.statistics.currentPositionValue.setText('None')

        self.statistics.currentBtcLabel.setText(f'{self.trader.coinName} Owned')
        self.statistics.currentBtcValue.setText(f'{round(self.trader.coin, 6)}')
        self.statistics.btcOwedLabel.setText(f'{self.trader.coinName} Owed')
        self.statistics.btcOwedValue.setText(f'{round(self.trader.coinOwed, 6)}')
        self.statistics.tradesMadeValue.setText(str(len(self.trader.trades)))
        self.statistics.currentTickerLabel.setText(str(self.trader.dataView.symbol))
        self.statistics.currentTickerValue.setText(f'${self.trader.dataView.get_current_price()}')

        if self.trader.get_stop_loss() is not None:
            if self.trader.lossStrategy == STOP_LOSS:
                self.statistics.lossPointLabel.setText('Stop Loss')
            else:
                self.statistics.lossPointLabel.setText('Trailing Loss')
            self.statistics.lossPointValue.setText(f'${round(self.trader.get_stop_loss(), 2)}')
        else:
            self.statistics.lossPointValue.setText('None')

        currentUTC = datetime.utcnow().timestamp()

        if len(self.trader.tradingOptions) > 0:
            option = self.trader.tradingOptions[0]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.plots[0]['x'].append(currentUTC)
            self.plots[0]['y'].append(initialAverage)
            self.plots[0]['plot'].setData(self.plots[0]['x'], self.plots[0]['y'])

            self.plots[1]['x'].append(currentUTC)
            self.plots[1]['y'].append(finalAverage)
            self.plots[1]['plot'].setData(self.plots[1]['x'], self.plots[1]['y'])

            self.statistics.baseInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})'
                                                                  f' {option.parameter.capitalize()}')
            self.statistics.baseInitialMovingAverageValue.setText(f'${initialAverage}')
            self.statistics.baseFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})'
                                                                f' {option.parameter.capitalize()}')
            self.statistics.baseFinalMovingAverageValue.setText(f'${finalAverage}')

        if len(self.trader.tradingOptions) > 1:
            self.statistics.nextInitialMovingAverageLabel.show()
            self.statistics.nextInitialMovingAverageValue.show()
            self.statistics.nextFinalMovingAverageLabel.show()
            self.statistics.nextFinalMovingAverageValue.show()

            option = self.trader.tradingOptions[1]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.plots[2]['x'].append(currentUTC)
            self.plots[2]['y'].append(initialAverage)
            self.plots[2]['plot'].setData(self.plots[2]['x'], self.plots[2]['y'])

            self.plots[3]['x'].append(currentUTC)
            self.plots[3]['y'].append(finalAverage)
            self.plots[3]['plot'].setData(self.plots[3]['x'], self.plots[3]['y'])

            self.statistics.nextInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})'
                                                                  f' - {option.parameter.capitalize()}')
            print("", end="")  # so PyCharm stops nagging us
            self.statistics.nextInitialMovingAverageValue.setText(f'${initialAverage}')
            self.statistics.nextFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})'
                                                                f' - {option.parameter.capitalize()}')
            self.statistics.nextFinalMovingAverageValue.setText(f'${finalAverage}')
        else:
            self.statistics.nextInitialMovingAverageLabel.hide()
            self.statistics.nextInitialMovingAverageValue.hide()
            self.statistics.nextFinalMovingAverageLabel.hide()
            self.statistics.nextFinalMovingAverageValue.hide()

    def enable_override(self, caller):
        if caller == LIVE:
            self.overrideGroupBox.setEnabled(True)
        elif caller == SIMULATION:
            self.simulationOverrideGroupBox.setEnabled(True)
        else:
            raise ValueError("Invalid caller specified.")

    def disable_override(self, caller):
        if caller == LIVE:
            self.overrideGroupBox.setEnabled(False)
        elif caller == SIMULATION:
            self.simulationOverrideGroupBox.setEnabled(False)
        else:
            raise ValueError("Invalid caller specified.")

    def exit_position(self, caller, humanControl=True):
        if caller == LIVE:
            trader = self.trader
            if humanControl:
                self.pauseBotButton.setText('Resume Bot')
            else:
                self.pauseBotButton.setText('Pause Bot')
            self.forceShortButton.setEnabled(True)
            self.forceLongButton.setEnabled(True)
            self.exitPositionButton.setEnabled(False)
            self.waitOverrideButton.setEnabled(False)
        elif caller == SIMULATION:
            trader = self.simulationTrader
            if humanControl:
                self.pauseBotSimulationButton.setText('Resume Bot')
            else:
                self.pauseBotSimulationButton.setText('Pause Bot')
            self.forceShortSimulationButton.setEnabled(True)
            self.forceLongSimulationButton.setEnabled(True)
            self.exitPositionSimulationButton.setEnabled(False)
            self.waitOverrideSimulationButton.setEnabled(False)
        else:
            raise ValueError("Invalid caller specified.")

        trader.inHumanControl = humanControl
        if trader.get_position() == LONG:
            if humanControl:
                trader.sell_long('Force exited long.', force=True)
            else:
                trader.sell_long('Exiting long because of override and resuming autonomous logic.', force=True)
        elif trader.get_position() == SHORT:
            if humanControl:
                trader.buy_short('Force exited short.', force=True)
            else:
                trader.buy_short('Exiting short because of override and resuming autonomous logic..', force=True)

    def force_long(self, caller):
        if caller == SIMULATION:
            trader = self.simulationTrader
            self.pauseBotSimulationButton.setText('Resume Bot')
            self.add_to_simulation_activity_monitor('Forced long and stopped autonomous logic.')
            self.forceShortSimulationButton.setEnabled(False)
            self.forceLongSimulationButton.setEnabled(False)
            self.exitPositionSimulationButton.setEnabled(True)
            self.waitOverrideSimulationButton.setEnabled(True)
        elif caller == LIVE:
            trader = self.trader
            self.pauseBotButton.setText('Resume Bot')
            self.add_to_activity_monitor('Forced long and stopping autonomous logic.')
            self.forceShortButton.setEnabled(False)
            self.forceLongButton.setEnabled(False)
            self.exitPositionButton.setEnabled(True)
            self.waitOverrideButton.setEnabled(True)
        else:
            raise ValueError("Invalid type of caller specified.")

        trader.inHumanControl = True
        if trader.get_position() == SHORT:
            trader.buy_short('Exited short because long was forced.', force=True)
        trader.buy_long('Force executed long.', force=True)

    def force_short(self, caller):
        if caller == SIMULATION:
            trader = self.simulationTrader
            self.pauseBotSimulationButton.setText('Resume Bot')
            self.add_to_simulation_activity_monitor('Forcing short and stopping autonomous logic.')
            self.forceShortSimulationButton.setEnabled(False)
            self.forceLongSimulationButton.setEnabled(False)
            self.exitPositionSimulationButton.setEnabled(True)
            self.waitOverrideSimulationButton.setEnabled(True)
        elif caller == LIVE:
            trader = self.trader
            self.pauseBotButton.setText('Resume Bot')
            self.add_to_activity_monitor('Forced short and stopped autonomous logic.')
            self.forceShortButton.setEnabled(False)
            self.forceLongButton.setEnabled(False)
            self.exitPositionButton.setEnabled(True)
            self.waitOverrideButton.setEnabled(True)
        else:
            raise ValueError("Invalid type of caller specified.")

        trader.inHumanControl = True
        if trader.get_position() == LONG:
            trader.sell_long('Exited long because short was forced.', force=True)
        trader.sell_short('Force executed short.', force=True)

    def pause_or_resume_bot(self, caller):
        """
        Pauses or resumes bot logic based on caller.
        :param caller: Caller object that specifies which trading object will be paused or resumed.
        """
        if caller == LIVE:
            if self.pauseBotButton.text() == 'Pause Bot':
                self.trader.inHumanControl = True
                self.pauseBotButton.setText('Resume Bot')
                self.add_to_activity_monitor('Pausing bot logic.')
            else:
                self.trader.inHumanControl = False
                self.pauseBotButton.setText('Pause Bot')
                self.add_to_activity_monitor('Resuming bot logic.')
        elif caller == SIMULATION:
            if self.pauseBotSimulationButton.text() == 'Pause Bot':
                self.simulationTrader.inHumanControl = True
                self.pauseBotSimulationButton.setText('Resume Bot')
                self.add_to_simulation_activity_monitor('Pausing bot logic.')
            else:
                self.simulationTrader.inHumanControl = False
                self.pauseBotSimulationButton.setText('Pause Bot')
                self.add_to_simulation_activity_monitor('Resuming bot logic.')
        else:
            raise ValueError("Invalid caller type specified.")

    def get_backtest_trading_options(self):
        """
        Returns trading options for backtest trading configuration.
        :return: Backtest trading options list.
        """
        baseAverageType = self.configuration.backtestAverageTypeComboBox.currentText()
        baseParameter = self.configuration.backtestParameterComboBox.currentText().lower()
        baseInitialValue = self.configuration.backtestInitialValueSpinBox.value()
        baseFinalValue = self.configuration.backtestFinalValueSpinBox.value()
        options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]

        if self.configuration.backtestDoubleCrossCheckMark.isChecked():
            additionalAverageType = self.configuration.backtestDoubleAverageComboBox.currentText()
            additionalParameter = self.configuration.backtestDoubleParameterComboBox.currentText().lower()
            additionalInitialValue = self.configuration.backtestDoubleInitialValueSpinBox.value()
            additionalFinalValue = self.configuration.backtestDoubleFinalValueSpinBox.value()
            option = Option(additionalAverageType, additionalParameter, additionalInitialValue,
                            additionalFinalValue)
            options.append(option)

        return options

    def get_simulation_trading_options(self) -> list:
        """
        Returns trading options for simulation trading configuration.
        :return: Simulation trading options list.
        """
        baseAverageType = self.configuration.simulationAverageTypeComboBox.currentText()
        baseParameter = self.configuration.simulationParameterComboBox.currentText().lower()
        baseInitialValue = self.configuration.simulationInitialValueSpinBox.value()
        baseFinalValue = self.configuration.simulationFinalValueSpinBox.value()
        options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]

        if self.configuration.simulationDoubleCrossCheckMark.isChecked():
            additionalAverageType = self.configuration.simulationDoubleAverageComboBox.currentText()
            additionalParameter = self.configuration.simulationDoubleParameterComboBox.currentText().lower()
            additionalInitialValue = self.configuration.simulationDoubleInitialValueSpinBox.value()
            additionalFinalValue = self.configuration.simulationDoubleFinalValueSpinBox.value()
            option = Option(additionalAverageType, additionalParameter, additionalInitialValue,
                            additionalFinalValue)
            options.append(option)

        return options

    def get_live_trading_options(self) -> list:
        """
        Returns trading options for live trading configuration.
        :return: Live trading options list.
        """
        baseAverageType = self.configuration.averageTypeComboBox.currentText()
        baseParameter = self.configuration.parameterComboBox.currentText().lower()
        baseInitialValue = self.configuration.initialValueSpinBox.value()
        baseFinalValue = self.configuration.finalValueSpinBox.value()

        options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]
        if self.configuration.doubleCrossCheckMark.isChecked():
            additionalAverageType = self.configuration.doubleAverageComboBox.currentText()
            additionalParameter = self.configuration.doubleParameterComboBox.currentText().lower()
            additionalInitialValue = self.configuration.doubleInitialValueSpinBox.value()
            additionalFinalValue = self.configuration.doubleFinalValueSpinBox.value()
            option = Option(additionalAverageType, additionalParameter, additionalInitialValue,
                            additionalFinalValue)
            options.append(option)

        return options

    def get_trading_options(self, caller) -> list:
        """
        Returns trading options for caller specified.
        :param caller: Caller for which trading options will be returned.
        :return: Trading options based on caller.
        """
        if caller == BACKTEST:
            return self.get_backtest_trading_options()

        elif caller == SIMULATION:
            return self.get_simulation_trading_options()

        elif caller == LIVE:
            return self.get_live_trading_options()

        else:
            raise ValueError("Invalid caller specified.")

    def get_loss_settings(self, caller) -> tuple:
        """
        Returns loss settings for caller specified.
        :param caller: Caller for which loss settings will be returned.
        :return: Tuple with stop loss type and loss percentage.
        """
        if caller == BACKTEST:
            if self.configuration.backtestTrailingLossRadio.isChecked():
                return TRAILING_LOSS, self.configuration.backtestLossPercentageSpinBox.value()
            else:
                return STOP_LOSS, self.configuration.backtestLossPercentageSpinBox.value()
        elif caller == SIMULATION:
            if self.configuration.simulationTrailingLossRadio.isChecked():
                return TRAILING_LOSS, self.configuration.simulationLossPercentageSpinBox.value()
            else:
                return STOP_LOSS, self.configuration.simulationLossPercentageSpinBox.value()
        elif caller == LIVE:
            if self.configuration.trailingLossRadio.isChecked():
                return TRAILING_LOSS, self.configuration.lossPercentageSpinBox.value()
            else:
                return STOP_LOSS, self.configuration.lossPercentageSpinBox.value()

    def closeEvent(self, event):
        """
        Close event override. Makes user confirm they want to end program if something is running live.
        :param event: close event
        """
        qm = QMessageBox
        ret = qm.question(self, 'Close?', "Are you sure to end AlgoBot?",
                          qm.Yes | qm.No)

        if ret == qm.Yes:
            if self.runningLive:
                self.end_bot(LIVE)
            elif self.simulationRunningLive:
                self.end_bot(SIMULATION)
            event.accept()
        else:
            event.ignore()

    def setup_graphs(self):
        """
        Sets up all available graphs in application.
        """
        currentDate = datetime.utcnow().timestamp()
        nextDate = currentDate + 3600000

        for graph in self.graphs:
            graph = graph['graph']
            graph.setAxisItems({'bottom': DateAxisItem()})
            graph.setBackground('w')
            graph.setLabel('left', 'USDT')
            graph.setLabel('bottom', 'Datetime in UTC')
            graph.setLimits(xMin=currentDate, xMax=nextDate)
            graph.addLegend()

            if graph == self.backtestGraph:
                graph.setTitle("Backtest Price Change")
            elif graph == self.simulationGraph:
                graph.setTitle("Simulation Price Change")
            elif graph == self.realGraph:
                graph.setTitle("Live Price Change")
            elif graph == self.simulationAvgGraph:
                graph.setTitle("Simulation Moving Averages")
            elif graph == self.avgGraph:
                graph.setTitle("Live Moving Averages")

        # self.graphWidget.setLimits(xMin=currentDate, xMax=nextDate)
        # self.graphWidget.plotItem.setMouseEnabled(y=False)

    def add_data_to_plot(self, targetGraph: PlotWidget, plotIndex: int, x: float, y: float):
        """
        Adds data to plot in provided graph.
        :param targetGraph: Graph to use for plot to add data to.
        :param plotIndex: Index of plot in target graph's list of plots.
        :param x: X value to add.
        :param y: Y value to add.
        """
        for graph in self.graphs:
            if graph['graph'] == targetGraph:
                plot = graph['plots'][plotIndex]
                plot['x'].append(x)
                plot['y'].append(y)
                plot['plot'].setData(plot['x'], plot['y'])

    def append_plot_to_graph(self, targetGraph, toAdd: list):
        """
        Appends plot to graph provided.
        :param targetGraph: Graph to add plot to.
        :param toAdd: List of plots to add to target graph.
        """
        for graph in self.graphs:
            if graph['graph'] == targetGraph:
                graph['plots'] += toAdd

    def destroy_graph_plots(self, targetGraph: PlotWidget):
        """
        Resets graph plots for graph provided.
        :param targetGraph: Graph to destroy plots for.
        """
        for graph in self.graphs:
            if graph['graph'] == targetGraph:
                graph['plots'] = []

    def setup_net_graph_plot(self, graph, trader, color):
        """
        Sets up net balance plot for graph provided.
        :param trader: Type of trader that will use this graph.
        :param graph: Graph where plot will be setup.
        :param color: Color plot will be setup in.
        """
        net = trader.startingBalance
        currentDate = datetime.utcnow().timestamp()
        self.append_plot_to_graph(graph, [{
            'plot': self.create_graph_plot(graph, (currentDate,), (net,),
                                           color=color, plotName='Net'),
            'x': [currentDate],
            'y': [net]
        }])

    @staticmethod
    def get_option_info(option: Option, trader):
        """
        Returns basic information about option provided.
        :param option: Option object for whose information will be retrieved.
        :param trader: Trader object to be used to get averages.
        :return: Tuple of initial average, final average, initial option name, and final option name.
        """
        initialAverage = trader.get_average(option.movingAverage, option.parameter, option.initialBound)
        finalAverage = trader.get_average(option.movingAverage, option.parameter, option.finalBound)
        initialName = f'{option.movingAverage}({option.initialBound}) {option.parameter.capitalize()}'
        finalName = f'{option.movingAverage}({option.finalBound}) {option.parameter.capitalize()}'
        return initialAverage, finalAverage, initialName, finalName

    def setup_average_graph_plot(self, graph, trader, colors):
        """
        Sets up moving average plots for graph provided.
        :param trader: Type of trader that will use this graph.
        :param graph: Graph where plots will be setup.
        :param colors: List of colors plots will be setup in.
        """
        currentDate = datetime.utcnow().timestamp()
        colorCounter = 1
        for option in trader.tradingOptions:
            initialAverage, finalAverage, initialName, finalName = self.get_option_info(option, trader)
            initialPlotDict = {
                'plot': self.create_graph_plot(graph, (currentDate,), (initialAverage,),
                                               color=colors[colorCounter], plotName=initialName),
                'x': [currentDate],
                'y': [initialAverage]
            }
            secondaryPlotDict = {
                'plot': self.create_graph_plot(graph, (currentDate,), (finalAverage,),
                                               color=colors[colorCounter + 1], plotName=finalName),
                'x': [currentDate],
                'y': [finalAverage]
            }
            colorCounter += 2
            self.append_plot_to_graph(graph, [initialPlotDict, secondaryPlotDict])

    def setup_graph_plots(self, graph, trader, graphType):
        """
        Setups graph plots for graph, trade, and graphType specified.
        :param graph: Graph that will be setup.
        :param trader: Trade object that will use this graph.
        :param graphType: Graph type; i.e. moving average or net balance.
        """
        colors = self.get_graph_colors()
        currentDate = datetime.utcnow().timestamp()
        if graphType == NET_GRAPH:
            self.setup_net_graph_plot(graph=graph, trader=trader, color=colors[0])
        elif graphType == AVG_GRAPH:
            self.setup_average_graph_plot(graph=graph, trader=trader, colors=colors)
        else:
            raise TypeError("Invalid type of graph provided.")

    def get_graph_colors(self):
        """
        Returns graph colors to be placed based on configuration.
        """
        config = self.configuration
        colorDict = {'blue': 'b',
                     'green': 'g',
                     'red': 'r',
                     'cyan': 'c',
                     'magenta': 'm',
                     'yellow': 'y',
                     'black': 'k',
                     'white': 'w'}
        colors = [config.balanceColor.currentText(), config.avg1Color.currentText(), config.avg2Color.currentText(),
                  config.avg3Color.currentText(), config.avg4Color.currentText()]
        return [colorDict[color.lower()] for color in colors]

    @staticmethod
    def create_graph_plot(graph, x, y, plotName, color):
        """
        Plots to graph provided.
        :param graph: Graph function will plot on.
        :param x: X values of graph.
        :param y: Y values of graph.
        :param plotName: Name of graph.
        :param color: Color graph will be drawn in.
        """
        pen = mkPen(color=color)
        return graph.plot(x, y, name=plotName, pen=pen)

    @staticmethod
    def clear_table(table):
        """
        Sets table row count to 0.
        :param table: Table which is to be cleared.
        """
        table.setRowCount(0)

    @staticmethod
    def test_table(table, trade):
        """
        Initial function made to test table functionalities in QT.
        :param table: Table to insert row at.
        :param trade: Trade information to add.
        """
        rowPosition = table.rowCount()
        columns = table.columnCount()

        table.insertRow(rowPosition)
        for column in range(columns):
            table.setItem(rowPosition, column, QTableWidgetItem(str(trade[column])))

    def add_to_simulation_activity_monitor(self, message: str):
        """
        Function that adds activity information to the simulation activity monitor.
        :param message: Message to add to simulation activity log.
        """
        self.add_to_table(self.simulationActivityMonitor, [message])

    def add_to_activity_monitor(self, message: str):
        """
        Function that adds activity information to activity monitor.
        :param message: Message to add to activity log.
        """
        self.add_to_table(self.activityMonitor, [message])

    @staticmethod
    def add_to_table(table, data):
        """
        Function that will add specified data to a provided table.
        :param table: Table we will add data to.
        :param data: Data we will add to table.
        """
        rowPosition = table.rowCount()
        columns = table.columnCount()

        data.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if len(data) != columns:
            raise ValueError('Data needs to have the same amount of columns as table.')

        table.insertRow(rowPosition)
        for column in range(0, columns):
            table.setItem(rowPosition, column, QTableWidgetItem(str(data[column])))

    def update_trades_table_and_activity_monitor(self, caller):
        """
        Updates trade table and activity based on caller.
        :param caller: Caller object that will rule which tables get updated.
        """
        if caller == SIMULATION:
            table = self.simulationHistoryTable
            trades = self.simulationTrader.trades
        elif caller == LIVE:
            table = self.historyTable
            trades = self.trader.trades
        else:
            raise ValueError('Invalid caller specified.')

        if len(trades) > table.rowCount():  # Basically, only update when row count is not equal to trades count.
            remaining = len(trades) - table.rowCount()
            for trade in trades[-remaining:]:
                tradeData = [trade['orderID'],
                             trade['pair'],
                             trade['price'],
                             trade['percentage'],
                             trade['profit'],
                             trade['method'],
                             trade['action']]
                self.add_to_table(table, tradeData)
                if caller == LIVE:  # Also add action to main activity monitor.
                    self.add_to_activity_monitor(trade['action'])
                else:
                    self.add_to_simulation_activity_monitor(trade['action'])

    def show_main_settings(self):
        """
        Opens main settings in the configuration window.
        """
        self.configuration.show()
        self.configuration.configurationTabWidget.setCurrentIndex(0)
        self.configuration.mainConfigurationTabWidget.setCurrentIndex(0)

    def show_backtest_settings(self):
        """
        Opens backtest settings in the configuration window.
        """
        self.configuration.show()
        self.configuration.configurationTabWidget.setCurrentIndex(1)
        self.configuration.backtestConfigurationTabWidget.setCurrentIndex(0)

    def show_simulation_settings(self):
        """
        Opens simulation settings in the configuration window.
        """
        self.configuration.show()
        self.configuration.configurationTabWidget.setCurrentIndex(2)
        self.configuration.simulationConfigurationTabWidget.setCurrentIndex(0)

    def create_configuration_slots(self):
        """
        Creates configuration slots.
        """
        self.configuration.lightModeRadioButton.toggled.connect(lambda: self.set_light_mode())
        self.configuration.darkModeRadioButton.toggled.connect(lambda: self.set_dark_mode())
        self.configuration.bloombergModeRadioButton.toggled.connect(lambda: self.set_bloomberg_mode())
        self.configuration.bullModeRadioButton.toggled.connect(lambda: self.set_bull_mode())
        self.configuration.bearModeRadioButton.toggled.connect(lambda: self.set_bear_mode())
        self.configuration.printingModeRadioButton.toggled.connect(lambda: self.set_printing_mode())
        self.configuration.simpleLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(False))
        self.configuration.advancedLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(True))

    def create_action_slots(self):
        """
        Creates actions slots.
        """
        self.otherCommandsAction.triggered.connect(lambda: self.otherCommands.show())
        self.configurationAction.triggered.connect(lambda: self.configuration.show())
        self.statisticsAction.triggered.connect(lambda: self.statistics.show())
        self.aboutAlgobotAction.triggered.connect(lambda: self.about.show())

    def create_bot_slots(self):
        """
        Creates bot slots.
        """
        self.runBotButton.clicked.connect(lambda: self.initiate_bot_thread(caller=LIVE))
        self.endBotButton.clicked.connect(lambda: self.end_bot(caller=LIVE))
        self.configureBotButton.clicked.connect(self.show_main_settings)
        self.forceLongButton.clicked.connect(self.force_long)
        self.forceShortButton.clicked.connect(self.force_short)
        self.pauseBotButton.clicked.connect(self.pause_or_resume_bot)
        self.exitPositionButton.clicked.connect(lambda: self.exit_position(LIVE, True))
        self.waitOverrideButton.clicked.connect(lambda: self.exit_position(LIVE, False))

    def create_simulation_slots(self):
        """
        Creates simulation slots.
        """
        self.runSimulationButton.clicked.connect(lambda: self.initiate_bot_thread(caller=SIMULATION))
        self.endSimulationButton.clicked.connect(lambda: self.end_bot(caller=SIMULATION))
        self.configureSimulationButton.clicked.connect(self.show_simulation_settings)
        self.forceLongSimulationButton.clicked.connect(lambda: self.force_long(SIMULATION))
        self.forceShortSimulationButton.clicked.connect(lambda: self.force_short(SIMULATION))
        self.pauseBotSimulationButton.clicked.connect(lambda: self.pause_or_resume_bot(SIMULATION))
        self.exitPositionSimulationButton.clicked.connect(lambda: self.exit_position(SIMULATION, True))
        self.waitOverrideSimulationButton.clicked.connect(lambda: self.exit_position(SIMULATION, True))

    def create_backtest_slots(self):
        """
        Creates backtest slots.
        """
        self.configureBacktestButton.clicked.connect(self.show_backtest_settings)
        self.runBacktestButton.clicked.connect(lambda: print("backtest pressed"))
        self.endBacktestButton.clicked.connect(lambda: print("end backtest"))

    def create_interface_slots(self):
        """
        Creates interface slots.
        """
        self.create_bot_slots()
        self.create_simulation_slots()
        self.create_backtest_slots()

    def initiate_slots(self):
        """
        Initiates all interface slots.
        """
        self.create_action_slots()
        self.create_configuration_slots()
        self.create_interface_slots()

    def load_tickers(self):
        """
        Loads all available tickers from Binance API and displays them on appropriate combo boxes in application.
        """
        tickers = [ticker['symbol'] for ticker in Data(loadData=False).binanceClient.get_all_tickers()
                   if 'USDT' in ticker['symbol']]
        tickers.sort()
        self.configuration.tickerComboBox.clear()  # Clear all existing live tickers.
        self.configuration.backtestTickerComboBox.clear()  # Clear all existing backtest tickers.
        self.configuration.simulationTickerComboBox.clear()  # Clear all existing simulation tickers.

        self.configuration.tickerComboBox.addItems(tickers)  # Add the tickers to list of live tickers.
        self.configuration.backtestTickerComboBox.addItems(tickers)  # Add the tickers to list of backtest tickers.
        self.configuration.simulationTickerComboBox.addItems(tickers)  # Add the tickers to list of simulation tickers.

        self.otherCommands.csvGenerationTicker.clear()  # Clear CSV generation tickers.
        self.otherCommands.csvGenerationTicker.addItems(tickers)  # Add the tickers to list of CSV generation tickers.

    def create_popup(self, msg):
        """
        Creates a popup with message provided.
        :param msg: Message provided.
        """
        if '-1021' in msg:
            msg = msg + ' Please sync your system time.'
        QMessageBox.about(self, 'Warning', msg)

    def set_dark_mode(self):
        """
        Switches interface to a dark theme.
        """
        app.setPalette(get_dark_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_light_mode(self):
        """
        Switches interface to a light theme.
        """
        app.setPalette(get_light_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('w')

    def set_bloomberg_mode(self):
        """
        Switches interface to bloomberg theme.
        """
        app.setPalette(get_bloomberg_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_bear_mode(self):
        """
        Sets bear mode color theme. Theme is red and black mimicking a red day.
        """
        app.setPalette(get_red_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_bull_mode(self):
        """
        Sets bull mode color theme. Theme is green and black mimicking a green day.
        """
        app.setPalette(get_green_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_printing_mode(self):
        """
        Sets printing mode color theme. Theme is dark green and white mimicking dollars.
        """
        app.setPalette(get_light_green_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('w')

    @staticmethod
    def timestamp_message(msg, output=None):
        """
        This is not used anymore, but it adds a message to a ListWidget object from QT.
        :param msg: Message to be added.
        :param output: ListWidget object.
        """
        output.append(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {msg}')

    def display_trade_options(self):
        """
        This is never used, but it displays trading options.
        """
        for option in self.trader.tradingOptions:
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.timestamp_message(f'Parameter: {option.parameter}')
            self.timestamp_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
            self.timestamp_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')


def main():
    app.setStyle('Fusion')
    helpers.initialize_logger()
    interface = Interface()
    interface.showMaximized()
    app.setWindowIcon(QIcon('../media/algobotwolf.png'))
    sys.excepthook = except_hook
    sys.exit(app.exec_())


def except_hook(cls, exception, trace_back):
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    main()
