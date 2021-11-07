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
from PyQt5.QtWidgets import QApplication, QCompleter, QFileDialog, QMainWindow, QMessageBox, QTableWidgetItem

import algobot.assets
from algobot.algodict import get_interface_dictionary
from algobot.data import Data
from algobot.enums import BACKTEST, LIVE, LONG, OPTIMIZER, SHORT, SIMULATION, GraphType
from algobot.graph_helpers import (add_data_to_plot, destroy_graph_plots, get_graph_dictionary,
                                   set_backtest_graph_limits_and_empty_plots, setup_graph_plots, setup_graphs,
                                   update_backtest_graph_limits, update_main_graphs)
from algobot.helpers import ROOT_DIR, create_folder, create_folder_if_needed, get_caller_string, open_file_or_folder
from algobot.interface.about import About
from algobot.interface.builder.strategy_builder import StrategyBuilder
from algobot.interface.config_utils.slot_utils import load_hide_show_strategies
from algobot.interface.config_utils.state_utils import load_state, save_state
from algobot.interface.config_utils.strategy_utils import get_strategies
from algobot.interface.configuration import Configuration
from algobot.interface.other_commands import OtherCommands
from algobot.interface.statistics import Statistics
from algobot.interface.utils import (add_to_table, clear_table, create_popup, open_from_msg_box,
                                     show_and_bring_window_to_front)
from algobot.news_scraper import scrape_news
from algobot.slots import initiate_slots
from algobot.telegram_bot import TelegramBot
from algobot.threads import backtest_thread, bot_thread, optimizer_thread, worker_thread
from algobot.traders.backtester import Backtester
from algobot.traders.real_trader import RealTrader
from algobot.traders.simulation_trader import SimulationTrader

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
        self.other_commands = OtherCommands(self)  # Loading other commands
        self.about = About(self)  # Loading about information
        self.strategy_builder = StrategyBuilder(self)
        self.statistics = Statistics(self)  # Loading statistics
        self.thread_pool = QThreadPool(self)  # Initiating threading pool
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

        self.interface_dictionary = get_interface_dictionary(self)
        self.advanced_logging = False
        self.running_live = False
        self.simulation_running_live = False
        self.optimizer: Union[Backtester, None] = None
        self.backtester: Union[Backtester, None] = None
        self.trader: Union[RealTrader, None] = None
        self.simulation_trader: Union[SimulationTrader, None] = None
        self.simulation_lower_interval_data: Union[Data, None] = None
        self.lower_interval_data: Union[Data, None] = None
        self.telegram_bot = None
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

        # TODO: Refactor this. We call this here, because we rely on loading the previous state if it exists.
        load_hide_show_strategies(self.configuration)

        self.graph_update_seconds = 1
        self.graph_update_schedule: List[float or None] = [None, None]  # LIVE, SIM

    def inform_telegram(self, message: str, stop_bot: bool = False):
        """
        Sends a notification to Telegram if some action is taken by the bot.
        :param message: Message to send.
        :param stop_bot: Boolean for whether bot should be stopped or not.
        """
        try:
            if self.telegram_bot is None:
                api_key = self.configuration.telegramApiKey.text()
                self.telegram_bot = TelegramBot(gui=self, token=api_key, bot_thread=None)

            chat_id = self.configuration.telegramChatID.text()
            if self.configuration.chat_pass:
                self.telegram_bot.send_message(chat_id, message)

            if stop_bot:
                self.telegram_bot.stop()
                self.telegram_bot = None
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
        news_thread = worker_thread.Worker(scrape_news)
        news_thread.signals.error.connect(self.news_thread_error)
        news_thread.signals.finished.connect(self.setup_news)
        news_thread.signals.restore.connect(lambda: self.refreshNewsButton.setEnabled(True))
        self.thread_pool.start(news_thread)

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
        ticker_thread = worker_thread.Worker(self.get_tickers)
        ticker_thread.signals.error.connect(self.tickers_thread_error)
        ticker_thread.signals.finished.connect(self.setup_tickers)
        ticker_thread.signals.restore.connect(lambda: self.configuration.updateTickers.setEnabled(True))
        self.thread_pool.start(ticker_thread)

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
        tickers = [ticker['symbol'] for ticker in Data(load_data=False, log=False).binance_client.get_all_tickers()]
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
        ticker_widgets = [config.tickerLineEdit, config.backtestTickerLineEdit, config.simulationTickerLineEdit,
                          config.optimizerTickerLineEdit]

        completer = QCompleter(filtered_tickers)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        for widget in ticker_widgets:
            widget.setCompleter(completer)

        full_completer = QCompleter(tickers)
        full_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.other_commands.csvGenerationTicker.setCompleter(full_completer)
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
        elif not isinstance(combos, dict):
            return True

        for value in combos.values():
            if not self.check_combos(value):
                return False
        return True

    def export_optimizer(self, file_type: str):
        """
        Export table rows to CSV file.
        :param file_type: Type of file to export optimizer results to.
        """
        if self.optimizer:
            if len(self.optimizer.optimizer_rows) > 0:
                optimizer_folder_path = create_folder('Optimizer Results')
                inner_path = os.path.join(optimizer_folder_path, self.optimizer.symbol)
                create_folder_if_needed(inner_path, optimizer_folder_path)
                default_file_name = self.optimizer.get_default_result_file_name('optimizer', ext=file_type.lower())
                default_path = os.path.join(inner_path, default_file_name)
                file_path, _ = QFileDialog.getSaveFileName(self, 'Save Optimizer', default_path,
                                                           f'{file_type} (*.{file_type.lower()})')
                if not file_path:
                    create_popup(self, "Export cancelled.")
                else:
                    self.optimizer.export_optimizer_rows(file_path, file_type)
                    create_popup(self, f'Exported successfully to {file_path}.')

                if open_from_msg_box(text='Do you want to open the optimization report?', title='Optimizer Report'):
                    open_file_or_folder(file_path)

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

        selected_symbol = self.interface_dictionary[caller]['configuration']['ticker'].text()
        download_symbol = config.optimizer_backtest_dict[caller]['dataType']

        if selected_symbol != download_symbol and download_symbol.lower() != 'imported':
            create_popup(self, f"{noun.capitalize()} symbol ({selected_symbol}) does not match downloaded symbol "
                               f"({download_symbol}). Change your ticker to ({download_symbol}) "
                               f"or download ({selected_symbol}) data to get rid of this error.")
            return False

        selected_interval = self.interface_dictionary[caller]['configuration']['interval'].currentText().lower()
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

        self.threads[OPTIMIZER] = optimizer_thread.OptimizerThread(gui=self, logger=self.logger, combos=combos)
        worker = self.threads[OPTIMIZER]
        worker.signals.started.connect(lambda: self.set_optimizer_buttons(running=True, clear=True))
        worker.signals.restore.connect(lambda: self.set_optimizer_buttons(running=False, clear=False))
        worker.signals.error.connect(lambda x: create_popup(self, x))
        if self.configuration.enabledOptimizerNotification.isChecked():
            worker.signals.finished.connect(lambda: self.inform_telegram('Optimizer has finished running.',
                                                                         stop_bot=True))
        worker.signals.activity.connect(lambda data: add_to_table(self.optimizerTableWidget, data=data,
                                                                  insert_date=False))
        self.thread_pool.start(worker)

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
        self.threads[BACKTEST] = backtest_thread.BacktestThread(gui=self, logger=self.logger)

        worker = self.threads[BACKTEST]
        worker.signals.started.connect(self.setup_backtester)
        worker.signals.activity.connect(self.update_backtest_gui)
        worker.signals.error.connect(self.end_crash_bot_and_create_popup)
        worker.signals.finished.connect(self.end_backtest)
        worker.signals.message.connect(lambda message: self.add_to_monitor(BACKTEST, message))
        worker.signals.restore.connect(lambda: self.disable_interface(disable=False, caller=BACKTEST))
        worker.signals.updateGraphLimits.connect(lambda x: update_backtest_graph_limits(gui=self, limit=x))
        self.thread_pool.start(worker)

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
        backtest_folder_path = create_folder('Backtest Results')
        inner_path = os.path.join(backtest_folder_path, self.backtester.symbol)
        create_folder_if_needed(inner_path, backtest_folder_path)
        default_file = os.path.join(inner_path, self.backtester.get_default_result_file_name())
        file_name, _ = QFileDialog.getSaveFileName(self, 'Save Result', default_file, 'TXT (*.txt)')
        file_name = file_name.strip()
        file_name = file_name if file_name != '' else None

        if not file_name:
            self.add_to_backtest_monitor('Ended backtest.')
        else:
            path = self.backtester.write_results(result_file=file_name)
            self.add_to_backtest_monitor(f'Ended backtest and saved results to {path}.')

            if open_from_msg_box(text=f"Backtest results have been saved to {path}.", title="Backtest Results"):
                open_file_or_folder(path)

        self.backtestProgressBar.setValue(100)

    def update_backtest_gui(self, updated_dict: dict, add_data: bool = True, update_progress_bar: bool = True):
        """
        Updates activity backtest details to GUI.
        :param update_progress_bar: Boolean for whether progress bar should be updated based on the dictionary provided.
        :param add_data: Boolean to determine whether to add data to graph or not.
        :param updated_dict: Dictionary containing backtest data.
        """
        if update_progress_bar:
            self.backtestProgressBar.setValue(updated_dict['percentage'])

        net = updated_dict['net']
        utc = updated_dict['utc']

        if net < self.backtester.starting_balance:
            self.backtestProfitLabel.setText("Loss")
            self.backtestProfitPercentageLabel.setText("Loss Percentage")
        else:
            self.backtestProfitLabel.setText("Profit")
            self.backtestProfitPercentageLabel.setText("Profit Percentage")

        self.backtestBalance.setText(updated_dict['balance'])
        self.backtestPrice.setText(updated_dict['price'])
        self.backtestNet.setText(updated_dict['netString'])
        self.backtestCommissionsPaid.setText(updated_dict['commissionsPaid'])
        self.backtestProfit.setText(updated_dict['profit'])
        self.backtestProfitPercentage.setText(updated_dict['profitPercentage'])
        self.backtestTradesMade.setText(updated_dict['tradesMade'])
        self.backtestCurrentPeriod.setText(updated_dict['currentPeriod'])

        if add_data:
            graph_dict = self.interface_dictionary[BACKTEST]['mainInterface']['graph']
            add_data_to_plot(self, graph_dict, 0, y=net, timestamp=utc)

    def update_backtest_configuration_gui(self, stat_dict: dict):
        """
        Updates backtest interface initial configuration details.
        :param stat_dict: Dictionary containing configuration details.
        """
        self.backtestSymbol.setText(stat_dict['symbol'])
        self.backtestStartingBalance.setText(stat_dict['starting_balance'])
        self.backtestInterval.setText(stat_dict['interval'])
        self.backtestMarginEnabled.setText(stat_dict['margin_enabled'])
        self.backtestStopLossPercentage.setText(stat_dict['stop_loss_percentage'])
        self.backtestLossStrategy.setText(stat_dict['stop_loss_strategy'])
        self.backtestStartPeriod.setText(stat_dict['start_period'])
        self.backtestEndPeriod.setText(stat_dict['end_period'])
        if 'options' in stat_dict:
            self.backtestMovingAverage1.setText(stat_dict['options'][0][0])
            self.backtestMovingAverage2.setText(stat_dict['options'][0][1])
            if len(stat_dict['options']) > 1:
                self.backtestMovingAverage3.setText(stat_dict['options'][1][0])
                self.backtestMovingAverage4.setText(stat_dict['options'][1][1])

    def update_backtest_activity_based_on_graph(self, position: int, aux: int = -1):
        """
        Updates backtest activity based on where the line is in the backtest graph.
        :param position: Position to show activity at.
        :param aux: Shift position by the number provided.
        """
        if self.backtester is not None:
            if 1 <= position + aux < len(self.backtester.past_activity):
                try:
                    self.update_backtest_gui(self.backtester.past_activity[position + aux], add_data=False,
                                             update_progress_bar=False)
                except IndexError as e:
                    self.logger.exception(str(e))

    def reset_backtest_cursor(self):
        """
        Resets backtest hover cursor to end of graph.
        """
        graph_dict = get_graph_dictionary(self, self.backtestGraph)
        if self.backtester is not None and graph_dict.get('line') is not None:
            index = len(self.backtester.past_activity)
            graph_dict['line'].setPos(index)
            self.update_backtest_activity_based_on_graph(index)

    def setup_backtester(self, configuration_dictionary: dict):
        """
        Set up backtest GUI with dictionary provided.
        :param configuration_dictionary: Dictionary with configuration details.
        """
        interface_dict = self.interface_dictionary[BACKTEST]['mainInterface']
        symbol = configuration_dictionary['symbol']
        interval = configuration_dictionary['interval']
        destroy_graph_plots(self, interface_dict['graph'])
        setup_graph_plots(self, interface_dict['graph'], self.backtester, GraphType.NET)
        set_backtest_graph_limits_and_empty_plots(self)
        self.update_backtest_configuration_gui(configuration_dictionary)
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

            msg_box = QMessageBox
            ret = msg_box.question(self, 'Warning', message, msg_box.Yes | msg_box.No)
            return ret == msg_box.Yes
        return True

    def validate_ticker(self, caller: int):
        """
        Validate ticker provided before running a bot.
        """
        selected_ticker = self.interface_dictionary[caller]['configuration']['ticker'].text()
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
        worker = bot_thread.BotThread(gui=self, caller=caller, logger=self.logger)
        worker.signals.small_error.connect(lambda x: create_popup(self, x))
        worker.signals.error.connect(self.end_crash_bot_and_create_popup)
        worker.signals.activity.connect(self.add_to_monitor)
        worker.signals.started.connect(self.initial_bot_ui_setup)
        worker.signals.updated.connect(self.update_interface_info)
        worker.signals.progress.connect(self.download_progress_update)
        worker.signals.add_trade.connect(lambda trade: self.update_trades_table_and_activity_monitor(trade, caller))
        worker.signals.restore.connect(lambda: self.disable_interface(disable=False, caller=caller))

        # All these below are for Telegram.
        worker.signals.force_long.connect(lambda: self.force_long(LIVE))
        worker.signals.force_short.connect(lambda: self.force_short(LIVE))
        worker.signals.exit_position.connect(lambda: self.exit_position(LIVE))
        worker.signals.wait_override.connect(lambda: self.exit_position(LIVE, False))
        worker.signals.pause.connect(lambda: self.pause_or_resume_bot(LIVE))
        worker.signals.resume.connect(lambda: self.pause_or_resume_bot(LIVE))
        worker.signals.set_custom_stop_loss.connect(self.set_custom_stop_loss)
        worker.signals.remove_custom_stop_loss.connect(lambda: self.set_custom_stop_loss(LIVE, False))
        self.thread_pool.start(worker)

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
        thread = worker_thread.Worker(lambda: self.end_bot_gracefully(caller=caller))
        thread.signals.error.connect(lambda x: create_popup(self, x))
        thread.signals.finished.connect(lambda: self.add_end_bot_status(caller=caller))
        thread.signals.restore.connect(lambda: self.reset_bot_interface(caller=caller))
        self.thread_pool.start(thread)

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
        temp_trader = None
        elapsed = time.time()

        if caller == SIMULATION:
            self.simulation_running_live = False
            if self.simulation_trader:
                self.simulation_trader.data_view.download_loop = False

                if self.simulation_lower_interval_data:
                    self.simulation_lower_interval_data.download_loop = False

                while not self.simulation_trader.completed_loop:
                    self.simulation_running_live = False
                    if time.time() > elapsed + 15:
                        break

                temp_trader = self.simulation_trader
                if self.simulation_lower_interval_data:
                    self.simulation_lower_interval_data.dump_to_table()
                    self.simulation_lower_interval_data = None
        elif caller == LIVE:
            self.running_live = False
            if self.trader:
                self.trader.data_view.download_loop = False

                if self.lower_interval_data:
                    self.lower_interval_data.download_loop = False

                if self.configuration.chat_pass:
                    self.telegram_bot.send_message(self.configuration.telegramChatID.text(), "Bot has been ended.")
                if self.telegram_bot:
                    self.telegram_bot.stop()
                    self.telegram_bot = None

                while not self.trader.completed_loop:
                    self.running_live = False
                    if time.time() > elapsed + 15:
                        break

                temp_trader = self.trader
                if self.lower_interval_data:
                    self.lower_interval_data.dump_to_table()
                    self.lower_interval_data = None
        else:
            raise ValueError("Invalid type of caller provided.")

        if callback:
            callback.emit("Dumping data to database...")

        if temp_trader:
            temp_trader.log_trades_and_daily_net()
            temp_trader.data_view.dump_to_table()

        if callback:
            callback.emit("Dumped all new data to database.")

    def end_crash_bot_and_create_popup(self, caller: int, msg: str):
        """
        Function that force ends bot in the event that it crashes.
        """
        if caller == LIVE:
            self.running_live = False
            if self.lower_interval_data and not self.lower_interval_data.download_completed:
                self.download_progress_update(value=0, message="Lower interval data download failed.", caller=caller)
        elif caller == SIMULATION:
            self.simulation_running_live = False
            if self.simulation_lower_interval_data and not self.simulation_lower_interval_data.download_completed:
                self.download_progress_update(value=0, message="Lower interval data download failed.", caller=caller)

        trader = self.get_trader(caller=caller)
        if trader and caller != BACKTEST and not trader.data_view.download_completed:
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
        trader_position = trader.get_position()
        if trader_position is not None:
            self.add_to_monitor(caller, f"Detected {trader.get_position_string().lower()} position before bot run.")
        interface_dict = self.interface_dictionary[caller]['mainInterface']
        self.disable_interface(True, caller, False)
        self.enable_override(caller)
        destroy_graph_plots(self, interface_dict['graph'])
        destroy_graph_plots(self, interface_dict['averageGraph'])
        self.statistics.initialize_tab(trader.get_grouped_statistics(), tab_type=get_caller_string(caller))
        setup_graph_plots(self, interface_dict['graph'], trader, GraphType.NET)

        average_graph_dict = get_graph_dictionary(self, interface_dict['averageGraph'])
        if self.configuration.graphIndicatorsCheckBox.isChecked():
            average_graph_dict['enable'] = True
            setup_graph_plots(self, interface_dict['averageGraph'], trader, GraphType.AVG)
        else:
            average_graph_dict['enable'] = False

    def disable_interface(self, disable: bool, caller, everything: bool = False):
        """
        Function that will control trading configuration interfaces.
        :param everything: Disables everything during initialization.
        :param disable: If true, configuration settings get disabled.
        :param caller: Caller that determines which configuration settings get disabled.
        """
        disable = not disable
        self.interface_dictionary[caller]['configuration']['mainTab'].setEnabled(disable)
        self.interface_dictionary[caller]['mainInterface']['runBotButton'].setEnabled(disable)

        tab = self.configuration.get_category_tab(caller)
        for strategy_name in self.configuration.strategies:
            if strategy_name not in self.configuration.hidden_strategies:
                self.configuration.strategy_dict[tab, strategy_name, 'groupBox'].setEnabled(disable)

        if everything:
            self.interface_dictionary[caller]['mainInterface']['endBotButton'].setEnabled(disable)
        else:
            self.interface_dictionary[caller]['mainInterface']['endBotButton'].setEnabled(not disable)

    def update_interface_info(self, caller, value_dict: dict, grouped_dict: dict):
        """
        Updates interface elements based on caller.
        :param grouped_dict: Dictionary with which to populate the statistics window.
        :param value_dict: Dictionary containing statistics.
        :param caller: Object that determines which object gets updated.
        """
        self.statistics.modify_tab(grouped_dict, tab_type=get_caller_string(caller))
        self.update_main_interface_and_graphs(caller=caller, value_dict=value_dict)
        self.handle_position_buttons(caller=caller)
        self.handle_custom_stop_loss_buttons(caller=caller)

    def update_interface_text(self, caller: int, value_dict: dict):
        """
        Updates interface text based on caller and value dictionary provided.
        :param caller: Caller that decides which interface gets updated.
        :param value_dict: Dictionary with values to populate interface with.
        :return: None
        """
        main_interface_dictionary = self.interface_dictionary[caller]['mainInterface']
        main_interface_dictionary['profitLabel'].setText(value_dict['profitLossLabel'])
        main_interface_dictionary['profitValue'].setText(value_dict['profitLossValue'])
        main_interface_dictionary['percentageValue'].setText(value_dict['percentageValue'])
        main_interface_dictionary['netTotalValue'].setText(value_dict['netValue'])
        main_interface_dictionary['tickerLabel'].setText(value_dict['tickerLabel'])
        main_interface_dictionary['tickerValue'].setText(value_dict['tickerValue'])
        main_interface_dictionary['positionValue'].setText(value_dict['currentPositionValue'])

    def update_main_interface_and_graphs(self, caller: int, value_dict: dict):
        """
        Updates main interface GUI elements based on caller.
        :param value_dict: Dictionary with trader values in formatted data types.
        :param caller: Caller that decides which main interface gets updated.
        """
        self.update_interface_text(caller=caller, value_dict=value_dict)
        index = 0 if caller == LIVE else 1
        if self.graph_update_schedule[index] is None or time.time() > self.graph_update_schedule[index]:
            update_main_graphs(gui=self, caller=caller, value_dict=value_dict)
            self.graph_update_schedule[index] = time.time() + self.graph_update_seconds

    def destroy_trader(self, caller):
        """
        Destroys trader based on caller by setting them equal to none.
        :param caller: Caller that determines which trading object gets destroyed.
        """
        if caller == SIMULATION:
            self.simulation_trader = None
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
        main_dict = self.interface_dictionary[caller]['mainInterface']

        if trader.custom_stop_loss is None:
            main_dict['enableCustomStopLossButton'].setEnabled(True)
            main_dict['disableCustomStopLossButton'].setEnabled(False)
        else:
            main_dict['enableCustomStopLossButton'].setEnabled(False)
            main_dict['disableCustomStopLossButton'].setEnabled(True)

    def handle_position_buttons(self, caller):
        """
        Handles interface position buttons based on caller.
        :param caller: Caller object for whose interface buttons will be affected.
        """
        interface_dict = self.interface_dictionary[caller]['mainInterface']
        trader = self.get_trader(caller)

        in_position = trader.current_position is not None
        interface_dict['exitPositionButton'].setEnabled(in_position)
        interface_dict['waitOverrideButton'].setEnabled(in_position)

        if trader.current_position == LONG:
            interface_dict['forceLongButton'].setEnabled(False)
            interface_dict['forceShortButton'].setEnabled(True)
        elif trader.current_position == SHORT:
            interface_dict['forceLongButton'].setEnabled(True)
            interface_dict['forceShortButton'].setEnabled(False)
        elif trader.current_position is None:
            interface_dict['forceLongButton'].setEnabled(True)
            interface_dict['forceShortButton'].setEnabled(True)

    def enable_override(self, caller, enabled: bool = True):
        """
        Enables override interface for which caller specifies.
        :param enabled: Boolean that determines whether override is enabled or disable. By default, it is enabled.
        :param caller: Caller that will specify which interface will have its override interface enabled.
        """
        self.interface_dictionary[caller]['mainInterface']['overrideGroupBox'].setEnabled(enabled)
        self.interface_dictionary[caller]['mainInterface']['customStopLossGroupBox'].setEnabled(enabled)

    def exit_position_thread(self, caller, human_control: bool):
        """
        Thread that'll take care of exiting position.
        :param caller: Caller that will specify which trader will exit position.
        :param human_control: Boolean that will specify whether bot gives up control or not.
        """
        trader = self.get_trader(caller)
        trader.in_human_control = human_control
        if trader.current_position == LONG:
            if human_control:
                trader.sell_long('Force exited long.', force=True)
            else:
                trader.sell_long('Exited long because of override and resumed autonomous logic.', force=True)
        elif trader.current_position == SHORT:
            if human_control:
                trader.buy_short('Force exited short.', force=True)
            else:
                trader.buy_short('Exited short because of override and resumed autonomous logic.', force=True)
        # self.inform_telegram("Force exited position from GUI.", caller=caller)

    def set_exit_position_gui(self, caller, human_control: bool):
        """
        This function will configure GUI to reflect exit position aftermath.
        :param caller: Caller that will specify which interface's GUI will change.
        :param human_control: Boolean that will specify how interface's GUI will change.
        """
        text = "Resume Bot" if human_control else "Pause Bot"
        self.modify_override_buttons(caller=caller, pause_text=text, short_btn=True, long_btn=True, exit_btn=False,
                                     wait_btn=False)

    def exit_position(self, caller, human_control: bool = True):
        """
        Exits position by either giving up control or not. If the boolean humanControl is true, bot gives up control.
        If the boolean is false, the bot still retains control, but exits trade and waits for opposite trend.
        :param human_control: Boolean that will specify whether bot gives up control or not.
        :param caller: Caller that will specify which trader will exit position.
        """
        self.add_to_monitor(caller, 'Exiting position...')
        thread = worker_thread.Worker(lambda: self.exit_position_thread(caller=caller, human_control=human_control))
        thread.signals.started.connect(lambda: self.enable_override(caller=caller, enabled=False))
        thread.signals.finished.connect(lambda: self.set_exit_position_gui(caller=caller, human_control=human_control))
        thread.signals.restore.connect(lambda: self.enable_override(caller=caller, enabled=True))
        thread.signals.error.connect(lambda x: create_popup(self, x))
        self.thread_pool.start(thread)

    def set_force_long_gui(self, caller):
        """
        Thread that'll configure GUI to reflect force long aftermath.
        :param caller: Caller that will specify which interface's GUI will change.
        """
        self.modify_override_buttons(caller=caller, pause_text="Resume Bot", short_btn=True, long_btn=False,
                                     exit_btn=True, wait_btn=True)

    def force_long_thread(self, caller):
        """
        Thread that'll take care of forcing long.
        :param caller: Caller that will specify which trader will force long.
        """
        trader = self.get_trader(caller)
        trader.in_human_control = True
        if trader.current_position == SHORT:
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
        thread = worker_thread.Worker(lambda: self.force_long_thread(caller=caller))
        thread.signals.started.connect(lambda: self.enable_override(caller=caller, enabled=False))
        thread.signals.finished.connect(lambda: self.set_force_long_gui(caller=caller))
        thread.signals.restore.connect(lambda: self.enable_override(caller=caller, enabled=True))
        thread.signals.error.connect(lambda x: create_popup(self, x))
        self.thread_pool.start(thread)

    def set_force_short_gui(self, caller):
        """
        Thread that'll configure GUI to reflect force short aftermath.
        :param caller: Caller that will specify which interface's GUI will change.
        """
        self.modify_override_buttons(caller=caller, pause_text="Resume Bot", short_btn=False, long_btn=True,
                                     exit_btn=True, wait_btn=True)

    def force_short_thread(self, caller):
        """
        Thread that'll take care of forcing short.
        :param caller: Caller that will specify which trader will force short.
        """
        trader = self.get_trader(caller)
        trader.in_human_control = True
        if trader.current_position == LONG:
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
        thread = worker_thread.Worker(lambda: self.force_short_thread(caller=caller))
        thread.signals.started.connect(lambda: self.enable_override(caller=caller, enabled=False))
        thread.signals.finished.connect(lambda: self.set_force_short_gui(caller=caller))
        thread.signals.restore.connect(lambda: self.enable_override(caller=caller, enabled=True))
        thread.signals.error.connect(lambda x: create_popup(self, x))
        self.thread_pool.start(thread)

    def modify_override_buttons(self,
                                caller,
                                pause_text: str,
                                short_btn: bool,
                                long_btn: bool,
                                exit_btn: bool,
                                wait_btn: bool):
        """
        Modify force override button with booleans provided above for caller.
        :param caller: Caller object that specifies which trading object will have its override buttons modified.
        :param pause_text: Text to show in the pause bot button.
        :param short_btn: Boolean that'll determine if the force short button is enabled or disabled.
        :param long_btn: Boolean that'll determine if the force long button is enabled or disabled.
        :param exit_btn: Boolean that'll determine if the exit button is enabled or disabled.
        :param wait_btn: Boolean that'll determine if the wait override button is enabled or disabled.
        """
        interface_dict = self.interface_dictionary[caller]['mainInterface']
        interface_dict['pauseBotButton'].setText(pause_text)
        interface_dict['forceShortButton'].setEnabled(short_btn)
        interface_dict['forceLongButton'].setEnabled(long_btn)
        interface_dict['exitPositionButton'].setEnabled(exit_btn)
        interface_dict['waitOverrideButton'].setEnabled(wait_btn)

    def pause_or_resume_bot(self, caller):
        """
        Pauses or resumes bot logic based on caller.
        :param caller: Caller object that specifies which trading object will be paused or resumed.
        """
        trader = self.get_trader(caller)
        pause_button = self.interface_dictionary[caller]['mainInterface']['pauseBotButton']
        if pause_button.text() == 'Pause Bot':
            trader.in_human_control = True
            pause_button.setText('Resume Bot')
            self.add_to_monitor(caller, 'Pausing bot logic.')
        else:
            trader.in_human_control = False
            pause_button.setText('Pause Bot')
            self.add_to_monitor(caller, 'Resuming bot logic.')

    def set_advanced_logging(self, boolean: bool):
        """
        Sets logging standard.
        :param boolean: Boolean that will determine whether logging is advanced or not. If true, advanced, else regular.
        """
        self.advanced_logging = boolean
        if self.advanced_logging:
            self.add_to_live_activity_monitor('Logging method has been changed to advanced.')
            self.add_to_simulation_activity_monitor('Logging method has been changed to advanced.')
        else:
            self.add_to_live_activity_monitor('Logging method has been changed to simple.')
            self.add_to_simulation_activity_monitor('Logging method has been changed to simple.')

    def set_custom_stop_loss(self, caller, enable: bool = True, foreign_value: float or None = None):
        """
        Enables or disables custom stop loss.
        :param foreign_value: Foreign value to set for custom stop loss not related to GUI.
        :param enable: Boolean that determines whether custom stop loss is enabled or disabled. Default is enable.
        :param caller: Caller that decides which trader object gets the stop loss.
        """
        trader = self.get_trader(caller)
        main_dict = self.interface_dictionary[caller]['mainInterface']
        if enable:
            if foreign_value is None:
                custom_stop_loss = main_dict['customStopLossValue'].value()
            else:
                custom_stop_loss = foreign_value
                main_dict['customStopLossValue'].setValue(round(foreign_value, trader.precision))
            trader.custom_stop_loss = custom_stop_loss
            main_dict['enableCustomStopLossButton'].setEnabled(False)
            main_dict['disableCustomStopLossButton'].setEnabled(True)
            self.add_to_monitor(caller, f'Set custom stop loss at ${custom_stop_loss}')
        else:
            trader.custom_stop_loss = None
            main_dict['enableCustomStopLossButton'].setEnabled(True)
            main_dict['disableCustomStopLossButton'].setEnabled(False)
            self.add_to_monitor(caller, 'Removed custom stop loss.')

    @staticmethod
    def test_table(table, trade: list):
        """
        Initial function made to test table functionality in QT.
        :param table: Table to insert row at.
        :param trade: Trade information to add.
        """
        row_position = table.rowCount()
        columns = table.columnCount()

        table.insertRow(row_position)
        for column in range(columns):
            cell = QTableWidgetItem(str(trade[column]))
            table.setItem(row_position, column, cell)

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
        table = self.interface_dictionary[caller]['mainInterface']['historyTable']
        trader = self.get_trader(caller)

        if not trader:
            return

        trade_data = [trade['orderID'],
                      trade['pair'],
                      trade['price'],
                      trade['percentage'],
                      trade['profit'],
                      trade['method'],
                      trade['action']]

        add_to_table(table, trade_data)
        self.add_to_monitor(caller, trade['action'])

        if caller == LIVE and self.telegram_bot and self.configuration.enableTelegramSendMessage.isChecked():
            self.inform_telegram(message=trade['action'])

        monitor = self.get_activity_table(caller=caller)
        monitor.scrollToBottom()
        table.scrollToBottom()

    def closeEvent(self, event):  # pylint:disable=invalid-name
        """
        Close event override. Makes user confirm they want to end program if something is running live.
        :param event: close event
        """
        save_state(self.configuration)
        msg_box = QMessageBox
        message = ""
        if self.simulation_running_live and self.running_live:
            message = "There is a live bot and a simulation running."
        elif self.simulation_running_live:
            message = "There is a simulation running."
        elif self.running_live:
            message = "There is a live bot running."
        ret = msg_box.question(self, 'Close?', f"{message} Are you sure you want to end Algobot?",
                               msg_box.Yes | msg_box.No)

        if ret == msg_box.Yes:
            if self.running_live:
                self.end_bot_gracefully(caller=LIVE)
            elif self.simulation_running_live:
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
            thread = worker_thread.Worker(self.trader.retrieve_margin_values)
            thread.signals.finished.connect(lambda: create_popup(self, 'Successfully updated values.'))
            thread.signals.error.connect(lambda x: create_popup(self, x))
            self.thread_pool.start(thread)
        else:
            create_popup(self, 'There is currently no live bot running.')

    def get_preferred_symbol(self) -> Union[None, str]:
        """
        Get preferred symbol on precedence of live bot, simulation bot, then finally backtest bot.
        :return: Preferred symbol.
        """
        if self.trader:
            return self.trader.symbol
        elif self.simulation_trader:
            return self.simulation_trader.symbol
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
            symbol = self.interface_dictionary[caller]['configuration']['ticker'].text()
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
            symbol = self.interface_dictionary[caller]['configuration']['ticker'].text()
            if symbol.strip() == '':
                webbrowser.open("https://www.tradingview.com/")
            else:
                webbrowser.open(f"https://www.tradingview.com/symbols/{symbol}/?exchange=BINANCE")

    def export_trades(self, caller):
        """
        Export trade history to a CSV file.
        :param caller: Caller that'll determine which trades get exported.
        """
        table = self.interface_dictionary[caller]['mainInterface']['historyTable']
        label = self.interface_dictionary[caller]['mainInterface']['historyLabel']
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
            default_file = os.path.join(path, 'live_trades.csv')
        else:
            default_file = os.path.join(path, 'simulation_trades.csv')

        path, _ = QFileDialog.getSaveFileName(self, 'Export Trades', default_file, 'CSV (*.csv)')

        if path:
            with open(path, 'w', encoding='utf-8') as f:
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
        table = self.interface_dictionary[caller]['mainInterface']['historyTable']
        label = self.interface_dictionary[caller]['mainInterface']['historyLabel']
        path = create_folder("Trade History")
        path, _ = QFileDialog.getOpenFileName(self, 'Import Trades', path, "CSV (*.csv)")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                rows = f.readlines()
                for row in rows:
                    row = row.strip().split(',')
                    add_to_table(table, row, insert_date=False)
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
            return self.simulation_lower_interval_data
        elif caller == LIVE:
            return self.lower_interval_data
        else:
            raise TypeError("Invalid type of caller specified.")

    def get_trader(self, caller: int) -> Union[SimulationTrader, Backtester]:
        """
        Returns a trader object.
        :param caller: Caller that decides which trader object gets returned.
        :return: Trader object.
        """
        if caller == SIMULATION:
            return self.simulation_trader
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
    """
    Exception hook.
    """
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    main()
