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

import algobot.assets
from algobot.algodict import get_interface_dictionary
from algobot.data import Data
from algobot.enums import (AVG_GRAPH, BACKTEST, LIVE, LONG, NET_GRAPH, SHORT,
                           SIMULATION)
from algobot.graph_helpers import (add_data_to_plot, destroy_graph_plots,
                                   get_graph_dictionary,
                                   set_backtest_graph_limits_and_empty_plots,
                                   setup_graph_plots, setup_graphs,
                                   update_backtest_graph_limits,
                                   update_main_graphs)
from algobot.helpers import (ROOT_DIR, add_to_table, create_folder,
                             create_folder_if_needed, get_caller_string,
                             get_logger, open_file_or_folder)
from algobot.interface.about import About
from algobot.interface.configuration import Configuration
from algobot.interface.other_commands import OtherCommands
from algobot.interface.statistics import Statistics
from algobot.news_scraper import scrape_news
from algobot.option import Option
from algobot.slots import initiate_slots
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
        setup_graphs(gui=self)  # Setting up graphs.
        initiate_slots(app=app, gui=self)  # Initiating slots.

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
    def get_tickers() -> List[str]:
        """
        Returns all available tickers from Binance API.
        :return: List of all available tickers.
        """
        tickers = [ticker['symbol'] for ticker in Data(loadData=False, log=False).binanceClient.get_all_tickers()
                   if 'USDT' in ticker['symbol']]

        tickers.sort()
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
        worker.signals.updateGraphLimits.connect(lambda: update_backtest_graph_limits(self))
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
        backtestFolderPath = create_folder('Backtest Results')
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
        add_data_to_plot(self, self.interfaceDictionary[BACKTEST]['mainInterface']['graph'], 0, y=net, timestamp=utc)

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
        graphDict = get_graph_dictionary(self, self.backtestGraph)
        if self.backtester is not None and graphDict.get('line') is not None:
            index = len(self.backtester.pastActivity)
            graphDict['line'].setPos(index)
            self.update_backtest_activity_based_on_graph(index)

    def setup_backtester(self, configurationDictionary: dict):
        """
        Set up backtest GUI with dictionary provided.
        :param configurationDictionary: Dictionary with configuration details.
        """
        interfaceDict = self.interfaceDictionary[BACKTEST]['mainInterface']
        symbol = configurationDictionary['symbol']
        interval = configurationDictionary['interval']
        destroy_graph_plots(self, interfaceDict['graph'])
        setup_graph_plots(self, interfaceDict['graph'], self.backtester, NET_GRAPH)
        set_backtest_graph_limits_and_empty_plots(self)
        self.update_backtest_configuration_gui(configurationDictionary)
        self.add_to_backtest_monitor(f"Started backtest with {symbol} data and {interval.lower()} interval periods.")

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
        destroy_graph_plots(self, interfaceDict['graph'])
        destroy_graph_plots(self, interfaceDict['averageGraph'])
        self.statistics.initialize_tab(trader.get_grouped_statistics(), tabType=get_caller_string(caller))
        setup_graph_plots(self, interfaceDict['graph'], trader, NET_GRAPH)

        averageGraphDict = get_graph_dictionary(self, interfaceDict['averageGraph'])
        if self.configuration.graphIndicatorsCheckBox.isChecked():
            averageGraphDict['enable'] = True
            setup_graph_plots(self, interfaceDict['averageGraph'], trader, AVG_GRAPH)
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
        self.statistics.modify_tab(groupedDict, tabType=get_caller_string(caller))
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
            update_main_graphs(gui=self, caller=caller, valueDict=valueDict)
            self.graphUpdateSchedule[index] = time.time() + self.graphUpdateSeconds

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

    def onMouseMoved(self, point, graph):
        """
        Updates coordinates label when mouse is hovered over graph.
        :param point: Point hovering over graph.
        :param graph: Graph being hovered on.
        """
        p = graph.plotItem.vb.mapSceneToView(point)
        graphDict = get_graph_dictionary(self, graph)

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
        add_to_table(self.backtestTable, [message])
        self.backtestTable.scrollToBottom()

    def add_to_simulation_activity_monitor(self, message: str):
        """
        Function that adds activity information to the simulation activity monitor.
        :param message: Message to add to simulation activity log.
        """
        add_to_table(self.simulationActivityMonitor, [message])
        self.simulationActivityMonitor.scrollToBottom()

    def add_to_live_activity_monitor(self, message: str):
        """
        Function that adds activity information to activity monitor.
        :param message: Message to add to activity log.
        """
        add_to_table(self.activityMonitor, [message])
        self.activityMonitor.scrollToBottom()

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

        add_to_table(table, tradeData)
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

        path = create_folder("Trade History")

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
        path = create_folder("Trade History")
        path, _ = QFileDialog.getOpenFileName(self, 'Import Trades', path, "CSV (*.csv)")

        try:
            with open(path, 'r') as f:
                rows = f.readlines()
                for row in rows:
                    row = row.strip().split(',')
                    add_to_table(table, row, insertDate=False)
            label.setText("Imported trade history successfully.")
        except Exception as e:
            label.setText("Could not import trade history due to data corruption or no file being selected.")
            self.logger.exception(str(e))

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
