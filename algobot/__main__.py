"""
Main Algobot application.
"""

import os
import sys
import time
import webbrowser
from datetime import datetime
from typing import Dict, List, Union

from PyQt5 import QtCore, uic
from PyQt5.QtCore import QRunnable, QThreadPool
from PyQt5.QtGui import QIcon, QTextCursor
from PyQt5.QtWidgets import (QApplication, QCompleter, QFileDialog,
                             QMainWindow, QMessageBox, QTableWidgetItem)

import algobot.assets
from algobot.algodict import get_interface_dictionary
from algobot.data import Data
from algobot.enums import (BACKTEST, LIVE, LONG, OPTIMIZER, SHORT, SIMULATION,
                           GraphType)
from algobot.graph_helpers import (add_data_to_plot, destroy_graph_plots,
                                   get_graph_dictionary,
                                   set_backtest_graph_limits_and_empty_plots,
                                   setup_graph_plots, setup_graphs,
                                   update_backtest_graph_limits,
                                   update_main_graphs)
from algobot.helpers import (ROOT_DIR, create_folder, create_folder_if_needed,
                             get_caller_string, open_file_or_folder)
from algobot.interface.about import About
from algobot.interface.config_utils.state_utils import load_state, save_state
from algobot.interface.config_utils.strategy_utils import get_strategies
from algobot.interface.configuration import Configuration
from algobot.interface.other_commands import OtherCommands
from algobot.interface.statistics import Statistics
from algobot.interface.utils import (add_to_table, clear_table, create_popup,
                                     open_from_msg_box,
                                     show_and_bring_window_to_front)
from algobot.news_scraper import scrape_news
from algobot.slots import initiate_slots
from algobot.telegram_bot import TelegramBot
from algobot.threads import (backtestThread, botThread, optimizerThread,
                             workerThread)
from algobot.traders.backtester import Backtester
from algobot.traders.realtrader import RealTrader
from algobot.traders.simulationtrader import SimulationTrader

app = QApplication(sys.argv)
mainUi = os.path.join(ROOT_DIR, 'UI', 'algobot.ui')


class Interface(QMainWindow):
    """
        Main Algobot interface.
        Algobot currently supports trading with live bots and running simulations, optimizers, or backtests.

        To contribute, please visit: https://github.com/ZENALC/algobot.
        For bug reports or feature requests, please create an issue at: https://github.com/ZENALC/algobot/issues.
        For available documentation, please visit: https://github.com/ZENALC/algobot/wiki.
    """
    def __init__(self, parent=None):
        algobot.assets.qInitResources()
        super(Interface, self).__init__(parent)  # Initializing object
        uic.loadUi(mainUi, self)  # Loading the main UI
        self.logger = algobot.MAIN_LOGGER
        self.configuration = Configuration(parent=self, logger=self.logger)  # Loading configuration
        self.otherCommands = OtherCommands(self)  # Loading other commands
        self.about = About(self)  # Loading about information
        self.statistics = Statistics(self)  # Loading statistics
        self.threadPool = QThreadPool(self)  # Initiating threading pool
        self.threads: Dict[int, QRunnable or None] = {BACKTEST: None, SIMULATION: None, LIVE: None, OPTIMIZER: None}
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
        self.optimizer: Union[Backtester, None] = None
        self.backtester: Union[Backtester, None] = None
        self.trader: Union[RealTrader, None] = None
        self.simulationTrader: Union[SimulationTrader, None] = None
        self.simulationLowerIntervalData: Union[Data, None] = None
        self.lowerIntervalData: Union[Data, None] = None
        self.telegramBot = None
        self.tickers = []  # All available tickers.

        if algobot.CURRENT_VERSION != algobot.LATEST_VERSION:
            if algobot.LATEST_VERSION != 'unknown':
                self.add_to_live_activity_monitor(f"Update {algobot.LATEST_VERSION} is available.")
            else:
                self.add_to_live_activity_monitor('Failed to fetch latest version metadata.')

        self.add_to_live_activity_monitor('Initialized interface.')
        self.load_tickers_and_news()
        self.homeTab.setCurrentIndex(0)
        load_state(self.configuration)

        self.graphUpdateSeconds = 1
        self.graphUpdateSchedule: List[float or None] = [None, None]  # LIVE, SIM

    def inform_telegram(self, message: str, stop_bot: bool = False):
        """
        Sends a notification to Telegram if some action is taken by the bot.
        :param message: Message to send.
        :param stop_bot: Boolean for whether bot should be stopped or not.
        """
        try:
            if self.telegramBot is None:
                apiKey = self.configuration.telegramApiKey.text()
                self.telegramBot = TelegramBot(gui=self, token=apiKey, botThread=None)

            chatID = self.configuration.telegramChatID.text()
            if self.configuration.chatPass:
                self.telegramBot.send_message(chatID, message)

            if stop_bot:
                self.telegramBot.stop()
                self.telegramBot = None
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
        newsThread = workerThread.Worker(scrape_news)
        newsThread.signals.error.connect(self.news_thread_error)
        newsThread.signals.finished.connect(self.setup_news)
        newsThread.signals.restore.connect(lambda: self.refreshNewsButton.setEnabled(True))
        self.threadPool.start(newsThread)

    def news_thread_error(self, e: str):
        """
        Creates a popup regarding news retrieval error.
        :param e: Error string.
        """
        self.newsStatusLabel.setText("Failed to retrieve latest news.")
        if 'www.todayonchain.com' in e:
            create_popup(self, 'Failed to retrieve latest news due to a connectivity error.')
        else:
            create_popup(self, e)

    def tickers_thread(self):
        """
        Runs ticker thread and sets tickers to GUI.
        """
        self.configuration.serverResult.setText("Updating tickers...")
        self.configuration.updateTickers.setEnabled(False)
        tickerThread = workerThread.Worker(self.get_tickers)
        tickerThread.signals.error.connect(self.tickers_thread_error)
        tickerThread.signals.finished.connect(self.setup_tickers)
        tickerThread.signals.restore.connect(lambda: self.configuration.updateTickers.setEnabled(True))
        self.threadPool.start(tickerThread)

    def tickers_thread_error(self, e: str):
        """
        Creates a popup when tickers fail to get fetched.
        :param e: Error message.
        """
        fail = 'Failed to retrieve tickers because of a connectivity issue.'
        self.add_to_live_activity_monitor(fail)
        self.configuration.serverResult.setText(fail)
        if 'api.binance.com' in e:
            create_popup(self, fail)
        else:
            create_popup(self, e)

    @staticmethod
    def get_tickers() -> List[str]:
        """
        Returns all available tickers from Binance API.
        :return: List of all available tickers.
        """
        tickers = [ticker['symbol'] for ticker in Data(loadData=False, log=False).binanceClient.get_all_tickers()]
        return sorted(tickers)

    def setup_tickers(self, tickers: List[str]):
        """
        Sets up all available tickers from Binance API and displays them on appropriate comboboxes in application.
        By default, tickers that aren't traded with USDT are not shown for trading, but all available tickers are
        shown for downloads.
        :param tickers: List of tickers in a string format retrieved from Binance API.
        """
        self.tickers = tickers
        filtered_tickers = [ticker for ticker in tickers if 'USDT' in ticker]
        config = self.configuration
        tickerWidgets = [config.tickerLineEdit, config.backtestTickerLineEdit, config.simulationTickerLineEdit,
                         config.optimizerTickerLineEdit]

        completer = QCompleter(filtered_tickers)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        for widget in tickerWidgets:
            widget.setCompleter(completer)

        full_completer = QCompleter(tickers)
        full_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.otherCommands.csvGenerationTicker.setCompleter(full_completer)
        self.configuration.serverResult.setText("Updated tickers successfully.")

    def setup_news(self, news: List[str]):
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

    def check_combos(self, combos: dict) -> bool:
        """
        This function will recursively check optimizer combo values to see if settings are properly configured.
        :param combos: Combinations dictionary.
        """
        if not combos:
            return False
        elif type(combos) != dict:
            return True

        for key, value in combos.items():
            if not self.check_combos(value):
                return False
        return True

    def export_optimizer(self, file_type: str):
        """
        Export table rows to CSV file.
        :param file_type: Type of file to export optimizer results to.
        """
        if self.optimizer:
            if len(self.optimizer.optimizerRows) > 0:
                optimizerFolderPath = create_folder('Optimizer Results')
                innerPath = os.path.join(optimizerFolderPath, self.optimizer.symbol)
                create_folder_if_needed(innerPath, optimizerFolderPath)
                defaultFileName = self.optimizer.get_default_result_file_name('optimizer', ext=file_type.lower())
                defaultPath = os.path.join(innerPath, defaultFileName)
                filePath, _ = QFileDialog.getSaveFileName(self, 'Save Optimizer', defaultPath,
                                                          f'{file_type} (*.{file_type.lower()})')
                if not filePath:
                    create_popup(self, "Export cancelled.")
                else:
                    self.optimizer.export_optimizer_rows(filePath, file_type)
                    create_popup(self, f'Exported successfully to {filePath}.')

                if open_from_msg_box(text='Do you want to open the optimization report?', title='Optimizer Report'):
                    open_file_or_folder(filePath)

            else:
                create_popup(self, "No table rows found.")
        else:
            create_popup(self, 'No table rows found because optimizer has not been run yet.')

    def validate_optimizer_or_backtest(self, caller):
        """
        Validate optimizer/backtester to ensure it is correctly setup.
        :return: False if not validated and true if validated.
        """
        config = self.configuration
        noun = 'optimizer' if caller == OPTIMIZER else 'backtester'

        if not self.validate_ticker(caller):
            return False

        if config.optimizer_backtest_dict[caller]['data'] is None:
            create_popup(self, f"No data setup yet for {noun}. Please download or import data in settings first.")
            return False

        selected_symbol = self.interfaceDictionary[caller]['configuration']['ticker'].text()
        download_symbol = config.optimizer_backtest_dict[caller]['dataType']

        if selected_symbol != download_symbol and download_symbol.lower() != 'imported':
            create_popup(self, f"{noun.capitalize()} symbol ({selected_symbol}) does not match downloaded symbol "
                               f"({download_symbol}). Change your ticker to ({download_symbol}) "
                               f"or download ({selected_symbol}) data to get rid of this error.")
            return False

        selected_interval = self.interfaceDictionary[caller]['configuration']['interval'].currentText().lower()
        download_interval = config.optimizer_backtest_dict[caller]['dataInterval'].lower()

        if selected_interval != download_interval and download_symbol.lower() != 'imported':
            create_popup(self, f"{noun.capitalize()} interval ({selected_interval}) does not match downloaded interval "
                               f"({download_interval}). Change your data interval to ({download_interval}) "
                               f"or download ({selected_interval}) data to get rid of this error.")
            return False

        if download_symbol.lower() == 'imported':
            # TODO: Add verification for imports.
            create_popup(self, "You are using imported data. Please ensure they logically work correctly with your "
                               "inputs. Algobot currently does not support imported data verification.")

        return True

    def initiate_optimizer(self):
        """
        Main function to begin optimization.
        """
        if not self.validate_optimizer_or_backtest(caller=OPTIMIZER):
            return

        combos = self.configuration.get_optimizer_settings()
        if combos['strategies'] == {}:
            create_popup(self, "No strategies found. Make sure you have some strategies for optimization.")
            return

        if not self.check_combos(combos['strategies']):
            create_popup(self, "Please configure your strategies correctly.")
            return

        self.threads[OPTIMIZER] = optimizerThread.OptimizerThread(gui=self, logger=self.logger, combos=combos)
        worker = self.threads[OPTIMIZER]
        worker.signals.started.connect(lambda: self.set_optimizer_buttons(running=True, clear=True))
        worker.signals.restore.connect(lambda: self.set_optimizer_buttons(running=False, clear=False))
        worker.signals.error.connect(lambda x: create_popup(self, x))
        if self.configuration.enabledOptimizerNotification.isChecked():
            worker.signals.finished.connect(lambda: self.inform_telegram('Optimizer has finished running.',
                                                                         stop_bot=True))
        worker.signals.activity.connect(lambda data: add_to_table(self.optimizerTableWidget, data=data,
                                                                  insertDate=False))
        self.threadPool.start(worker)

    def set_optimizer_buttons(self, running: bool, clear: bool):
        """
        Will modify optimizer buttons based on running status and clear the table based on the clear status.
        :param running: Optimizer running or not.
        :param clear: Clear table or not.
        """
        self.runOptimizerButton.setEnabled(not running)
        self.stopOptimizerButton.setEnabled(running)

        if clear:
            clear_table(self.optimizerTableWidget)

    def end_optimizer(self):
        """
        Function to end optimizer thread if it exists.
        """
        thread = self.threads[OPTIMIZER]
        if thread:
            if thread.running:
                thread.stop()
            else:
                create_popup(self, "There is no optimizer running.")
        else:
            create_popup(self, "There is no optimizer running.")

    def initiate_backtest(self):
        """
        Initiates backtest based on settings configured. If there is no data configured, prompts user to configure data.
        """
        if not self.validate_optimizer_or_backtest(caller=BACKTEST):
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
        worker.signals.updateGraphLimits.connect(lambda x: update_backtest_graph_limits(gui=self, limit=x))
        self.threadPool.start(worker)

    def end_backtest_thread(self):
        """
        Ends backtest thread if it is running,
        :return: None
        """
        thread = self.threads[BACKTEST]
        if thread:
            if thread.running:
                thread.stop()
            else:
                create_popup(self, "There is no backtest running.")
        else:
            create_popup(self, "There is no backtest running.")

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

            if open_from_msg_box(text=f"Backtest results have been saved to {path}.", title="Backtest Results"):
                open_file_or_folder(path)

        self.backtestProgressBar.setValue(100)

    def update_backtest_gui(self, updatedDict: dict, add_data: bool = True, update_progress_bar: bool = True):
        """
        Updates activity backtest details to GUI.
        :param update_progress_bar: Boolean for whether progress bar should be updated based on the dictionary provided.
        :param add_data: Boolean to determine whether to add data to graph or not.
        :param updatedDict: Dictionary containing backtest data.
        """
        if update_progress_bar:
            self.backtestProgressBar.setValue(updatedDict['percentage'])

        net = updatedDict['net']
        utc = updatedDict['utc']

        if net < self.backtester.startingBalance:
            self.backtestProfitLabel.setText("Loss")
            self.backtestProfitPercentageLabel.setText("Loss Percentage")
        else:
            self.backtestProfitLabel.setText("Profit")
            self.backtestProfitPercentageLabel.setText("Profit Percentage")

        self.backtestBalance.setText(updatedDict['balance'])
        self.backtestPrice.setText(updatedDict['price'])
        self.backtestNet.setText(updatedDict['netString'])
        self.backtestCommissionsPaid.setText(updatedDict['commissionsPaid'])
        self.backtestProfit.setText(updatedDict['profit'])
        self.backtestProfitPercentage.setText(updatedDict['profitPercentage'])
        self.backtestTradesMade.setText(updatedDict['tradesMade'])
        self.backtestCurrentPeriod.setText(updatedDict['currentPeriod'])

        if add_data:
            graphDict = self.interfaceDictionary[BACKTEST]['mainInterface']['graph']
            add_data_to_plot(self, graphDict, 0, y=net, timestamp=utc)

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

    def update_backtest_activity_based_on_graph(self, position: int, aux: int = -1):
        """
        Updates backtest activity based on where the line is in the backtest graph.
        :param position: Position to show activity at.
        :param aux: Shift position by the number provided.
        """
        if self.backtester is not None:
            if 1 <= position + aux < len(self.backtester.pastActivity):
                try:
                    self.update_backtest_gui(self.backtester.pastActivity[position + aux], add_data=False,
                                             update_progress_bar=False)
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
        setup_graph_plots(self, interfaceDict['graph'], self.backtester, GraphType.NET)
        set_backtest_graph_limits_and_empty_plots(self)
        self.update_backtest_configuration_gui(configurationDictionary)
        self.add_to_backtest_monitor(f"Started backtest with {symbol} data and {interval.lower()} interval periods.")

    def check_strategies(self, caller: int) -> bool:
        """
        Checks if strategies exist based on the caller provided and prompts an appropriate message.
        """
        if not get_strategies(self.configuration, caller):
            if caller == BACKTEST:
                message = "No strategies found. Would you like to backtest a hold?"
            elif caller == SIMULATION:
                message = "No strategies found. Did you want to day-trade this simulation?"
            elif caller == LIVE:
                message = "No strategies found. Did you want to day-trade this live bot?"
            else:
                raise ValueError("Invalid type of caller specified.")

            qm = QMessageBox
            ret = qm.question(self, 'Warning', message, qm.Yes | qm.No)
            return ret == qm.Yes
        return True

    def validate_ticker(self, caller: int):
        """
        Validate ticker provided before running a bot.
        """
        selected_ticker = self.interfaceDictionary[caller]['configuration']['ticker'].text()
        if selected_ticker.strip() == '':
            create_popup(self, "Please specify a ticker. No ticker found.")
            return False
        if selected_ticker not in self.tickers:
            create_popup(self, f'Invalid ticker "{selected_ticker}" provided. If it is valid, '
                               f'then try updating your tickers in the configuration settings.')
            return False
        return True

    def initiate_bot_thread(self, caller: int):
        """
        Main function that initiates bot thread and handles all data-view logic.
        :param caller: Caller that decides whether a live bot or simulation bot is run.
        """
        if not self.validate_ticker(caller):
            return
        if not self.check_strategies(caller):
            return

        self.disable_interface(True, caller)
        worker = botThread.BotThread(gui=self, caller=caller, logger=self.logger)
        worker.signals.smallError.connect(lambda x: create_popup(self, x))
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

    def download_progress_update(self, value: int, message: str, caller):
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
        thread.signals.error.connect(lambda x: create_popup(self, x))
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
        """
        This function will attempt to end the bot in a graceful and appropriate manner. This is the only way a bot
        should end.
        :param caller: Caller object that'll determine which bot is to be ended.
        :param callback: Callback flag for thread used for emitting signals.
        """
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
            pair = self.configuration.tickerLineEdit.text()
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
        setup_graph_plots(self, interfaceDict['graph'], trader, GraphType.NET)

        averageGraphDict = get_graph_dictionary(self, interfaceDict['averageGraph'])
        if self.configuration.graphIndicatorsCheckBox.isChecked():
            averageGraphDict['enable'] = True
            setup_graph_plots(self, interfaceDict['averageGraph'], trader, GraphType.AVG)
        else:
            averageGraphDict['enable'] = False

    def disable_interface(self, disable: bool, caller, everything: bool = False):
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

    def exit_position_thread(self, caller, humanControl: bool):
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

    def set_exit_position_gui(self, caller, humanControl: bool):
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
        thread.signals.error.connect(lambda x: create_popup(self, x))
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
        thread.signals.error.connect(lambda x: create_popup(self, x))
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
        thread.signals.error.connect(lambda x: create_popup(self, x))
        self.threadPool.start(thread)

    def modify_override_buttons(self, caller, pauseText: str, shortBtn: bool, longBtn: bool, exitBtn: bool,
                                waitBtn: bool):
        """
        Modify force override button with booleans provided above for caller.
        :param caller: Caller object that specifies which trading object will have its override buttons modified.
        :param pauseText: Text to show in the pause bot button.
        :param shortBtn: Boolean that'll determine if the force short button is enabled or disabled.
        :param longBtn: Boolean that'll determine if the force long button is enabled or disabled.
        :param exitBtn: Boolean that'll determine if the exit button is enabled or disabled.
        :param waitBtn: Boolean that'll determine if the wait override button is enabled or disabled.
        """
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

    def set_advanced_logging(self, boolean: bool):
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
        """
        Returns activity table based on the caller provided.
        :param caller: Caller enum.
        :return: Activity table for the caller.
        """
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

    def update_trades_table_and_activity_monitor(self, trade: dict, caller):
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
        save_state(self.configuration)
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
        show_and_bring_window_to_front(self.configuration)
        self.configuration.configurationTabWidget.setCurrentIndex(0)
        self.configuration.mainConfigurationTabWidget.setCurrentIndex(0)

    def show_backtest_settings(self):
        """
        Opens backtest settings in the configuration window.
        """
        show_and_bring_window_to_front(self.configuration)
        self.configuration.configurationTabWidget.setCurrentIndex(1)
        self.configuration.backtestConfigurationTabWidget.setCurrentIndex(0)

    def show_optimizer_settings(self):
        """
        Open configuration settings for optimizer.
        """
        show_and_bring_window_to_front(self.configuration)
        self.configuration.configurationTabWidget.setCurrentIndex(2)
        self.configuration.optimizerConfigurationTabWidget.setCurrentIndex(0)

    def show_simulation_settings(self):
        """
        Opens simulation settings in the configuration window.
        """
        show_and_bring_window_to_front(self.configuration)
        self.configuration.configurationTabWidget.setCurrentIndex(3)
        self.configuration.simulationConfigurationTabWidget.setCurrentIndex(0)

    def show_statistics(self, index: int):
        """
        Opens statistics window and sets tab index to index provided.
        :param index: Index to be changed in the tab.
        """
        show_and_bring_window_to_front(self.statistics)
        self.statistics.statisticsTabWidget.setCurrentIndex(index)

    def update_binance_values(self):
        """
        This will update values from Binance.
        """
        if self.trader is not None:
            thread = workerThread.Worker(self.trader.retrieve_margin_values)
            thread.signals.finished.connect(lambda: create_popup(self, 'Successfully updated values.'))
            thread.signals.error.connect(lambda x: create_popup(self, x))
            self.threadPool.start(thread)
        else:
            create_popup(self, 'There is currently no live bot running.')

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
        :param caller: If provided, it'll open the link to the caller's symbol's link on Binance. By default, if no
        caller is provided, the homepage will open up.
        """
        if caller is None:
            webbrowser.open("https://www.binance.com/en")
        else:
            symbol = self.interfaceDictionary[caller]['configuration']['ticker'].text()
            if symbol.strip() == '' or 'USDT' not in symbol:  # TODO: Add more ticker pair separators.
                webbrowser.open("https://www.binance.com/en")
            else:
                index = symbol.index("USDT")
                symbol = f"USDT_{symbol[4:]}" if index == 0 else f"{symbol[:index]}_USDT"
                webbrowser.open(f"https://www.binance.com/en/trade/{symbol}")

    def open_trading_view(self, caller: int = None):
        """
        Opens TradingView hyperlink.
        :param caller: If provided, it'll open the link to the caller's symbol's link on TradingView.
        """
        if caller is None:
            webbrowser.open("https://www.tradingview.com/")
        else:
            symbol = self.interfaceDictionary[caller]['configuration']['ticker'].text()
            if symbol.strip() == '':
                webbrowser.open("https://www.tradingview.com/")
            else:
                webbrowser.open(f"https://www.tradingview.com/symbols/{symbol}/?exchange=BINANCE")

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

        if caller == LIVE:
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
        create_popup(self, message)

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
    """
    Main function.
    """
    app.setStyle('Fusion')
    interface = Interface()
    interface.showMaximized()
    app.setWindowIcon(QIcon('../media/algobotwolf.png'))
    sys.excepthook = except_hook
    sys.exit(app.exec_())


def except_hook(cls, exception, trace_back):
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    main()
