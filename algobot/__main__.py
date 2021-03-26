import os
import sys
import time
import webbrowser
from datetime import datetime
from typing import Dict, List, Union

from PyQt5 import uic
from PyQt5.QtCore import QRunnable, QThreadPool
from PyQt5.QtGui import QIcon, QTextCursor
from PyQt5.QtWidgets import (QApplication, QFileDialog, QMainWindow,
                             QMessageBox, QTableWidgetItem)
from pyqtgraph import InfiniteLine, PlotWidget, mkPen

import algobot.assets
from algobot.algodict import get_interface_dictionary
from algobot.data import Data
from algobot.enums import (AVG_GRAPH, BACKTEST, LIVE, LONG, NET_GRAPH, SHORT,
                           SIMULATION)
from algobot.helpers import (ROOT_DIR, create_folder_if_needed, get_logger,
                             open_file_or_folder)
from algobot.interface.about import About
from algobot.interface.configuration import Configuration
from algobot.interface.otherCommands import OtherCommands
from algobot.interface.palettes import (bloomberg_palette, dark_palette,
                                        green_palette, light_palette,
                                        red_palette)
from algobot.interface.statistics import Statistics
from algobot.option import Option
from algobot.scrapeNews import scrape_news
from algobot.threads import backtestThread, botThread, listThread, workerThread
from algobot.traders.backtester import Backtester
from algobot.traders.realtrader import RealTrader
from algobot.traders.simulationtrader import SimulationTrader

app = QApplication(sys.argv)
mainUi = os.path.join(ROOT_DIR, 'UI', 'algobot.ui')


class Interface(QMainWindow):
    """
        Main Algobot interface.
        Algobot currently supports trading with live bots, running simulations, and running backtests.
    """

    def __init__(self, parent=None):
        algobot.assets.qInitResources()
        super(Interface, self).__init__(parent)  # Initializing object
        uic.loadUi(mainUi, self)  # Loading the main UI
        self.logger = get_logger(logFile='algobot', loggerName='algobot')
        self.configuration = Configuration(parent=self, logger=self.logger)  # Loading configuration
        self.otherCommands = OtherCommands(self)  # Loading other commands
        self.about = About(self)  # Loading about information
        self.statistics = Statistics(self)  # Loading statistics
        self.threadPool = QThreadPool(self)  # Initiating threading pool
        self.threads: Dict[int, QRunnable or None] = {BACKTEST: None, SIMULATION: None, LIVE: None}
        self.graphs = (
            {'graph': self.simulationGraph, 'plots': [], 'label': self.simulationCoordinates, 'enable': True},
            {'graph': self.backtestGraph, 'plots': [], 'label': self.backtestCoordinates, 'enable': True},
            {'graph': self.liveGraph, 'plots': [], 'label': self.liveCoordinates, 'enable': True},
            {'graph': self.avgGraph, 'plots': [], 'label': self.liveAvgCoordinates, 'enable': True},
            {'graph': self.simulationAvgGraph, 'plots': [], 'label': self.simulationAvgCoordinates, 'enable': True},
        )
        self.graphLeeway = 10  # Amount of points to set extra for graph limits.
        self.setup_graphs()  # Setting up graphs.
        self.initiate_slots()  # Initiating slots.

        self.interfaceDictionary = get_interface_dictionary(self)
        self.advancedLogging = False
        self.runningLive = False
        self.simulationRunningLive = False
        self.backtester: Union[Backtester, None] = None
        self.trader: Union[RealTrader, None] = None
        self.simulationTrader: Union[SimulationTrader, None] = None
        self.simulationLowerIntervalData: Union[Data, None] = None
        self.lowerIntervalData: Union[Data, None] = None
        self.telegramBot = None
        self.add_to_live_activity_monitor('Initialized interface.')
        self.load_tickers_and_news()
        self.homeTab.setCurrentIndex(0)
        self.configuration.load_state()

        self.graphUpdateSeconds = 1
        self.graphUpdateSchedule: List[float or None] = [None, None]  # LIVE, SIM

    def inform_telegram(self, message):
        """
        Sends a notification to Telegram if some action is taken by the bot.
        :param message: Message to send.
        """
        try:
            chatID = self.configuration.telegramChatID.text()
            if self.configuration.chatPass:
                self.telegramBot.send_message(chatID, message)
        except Exception as e:
            self.logger.exception(str(e))

    def load_tickers_and_news(self):
        """
        Loads tickers and most recent news in their own threads.
        """
        self.tickers_thread()
        self.news_thread()

    def news_thread(self):
        """
        Runs news thread and sets news to GUI.
        """
        self.newsStatusLabel.setText("Retrieving latest news...")
        self.refreshNewsButton.setEnabled(False)
        newsThread = listThread.Worker(scrape_news)
        newsThread.signals.error.connect(self.news_thread_error)
        newsThread.signals.finished.connect(self.setup_news)
        newsThread.signals.restore.connect(lambda: self.refreshNewsButton.setEnabled(True))
        self.threadPool.start(newsThread)

    def news_thread_error(self, e):
        self.newsStatusLabel.setText("Failed to retrieve latest news.")
        if 'www.todayonchain.com' in e:
            self.create_popup('Failed to retrieve latest news due to a connectivity error.')
        else:
            self.create_popup(e)

    def tickers_thread(self):
        """
        Runs ticker thread and sets tickers to GUI.
        """
        self.configuration.serverResult.setText("Updating tickers...")
        self.configuration.updateTickers.setEnabled(False)
        tickerThread = listThread.Worker(self.get_tickers)
        tickerThread.signals.error.connect(self.tickers_thread_error)
        tickerThread.signals.finished.connect(self.setup_tickers)
        tickerThread.signals.restore.connect(lambda: self.configuration.updateTickers.setEnabled(True))
        self.threadPool.start(tickerThread)

    def tickers_thread_error(self, e):
        self.add_to_live_activity_monitor('Failed to retrieve tickers because of a connectivity issue.')
        if 'api.binance.com' in e:
            self.create_popup('Failed to retrieve tickers because of a connectivity issue.')
        else:
            self.create_popup(e)

    @staticmethod
    def get_tickers() -> list:
        """
        Returns all available tickers from Binance API.
        :return: List of all available tickers.
        """
        tickers = [ticker['symbol'] for ticker in Data(loadData=False, log=False).binanceClient.get_all_tickers()
                   if 'USDT' in ticker['symbol']]

        tickers.sort()
        # tickers.remove("BTCUSDT")
        # tickers.insert(0, 'BTCUSDT')

        return tickers

    def setup_tickers(self, tickers):
        """
        Sets up all available tickers from Binance API and displays them on appropriate combo boxes in application.
        """
        config = self.configuration
        tickerWidgets = [config.tickerComboBox, config.backtestTickerComboBox, config.simulationTickerComboBox,
                         self.otherCommands.csvGenerationTicker]

        for widget in tickerWidgets:
            widget.clear()
            widget.addItems(tickers)

        self.configuration.serverResult.setText("Updated tickers successfully.")

    def setup_news(self, news):
        """
        Sets up all latest available news with news list provided.
        :param news: List of news.
        """
        self.newsTextBrowser.clear()
        for link in news:
            self.newsTextBrowser.append(link)

        now = datetime.now()
        self.newsTextBrowser.moveCursor(QTextCursor.Start)
        self.newsStatusLabel.setText(f'Retrieved news successfully. (Updated: {now.strftime("%m/%d/%Y, %H:%M:%S")})')

    def initiate_backtest(self):
        """
        Initiates backtest based on settings configured. If there is no data configured, prompts user to configure data.
        """
        if self.configuration.data is None:
            self.create_popup("No data setup yet for backtesting. Please configure them in settings first.")
            return

        if not self.check_strategies(BACKTEST):
            return

        self.disable_interface(disable=True, caller=BACKTEST)
        self.threads[BACKTEST] = backtestThread.BacktestThread(gui=self, logger=self.logger)

        worker = self.threads[BACKTEST]
        worker.signals.started.connect(self.setup_backtester)
        worker.signals.activity.connect(self.update_backtest_gui)
        worker.signals.error.connect(self.end_crash_bot_and_create_popup)
        worker.signals.finished.connect(self.end_backtest)
        worker.signals.message.connect(lambda message: self.add_to_monitor(BACKTEST, message))
        worker.signals.restore.connect(lambda: self.disable_interface(disable=False, caller=BACKTEST))
        worker.signals.updateGraphLimits.connect(self.update_backtest_graph_limits)
        self.threadPool.start(worker)

    def end_backtest_thread(self):
        """
        Ends backtest thread if it is running,
        :return: None
        """
        thread = self.threads[BACKTEST]
        if thread:
            thread.stop()

    def end_backtest(self):
        """
        Ends backtest and prompts user if they want to see the results.
        """
        backtestFolderPath = self.create_folder('Backtest Results')
        innerPath = os.path.join(backtestFolderPath, self.backtester.symbol)
        create_folder_if_needed(innerPath, backtestFolderPath)
        defaultFile = os.path.join(innerPath, self.backtester.get_default_result_file_name())
        fileName, _ = QFileDialog.getSaveFileName(self, 'Save Result', defaultFile, 'TXT (*.txt)')
        fileName = fileName.strip()
        fileName = fileName if fileName != '' else None

        if not fileName:
            self.add_to_backtest_monitor('Ended backtest.')
        else:
            path = self.backtester.write_results(resultFile=fileName)
            self.add_to_backtest_monitor(f'Ended backtest and saved results to {path}.')

            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Information)
            msgBox.setText(f"Backtest results have been saved to {path}.")
            msgBox.setWindowTitle("Backtest Results")
            msgBox.setStandardButtons(QMessageBox.Open | QMessageBox.Close)
            if msgBox.exec_() == QMessageBox.Open:
                open_file_or_folder(path)

        self.backtestProgressBar.setValue(100)

    def update_backtest_gui(self, updatedDict: dict):
        """
        Updates activity backtest details to GUI.
        :param updatedDict: Dictionary containing backtest data.
        """
        self.backtestProgressBar.setValue(updatedDict['percentage'])
        net = updatedDict['net']
        utc = updatedDict['utc']

        if net < self.backtester.startingBalance:
            self.backtestProfitLabel.setText("Loss")
            self.backtestProfitPercentageLabel.setText("Loss Percentage")
        else:
            self.backtestProfitLabel.setText("Profit")
            self.backtestProfitPercentageLabel.setText("Profit Percentage")

        self.backtestbalance.setText(updatedDict['balance'])
        self.backtestNet.setText(updatedDict['netString'])
        self.backtestCommissionsPaid.setText(updatedDict['commissionsPaid'])
        self.backtestProfit.setText(updatedDict['profit'])
        self.backtestProfitPercentage.setText(updatedDict['profitPercentage'])
        self.backtestTradesMade.setText(updatedDict['tradesMade'])
        self.backtestCurrentPeriod.setText(updatedDict['currentPeriod'])
        self.add_data_to_plot(self.interfaceDictionary[BACKTEST]['mainInterface']['graph'], 0, y=net, timestamp=utc)

    def update_backtest_configuration_gui(self, statDict: dict):
        """
        Updates backtest interface initial configuration details.
        :param statDict: Dictionary containing configuration details.
        """
        self.backtestSymbol.setText(statDict['symbol'])
        self.backtestStartingBalance.setText(statDict['startingBalance'])
        self.backtestInterval.setText(statDict['interval'])
        self.backtestMarginEnabled.setText(statDict['marginEnabled'])
        self.backtestStopLossPercentage.setText(statDict['stopLossPercentage'])
        self.backtestLossStrategy.setText(statDict['stopLossStrategy'])
        self.backtestStartPeriod.setText(statDict['startPeriod'])
        self.backtestEndPeriod.setText(statDict['endPeriod'])
        if 'options' in statDict:
            self.backtestMovingAverage1.setText(statDict['options'][0][0])
            self.backtestMovingAverage2.setText(statDict['options'][0][1])
            if len(statDict['options']) > 1:
                self.backtestMovingAverage3.setText(statDict['options'][1][0])
                self.backtestMovingAverage4.setText(statDict['options'][1][1])

    def setup_backtester(self, configurationDictionary: dict):
        """
        Set up backtest GUI with dictionary provided.
        :param configurationDictionary: Dictionary with configuration details.
        """
        interfaceDict = self.interfaceDictionary[BACKTEST]['mainInterface']
        symbol = configurationDictionary['symbol']
        interval = configurationDictionary['interval']
        self.destroy_graph_plots(interfaceDict['graph'])
        self.setup_graph_plots(interfaceDict['graph'], self.backtester, NET_GRAPH)
        self.set_backtest_graph_limits_and_empty_plots()
        self.update_backtest_configuration_gui(configurationDictionary)
        self.add_to_backtest_monitor(f"Started backtest with {symbol} data and {interval.lower()} interval periods.")

    def update_backtest_graph_limits(self, limit: int = 105):
        graphDict = self.get_graph_dictionary(self.backtestGraph)
        graphDict['graph'].setLimits(xMin=0, xMax=limit + 1)

    def set_backtest_graph_limits_and_empty_plots(self, limit: int = 105):
        """
        Resets backtest graph and sets x-axis limits.
        """
        initialTimeStamp = self.backtester.data[0]['date_utc'].timestamp()
        graphDict = self.get_graph_dictionary(self.backtestGraph)
        graphDict['graph'].setLimits(xMin=0, xMax=limit)
        plot = graphDict['plots'][0]
        plot['x'] = [0]
        plot['y'] = [self.backtester.startingBalance]
        plot['z'] = [initialTimeStamp]
        plot['plot'].setData(plot['x'], plot['y'])

    def check_strategies(self, caller: int) -> float:
        if not self.configuration.get_strategies(caller):
            qm = QMessageBox
            if caller == BACKTEST:
                message = "No strategies found. Would you like to backtest a hold?"
            elif caller == SIMULATION:
                message = "No strategies found. Did you want to day-trade this simulation?"
            elif caller == LIVE:
                message = "No strategies found. Did you want to day-trade this live bot?"
            else:
                raise ValueError("Invalid type of caller specified.")

            ret = qm.question(self, 'Warning', message, qm.Yes | qm.No)
            return ret == qm.Yes
        return True

    def initiate_bot_thread(self, caller: int):
        """
        Main function that initiates bot thread and handles all data-view logic.
        :param caller: Caller that decides whether a live bot or simulation bot is run.
        """
        if not self.check_strategies(caller):
            return

        self.disable_interface(True, caller)

        worker = botThread.BotThread(gui=self, caller=caller, logger=self.logger)
        worker.signals.smallError.connect(self.create_popup)
        worker.signals.error.connect(self.end_crash_bot_and_create_popup)
        worker.signals.activity.connect(self.add_to_monitor)
        worker.signals.started.connect(self.initial_bot_ui_setup)
        worker.signals.updated.connect(self.update_interface_info)
        worker.signals.progress.connect(self.download_progress_update)
        worker.signals.addTrade.connect(lambda trade: self.update_trades_table_and_activity_monitor(trade, caller))
        worker.signals.restore.connect(lambda: self.disable_interface(disable=False, caller=caller))

        # All these below are for Telegram.
        worker.signals.forceLong.connect(lambda: self.force_long(LIVE))
        worker.signals.forceShort.connect(lambda: self.force_short(LIVE))
        worker.signals.exitPosition.connect(lambda: self.exit_position(LIVE))
        worker.signals.waitOverride.connect(lambda: self.exit_position(LIVE, False))
        worker.signals.pause.connect(lambda: self.pause_or_resume_bot(LIVE))
        worker.signals.resume.connect(lambda: self.pause_or_resume_bot(LIVE))
        worker.signals.setCustomStopLoss.connect(self.set_custom_stop_loss)
        worker.signals.removeCustomStopLoss.connect(lambda: self.set_custom_stop_loss(LIVE, False))
        self.threadPool.start(worker)

    def download_progress_update(self, value, message, caller):
        """
        This will update the GUI with the current download progress.
        :param value: Percentage completed.
        :param message: Message regarding what is currently being done.
        :param caller: Caller that decides which GUI element is updated.
        """
        if caller == SIMULATION:
            self.simulationDownloadProgress.setText(f"Completion: {value}% {message.lower()}")
        elif caller == LIVE:
            self.liveDownloadProgress.setText(f"Completion: {value}% {message.lower()}")
        else:
            raise ValueError("Invalid type of caller specified.")

    def end_bot_thread(self, caller):
        """
        Ends bot based on caller.
        :param caller: Caller that decides which bot will be ended.
        """
        self.disable_interface(True, caller=caller, everything=True)  # Disable everything until everything is done.
        self.enable_override(caller, False)  # Disable overrides.
        thread = workerThread.Worker(lambda: self.end_bot_gracefully(caller=caller))
        thread.signals.error.connect(self.create_popup)
        thread.signals.finished.connect(lambda: self.add_end_bot_status(caller=caller))
        thread.signals.restore.connect(lambda: self.reset_bot_interface(caller=caller))
        self.threadPool.start(thread)

    def add_end_bot_status(self, caller):
        """
        Adds a status update to let user know that bot has been ended.
        :param caller: Caller that'll determine which monitor gets updated.
        """
        if caller == SIMULATION:
            self.add_to_monitor(caller, "Killed simulation bot.")
        else:
            self.add_to_monitor(caller, "Killed bot.")

    def reset_bot_interface(self, caller):
        """
        Resets bot interface based on the caller provided.
        :param caller: Caller that'll determine which interface gets reset.
        """
        self.enable_override(caller, False)
        self.disable_interface(disable=False, caller=caller)

    def end_bot_gracefully(self, caller, callback=None):
        tempTrader = None
        elapsed = time.time()

        if caller == SIMULATION:
            self.simulationRunningLive = False
            if self.simulationTrader:
                self.simulationTrader.dataView.downloadLoop = False

                if self.simulationLowerIntervalData:
                    self.simulationLowerIntervalData.downloadLoop = False

                while not self.simulationTrader.completedLoop:
                    self.simulationRunningLive = False
                    if time.time() > elapsed + 15:
                        break

                tempTrader = self.simulationTrader
                if self.simulationLowerIntervalData:
                    self.simulationLowerIntervalData.dump_to_table()
                    self.simulationLowerIntervalData = None
        elif caller == LIVE:
            self.runningLive = False
            if self.trader:
                self.trader.dataView.downloadLoop = False

                if self.lowerIntervalData:
                    self.lowerIntervalData.downloadLoop = False

                if self.configuration.chatPass:
                    self.telegramBot.send_message(self.configuration.telegramChatID.text(), "Bot has been ended.")
                if self.telegramBot:
                    self.telegramBot.stop()
                    self.telegramBot = None

                while not self.trader.completedLoop:
                    self.runningLive = False
                    if time.time() > elapsed + 15:
                        break

                tempTrader = self.trader
                if self.lowerIntervalData:
                    self.lowerIntervalData.dump_to_table()
                    self.lowerIntervalData = None
        else:
            raise ValueError("Invalid type of caller provided.")

        if callback:
            callback.emit("Dumping data to database...")

        if tempTrader:
            tempTrader.log_trades_and_daily_net()
            tempTrader.dataView.dump_to_table()

        if callback:
            callback.emit("Dumped all new data to database.")

    def end_crash_bot_and_create_popup(self, caller: int, msg: str):
        """
        Function that force ends bot in the event that it crashes.
        """
        if caller == LIVE:
            self.runningLive = False
            if self.lowerIntervalData and not self.lowerIntervalData.downloadCompleted:
                self.download_progress_update(value=0, message="Lower interval data download failed.", caller=caller)
        elif caller == SIMULATION:
            self.simulationRunningLive = False
            if self.simulationLowerIntervalData and not self.simulationLowerIntervalData.downloadCompleted:
                self.download_progress_update(value=0, message="Lower interval data download failed.", caller=caller)

        trader = self.get_trader(caller=caller)
        if trader and caller != BACKTEST and not trader.dataView.downloadCompleted:
            self.download_progress_update(value=0, message="Download failed.", caller=caller)

        if '-1021' in msg:
            msg = msg + ' Please sync your system time.'
        if 'list index out of range' in msg:
            pair = self.configuration.tickerComboBox.currentText()
            msg = f'You may not have any assets in the symbol {pair}. Please check Binance and try again.'
        if 'Chat not found' in msg:
            msg = "Please check your Telegram bot chat ID or turn off Telegram notifications to get rid of this error."
        if "Invalid token" in msg:
            msg = "Please check your Telegram bot token or turn off Telegram integration to get rid of this error."

        self.create_popup_and_emit_message(caller, msg)

    def initial_bot_ui_setup(self, caller):
        """
        Sets up UI based on caller.
        :param caller: Caller that determines which UI gets setup.
        """
        trader = self.get_trader(caller)
        traderPosition = trader.get_position()
        if traderPosition is not None:
            self.add_to_monitor(caller, f"Detected {trader.get_position_string().lower()} position before bot run.")
        interfaceDict = self.interfaceDictionary[caller]['mainInterface']
        self.disable_interface(True, caller, False)
        self.enable_override(caller)
        self.destroy_graph_plots(interfaceDict['graph'])
        self.destroy_graph_plots(interfaceDict['averageGraph'])
        self.statistics.initialize_tab(trader.get_grouped_statistics(), tabType=self.get_caller_string(caller))
        self.setup_graph_plots(interfaceDict['graph'], trader, NET_GRAPH)

        averageGraphDict = self.get_graph_dictionary(interfaceDict['averageGraph'])
        if self.configuration.graphIndicatorsCheckBox.isChecked():
            averageGraphDict['enable'] = True
            self.setup_graph_plots(interfaceDict['averageGraph'], trader, AVG_GRAPH)
        else:
            averageGraphDict['enable'] = False

    def disable_interface(self, disable: bool, caller, everything=False):
        """
        Function that will control trading configuration interfaces.
        :param everything: Disables everything during initialization.
        :param disable: If true, configuration settings get disabled.
        :param caller: Caller that determines which configuration settings get disabled.
        """
        disable = not disable
        self.interfaceDictionary[caller]['configuration']['mainTab'].setEnabled(disable)
        self.interfaceDictionary[caller]['mainInterface']['runBotButton'].setEnabled(disable)

        tab = self.configuration.get_category_tab(caller)
        for strategy_name in self.configuration.strategies.keys():
            self.configuration.strategyDict[tab, strategy_name, 'groupBox'].setEnabled(disable)

        if everything:
            self.interfaceDictionary[caller]['mainInterface']['endBotButton'].setEnabled(disable)
        else:
            self.interfaceDictionary[caller]['mainInterface']['endBotButton'].setEnabled(not disable)

    def update_interface_info(self, caller, valueDict: dict, groupedDict: dict):
        """
        Updates interface elements based on caller.
        :param groupedDict: Dictionary with which to populate the statistics window.
        :param valueDict: Dictionary containing statistics.
        :param caller: Object that determines which object gets updated.
        """
        self.statistics.modify_tab(groupedDict, tabType=self.get_caller_string(caller))
        self.update_main_interface_and_graphs(caller=caller, valueDict=valueDict)
        self.handle_position_buttons(caller=caller)
        self.handle_custom_stop_loss_buttons(caller=caller)

    def update_interface_text(self, caller: int, valueDict: dict):
        """
        Updates interface text based on caller and value dictionary provided.
        :param caller: Caller that decides which interface gets updated.
        :param valueDict: Dictionary with values to populate interface with.
        :return: None
        """
        mainInterfaceDictionary = self.interfaceDictionary[caller]['mainInterface']
        mainInterfaceDictionary['profitLabel'].setText(valueDict['profitLossLabel'])
        mainInterfaceDictionary['profitValue'].setText(valueDict['profitLossValue'])
        mainInterfaceDictionary['percentageValue'].setText(valueDict['percentageValue'])
        mainInterfaceDictionary['netTotalValue'].setText(valueDict['netValue'])
        mainInterfaceDictionary['tickerLabel'].setText(valueDict['tickerLabel'])
        mainInterfaceDictionary['tickerValue'].setText(valueDict['tickerValue'])
        mainInterfaceDictionary['positionValue'].setText(valueDict['currentPositionValue'])

    def update_main_interface_and_graphs(self, caller: int, valueDict: dict):
        """
        Updates main interface GUI elements based on caller.
        :param valueDict: Dictionary with trader values in formatted data types.
        :param caller: Caller that decides which main interface gets updated.
        """
        self.update_interface_text(caller=caller, valueDict=valueDict)
        index = 0 if caller == LIVE else 1
        if self.graphUpdateSchedule[index] is None or time.time() > self.graphUpdateSchedule[index]:
            self.update_main_graphs(caller=caller, valueDict=valueDict)
            self.graphUpdateSchedule[index] = time.time() + self.graphUpdateSeconds

    def update_main_graphs(self, caller, valueDict):
        """
        Updates graphs and moving averages from statistics based on caller.
        :param valueDict: Dictionary with required values.
        :param caller: Caller that decides which graphs get updated.
        """
        precision = self.get_trader(caller=caller).precision
        interfaceDict = self.interfaceDictionary[caller]
        currentUTC = datetime.utcnow().timestamp()
        net = valueDict['net']

        netGraph = interfaceDict['mainInterface']['graph']
        averageGraph = interfaceDict['mainInterface']['averageGraph']

        graphDict = self.get_graph_dictionary(netGraph)
        graphXSize = len(graphDict['plots'][0]['x']) + self.graphLeeway
        netGraph.setLimits(xMin=0, xMax=graphXSize)
        self.add_data_to_plot(netGraph, 0, y=round(net, 2), timestamp=currentUTC)

        averageGraphDict = self.get_graph_dictionary(averageGraph)
        if averageGraphDict['enable']:
            averageGraph.setLimits(xMin=0, xMax=graphXSize)
            for index, optionDetail in enumerate(valueDict['optionDetails']):
                initialAverage, finalAverage = optionDetail[:2]
                self.add_data_to_plot(averageGraph, index * 2, round(initialAverage, precision), currentUTC)
                self.add_data_to_plot(averageGraph, index * 2 + 1, round(finalAverage, precision), currentUTC)

            self.add_data_to_plot(averageGraph, -1, y=round(valueDict['price'], precision), timestamp=currentUTC)

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
            self.backtester = None
        else:
            raise ValueError("invalid caller type specified.")

    def handle_custom_stop_loss_buttons(self, caller):
        """
        Handles GUI elements based on current caller's trading position.
        :param caller: Caller that'll determine which GUI elements get manipulated.
        """
        trader = self.get_trader(caller)
        mainDict = self.interfaceDictionary[caller]['mainInterface']

        if trader.customStopLoss is None:
            mainDict['enableCustomStopLossButton'].setEnabled(True)
            mainDict['disableCustomStopLossButton'].setEnabled(False)
        else:
            mainDict['enableCustomStopLossButton'].setEnabled(False)
            mainDict['disableCustomStopLossButton'].setEnabled(True)

    def handle_position_buttons(self, caller):
        """
        Handles interface position buttons based on caller.
        :param caller: Caller object for whose interface buttons will be affected.
        """
        interfaceDict = self.interfaceDictionary[caller]['mainInterface']
        trader = self.get_trader(caller)

        inPosition = False if trader.currentPosition is None else True
        interfaceDict['exitPositionButton'].setEnabled(inPosition)
        interfaceDict['waitOverrideButton'].setEnabled(inPosition)

        if trader.currentPosition == LONG:
            interfaceDict['forceLongButton'].setEnabled(False)
            interfaceDict['forceShortButton'].setEnabled(True)
        elif trader.currentPosition == SHORT:
            interfaceDict['forceLongButton'].setEnabled(True)
            interfaceDict['forceShortButton'].setEnabled(False)
        elif trader.currentPosition is None:
            interfaceDict['forceLongButton'].setEnabled(True)
            interfaceDict['forceShortButton'].setEnabled(True)

    def enable_override(self, caller, enabled: bool = True):
        """
        Enables override interface for which caller specifies.
        :param enabled: Boolean that determines whether override is enabled or disable. By default, it is enabled.
        :param caller: Caller that will specify which interface will have its override interface enabled.
        """
        self.interfaceDictionary[caller]['mainInterface']['overrideGroupBox'].setEnabled(enabled)
        self.interfaceDictionary[caller]['mainInterface']['customStopLossGroupBox'].setEnabled(enabled)

    def exit_position_thread(self, caller, humanControl):
        """
        Thread that'll take care of exiting position.
        :param caller: Caller that will specify which trader will exit position.
        :param humanControl: Boolean that will specify whether bot gives up control or not.
        """
        trader = self.get_trader(caller)
        trader.inHumanControl = humanControl
        if trader.currentPosition == LONG:
            if humanControl:
                trader.sell_long('Force exited long.', force=True)
            else:
                trader.sell_long('Exited long because of override and resumed autonomous logic.', force=True)
        elif trader.currentPosition == SHORT:
            if humanControl:
                trader.buy_short('Force exited short.', force=True)
            else:
                trader.buy_short('Exited short because of override and resumed autonomous logic.', force=True)
        # self.inform_telegram("Force exited position from GUI.", caller=caller)

    def set_exit_position_gui(self, caller, humanControl):
        """
        This function will configure GUI to reflect exit position aftermath.
        :param caller: Caller that will specify which interface's GUI will change.
        :param humanControl: Boolean that will specify how interface's GUI will change.
        """
        text = "Resume Bot" if humanControl else "Pause Bot"
        self.modify_override_buttons(caller=caller, pauseText=text, shortBtn=True, longBtn=True, exitBtn=False,
                                     waitBtn=False)

    def exit_position(self, caller, humanControl: bool = True):
        """
        Exits position by either giving up control or not. If the boolean humanControl is true, bot gives up control.
        If the boolean is false, the bot still retains control, but exits trade and waits for opposite trend.
        :param humanControl: Boolean that will specify whether bot gives up control or not.
        :param caller: Caller that will specify which trader will exit position.
        """
        self.add_to_monitor(caller, 'Exiting position...')
        thread = workerThread.Worker(lambda: self.exit_position_thread(caller=caller, humanControl=humanControl))
        thread.signals.started.connect(lambda: self.enable_override(caller=caller, enabled=False))
        thread.signals.finished.connect(lambda: self.set_exit_position_gui(caller=caller, humanControl=humanControl))
        thread.signals.restore.connect(lambda: self.enable_override(caller=caller, enabled=True))
        thread.signals.error.connect(self.create_popup)
        self.threadPool.start(thread)

    def set_force_long_gui(self, caller):
        """
        Thread that'll configure GUI to reflect force long aftermath.
        :param caller: Caller that will specify which interface's GUI will change.
        """
        self.modify_override_buttons(caller=caller, pauseText="Resume Bot", shortBtn=True, longBtn=False, exitBtn=True,
                                     waitBtn=True)

    def force_long_thread(self, caller):
        """
        Thread that'll take care of forcing long.
        :param caller: Caller that will specify which trader will force long.
        """
        trader = self.get_trader(caller)
        trader.inHumanControl = True
        if trader.currentPosition == SHORT:
            trader.buy_short('Exited short because long was forced.', force=True)
        trader.buy_long('Force executed long.', force=True)
        trader.reset_smart_stop_loss()
        # self.inform_telegram("Force executed long from GUI.", caller=caller)

    def force_long(self, caller):
        """
        Forces bot to take long position and gives up its control until bot is resumed.
        :param caller: Caller that will determine with trader will force long.
        """
        self.add_to_monitor(caller, 'Forcing long and stopping autonomous logic...')
        thread = workerThread.Worker(lambda: self.force_long_thread(caller=caller))
        thread.signals.started.connect(lambda: self.enable_override(caller=caller, enabled=False))
        thread.signals.finished.connect(lambda: self.set_force_long_gui(caller=caller))
        thread.signals.restore.connect(lambda: self.enable_override(caller=caller, enabled=True))
        thread.signals.error.connect(self.create_popup)
        self.threadPool.start(thread)

    def set_force_short_gui(self, caller):
        """
        Thread that'll configure GUI to reflect force short aftermath.
        :param caller: Caller that will specify which interface's GUI will change.
        """
        self.modify_override_buttons(caller=caller, pauseText="Resume Bot", shortBtn=False, longBtn=True, exitBtn=True,
                                     waitBtn=True)

    def force_short_thread(self, caller):
        """
        Thread that'll take care of forcing short.
        :param caller: Caller that will specify which trader will force short.
        """
        trader = self.get_trader(caller)
        trader.inHumanControl = True
        if trader.currentPosition == LONG:
            trader.sell_long('Exited long because short was forced.', force=True)
        trader.sell_short('Force executed short.', force=True)
        trader.reset_smart_stop_loss()
        # self.inform_telegram("Force executed short from GUI.", caller=caller)

    def force_short(self, caller):
        """
        Forces bot to take short position and gives up its control until bot is resumed.
        :param caller: Caller that will determine with trader will force short.
        """
        self.add_to_monitor(caller, 'Forcing short and stopping autonomous logic...')
        thread = workerThread.Worker(lambda: self.force_short_thread(caller=caller))
        thread.signals.started.connect(lambda: self.enable_override(caller=caller, enabled=False))
        thread.signals.finished.connect(lambda: self.set_force_short_gui(caller=caller))
        thread.signals.restore.connect(lambda: self.enable_override(caller=caller, enabled=True))
        thread.signals.error.connect(self.create_popup)
        self.threadPool.start(thread)

    def modify_override_buttons(self, caller, pauseText, shortBtn, longBtn, exitBtn, waitBtn):
        interfaceDict = self.interfaceDictionary[caller]['mainInterface']
        interfaceDict['pauseBotButton'].setText(pauseText)
        interfaceDict['forceShortButton'].setEnabled(shortBtn)
        interfaceDict['forceLongButton'].setEnabled(longBtn)
        interfaceDict['exitPositionButton'].setEnabled(exitBtn)
        interfaceDict['waitOverrideButton'].setEnabled(waitBtn)

    def pause_or_resume_bot(self, caller):
        """
        Pauses or resumes bot logic based on caller.
        :param caller: Caller object that specifies which trading object will be paused or resumed.
        """
        trader = self.get_trader(caller)
        pauseButton = self.interfaceDictionary[caller]['mainInterface']['pauseBotButton']
        if pauseButton.text() == 'Pause Bot':
            trader.inHumanControl = True
            pauseButton.setText('Resume Bot')
            self.add_to_monitor(caller, 'Pausing bot logic.')
        else:
            trader.inHumanControl = False
            pauseButton.setText('Pause Bot')
            self.add_to_monitor(caller, 'Resuming bot logic.')

    def set_advanced_logging(self, boolean):
        """
        Sets logging standard.
        :param boolean: Boolean that will determine whether logging is advanced or not. If true, advanced, else regular.
        """
        self.advancedLogging = boolean
        if self.advancedLogging:
            self.add_to_live_activity_monitor('Logging method has been changed to advanced.')
            self.add_to_simulation_activity_monitor('Logging method has been changed to advanced.')
        else:
            self.add_to_live_activity_monitor('Logging method has been changed to simple.')
            self.add_to_simulation_activity_monitor('Logging method has been changed to simple.')

    def set_custom_stop_loss(self, caller, enable: bool = True, foreignValue: float or None = None):
        """
        Enables or disables custom stop loss.
        :param foreignValue: Foreign value to set for custom stop loss not related to GUI.
        :param enable: Boolean that determines whether custom stop loss is enabled or disabled. Default is enable.
        :param caller: Caller that decides which trader object gets the stop loss.
        """
        trader = self.get_trader(caller)
        mainDict = self.interfaceDictionary[caller]['mainInterface']
        if enable:
            if foreignValue is None:
                customStopLoss = mainDict['customStopLossValue'].value()
            else:
                customStopLoss = foreignValue
                mainDict['customStopLossValue'].setValue(round(foreignValue, trader.precision))
            trader.customStopLoss = customStopLoss
            mainDict['enableCustomStopLossButton'].setEnabled(False)
            mainDict['disableCustomStopLossButton'].setEnabled(True)
            self.add_to_monitor(caller, f'Set custom stop loss at ${customStopLoss}')
        else:
            trader.customStopLoss = None
            mainDict['enableCustomStopLossButton'].setEnabled(True)
            mainDict['disableCustomStopLossButton'].setEnabled(False)
            self.add_to_monitor(caller, 'Removed custom stop loss.')

    def get_loss_settings(self, caller) -> dict:
        """
        Returns loss settings for caller specified.
        :param caller: Caller for which loss settings will be returned.
        :return: Tuple with stop loss type and loss percentage.
        """
        return self.configuration.get_loss_settings(caller)

    @staticmethod
    def get_option_info(option: Option, trader: SimulationTrader) -> tuple:
        """
        Returns basic information about option provided.
        :param option: Option object for whose information will be retrieved.
        :param trader: Trader object to be used to get averages.
        :return: Tuple of initial average, final average, initial option name, and final option name.
        """
        initialAverage = trader.get_average(option.movingAverage, option.parameter, option.initialBound)
        finalAverage = trader.get_average(option.movingAverage, option.parameter, option.finalBound)
        initialName, finalName = option.get_pretty_option()
        return initialAverage, finalAverage, initialName, finalName

    def setup_graphs(self):
        """
        Sets up all available graphs in application.
        """
        for graphDict in self.graphs:
            graph = graphDict['graph']
            graph.setLimits(xMin=0, xMax=self.graphLeeway, yMin=-1, yMax=1000_000_000_000_000)
            graph.setBackground('w')
            graph.setLabel('left', 'USDT')
            graph.setLabel('bottom', 'Data Points')
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

    def add_data_to_plot(self, targetGraph: PlotWidget, plotIndex: int, y: float, timestamp: float):
        """
        Adds data to plot in provided graph.
        :param targetGraph: Graph to use for plot to add data to.
        :param plotIndex: Index of plot in target graph's list of plots.
        :param y: Y value to add.
        :param timestamp: Timestamp value to add.
        """
        graphDict = self.get_graph_dictionary(targetGraph=targetGraph)
        plot = graphDict['plots'][plotIndex]

        secondsInDay = 86400  # Reset graph every 24 hours (assuming data is updated only once a second).
        if len(plot['x']) >= secondsInDay:
            plot['x'] = [0]
            plot['y'] = [y]
            plot['z'] = [timestamp]
        else:
            plot['x'].append(plot['x'][-1] + 1)
            plot['y'].append(y)
            plot['z'].append(timestamp)
        plot['plot'].setData(plot['x'], plot['y'])

    def append_plot_to_graph(self, targetGraph: PlotWidget, toAdd: list):
        """
        Appends plot to graph provided.
        :param targetGraph: Graph to add plot to.
        :param toAdd: List of plots to add to target graph.
        """
        graphDict = self.get_graph_dictionary(targetGraph=targetGraph)
        graphDict['plots'] += toAdd

    def destroy_graph_plots(self, targetGraph: PlotWidget):
        """
        Resets graph plots for graph provided.
        :param targetGraph: Graph to destroy plots for.
        """
        graphDict = self.get_graph_dictionary(targetGraph=targetGraph)
        graphDict['graph'].clear()
        graphDict['plots'] = []

    def setup_net_graph_plot(self, graph: PlotWidget, trader: SimulationTrader, color: str):
        """
        Sets up net balance plot for graph provided.
        :param trader: Type of trader that will use this graph.
        :param graph: Graph where plot will be setup.
        :param color: Color plot will be setup in.
        """
        net = trader.startingBalance
        currentDateTimestamp = datetime.utcnow().timestamp()
        plot = self.get_plot_dictionary(graph=graph, color=color, y=net, name='Net', timestamp=currentDateTimestamp)

        self.append_plot_to_graph(graph, [plot])

    def setup_average_graph_plots(self, graph: PlotWidget, trader, colors: list):
        """
        Sets up moving average plots for graph provided.
        :param trader: Type of trader that will use this graph.
        :param graph: Graph where plots will be setup.
        :param colors: List of colors plots will be setup in.
        """
        if trader.currentPrice is None:
            trader.currentPrice = trader.dataView.get_current_price()

        currentPrice = trader.currentPrice
        currentDateTimestamp = datetime.utcnow().timestamp()
        colorCounter = 1

        if 'movingAverage' in trader.strategies:
            for option in trader.strategies['movingAverage'].get_params():
                initialAverage, finalAverage, initialName, finalName = self.get_option_info(option, trader)
                initialPlotDict = self.get_plot_dictionary(graph=graph, color=colors[colorCounter % len(colors)],
                                                           y=initialAverage,
                                                           name=initialName, timestamp=currentDateTimestamp)
                secondaryPlotDict = self.get_plot_dictionary(graph=graph,
                                                             color=colors[(colorCounter + 1) % len(colors)],
                                                             y=finalAverage,
                                                             name=finalName, timestamp=currentDateTimestamp)
                colorCounter += 2
                self.append_plot_to_graph(graph, [initialPlotDict, secondaryPlotDict])

        tickerPlotDict = self.get_plot_dictionary(graph=graph, color=colors[0], y=currentPrice, name=trader.symbol,
                                                  timestamp=currentDateTimestamp)
        self.append_plot_to_graph(graph, [tickerPlotDict])

    def get_plot_dictionary(self, graph, color, y, name, timestamp) -> dict:
        """
        Creates a graph plot and returns a dictionary of it.
        :param graph: Graph to add plot to.
        :param color: Color of plot.
        :param y: Y value to start with for plot.
        :param name: Name of plot.
        :param timestamp: First UTC timestamp of plot.
        :return: Dictionary of plot information.
        """
        plot = self.create_graph_plot(graph, (0,), (y,), color=color, plotName=name)
        return {
            'plot': plot,
            'x': [0],
            'y': [y],
            'z': [timestamp],
            'name': name,
        }

    def create_infinite_line(self, graphDict: dict, colors: list = None):
        """
        Creates an infinite (hover) line and adds it as a reference to the graph dictionary provided.
        :param colors: Optional colors list.
        :param graphDict: A reference to this infinite line will be added to this graph dictionary.
        """
        colors = self.get_graph_colors() if colors is None else colors
        hoverLine = InfiniteLine(pos=0, pen=mkPen(colors[-1], width=1), movable=False)
        graphDict['graph'].addItem(hoverLine)
        graphDict['line'] = hoverLine

    def setup_graph_plots(self, graph: PlotWidget, trader: Union[SimulationTrader, Backtester], graphType: int):
        """
        Setups graph plots for graph, trade, and graphType specified.
        :param graph: Graph that will be setup.
        :param trader: Trade object that will use this graph.
        :param graphType: Graph type; i.e. moving average or net balance.
        """
        colors = self.get_graph_colors()
        if self.configuration.enableHoverLine.isChecked():
            self.create_infinite_line(self.get_graph_dictionary(graph), colors=colors)

        if graphType == NET_GRAPH:
            self.setup_net_graph_plot(graph=graph, trader=trader, color=colors[0])
        elif graphType == AVG_GRAPH:
            self.setup_average_graph_plots(graph=graph, trader=trader, colors=colors)
        else:
            raise TypeError("Invalid type of graph provided.")

    def get_graph_colors(self) -> list:
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
                  config.avg3Color.currentText(), config.avg4Color.currentText(), config.hoverLineColor.currentText()]
        return [colorDict[color.lower()] for color in colors]

    def create_graph_plot(self, graph: PlotWidget, x: tuple, y: tuple, plotName: str, color: str):
        """
        Creates a graph plot with parameters provided.
        :param graph: Graph function will plot on.
        :param x: X values of graph.
        :param y: Y values of graph.
        :param plotName: Name of graph.
        :param color: Color graph will be drawn in.
        """
        pen = mkPen(color=color)
        plot = graph.plot(x, y, name=plotName, pen=pen, autoDownsample=True, downsampleMethod='subsample')
        plot.curve.scene().sigMouseMoved.connect(lambda point: self.onMouseMoved(point=point, graph=graph))
        return plot

    def get_graph_dictionary(self, targetGraph) -> dict:
        """
        Loops over list of graphs and returns appropriate graph dictionary.
        :param targetGraph: Graph to find in list of graphs.
        :return: Dictionary with the graph values.
        """
        for graph in self.graphs:
            if graph["graph"] == targetGraph:
                return graph

    def onMouseMoved(self, point, graph):
        """
        Updates coordinates label when mouse is hovered over graph.
        :param point: Point hovering over graph.
        :param graph: Graph being hovered on.
        """
        p = graph.plotItem.vb.mapSceneToView(point)
        graphDict = self.get_graph_dictionary(graph)

        if p and graphDict.get('line'):  # Ensure that the hover line is enabled.
            graphDict['line'].setPos(p.x())
            xValue = int(p.x())

            if graphDict['plots'][0]['x'][-1] > xValue > graphDict['plots'][0]['x'][0]:
                date_object = datetime.utcfromtimestamp(graphDict['plots'][0]['z'][xValue])
                total = f'X: {xValue} Datetime in UTC: {date_object.strftime("%m/%d/%Y, %H:%M:%S")}'

                for plotDict in graphDict['plots']:
                    total += f' {plotDict["name"]}: {plotDict["y"][xValue]}'

                graphDict['label'].setText(total)

                if graph == self.backtestGraph and self.backtester is not None:
                    self.update_backtest_activity_based_on_graph(xValue)

    def update_backtest_activity_based_on_graph(self, position: int):
        """
        Updates backtest activity based on where the line is in the backtest graph.
        :param position: Position to show activity at.
        """
        if self.backtester is not None:
            if 1 <= position <= len(self.backtester.pastActivity):
                try:
                    self.update_backtest_gui(self.backtester.pastActivity[position - 1])
                except IndexError as e:
                    self.logger.exception(str(e))

    def reset_backtest_cursor(self):
        """
        Resets backtest hover cursor to end of graph.
        """
        graphDict = self.get_graph_dictionary(self.backtestGraph)
        if self.backtester is not None and graphDict.get('line') is not None:
            index = len(self.backtester.pastActivity)
            graphDict['line'].setPos(index)
            self.update_backtest_activity_based_on_graph(index)

    @staticmethod
    def clear_table(table):
        """
        Sets table row count to 0.
        :param table: Table which is to be cleared.
        """
        table.setRowCount(0)

    @staticmethod
    def test_table(table, trade: list):
        """
        Initial function made to test table functionality in QT.
        :param table: Table to insert row at.
        :param trade: Trade information to add.
        """
        rowPosition = table.rowCount()
        columns = table.columnCount()

        table.insertRow(rowPosition)
        for column in range(columns):
            cell = QTableWidgetItem(str(trade[column]))
            table.setItem(rowPosition, column, cell)

    def get_activity_table(self, caller):
        if caller == LIVE:
            return self.activityMonitor
        elif caller == SIMULATION:
            return self.simulationActivityMonitor
        elif caller == BACKTEST:
            return self.backtestTable
        else:
            raise ValueError("Invalid type of caller specified.")

    def add_to_monitor(self, caller: int, message: str):
        """
        Adds message to the monitor based on caller.
        :param caller: Caller that determines which table gets the message.
        :param message: Message to be added.
        """
        if caller == SIMULATION:
            self.add_to_simulation_activity_monitor(message)
        elif caller == LIVE:
            self.add_to_live_activity_monitor(message)
        elif caller == BACKTEST:
            self.add_to_backtest_monitor(message)
        else:
            raise TypeError("Invalid type of caller specified.")

    def add_to_backtest_monitor(self, message: str):
        """
        Function that adds activity information to the backtest activity monitor.
        :param message: Message to add to backtest activity log.
        """
        self.add_to_table(self.backtestTable, [message])
        self.backtestTable.scrollToBottom()

    def add_to_simulation_activity_monitor(self, message: str):
        """
        Function that adds activity information to the simulation activity monitor.
        :param message: Message to add to simulation activity log.
        """
        self.add_to_table(self.simulationActivityMonitor, [message])
        self.simulationActivityMonitor.scrollToBottom()

    def add_to_live_activity_monitor(self, message: str):
        """
        Function that adds activity information to activity monitor.
        :param message: Message to add to activity log.
        """
        self.add_to_table(self.activityMonitor, [message])
        self.activityMonitor.scrollToBottom()

    @staticmethod
    def add_to_table(table, data: list, insertDate=True):
        """
        Function that will add specified data to a provided table.
        :param insertDate: Boolean to add date to 0th index of data or not.
        :param table: Table we will add data to.
        :param data: Data we will add to table.
        """
        rowPosition = table.rowCount()
        columns = table.columnCount()

        if insertDate:
            data.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if len(data) != columns:
            raise ValueError('Data needs to have the same amount of columns as table.')

        table.insertRow(rowPosition)
        for column in range(0, columns):
            table.setItem(rowPosition, column, QTableWidgetItem(str(data[column])))

    def update_trades_table_and_activity_monitor(self, trade, caller):
        """
        Updates trade table and activity based on caller and sends message to Telegram if live bot is trading and
        Telegram feature is enabled.
        :param trade: Trade information to add to activity monitor and trades table.
        :param caller: Caller object that will rule which tables get updated.
        """
        table = self.interfaceDictionary[caller]['mainInterface']['historyTable']
        trader = self.get_trader(caller)

        if not trader:
            return

        tradeData = [trade['orderID'],
                     trade['pair'],
                     trade['price'],
                     trade['percentage'],
                     trade['profit'],
                     trade['method'],
                     trade['action']]

        self.add_to_table(table, tradeData)
        self.add_to_monitor(caller, trade['action'])

        if caller == LIVE and self.telegramBot and self.configuration.enableTelegramSendMessage.isChecked():
            self.inform_telegram(message=trade['action'])

        monitor = self.get_activity_table(caller=caller)
        monitor.scrollToBottom()
        table.scrollToBottom()

    def closeEvent(self, event):
        """
        Close event override. Makes user confirm they want to end program if something is running live.
        :param event: close event
        """
        self.configuration.save_state()
        qm = QMessageBox
        message = ""
        if self.simulationRunningLive and self.runningLive:
            message = "There is a live bot and a simulation running."
        elif self.simulationRunningLive:
            message = "There is a simulation running."
        elif self.runningLive:
            message = "There is a live bot running."
        ret = qm.question(self, 'Close?', f"{message} Are you sure you want to end Algobot?",
                          qm.Yes | qm.No)

        if ret == qm.Yes:
            if self.runningLive:
                self.end_bot_gracefully(caller=LIVE)
            elif self.simulationRunningLive:
                self.end_bot_gracefully(caller=SIMULATION)
            event.accept()
        else:
            event.ignore()

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

    @staticmethod
    def get_caller_string(caller):
        if caller == LIVE:
            return 'live'
        elif caller == SIMULATION:
            return 'simulation'
        elif caller == BACKTEST:
            return 'backtest'
        else:
            raise ValueError("Invalid type of caller specified.")

    def show_statistics(self, index: int):
        """
        Opens statistics window and sets tab index to index provided.
        :param index: Index to be changed in the tab.
        """
        self.statistics.show()
        self.statistics.statisticsTabWidget.setCurrentIndex(index)

    def update_binance_values(self):
        if self.trader is not None:
            thread = workerThread.Worker(self.trader.retrieve_margin_values)
            thread.signals.finished.connect(lambda: self.create_popup('Successfully updated values.'))
            thread.signals.error.connect(self.create_popup)
            self.threadPool.start(thread)
        else:
            self.create_popup('There is currently no live bot running.')

    def create_configuration_slots(self):
        """
        Creates configuration slots.
        """
        self.configuration.lightModeRadioButton.toggled.connect(lambda: self.set_light_mode())
        self.configuration.darkModeRadioButton.toggled.connect(lambda: self.set_dark_mode())
        self.configuration.bloombergModeRadioButton.toggled.connect(lambda: self.set_bloomberg_mode())
        self.configuration.bullModeRadioButton.toggled.connect(lambda: self.set_bull_mode())
        self.configuration.bearModeRadioButton.toggled.connect(lambda: self.set_bear_mode())
        self.configuration.simpleLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(False))
        self.configuration.advancedLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(True))

        self.configuration.updateBinanceValues.clicked.connect(self.update_binance_values)
        self.configuration.updateTickers.clicked.connect(self.tickers_thread)

    @staticmethod
    def create_folder(folder):
        targetPath = os.path.join(ROOT_DIR, folder)
        create_folder_if_needed(targetPath)

        return targetPath

    def open_folder(self, folder):
        targetPath = self.create_folder(folder)
        open_file_or_folder(targetPath)

    def create_action_slots(self):
        """
        Creates actions slots.
        """
        self.otherCommandsAction.triggered.connect(lambda: self.otherCommands.show())
        self.configurationAction.triggered.connect(lambda: self.configuration.show())
        self.aboutAlgobotAction.triggered.connect(lambda: self.about.show())
        self.liveStatisticsAction.triggered.connect(lambda: self.show_statistics(0))
        self.simulationStatisticsAction.triggered.connect(lambda: self.show_statistics(1))
        self.openBacktestResultsFolderAction.triggered.connect(lambda: self.open_folder("Backtest Results"))
        self.openLogFolderAction.triggered.connect(lambda: self.open_folder("Logs"))
        self.openCsvFolderAction.triggered.connect(lambda: self.open_folder('CSV'))
        self.openDatabasesFolderAction.triggered.connect(lambda: self.open_folder('Databases'))
        self.openCredentialsFolderAction.triggered.connect(lambda: self.open_folder('Credentials'))
        self.openConfigurationsFolderAction.triggered.connect(lambda: self.open_folder('Configuration'))
        self.sourceCodeAction.triggered.connect(lambda: webbrowser.open("https://github.com/ZENALC/algobot"))
        self.tradingViewLiveAction.triggered.connect(lambda: self.open_trading_view(LIVE))
        self.tradingViewSimulationAction.triggered.connect(lambda: self.open_trading_view(SIMULATION))
        self.tradingViewBacktestAction.triggered.connect(lambda: self.open_trading_view(BACKTEST))
        self.tradingViewHomepageAction.triggered.connect(lambda: self.open_trading_view(None))
        self.binanceHomepageAction.triggered.connect(lambda: self.open_binance(None))
        self.binanceLiveAction.triggered.connect(lambda: self.open_binance(LIVE))
        self.binanceSimulationAction.triggered.connect(lambda: self.open_binance(SIMULATION))
        self.binanceBacktestAction.triggered.connect(lambda: self.open_binance(BACKTEST))

    def get_preferred_symbol(self) -> Union[None, str]:
        """
        Get preferred symbol on precedence of live bot, simulation bot, then finally backtest bot.
        :return: Preferred symbol.
        """
        if self.trader:
            return self.trader.symbol
        elif self.simulationTrader:
            return self.simulationTrader.symbol
        elif self.backtester:
            return self.backtester.symbol
        else:
            return None

    def open_binance(self, caller: int = None):
        """
        Opens Binance hyperlink.
        :param caller: If provided, it'll open the link to the caller's symbol's link on Binance.
        """
        if caller is None:
            symbol = None
        else:
            symbol = self.interfaceDictionary[caller]['configuration']['ticker'].currentText()
            index = symbol.index("USDT")
            if index == 0:
                symbol = f"USDT_{symbol[4:]}"
            else:
                symbol = f"{symbol[:index]}_USDT"

        if symbol:
            webbrowser.open(f"https://www.binance.com/en/trade/{symbol}")
        else:
            webbrowser.open("https://www.binance.com/en")

    def open_trading_view(self, caller: int = None):
        """
        Opens TradingView hyperlink.
        :param caller: If provided, it'll open the link to the caller's symbol's link on TradingView.
        """
        if caller is None:
            symbol = None
        else:
            symbol = self.interfaceDictionary[caller]['configuration']['ticker'].currentText()

        if symbol:
            webbrowser.open(f"https://www.tradingview.com/symbols/{symbol}/?exchange=BINANCE")
        else:
            webbrowser.open("https://www.tradingview.com/")

    def export_trades(self, caller):
        """
        Export trade history to a CSV file.
        :param caller: Caller that'll determine which trades get exported.
        """
        table = self.interfaceDictionary[caller]['mainInterface']['historyTable']
        label = self.interfaceDictionary[caller]['mainInterface']['historyLabel']
        columns = table.columnCount()
        rows = table.rowCount()
        trades = []

        if rows == 0:
            label.setText("No data in table currently.")
            return

        for row in range(rows):
            trade = []
            for column in range(columns):
                item = table.item(row, column)
                trade.append(item.text())
            trades.append(trade)

        path = self.create_folder("Trade History")

        if caller == SIMULATION:
            defaultFile = os.path.join(path, 'live_trades.csv')
        else:
            defaultFile = os.path.join(path, 'simulation_trades.csv')

        path, _ = QFileDialog.getSaveFileName(self, 'Export Trades', defaultFile, 'CSV (*.csv)')

        if path:
            with open(path, 'w') as f:
                for trade in trades:
                    f.write(','.join(trade) + '\n')
            label.setText(f"Exported trade history successfully to {path}.")
        else:
            label.setText("Could not save trade history.")

    def import_trades(self, caller):
        """
        Import trade histories from a file.
        :param caller: Caller that will determine which trade table gets updated.
        """
        table = self.interfaceDictionary[caller]['mainInterface']['historyTable']
        label = self.interfaceDictionary[caller]['mainInterface']['historyLabel']
        path = self.create_folder("Trade History")
        path, _ = QFileDialog.getOpenFileName(self, 'Import Trades', path, "CSV (*.csv)")

        try:
            with open(path, 'r') as f:
                rows = f.readlines()
                for row in rows:
                    row = row.strip().split(',')
                    self.add_to_table(table, row, insertDate=False)
            label.setText("Imported trade history successfully.")
        except Exception as e:
            label.setText("Could not import trade history due to data corruption or no file being selected.")
            self.logger.exception(str(e))

    # noinspection DuplicatedCode
    def create_bot_slots(self):
        """
        Creates bot slots.
        """
        self.runBotButton.clicked.connect(lambda: self.initiate_bot_thread(caller=LIVE))
        self.endBotButton.clicked.connect(lambda: self.end_bot_thread(caller=LIVE))
        self.configureBotButton.clicked.connect(self.show_main_settings)
        self.forceLongButton.clicked.connect(lambda: self.force_long(LIVE))
        self.forceShortButton.clicked.connect(lambda: self.force_short(LIVE))
        self.pauseBotButton.clicked.connect(lambda: self.pause_or_resume_bot(LIVE))
        self.exitPositionButton.clicked.connect(lambda: self.exit_position(LIVE, True))
        self.waitOverrideButton.clicked.connect(lambda: self.exit_position(LIVE, False))
        self.enableCustomStopLossButton.clicked.connect(lambda: self.set_custom_stop_loss(LIVE, True))
        self.disableCustomStopLossButton.clicked.connect(lambda: self.set_custom_stop_loss(LIVE, False))
        self.clearTableButton.clicked.connect(lambda: self.clear_table(self.activityMonitor))
        self.clearLiveTradesButton.clicked.connect(lambda: self.clear_table(self.historyTable))
        self.exportLiveTradesButton.clicked.connect(lambda: self.export_trades(caller=LIVE))
        self.importLiveTradesButton.clicked.connect(lambda: self.import_trades(caller=LIVE))

    # noinspection DuplicatedCode
    def create_simulation_slots(self):
        """
        Creates simulation slots.
        """
        self.runSimulationButton.clicked.connect(lambda: self.initiate_bot_thread(caller=SIMULATION))
        self.endSimulationButton.clicked.connect(lambda: self.end_bot_thread(caller=SIMULATION))
        self.configureSimulationButton.clicked.connect(self.show_simulation_settings)
        self.forceLongSimulationButton.clicked.connect(lambda: self.force_long(SIMULATION))
        self.forceShortSimulationButton.clicked.connect(lambda: self.force_short(SIMULATION))
        self.pauseBotSimulationButton.clicked.connect(lambda: self.pause_or_resume_bot(SIMULATION))
        self.exitPositionSimulationButton.clicked.connect(lambda: self.exit_position(SIMULATION, True))
        self.waitOverrideSimulationButton.clicked.connect(lambda: self.exit_position(SIMULATION, False))
        self.enableSimulationCustomStopLossButton.clicked.connect(lambda: self.set_custom_stop_loss(SIMULATION, True))
        self.disableSimulationCustomStopLossButton.clicked.connect(lambda: self.set_custom_stop_loss(SIMULATION, False))
        self.clearSimulationTableButton.clicked.connect(lambda: self.clear_table(self.simulationActivityMonitor))
        self.clearSimulationTradesButton.clicked.connect(lambda: self.clear_table(self.simulationHistoryTable))
        self.exportSimulationTradesButton.clicked.connect(lambda: self.export_trades(caller=SIMULATION))
        self.importSimulationTradesButton.clicked.connect(lambda: self.import_trades(caller=SIMULATION))

    def create_backtest_slots(self):
        """
        Creates backtest slots.
        """
        self.configureBacktestButton.clicked.connect(self.show_backtest_settings)
        self.runBacktestButton.clicked.connect(self.initiate_backtest)
        self.endBacktestButton.clicked.connect(self.end_backtest_thread)
        self.clearBacktestTableButton.clicked.connect(lambda: self.clear_table(self.backtestTable))
        self.viewBacktestsButton.clicked.connect(lambda: self.open_folder("Backtest Results"))
        self.backtestResetCursorButton.clicked.connect(self.reset_backtest_cursor)

    def create_interface_slots(self):
        """
        Creates interface slots.
        """
        self.create_bot_slots()
        self.create_simulation_slots()
        self.create_backtest_slots()

        # Other buttons in interface.
        self.refreshNewsButton.clicked.connect(self.news_thread)

    def initiate_slots(self):
        """
        Initiates all interface slots.
        """
        self.create_action_slots()
        self.create_configuration_slots()
        self.create_interface_slots()

    def create_popup_and_emit_message(self, caller: int, message: str):
        """
        Creates a popup and emits message simultaneously with caller and messages provided.
        :param caller: Caller activity monitor to add message to.
        :param message: Message to create popup of emit to activity monitor.
        """
        self.add_to_monitor(caller, message)
        self.create_popup(message)

    def create_popup(self, msg: str):
        """
        Creates a popup with message provided.
        :param msg: Message provided.
        """
        QMessageBox.about(self, 'Warning', msg)

    def set_dark_mode(self):
        """
        Switches interface to a dark theme.
        """
        app.setPalette(dark_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_light_mode(self):
        """
        Switches interface to a light theme.
        """
        app.setPalette(light_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('w')

    def set_bloomberg_mode(self):
        """
        Switches interface to bloomberg theme.
        """
        app.setPalette(bloomberg_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_bear_mode(self):
        """
        Sets bear mode color theme. Theme is red and black mimicking a red day.
        """
        app.setPalette(red_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def set_bull_mode(self):
        """
        Sets bull mode color theme. Theme is green and black mimicking a green day.
        """
        app.setPalette(green_palette())
        for graph in self.graphs:
            graph = graph['graph']
            graph.setBackground('k')

    def get_lower_interval_data(self, caller: int) -> Data:
        """
        Returns interface's lower interval data object.
        :param caller: Caller that determines which lower interval data object gets returned.
        :return: Data object.
        """
        if caller == SIMULATION:
            return self.simulationLowerIntervalData
        elif caller == LIVE:
            return self.lowerIntervalData
        else:
            raise TypeError("Invalid type of caller specified.")

    def get_trader(self, caller: int) -> Union[SimulationTrader, Backtester]:
        """
        Returns a trader object.
        :param caller: Caller that decides which trader object gets returned.
        :return: Trader object.
        """
        if caller == SIMULATION:
            return self.simulationTrader
        elif caller == LIVE:
            return self.trader
        elif caller == BACKTEST:
            return self.backtester
        else:
            raise TypeError("Invalid type of caller specified.")


def main():
    app.setStyle('Fusion')
    # helpers.initialize_logger()
    interface = Interface()
    interface.showMaximized()
    app.setWindowIcon(QIcon('../media/algobotwolf.png'))
    sys.excepthook = except_hook
    sys.exit(app.exec_())


def except_hook(cls, exception, trace_back):
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    main()
