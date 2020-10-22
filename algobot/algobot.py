import sys
import assets
import helpers
import os

from data import Data
from datetime import datetime
from threadWorkers import Worker
from palettes import *
from telegramBot import TelegramBot
from telegram.error import InvalidToken
from telegram.ext import Updater
from binance.client import Client
from realtrader import RealTrader
from simulationtrader import SimulatedTrader
from option import Option
from enums import *

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QDialog, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import QThreadPool
from PyQt5.QtGui import QIcon
from pyqtgraph import DateAxisItem, mkPen, PlotWidget

app = QApplication(sys.argv)

mainUi = f'../UI{os.path.sep}algobot.ui'
configurationUi = f'../UI{os.path.sep}configuration.ui'
otherCommandsUi = f'../UI{os.path.sep}otherCommands.ui'
statisticsUi = f'../UI{os.path.sep}statistics.ui'
aboutUi = f'../UI{os.path.sep}about.ui'


class Interface(QMainWindow):
    def __init__(self, parent=None):
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
        self.trader = None
        self.simulationTrader = None
        self.traderType = None
        self.simulationLowerIntervalData = None
        self.lowerIntervalData = None
        self.telegramBot = None
        self.add_to_activity_monitor('Initialized interface.')

    def initiate_bot_thread(self, caller):
        worker = Worker(lambda: self.run_bot(caller))
        worker.signals.error.connect(self.end_bot_and_create_popup)
        # worker.signals.result.connect(lambda: print("lol"))
        self.threadPool.start(worker)

    def end_bot_and_create_popup(self, msg):
        # self.disable_interface(False)
        self.endBotButton.setEnabled(False)
        self.endSimulationButton.setEnabled(False)
        # self.timestamp_message('Ended bot because of an error.')
        self.create_popup(msg)

    def automate_simulation_trading(self):
        crossInform = False
        lowerCrossPosition = -5
        trader = self.simulationTrader

        while self.simulationRunningLive:
            try:
                if not self.simulationTrader.dataView.data_is_updated():
                    self.add_to_simulation_activity_monitor("Updating data...")
                    self.simulationTrader.dataView.update_data()

                if self.simulationTrader.get_position() is not None:
                    crossInform = False

                if not crossInform and trader.get_position() is None and not trader.inHumanControl:
                    crossInform = True
                    self.add_to_simulation_activity_monitor("Waiting for a cross.")

                self.update_simulation_info()
                self.update_trades_table_and_activity_monitor(SIMULATION)

                if self.advancedLogging:
                    trader.output_basic_information()

                trader.currentPrice = trader.dataView.get_current_price()
                currentPrice = trader.currentPrice
                if trader.longTrailingPrice is not None and currentPrice > trader.longTrailingPrice:
                    trader.longTrailingPrice = currentPrice
                if trader.shortTrailingPrice is not None and currentPrice < trader.shortTrailingPrice:
                    trader.shortTrailingPrice = currentPrice

                if not trader.inHumanControl:
                    trader.main_logic()

                if lowerCrossPosition != trader.get_position():
                    if trader.check_cross_v2(dataObject=self.lowerIntervalData):
                        lowerCrossPosition = trader.get_position()
                        self.add_to_simulation_activity_monitor('Lower interval cross detected.')

                if trader.get_position() is None:
                    self.exitPositionSimulationButton.setEnabled(False)
                    self.waitOverrideSimulationButton.setEnabled(False)
                else:
                    self.exitPositionSimulationButton.setEnabled(True)
                    self.waitOverrideSimulationButton.setEnabled(True)

                if trader.get_position() == LONG:
                    self.forceLongSimulationButton.setEnabled(False)
                    self.forceShortSimulationButton.setEnabled(True)

                if trader.get_position() == SHORT:
                    self.forceLongSimulationButton.setEnabled(True)
                    self.forceShortSimulationButton.setEnabled(False)
            except Exception as e:
                raise e

    def automate_trading(self):
        crossInform = False
        lowerCrossPosition = -5

        while self.runningLive:
            try:
                if not self.trader.dataView.data_is_updated():
                    self.add_to_activity_monitor("Updating data...")
                    self.trader.dataView.update_data()

                if self.trader.get_position() is not None:
                    crossInform = False

                if not crossInform and self.trader.get_position() is None and not self.trader.inHumanControl:
                    crossInform = True
                    self.timestamp_message("Waiting for a cross.")

                self.update_info()
                self.update_trades_table_and_activity_monitor(LIVE)
                # self.update_trades_to_list_view()

                if self.advancedLogging:
                    self.trader.output_basic_information()

                self.trader.currentPrice = self.trader.dataView.get_current_price()
                currentPrice = self.trader.currentPrice
                if self.trader.longTrailingPrice is not None and currentPrice > self.trader.longTrailingPrice:
                    self.trader.longTrailingPrice = currentPrice
                if self.trader.shortTrailingPrice is not None and currentPrice < self.trader.shortTrailingPrice:
                    self.trader.shortTrailingPrice = currentPrice

                if not self.trader.inHumanControl:
                    self.trader.main_logic()

                if lowerCrossPosition != self.trader.get_position():
                    if self.trader.check_cross_v2(dataObject=self.lowerIntervalData):
                        lowerCrossPosition = self.trader.get_position()
                        self.timestamp_message('Lower interval cross detected.')

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
            except Exception as e:
                raise e
                # self.trader.output_message(f'Error: {e}')

    def run_bot(self, caller):
        self.create_trader(caller)
        self.disable_interface(True, caller)
        self.set_parameters(caller)
        self.enable_override(caller)

        if caller == LIVE and self.configuration.enableTelegramTrading.isChecked():
            try:
                if self.telegramBot is None:
                    apiKey = self.configuration.telegramApiKey.text()
                    self.telegramBot = TelegramBot(gui=self, apiKey=apiKey)
                self.telegramBot.start()
                self.add_to_activity_monitor('Starting Telegram bot.')
            except InvalidToken:
                self.add_to_activity_monitor('Invalid token for Telegram. Please recheck credentials in settings.')

        if caller == LIVE:
            self.clear_table(self.historyTable)
            self.runningLive = True
            self.setup_graph_plots(self.realGraph, self.trader, 'net')
            self.setup_graph_plots(self.avgGraph, self.trader, 'average')
            self.automate_trading()
        elif caller == SIMULATION:
            self.clear_table(self.simulationHistoryTable)
            self.simulationRunningLive = True
            self.setup_graph_plots(self.simulationGraph, self.simulationTrader, 'net')
            self.setup_graph_plots(self.simulationAvgGraph, self.simulationTrader, 'average')
            self.automate_simulation_trading()

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
            self.simulationTrader = SimulatedTrader(startingBalance=startingBalance,
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
            self.simulationTrader.lossStrategy, self.simulationTrader.lossPercentageDecimal = self.get_loss_settings(caller)
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
            initialAverage = trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.add_data_to_plot(self.simulationAvgGraph, index * 2, currentUTC, initialAverage)
            self.add_data_to_plot(self.simulationAvgGraph, index * 2 + 1, currentUTC, finalAverage)
            initialAverageLabel = f'{option.movingAverage}({option.initialBound})  {option.parameter.capitalize()}'
            finalAverageLabel = f'{option.movingAverage}({option.finalBound}) {option.parameter.capitalize()}'

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

    def get_trading_options(self, caller):
        if caller == BACKTEST:
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
        elif caller == SIMULATION:
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
        elif caller == LIVE:
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
        else:
            raise ValueError("Invalid caller specified.")

    def get_loss_settings(self, caller):
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

    def setup_graph_plots(self, graph, trader, graphType):
        colors = self.get_graph_colors()
        currentDate = datetime.utcnow().timestamp()
        if graphType == 'net':
            net = 1
            self.append_plot_to_graph(graph, [{
                'plot': self.create_graph_plot(graph, (currentDate,), (net,),
                                               color=colors[0], plotName='Net'),
                'x': [currentDate],
                'y': [net]
            }])
        elif graphType == 'average':
            colorCounter = 1
            for option in trader.tradingOptions:
                initialAverage = trader.get_average(option.movingAverage, option.parameter, option.initialBound)
                finalAverage = trader.get_average(option.movingAverage, option.parameter, option.finalBound)
                initialName = f'{option.movingAverage}({option.initialBound}) {option.parameter.capitalize()}'
                finalName = f'{option.movingAverage}({option.finalBound}) {option.parameter.capitalize()}'
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
        table.setRowCount(0)

    def test_table(self, table, trade):
        """
        Initial function made to test table functionalities in QT.
        :param table: Table to insert row at.
        :param trade: Trade information to add.
        """
        rowPosition = self.simulationTable.rowCount()
        columns = self.simulationTable.columnCount()

        self.simulationTable.insertRow(rowPosition)
        for column in range(columns):
            table.setItem(rowPosition, column, QTableWidgetItem(str(trade[column])))

    def add_to_simulation_activity_monitor(self, message: str):
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
        if caller == SIMULATION:
            table = self.simulationHistoryTable
            trades = self.simulationTrader.trades
        elif caller == LIVE:
            table = self.historyTable
            trades = self.trader.trades
        else:
            raise ValueError('Invalid caller specified.')

        if len(trades) > table.rowCount():
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
                if caller == LIVE:
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
        self.aboutNigerianPrinceAction.triggered.connect(lambda: self.about.show())

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
        app.setPalette(get_red_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_bull_mode(self):
        app.setPalette(get_green_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_printing_mode(self):
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


class Configuration(QDialog):
    def __init__(self, parent=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.load_slots()
        self.load_credentials()

    def load_slots(self):
        """
        Loads all configuration interface slots.
        """
        self.doubleCrossCheckMark.toggled.connect(self.toggle_double_cross_groupbox)
        self.simulationDoubleCrossCheckMark.toggled.connect(self.toggle_simulation_double_cross_groupbox)
        self.backtestDoubleCrossCheckMark.toggled.connect(self.toggle_backtest_double_cross_groupbox)

        self.simulationCopySettingsButton.clicked.connect(self.copy_settings_to_simulation)

        self.backtestCopySettingsButton.clicked.connect(self.copy_settings_to_backtest)
        self.backtestImportDataButton.clicked.connect(self.import_data)
        self.backtestDownloadDataButton.clicked.connect(self.download_data)

        self.testCredentialsButton.clicked.connect(self.test_binance_credentials)
        self.saveCredentialsButton.clicked.connect(self.save_credentials)
        self.loadCredentialsButton.clicked.connect(self.load_credentials)
        self.testTelegramButton.clicked.connect(self.test_telegram)

    def test_binance_credentials(self):
        apiKey = self.binanceApiKey.text()
        apiSecret = self.binanceApiSecret.text()
        try:
            Client(apiKey, apiSecret).get_account()
            self.credentialResult.setText('Connected successfully.')
        except Exception as e:
            stringError = str(e)
            if '1000ms' in stringError:
                self.credentialResult.setText('Time not synchronized. Please synchronize your time.')
            else:
                self.credentialResult.setText(stringError)

    def load_credentials(self):
        try:
            credentials = helpers.load_credentials()
            self.binanceApiKey.setText(credentials['apiKey'])
            self.binanceApiSecret.setText(credentials['apiSecret'])
            self.telegramApiKey.setText(credentials['telegramApiKey'])
            self.credentialResult.setText('Credentials have been loaded successfully.')
        except FileNotFoundError:
            self.credentialResult.setText('Credentials not found. Please first save credentials to load them.')
        except Exception as e:
            self.credentialResult.setText(str(e))

    def save_credentials(self):
        apiKey = self.binanceApiKey.text()
        if len(apiKey) == 0:
            self.credentialResult.setText('Please fill in Binance API key details.')
            return

        apiSecret = self.binanceApiSecret.text()
        if len(apiSecret) == 0:
            self.credentialResult.setText('Please fill in Binance API secret details.')
            return

        telegramApiKey = self.telegramApiKey.text()
        helpers.write_credentials(apiKey=apiKey, apiSecret=apiSecret, telegramApiKey=telegramApiKey)
        self.credentialResult.setText('Credentials have been saved successfully.')

    def test_telegram(self):
        """
        Tests Telegram connection.
        """
        try:
            telegramApikey = self.telegramApiKey.text()
            Updater(telegramApikey, use_context=True)
            self.telegrationConnectionResult.setText('Connected successfully.')
        except Exception as e:
            self.telegrationConnectionResult.setText(str(e))

    def download_data(self):
        self.backtestInfoLabel.setText("Downloading data...")

    def import_data(self):
        self.backtestInfoLabel.setText("Importing data...")

    def copy_settings_to_simulation(self):
        self.simulationIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.simulationTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())

        self.simulationAverageTypeComboBox.setCurrentIndex(self.averageTypeComboBox.currentIndex())
        self.simulationParameterComboBox.setCurrentIndex(self.parameterComboBox.currentIndex())
        self.simulationInitialValueSpinBox.setValue(self.initialValueSpinBox.value())
        self.simulationFinalValueSpinBox.setValue(self.finalValueSpinBox.value())

        self.simulationDoubleCrossCheckMark.setChecked(self.doubleCrossCheckMark.isChecked())
        self.simulationDoubleAverageComboBox.setCurrentIndex(self.doubleAverageComboBox.currentIndex())
        self.simulationDoubleParameterComboBox.setCurrentIndex(self.doubleParameterComboBox.currentIndex())
        self.simulationDoubleInitialValueSpinBox.setValue(self.doubleInitialValueSpinBox.value())
        self.simulationDoubleFinalValueSpinBox.setValue(self.doubleFinalValueSpinBox.value())

        self.simulationLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.simulationPriceLimitSpinBox.setValue(self.priceLimitSpinBox.value())
        self.simulationStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.simulationTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())

    def copy_settings_to_backtest(self):
        self.backtestIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.backtestTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())

        self.backtestAverageTypeComboBox.setCurrentIndex(self.averageTypeComboBox.currentIndex())
        self.backtestParameterComboBox.setCurrentIndex(self.parameterComboBox.currentIndex())
        self.backtestInitialValueSpinBox.setValue(self.initialValueSpinBox.value())
        self.backtestFinalValueSpinBox.setValue(self.finalValueSpinBox.value())

        self.backtestDoubleCrossCheckMark.setChecked(self.doubleCrossCheckMark.isChecked())
        self.backtestDoubleAverageComboBox.setCurrentIndex(self.doubleAverageComboBox.currentIndex())
        self.backtestDoubleParameterComboBox.setCurrentIndex(self.doubleParameterComboBox.currentIndex())
        self.backtestDoubleInitialValueSpinBox.setValue(self.doubleInitialValueSpinBox.value())
        self.backtestDoubleFinalValueSpinBox.setValue(self.doubleFinalValueSpinBox.value())

        self.backtestLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.backtestStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.backtestTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())

    def toggle_double_cross_groupbox(self):
        self.toggle_groupbox(self.doubleCrossCheckMark, self.doubleCrossGroupBox)

    def toggle_simulation_double_cross_groupbox(self):
        self.toggle_groupbox(self.simulationDoubleCrossCheckMark, self.simulationDoubleCrossGroupBox)

    def toggle_backtest_double_cross_groupbox(self):
        self.toggle_groupbox(self.backtestDoubleCrossCheckMark, self.backtestDoubleCrossGroupBox)

    @staticmethod
    def toggle_groupbox(checkMark, groupBox):
        if checkMark.isChecked():
            groupBox.setEnabled(True)
        else:
            groupBox.setEnabled(False)


class OtherCommands(QDialog):
    def __init__(self, parent=None):
        super(OtherCommands, self).__init__(parent)  # Initializing object
        uic.loadUi(otherCommandsUi, self)  # Loading the main UI

        self.threadPool = QThreadPool()

        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)
        self.movingAverageMiscellaneousParameter.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousType.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousValue.valueChanged.connect(self.initiate_misc_get_moving_average)

    def initiate_misc_get_moving_average(self):
        thread = Worker(self.get_moving_average_miscellaneous)
        self.threadPool.start(thread)

    def get_moving_average_miscellaneous(self):
        self.movingAverageMiscellaneousResult.setText("haha what did you expect?")

    def initiate_csv_generation(self):
        thread = Worker(self.generate_csv)
        self.threadPool.start(thread)

    def generate_csv(self):
        self.generateCSVButton.setEnabled(False)

        symbol = self.csvGenerationTicker.currentText()
        interval = helpers.convert_interval(self.csvGenerationDataInterval.currentText())
        self.csvGenerationStatus.setText("Downloading data...")
        savedPath = Data(loadData=False, interval=interval, symbol=symbol).get_csv_file()

        # messageBox = QMessageBox()
        # messageBox.setText(f"Successfully saved CSV data to {savedPath}.")
        # messageBox.setIcon(QMessageBox.Information)
        # messageBox.exec_()
        self.csvGenerationStatus.setText(f"Successfully saved CSV data to {savedPath}.")
        self.generateCSVButton.setEnabled(True)


class Statistics(QDialog):
    def __init__(self, parent=None):
        super(Statistics, self).__init__(parent)  # Initializing object
        uic.loadUi(statisticsUi, self)  # Loading the main UI


class About(QDialog):
    def __init__(self, parent=None):
        super(About, self).__init__(parent)  # Initializing object
        uic.loadUi(aboutUi, self)  # Loading the main UI


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
