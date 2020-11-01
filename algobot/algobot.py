import assets
import sys
import helpers
import os
import threadWorkers

from data import Data
from datetime import datetime
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
            {'graph': self.liveGraph, 'plots': []},
            {'graph': self.avgGraph, 'plots': []},
            {'graph': self.simulationAvgGraph, 'plots': []},
        )
        self.setup_graphs()  # Setting up graphs
        self.initiate_slots()  # Initiating slots
        self.threadPool.start(threadWorkers.Worker(self.load_tickers))  # Load tickers

        self.advancedLogging = True
        self.runningLive = False
        self.simulationRunningLive = False
        self.backtestRunningLive = False
        self.traders = {SIMULATION: None, LIVE: None}
        self.trader: RealTrader or None = None
        self.simulationTrader: SimulationTrader or None = None
        self.simulationLowerIntervalData: Data or None = None
        self.lowerIntervalData: Data or None = None
        self.telegramBot = None
        self.add_to_live_activity_monitor('Initialized interface.')

    def initiate_live_bot_thread(self):
        """
        Hacky fix to initiate live bot thread. Needs to be optimized.
        """
        worker = threadWorkers.Worker(lambda: self.run_bot(caller=LIVE))
        worker.signals.error.connect(self.end_live_bot_and_create_popup)
        self.threadPool.start(worker)

    def end_live_bot_and_create_popup(self, msg):
        """
        Hacky fix to end live bot thread. Needs to be optimized.
        """
        self.disable_interface(boolean=False, caller=LIVE)
        self.endBotButton.setEnabled(False)
        self.add_to_live_activity_monitor(msg)
        self.create_popup(msg)

    def initiate_simulation_bot_thread(self):
        """
        Hacky fix to initiate simulation bot thread. Needs to be optimized.
        """
        worker = threadWorkers.Worker(lambda: self.run_bot(caller=SIMULATION))
        worker.signals.error.connect(self.end_simulation_bot_and_create_popup)
        self.threadPool.start(worker)

    def end_simulation_bot_and_create_popup(self, msg):
        """
        Hacky fix to end simulation bot thread. Needs to be optimized.
        """
        self.disable_interface(boolean=False, caller=SIMULATION)
        self.endSimulationButton.setEnabled(False)
        self.add_to_simulation_activity_monitor(msg)
        self.create_popup(msg)

    def initiate_bot_thread(self, caller):
        self.disable_interface(True, caller, everything=True)
        worker = threadWorkers.BotThread(gui=self, caller=caller)
        worker.signals.error.connect(self.end_simulation_bot_and_create_popup)
        worker.signals.liveActivity.connect(self.add_to_live_activity_monitor)
        worker.signals.simulationActivity.connect(self.add_to_simulation_activity_monitor)
        worker.signals.started.connect(self.initial_bot_ui_setup)
        worker.signals.updated.connect(self.update_interface_info)
        self.threadPool.start(worker)

    def initial_bot_ui_setup(self, caller):
        trader = self.simulationTrader if caller == SIMULATION else self.trader
        interfaceDict = self.get_interface_dictionary(caller)['mainInterface']
        self.disable_interface(True, caller, False)
        self.enable_override(caller)
        self.clear_table(interfaceDict['historyTable'])
        self.destroy_graph_plots(interfaceDict['graph'])
        self.destroy_graph_plots(interfaceDict['averageGraph'])
        self.setup_graph_plots(interfaceDict['graph'], trader, NET_GRAPH)
        self.setup_graph_plots(interfaceDict['averageGraph'], trader, AVG_GRAPH)
    #
    # TO FIX
    # def end_bot_and_create_popup(self, msg, caller):
    #     self.disable_interface(boolean=False, caller=caller)
    #     self.endBotButton.setEnabled(False)
    #     self.endSimulationButton.setEnabled(False)
    #     self.create_popup(msg)

    def update_data(self, caller):
        """
        Updates data if updated data exists for caller object.
        :param caller: Object type that will be updated.
        """
        if caller == LIVE and not self.trader.dataView.data_is_updated():
            self.add_to_live_activity_monitor('New data found. Updating...')
            self.trader.dataView.update_data()
            self.add_to_live_activity_monitor('Updated data successfully.')
        elif caller == SIMULATION and not self.simulationTrader.dataView.data_is_updated():
            self.add_to_simulation_activity_monitor('New data found. Updating...')
            self.simulationTrader.dataView.update_data()
            self.add_to_simulation_activity_monitor('Updated data successfully.')

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

    # to fix
    def handle_cross_notification(self, caller, notification):
        """
        Handles cross notifications.
        :param caller: Caller object for whom function will handle cross notifications.
        :param notification: Notification boolean whether it is time to notify or not.
        :return: Boolean whether cross should be notified on next function call.
        """
        if caller == SIMULATION:
            if self.simulationTrader.currentPosition is None:
                if not self.simulationTrader.inHumanControl and notification:
                    self.add_to_simulation_activity_monitor("Waiting for a cross.")
                    return False
            else:
                return False
        elif caller == LIVE:
            if self.trader.currentPosition is not None:
                return False
            else:
                if not notification and not self.trader.inHumanControl:
                    self.add_to_live_activity_monitor("Waiting for a cross.")
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
                self.add_to_live_activity_monitor(f'{trends[lowerTrend]} trend detected on lower interval data.')
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
            self.add_to_live_activity_monitor('Started Telegram bot.')
        except InvalidToken:
            self.add_to_live_activity_monitor('Invalid token for Telegram. Please recheck credentials in settings.')

    def automate_trading(self, caller):
        """
        Main function to automate trading.
        :param caller: Caller object to automate trading for.
        """
        # crossNotification = False
        lowerTrend = None
        if caller == LIVE:
            runningLoop = self.runningLive
        elif caller == SIMULATION:
            runningLoop = self.simulationRunningLive
        else:
            raise TypeError("Unknown type of caller specified.")

        while runningLoop:
            try:
                self.update_data(caller=caller)
                self.update_interface_info(caller=caller)
                self.handle_logging(caller=caller)
                self.handle_trailing_prices(caller=caller)
                self.handle_trading(caller=caller)
                # crossNotification = self.handle_cross_notification(caller=caller, notification=crossNotification)
                lowerTrend = self.handle_lower_interval_cross(caller, lowerTrend)
            except Exception as e:
                raise e

    def run_bot(self, caller):
        """
        Runs bot with caller specified.
        :param caller: Type of bot to run - simulation or live.
        """
        self.create_trader(caller)
        self.set_parameters(caller)

        if caller == LIVE:
            trader = self.trader
            if self.configuration.enableTelegramTrading.isChecked():
                self.handle_telegram_bot()
            self.runningLive = True
        elif caller == SIMULATION:
            trader = self.simulationTrader
            self.simulationRunningLive = True
        else:
            raise RuntimeError("Invalid type of caller specified.")

        self.initial_bot_ui_setup(caller=caller)
        self.automate_trading(caller)

    def end_bot(self, caller):
        """
        Ends bot based on caller.
        :param caller: Caller that decides which bot will be ended.
        """
        self.disable_interface(True, caller=caller, everything=True)
        if caller == SIMULATION:
            self.simulationRunningLive = False
            self.simulationTrader.get_simulation_result()
            self.runSimulationButton.setEnabled(True)
            self.endSimulationButton.setEnabled(False)
            self.add_to_simulation_activity_monitor("Ended simulation.")
            tempTrader = self.simulationTrader
            if self.simulationLowerIntervalData is not None:
                self.simulationLowerIntervalData.dump_to_table()
                self.simulationLowerIntervalData = None
        else:
            self.runningLive = False
            self.endBotButton.setEnabled(False)
            self.runBotButton.setEnabled(True)
            self.telegramBot.stop()
            self.add_to_live_activity_monitor('Killed Telegram bot.')
            self.add_to_live_activity_monitor("Killed bot.")
            tempTrader = self.trader
            if self.lowerIntervalData is not None:
                self.lowerIntervalData.dump_to_table()
                self.lowerIntervalData = None

        tempTrader.log_trades()
        self.disable_override(caller)
        self.update_trades_table_and_activity_monitor(caller)
        self.disable_interface(False, caller=caller)
        tempTrader.dataView.dump_to_table()
        # self.destroy_trader(caller)

    def destroy_trader(self, caller):
        """
        Destroys trader based on caller by setting them equal to none.
        :param caller: Caller that determines which trading object gets destroyed.
        """
        if caller == SIMULATION:
            self.simulationTrader = None
        elif caller == LIVE:
            self.trader = None
        elif caller == BACKTEST:
            pass
        else:
            raise ValueError("invalid caller type specified.")

    def create_trader(self, caller):
        """
        Creates a trader based on caller.
        :param caller: Caller object that will determine what type of trader is created.
        """
        if caller == SIMULATION:
            symbol = self.configuration.simulationTickerComboBox.currentText()
            interval = helpers.convert_interval(self.configuration.simulationIntervalComboBox.currentText())
            startingBalance = self.configuration.simulationStartingBalanceSpinBox.value()
            self.add_to_simulation_activity_monitor(f"Retrieving data for interval {interval}...")
            self.simulationTrader = SimulationTrader(startingBalance=startingBalance,
                                                     symbol=symbol,
                                                     interval=interval,
                                                     loadData=True)
            self.add_to_simulation_activity_monitor("Retrieved data successfully.")
        elif caller == LIVE:
            symbol = self.configuration.tickerComboBox.currentText()
            interval = helpers.convert_interval(self.configuration.intervalComboBox.currentText())
            apiSecret = self.configuration.binanceApiSecret.text()
            apiKey = self.configuration.binanceApiKey.text()
            if len(apiSecret) == 0:
                raise ValueError('Please specify an API secret key. No API secret key found.')
            elif len(apiKey) == 0:
                raise ValueError("Please specify an API key. No API key found.")
            self.add_to_live_activity_monitor(f"Retrieving data for interval {interval}...")
            self.trader = RealTrader(apiSecret=apiSecret, apiKey=apiKey, interval=interval, symbol=symbol)
            self.add_to_live_activity_monitor("Retrieved data successfully.")
        else:
            raise ValueError("Invalid caller.")

        self.initialize_lower_interval_trading(caller=caller, interval=interval)

    def initialize_lower_interval_trading(self, caller, interval):
        """
        Initializes lower interval trading data object.
        :param caller: Caller that determines whether lower interval is for simulation or live bot.
        :param interval: Current interval for simulation or live bot.
        """
        sortedIntervals = ('1m', '3m', '5m', '15m', '30m', '1h', '2h', '12h', '4h', '6h', '8h', '1d', '3d')
        if interval != '1m':
            lowerInterval = sortedIntervals[sortedIntervals.index(interval) - 1]
            if caller == LIVE:
                self.add_to_live_activity_monitor(f'Retrieving data for lower interval {lowerInterval}...')
                self.lowerIntervalData = Data(lowerInterval)
                self.add_to_live_activity_monitor('Retrieved lower interval data successfully.')
            else:
                self.add_to_simulation_activity_monitor(f'Retrieving data for lower interval {lowerInterval}...')
                self.simulationLowerIntervalData = Data(lowerInterval)
                self.add_to_simulation_activity_monitor("Retrieved lower interval data successfully.")

    def set_parameters(self, caller):
        """
        Retrieves moving average options and loss settings based on caller.
        :param caller: Caller that dictates which parameters get set.
        :return:
        """
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
        """
        Sets logging standard.
        :param boolean: Boolean that will determine whether logging is advanced or not. If true, advanced, else regular.
        """
        if self.advancedLogging:
            self.add_to_live_activity_monitor(f'Logging method has been changed to advanced.')
        else:
            self.add_to_live_activity_monitor(f'Logging method has been changed to simple.')
        self.advancedLogging = boolean

    def disable_interface(self, boolean, caller, everything=False):
        """
        Function that will control trading configuration interfaces.
        :param everything: Disables everything during initialization.
        :param boolean: If true, configuration settings get disabled.
        :param caller: Caller that determines which configuration settings get disabled.
        """
        boolean = not boolean
        interfaceDict = self.get_interface_dictionary(caller=caller)
        interfaceDict['configuration']['mainConfigurationTabWidget'].setEnabled(boolean)
        interfaceDict['mainInterface']['runBotButton'].setEnabled(boolean)
        if not everything:
            interfaceDict['mainInterface']['endBotButton'].setEnabled(not boolean)
        else:
            interfaceDict['mainInterface']['endBotButton'].setEnabled(boolean)

    def update_statistics(self, interfaceDictionary: dict, trader):
        """
        Main function that will update interface with information based on interface dictionary and trader.
        :param trader: Trader object used to determine statistics.
        :param interfaceDictionary: Dictionary that will dictate that QT objects are updated.
        """
        net = trader.get_net()
        profit = trader.get_profit()
        stopLoss = trader.get_stop_loss()
        percentage = trader.get_profit_percentage(trader.startingBalance, net)

        currentPriceString = f'${trader.dataView.get_current_price()}'
        percentageString = f'{round(percentage, 2)}%'
        profitString = f'${abs(round(profit, 2))}'
        netString = f'${round(net, 2)}'

        # These are for statistics window.
        statisticsDictionary = interfaceDictionary['statistics']
        statisticsDictionary['startingBalanceValue'].setText(f'${round(trader.startingBalance, 2)}')
        statisticsDictionary['currentBalanceValue'].setText(f'${round(trader.balance, 2)}')
        statisticsDictionary['netValue'].setText(netString)
        statisticsDictionary['profitLossLabel'].setText(trader.get_profit_or_loss_string(profit=profit))
        statisticsDictionary['profitLossValue'].setText(profitString)
        statisticsDictionary['percentageValue'].setText(percentageString)
        statisticsDictionary['tradesMadeValue'].setText(str(len(trader.trades)))
        statisticsDictionary['coinOwnedLabel'].setText(f'{trader.coinName} Owned')
        statisticsDictionary['coinOwnedValue'].setText(f'{round(trader.coin, 6)}')
        statisticsDictionary['coinOwedLabel'].setText(f'{trader.coinName} Owed')
        statisticsDictionary['coinOwedValue'].setText(f'{round(trader.coinOwed, 6)}')
        statisticsDictionary['currentTickerLabel'].setText(str(trader.dataView.symbol))
        statisticsDictionary['currentTickerValue'].setText(currentPriceString)
        statisticsDictionary['lossPointLabel'].setText(trader.get_stop_loss_strategy_string())
        statisticsDictionary['lossPointValue'].setText(trader.get_safe_rounded_string(stopLoss))
        statisticsDictionary['customStopPointValue'].setText(trader.get_safe_rounded_string(trader.customStopLoss))
        statisticsDictionary['currentPositionValue'].setText(trader.get_position_string())
        statisticsDictionary['autonomousValue'].setText(str(not trader.inHumanControl))

        # These are for main interface window.
        mainInterfaceDictionary = interfaceDictionary['mainInterface']
        mainInterfaceDictionary['profitLabel'].setText(trader.get_profit_or_loss_string(profit=profit))
        mainInterfaceDictionary['profitValue'].setText(profitString)
        mainInterfaceDictionary['percentageValue'].setText(percentageString)
        mainInterfaceDictionary['netTotalValue'].setText(netString)
        mainInterfaceDictionary['tickerLabel'].setText(trader.symbol)
        mainInterfaceDictionary['tickerValue'].setText(currentPriceString)

        if trader == self.simulationTrader:
            self.update_simulation_graphs(net=net)
        elif trader == self.trader:
            self.update_live_graphs(net=net)

    def update_interface_info(self, caller, statDict):
        """
        Updates interface elements based on caller.
        :param statDict: Dictionary containing statistics.
        :param caller: Object that determines which object gets updated.
        """
        if caller == SIMULATION:
            trader = self.simulationTrader
        elif caller == LIVE:
            trader = self.trader
        else:
            raise TypeError("Invalid type of caller specified.")

        interfaceDict = self.get_interface_dictionary(caller)
        # self.update_statistics(interfaceDict, trader=trader)
        self.update_statistics_testing(interfaceDict, statDict=statDict, caller=caller)
        self.update_trades_table_and_activity_monitor(caller=caller)
        self.handle_position_buttons(caller=caller)

    # noinspection DuplicatedCode
    def update_statistics_testing(self, interfaceDictionary, statDict, caller):
        statisticsDictionary = interfaceDictionary['statistics']
        statisticsDictionary['startingBalanceValue'].setText(statDict['startingBalanceValue'])
        statisticsDictionary['currentBalanceValue'].setText(statDict['currentBalanceValue'])
        statisticsDictionary['netValue'].setText(statDict['netValue'])
        statisticsDictionary['profitLossLabel'].setText(statDict['profitLossLabel'])
        statisticsDictionary['profitLossValue'].setText(statDict['profitLossValue'])
        statisticsDictionary['percentageValue'].setText(statDict['percentageValue'])
        statisticsDictionary['tradesMadeValue'].setText(statDict['tradesMadeValue'])
        statisticsDictionary['coinOwnedLabel'].setText(statDict['coinOwnedLabel'])
        statisticsDictionary['coinOwnedValue'].setText(statDict['coinOwnedValue'])
        statisticsDictionary['coinOwedLabel'].setText(statDict['coinOwedLabel'])
        statisticsDictionary['coinOwedValue'].setText(statDict['coinOwedValue'])
        statisticsDictionary['currentTickerLabel'].setText(statDict['tickerLabel'])
        statisticsDictionary['currentTickerValue'].setText(statDict['tickerValue'])
        statisticsDictionary['lossPointLabel'].setText(statDict['lossPointLabel'])
        statisticsDictionary['lossPointValue'].setText(statDict['lossPointLabel'])
        statisticsDictionary['customStopPointValue'].setText(statDict['customStopPointValue'])
        statisticsDictionary['currentPositionValue'].setText(statDict['currentPositionValue'])
        statisticsDictionary['autonomousValue'].setText(statDict['autonomousValue'])

        # These are for main interface window.
        mainInterfaceDictionary = interfaceDictionary['mainInterface']
        mainInterfaceDictionary['profitLabel'].setText(statDict['profitLossLabel'])
        mainInterfaceDictionary['profitValue'].setText(statDict['profitLossValue'])
        mainInterfaceDictionary['percentageValue'].setText(statDict['percentageValue'])
        mainInterfaceDictionary['netTotalValue'].setText(statDict['netValue'])
        mainInterfaceDictionary['tickerLabel'].setText(statDict['tickerLabel'])
        mainInterfaceDictionary['tickerValue'].setText(statDict['tickerValue'])

        net = statDict['net']
        optionDetails = statDict['optionDetails']
        self.update_graphs(net=net, caller=caller, optionDetails=optionDetails)

        # net = statDict['net']
        # if trader == self.simulationTrader:
        #     self.update_simulation_graphs(net=net)
        # elif trader == self.trader:
        #     self.update_live_graphs(net=net)

    # noinspection DuplicatedCode
    def get_interface_dictionary(self, caller):
        """
        Returns dictionary of objects from QT. Used for DRY principles.
        :param caller: Caller that will determine which sub dictionary gets returned.
        :return: Dictionary of objects.
        """
        interfaceDictionary = {
            SIMULATION: {
                'statistics': {
                    'startingBalanceValue': self.statistics.simulationStartingBalanceValue,
                    'currentBalanceValue': self.statistics.simulationCurrentBalanceValue,
                    'netValue': self.statistics.simulationNetValue,
                    'profitLossLabel': self.statistics.simulationProfitLossLabel,
                    'profitLossValue': self.statistics.simulationProfitLossValue,
                    'percentageValue': self.statistics.simulationPercentageValue,
                    'tradesMadeValue': self.statistics.simulationTradesMadeValue,
                    'coinOwnedLabel': self.statistics.simulationCoinOwnedLabel,
                    'coinOwnedValue': self.statistics.simulationCoinOwnedValue,
                    'coinOwedLabel': self.statistics.simulationCoinOwedLabel,
                    'coinOwedValue': self.statistics.simulationCoinOwedValue,
                    'currentTickerLabel': self.statistics.simulationCurrentTickerLabel,
                    'currentTickerValue': self.statistics.simulationCurrentTickerValue,
                    'lossPointLabel': self.statistics.simulationLossPointLabel,
                    'lossPointValue': self.statistics.simulationLossPointValue,
                    'customStopPointValue': self.statistics.simulationCustomStopPointValue,
                    'currentPositionValue': self.statistics.simulationCurrentPositionValue,
                    'autonomousValue': self.statistics.simulationAutonomousValue,
                    'baseInitialMovingAverageLabel': self.statistics.simulationBaseInitialMovingAverageLabel,
                    'baseInitialMovingAverageValue': self.statistics.simulationBaseInitialMovingAverageValue,
                    'baseFinalMovingAverageLabel': self.statistics.simulationBaseFinalMovingAverageLabel,
                    'baseFinalMovingAverageValue': self.statistics.simulationBaseFinalMovingAverageValue,
                    'nextInitialMovingAverageLabel': self.statistics.simulationNextInitialMovingAverageLabel,
                    'nextInitialMovingAverageValue': self.statistics.simulationNextInitialMovingAverageValue,
                    'nextFinalMovingAverageLabel': self.statistics.simulationNextFinalMovingAverageLabel,
                    'nextFinalMovingAverageValue': self.statistics.simulationNextFinalMovingAverageValue
                },
                'mainInterface': {
                    # Portfolio
                    'profitLabel': self.simulationProfitLabel,
                    'profitValue': self.simulationProfitValue,
                    'percentageValue': self.simulationPercentageValue,
                    'netTotalValue': self.simulationNetTotalValue,
                    'tickerLabel': self.simulationTickerLabel,
                    'tickerValue': self.simulationTickerValue,
                    # Buttons
                    'pauseBotButton': self.pauseBotSimulationButton,
                    'runBotButton': self.runSimulationButton,
                    'endBotButton': self.endSimulationButton,
                    'forceShortButton': self.forceShortSimulationButton,
                    'forceLongButton': self.forceLongSimulationButton,
                    'exitPositionButton': self.exitPositionSimulationButton,
                    'waitOverrideButton': self.waitOverrideSimulationButton,
                    # Override
                    'overrideGroupBox': self.simulationOverrideGroupBox,
                    # Graphs
                    'graph': self.simulationGraph,
                    'averageGraph': self.simulationAvgGraph,
                    # Table
                    'historyTable': self.simulationHistoryTable,
                },
                'configuration': {
                    'baseAverageType': self.configuration.simulationAverageTypeComboBox,
                    'baseParameter':  self.configuration.simulationParameterComboBox,
                    'baseInitialValue':  self.configuration.simulationInitialValueSpinBox,
                    'baseFinalValue': self.configuration.simulationFinalValueSpinBox,
                    'doubleCrossCheck': self.configuration.simulationDoubleCrossCheckMark,
                    'additionalAverageType': self.configuration.simulationDoubleAverageComboBox,
                    'additionalParameter': self.configuration.simulationDoubleParameterComboBox,
                    'additionalInitialValue':  self.configuration.simulationDoubleInitialValueSpinBox,
                    'additionalFinalValue': self.configuration.simulationDoubleFinalValueSpinBox,
                    'trailingLossRadio': self.configuration.simulationTrailingLossRadio,
                    'lossPercentage': self.configuration.simulationLossPercentageSpinBox,
                    'mainConfigurationTabWidget': self.configuration.simulationConfigurationTabWidget,
                }
            },
            LIVE: {
                'statistics': {
                    'startingBalanceValue': self.statistics.startingBalanceValue,
                    'currentBalanceValue': self.statistics.currentBalanceValue,
                    'netValue': self.statistics.netValue,
                    'profitLossLabel': self.statistics.profitLossLabel,
                    'profitLossValue': self.statistics.profitLossValue,
                    'percentageValue': self.statistics.percentageValue,
                    'tradesMadeValue': self.statistics.tradesMadeValue,
                    'coinOwnedLabel': self.statistics.coinOwnedLabel,
                    'coinOwnedValue': self.statistics.coinOwnedValue,
                    'coinOwedLabel': self.statistics.coinOwedLabel,
                    'coinOwedValue': self.statistics.coinOwedValue,
                    'currentTickerLabel': self.statistics.currentTickerLabel,
                    'currentTickerValue': self.statistics.currentTickerValue,
                    'lossPointLabel': self.statistics.lossPointLabel,
                    'lossPointValue': self.statistics.lossPointValue,
                    'customStopPointValue': self.statistics.customStopPointValue,
                    'currentPositionValue': self.statistics.currentPositionValue,
                    'autonomousValue': self.statistics.autonomousValue,
                    'baseInitialMovingAverageLabel': self.statistics.baseInitialMovingAverageLabel,
                    'baseInitialMovingAverageValue': self.statistics.baseInitialMovingAverageValue,
                    'baseFinalMovingAverageLabel': self.statistics.baseFinalMovingAverageLabel,
                    'baseFinalMovingAverageValue': self.statistics.baseFinalMovingAverageValue,
                    'nextInitialMovingAverageLabel': self.statistics.nextInitialMovingAverageLabel,
                    'nextInitialMovingAverageValue': self.statistics.nextInitialMovingAverageValue,
                    'nextFinalMovingAverageLabel': self.statistics.nextFinalMovingAverageLabel,
                    'nextFinalMovingAverageValue': self.statistics.nextFinalMovingAverageValue
                },
                'mainInterface': {
                    # Portfolio
                    'profitLabel': self.profitLabel,
                    'profitValue': self.profitValue,
                    'percentageValue': self.percentageValue,
                    'netTotalValue': self.netTotalValue,
                    'tickerLabel': self.tickerLabel,
                    'tickerValue': self.tickerValue,
                    # Buttons
                    'pauseBotButton': self.pauseBotButton,
                    'runBotButton': self.runBotButton,
                    'endBotButton': self.endBotButton,
                    'forceShortButton': self.forceShortButton,
                    'forceLongButton': self.forceLongButton,
                    'exitPositionButton': self.exitPositionButton,
                    'waitOverrideButton': self.waitOverrideButton,
                    # Override
                    'overrideGroupBox': self.overrideGroupBox,
                    # Graphs
                    'graph': self.liveGraph,
                    'averageGraph': self.avgGraph,
                    # Table
                    'historyTable': self.historyTable,
                },
                'configuration': {
                    'baseAverageType': self.configuration.averageTypeComboBox,
                    'baseParameter': self.configuration.parameterComboBox,
                    'baseInitialValue': self.configuration.initialValueSpinBox,
                    'baseFinalValue': self.configuration.finalValueSpinBox,
                    'doubleCrossCheck': self.configuration.doubleCrossCheckMark,
                    'additionalAverageType': self.configuration.doubleAverageComboBox,
                    'additionalParameter': self.configuration.doubleParameterComboBox,
                    'additionalInitialValue': self.configuration.doubleInitialValueSpinBox,
                    'additionalFinalValue': self.configuration.doubleFinalValueSpinBox,
                    'trailingLossRadio': self.configuration.trailingLossRadio,
                    'lossPercentage': self.configuration.lossPercentageSpinBox,
                    'mainConfigurationTabWidget': self.configuration.mainConfigurationTabWidget,
                }
            },
            BACKTEST: {
                'configuration': {
                    'baseAverageType': self.configuration.backtestAverageTypeComboBox,
                    'baseParameter':  self.configuration.backtestParameterComboBox,
                    'baseInitialValue':  self.configuration.backtestInitialValueSpinBox,
                    'baseFinalValue': self.configuration.backtestFinalValueSpinBox,
                    'doubleCrossCheck': self.configuration.backtestDoubleCrossCheckMark,
                    'additionalAverageType': self.configuration.backtestDoubleAverageComboBox,
                    'additionalParameter': self.configuration.backtestDoubleParameterComboBox,
                    'additionalInitialValue':  self.configuration.backtestDoubleInitialValueSpinBox,
                    'additionalFinalValue': self.configuration.backtestDoubleFinalValueSpinBox,
                    'trailingLossRadio': self.configuration.backtestTrailingLossRadio,
                    'lossPercentage': self.configuration.backtestLossPercentageSpinBox,
                    'mainConfigurationTabWidget': self.configuration.backtestConfigurationTabWidget
                },
                'mainInterface': {
                    'runBotButton': self.runBacktestButton,
                    'endBotButton': self.endBacktestButton
                }
            }
        }
        return interfaceDictionary[caller]

    def update_graphs(self, net: float, caller: int, optionDetails: list):
        interfaceDict = self.get_interface_dictionary(caller=caller)
        currentUTC = datetime.utcnow().timestamp()
        self.add_data_to_plot(interfaceDict['mainInterface']['graph'], 0, currentUTC, net)

        if len(optionDetails) == 1:
            self.hide_next_moving_averages(caller)

        for index, optionDetail in enumerate(optionDetails):
            initialAverage, finalAverage, initialAverageLabel, finalAverageLabel = optionDetail
            self.add_data_to_plot(interfaceDict['mainInterface']['averageGraph'], index * 2, currentUTC, initialAverage)
            self.add_data_to_plot(interfaceDict['mainInterface']['averageGraph'], index * 2 + 1, currentUTC,
                                  finalAverage)

            if index == 0:
                interfaceDict['statistics']['baseInitialMovingAverageLabel'].setText(initialAverageLabel)
                interfaceDict['statistics']['baseInitialMovingAverageValue'].setText(f'${initialAverage}')
                interfaceDict['statistics']['baseFinalMovingAverageLabel'].setText(finalAverageLabel)
                interfaceDict['statistics']['baseFinalMovingAverageValue'].setText(f'${finalAverage}')
            if index == 1:
                self.show_next_moving_averages(caller=caller)
                interfaceDict['statistics']['nextInitialMovingAverageLabel'].setText(initialAverageLabel)
                interfaceDict['statistics']['nextInitialMovingAverageValue'].setText(f'${initialAverage}')
                interfaceDict['statistics']['nextFinalMovingAverageLabel'].setText(finalAverageLabel)
                interfaceDict['statistics']['nextFinalMovingAverageValue'].setText(f'${finalAverage}')

    def update_live_graphs(self, net):
        """
        Helper function that will update live graphs.
        :param net: Final net value. Passed to function to avoid calling net function.
        """
        trader = self.trader
        currentUTC = datetime.utcnow().timestamp()
        self.add_data_to_plot(self.liveGraph, 0, currentUTC, net)

        if len(trader.tradingOptions) == 1:
            self.hide_next_moving_averages(LIVE)

        for index, option in enumerate(trader.tradingOptions):
            initialAverage, finalAverage, initialAverageLabel, finalAverageLabel = self.get_option_info(option, trader)
            self.add_data_to_plot(self.avgGraph, index * 2, currentUTC, initialAverage)
            self.add_data_to_plot(self.avgGraph, index * 2 + 1, currentUTC, finalAverage)

            if index == 0:
                self.statistics.baseInitialMovingAverageLabel.setText(initialAverageLabel)
                self.statistics.baseInitialMovingAverageValue.setText(f'${initialAverage}')
                self.statistics.baseFinalMovingAverageLabel.setText(finalAverageLabel)
                self.statistics.baseFinalMovingAverageValue.setText(f'${finalAverage}')

            if index == 1:
                self.show_next_moving_averages(LIVE)
                self.statistics.nextInitialMovingAverageLabel.setText(initialAverageLabel)
                self.statistics.nextInitialMovingAverageValue.setText(f'${initialAverage}')
                self.statistics.nextFinalMovingAverageLabel.setText(finalAverageLabel)
                self.statistics.nextFinalMovingAverageValue.setText(f'${finalAverage}')

    def update_simulation_graphs(self, net):
        """
        Helper function that will update simulation graphs.
        :param net: Final net value. Passed to function to avoid calling net function.
        """
        trader = self.simulationTrader
        currentUTC = datetime.utcnow().timestamp()
        self.add_data_to_plot(self.simulationGraph, 0, currentUTC, net)

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
                    self.hide_next_moving_averages(SIMULATION)

            if index > 0:
                self.show_next_moving_averages(SIMULATION)
                self.statistics.simulationNextInitialMovingAverageLabel.setText(initialAverageLabel)
                self.statistics.simulationNextInitialMovingAverageValue.setText(f'${initialAverage}')
                self.statistics.simulationNextFinalMovingAverageLabel.setText(finalAverageLabel)
                self.statistics.nextFinalMovingAverageValue.setText(f'${finalAverage}')

    def show_next_moving_averages(self, caller):
        """
        :param caller: Caller that will decide which statistics get shown..
        Shows next moving averages statistics based on caller.
        """
        interfaceDict = self.get_interface_dictionary(caller)['statistics']
        interfaceDict['nextInitialMovingAverageLabel'].show()
        interfaceDict['nextInitialMovingAverageValue'].show()
        interfaceDict['nextFinalMovingAverageLabel'].show()
        interfaceDict['nextFinalMovingAverageValue'].show()

    def hide_next_moving_averages(self, caller):
        """
        :param caller: Caller that will decide which statistics get hidden.
        Hides next moving averages statistics based on caller.
        """
        interfaceDict = self.get_interface_dictionary(caller)['statistics']
        interfaceDict['nextInitialMovingAverageLabel'].hide()
        interfaceDict['nextInitialMovingAverageValue'].hide()
        interfaceDict['nextFinalMovingAverageLabel'].hide()
        interfaceDict['nextFinalMovingAverageValue'].hide()

    def enable_override(self, caller):
        """
        Enables override interface for which caller specifies.
        :param caller: Caller that will specify which interface will have its override interface enabled.
        """
        interfaceDict = self.get_interface_dictionary(caller)
        interfaceDict['mainInterface']['overrideGroupBox'].setEnabled(True)

    def disable_override(self, caller):
        """
        Disables override interface for which caller specifies.
        :param caller: Caller that will specify which interface will have its override interface disabled.
        """
        interfaceDict = self.get_interface_dictionary(caller)
        interfaceDict['mainInterface']['overrideGroupBox'].setEnabled(False)

    def exit_position(self, caller, humanControl=True):
        """
        Exits position by either giving up control or not. If the boolean humanControl is true, bot gives up control.
        If the boolean is false, the bot still retains control, but exits trade and waits for opposite trend.
        :param humanControl: Boolean that will specify whether bot gives up control or not.
        :param caller: Caller that will specify which trader will exit position.
        """
        if caller == LIVE:
            trader = self.trader
        elif caller == SIMULATION:
            trader = self.simulationTrader
        else:
            raise ValueError("Invalid caller specified.")

        interfaceDict = self.get_interface_dictionary(caller)['mainInterface']
        if humanControl:
            interfaceDict['pauseBotButton'].setText('Resume Bot')
        else:
            interfaceDict['pauseBotButton'].setText('Pause Bot')
        interfaceDict['forceShortButton'].setEnabled(True)
        interfaceDict['forceLongButton'].setEnabled(True)
        interfaceDict['exitPositionButton'].setEnabled(False)
        interfaceDict['waitOverrideButton'].setEnabled(False)

        trader.inHumanControl = humanControl
        if trader.currentPosition == LONG:
            if humanControl:
                trader.sell_long('Force exited long.', force=True)
            else:
                trader.sell_long('Exited long because of override and resuming autonomous logic.', force=True)
        elif trader.currentPosition == SHORT:
            if humanControl:
                trader.buy_short('Force exited short.', force=True)
            else:
                trader.buy_short('Exited short because of override and resuming autonomous logic.', force=True)

    def force_long(self, caller):
        """
        Forces bot to take long position and gives up its control until bot is resumed.
        :param caller: Caller that will determine with trader will force long.
        """
        if caller == SIMULATION:
            trader = self.simulationTrader
            self.add_to_simulation_activity_monitor('Forced long and stopped autonomous logic.')
        elif caller == LIVE:
            trader = self.trader
            self.add_to_live_activity_monitor('Forced long and stopping autonomous logic.')
        else:
            raise ValueError("Invalid type of caller specified.")

        interfaceDict = self.get_interface_dictionary(caller)['mainInterface']
        interfaceDict['pauseBotButton'].setText('Resume Bot')
        interfaceDict['forceShortButton'].setEnabled(True)
        interfaceDict['forceLongButton'].setEnabled(False)
        interfaceDict['exitPositionButton'].setEnabled(True)
        interfaceDict['waitOverrideButton'].setEnabled(True)

        trader.inHumanControl = True
        if trader.currentPosition == SHORT:
            trader.buy_short('Exited short because long was forced.', force=True)
        trader.buy_long('Force executed long.', force=True)

    def force_short(self, caller):
        """
        Forces bot to take short position and gives up its control until bot is resumed.
        :param caller: Caller that will determine with trader will force short.
        """
        if caller == SIMULATION:
            trader = self.simulationTrader
            self.add_to_simulation_activity_monitor('Forcing short and stopping autonomous logic.')
        elif caller == LIVE:
            trader = self.trader
            self.add_to_live_activity_monitor('Forced short and stopped autonomous logic.')
        else:
            raise ValueError("Invalid type of caller specified.")

        interfaceDict = self.get_interface_dictionary(caller)['mainInterface']
        interfaceDict['pauseBotButton'].setText('Resume Bot')
        interfaceDict['forceShortButton'].setEnabled(False)
        interfaceDict['forceLongButton'].setEnabled(True)
        interfaceDict['exitPositionButton'].setEnabled(True)
        interfaceDict['waitOverrideButton'].setEnabled(True)

        trader.inHumanControl = True
        if trader.currentPosition == LONG:
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
                self.add_to_live_activity_monitor('Pausing bot logic.')
            else:
                self.trader.inHumanControl = False
                self.pauseBotButton.setText('Pause Bot')
                self.add_to_live_activity_monitor('Resuming bot logic.')
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

    def get_trading_options(self, caller) -> list:
        """
        Returns trading options based on caller specified.
        :param caller: Caller object that will determine which trading options are returned.
        :return: Trading options based on caller.
        """
        configDictionary = self.get_interface_dictionary(caller)['configuration']
        baseAverageType = configDictionary['baseAverageType'].currentText()
        baseParameter = configDictionary['baseParameter'].currentText().lower()
        baseInitialValue = configDictionary['baseInitialValue'].value()
        baseFinalValue = configDictionary['baseFinalValue'].value()
        options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]

        if configDictionary['doubleCrossCheck'].isChecked():
            additionalAverageType = configDictionary['additionalAverageType'].currentText()
            additionalParameter = configDictionary['additionalParameter'].currentText().lower()
            additionalInitialValue = configDictionary['additionalInitialValue'].value()
            additionalFinalValue = configDictionary['additionalFinalValue'].value()
            option = Option(additionalAverageType, additionalParameter, additionalInitialValue, additionalFinalValue)
            options.append(option)

        return options

    def get_loss_settings(self, caller) -> tuple:
        """
        Returns loss settings for caller specified.
        :param caller: Caller for which loss settings will be returned.
        :return: Tuple with stop loss type and loss percentage.
        """
        configDictionary = self.get_interface_dictionary(caller)['configuration']
        if configDictionary['trailingLossRadio'].isChecked():
            return TRAILING_LOSS, configDictionary['lossPercentage'].value() / 100
        return STOP_LOSS, configDictionary['lossPercentage'].value() / 100

    @staticmethod
    def get_option_info(option: Option, trader) -> tuple:
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

    def closeEvent(self, event):
        """
        Close event override. Makes user confirm they want to end program if something is running live.
        :param event: close event
        """
        qm = QMessageBox
        ret = qm.question(self, 'Close?', "Are you sure to end AlgoBot?",
                          qm.Yes | qm.No)

        if ret == qm.Yes:
            for thread in self.threadPool:
                thread.threadactive = False
                thread.wait()
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
            elif graph == self.liveGraph:
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
        Resets graph plots for graph provided. Does not do anything. Fixing needed.
        :param targetGraph: Graph to destroy plots for.
        """
        for graph in self.graphs:
            if graph['graph'] == targetGraph:
                graph['graph'].clear()
                graph['plots'] = []

    def setup_net_graph_plot(self, graph: PlotWidget, trader, color: str):
        """
        Sets up net balance plot for graph provided.
        :param trader: Type of trader that will use this graph.
        :param graph: Graph where plot will be setup.
        :param color: Color plot will be setup in.
        """
        net = trader.startingBalance
        currentDateTimestamp = datetime.utcnow().timestamp()
        graph.setLimits(xMin=currentDateTimestamp)
        self.append_plot_to_graph(graph, [{
            'plot': self.create_graph_plot(graph, (currentDateTimestamp,), (net,),
                                           color=color, plotName='Net'),
            'x': [currentDateTimestamp],
            'y': [net]
        }])

    def setup_average_graph_plots(self, graph: PlotWidget, trader, colors: list):
        """
        Sets up moving average plots for graph provided.
        :param trader: Type of trader that will use this graph.
        :param graph: Graph where plots will be setup.
        :param colors: List of colors plots will be setup in.
        """
        currentDateTimestamp = datetime.utcnow().timestamp()
        graph.setLimits(xMin=currentDateTimestamp)
        colorCounter = 1
        for option in trader.tradingOptions:
            initialAverage, finalAverage, initialName, finalName = self.get_option_info(option, trader)
            initialPlotDict = {
                'plot': self.create_graph_plot(graph, (currentDateTimestamp,), (initialAverage,),
                                               color=colors[colorCounter], plotName=initialName),
                'x': [currentDateTimestamp],
                'y': [initialAverage]
            }
            secondaryPlotDict = {
                'plot': self.create_graph_plot(graph, (currentDateTimestamp,), (finalAverage,),
                                               color=colors[colorCounter + 1], plotName=finalName),
                'x': [currentDateTimestamp],
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
        if graphType == NET_GRAPH:
            self.setup_net_graph_plot(graph=graph, trader=trader, color=colors[0])
        elif graphType == AVG_GRAPH:
            self.setup_average_graph_plots(graph=graph, trader=trader, colors=colors)
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
        Creates a graph plot with parameters provided.
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
        Initial function made to test table functionality in QT.
        :param table: Table to insert row at.
        :param trade: Trade information to add.
        """
        rowPosition = table.rowCount()
        columns = table.columnCount()

        table.insertRow(rowPosition)
        for column in range(columns):
            table.setItem(rowPosition, column, QTableWidgetItem(str(trade[column])))

    def add_to_monitor(self, caller, message):
        if caller == SIMULATION:
            self.add_to_simulation_activity_monitor(message)
        elif caller == LIVE:
            self.add_to_live_activity_monitor(message)

    def add_to_simulation_activity_monitor(self, message: str):
        """
        Function that adds activity information to the simulation activity monitor.
        :param message: Message to add to simulation activity log.
        """
        self.add_to_table(self.simulationActivityMonitor, [message])

    def add_to_live_activity_monitor(self, message: str):
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
                    self.add_to_live_activity_monitor(trade['action'])
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
        self.runBotButton.clicked.connect(self.initiate_live_bot_thread)
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
        if 'list index out of range' in msg:
            pair = self.configuration.tickerComboBox.currentText()
            msg = f'You may not have any assets in the symbol {pair}. Please check Binance and try again.'
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
