"""
Main bot thread (sim or live bot).
"""

import time
import traceback
from datetime import datetime, timedelta

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from algobot.data import Data
from algobot.enums import LIVE, SIMULATION
from algobot.helpers import convert_long_interval, convert_small_interval, get_elapsed_time, parse_precision
from algobot.interface.config_utils.strategy_utils import get_strategies
from algobot.interface.config_utils.telegram_utils import test_telegram
from algobot.telegram_bot import TelegramBot
from algobot.traders.real_trader import RealTrader
from algobot.traders.simulation_trader import SimulationTrader


class BotSignals(QObject):
    """
    Signals available for the BotThread.
    """
    small_error = pyqtSignal(str)  # Signal emitted when small errors such as internet losses occur.
    started = pyqtSignal(str)  # Signal emitted when bot first starts.
    activity = pyqtSignal(str, str)  # Signal emitted to broadcast current activity.
    updated = pyqtSignal(str, dict, dict)  # Signal emitted when bot is updated.
    finished = pyqtSignal()  # Signal emitted when bot is ended.
    error = pyqtSignal(str, str)  # Signal emitted when a critical error occurs.
    restore = pyqtSignal()  # Signal emitted to restore GUI.
    progress = pyqtSignal(int, str, str)  # Signal emitted to broadcast progress.
    add_trade = pyqtSignal(dict)  # Signal emitted when a transaction occurs.

    # All of these below are for Telegram integration.
    force_long = pyqtSignal()  # Signal emitted to force a long position.
    force_short = pyqtSignal()  # Signal emitted to force a short position.
    exit_position = pyqtSignal()  # Signal emitted to force exit a position.
    wait_override = pyqtSignal()  # Signal emitted to wait override a position.
    resume = pyqtSignal()  # Signal emitted to resume bot logic.
    pause = pyqtSignal()  # Signal emitted to pause bot logic.
    remove_custom_stop_loss = pyqtSignal()  # Signal emitted to remove custom stop loss.
    set_custom_stop_loss = pyqtSignal(str, bool, float)  # Signal emitted to set a custom stop loss.


class BotThread(QRunnable):
    """
    Main bot thread to run simulations and live bots.
    """
    def __init__(self, caller: int, gui, logger):
        super(BotThread, self).__init__()
        self.signals = BotSignals()
        self.logger = logger
        self.gui = gui
        self.starting_time = time.time()
        self.elapsed = '1 second'  # Total elapsed run time.
        self.percentage = None  # Total percentage gain or loss.

        self.daily_interval_seconds = 86400  # Interval for daily percentage.
        self.daily_percentage = 0  # Initial change percentage.
        self.previous_day_time = None  # Previous day net time to compare to.
        self.previous_day_net = None  # Previous day net value to compare to.

        self.schedule_period = None  # Next schedule period in string format.
        self.next_scheduled_event = None  # These are for periodic scheduling. This variable holds next schedule event.
        self.schedule_seconds = None  # Amount of seconds to schedule in.

        self.lower_interval_notification = False
        self.lower_trend = 'None'
        self.telegram_chat_id = gui.configuration.telegramChatID.text()
        self.caller = caller
        self.trader = None

        self.failed = False  # All these variables pertain to bot failures.
        self.fail_count = 0  # Current amount of times the bot has failed.
        self.fail_limit = gui.configuration.failureLimitSpinBox.value()
        self.fail_sleep = gui.configuration.failureSleepSpinBox.value()
        self.fail_error = ''

    def initialize_lower_interval_trading(self, caller, interval: str):
        """
        Initializes lower interval trading data object.
        :param caller: Caller that determines whether lower interval is for simulation or live bot.
        :param interval: Current interval for simulation or live bot.
        """
        sorted_intervals = ('1m', '3m', '5m', '15m', '30m', '1h', '2h', '12h', '4h', '6h', '8h', '1d', '3d')
        gui = self.gui
        symbol = self.trader.symbol

        if interval != '1m':
            lower_interval = sorted_intervals[sorted_intervals.index(interval) - 1]
            interval_string = convert_small_interval(lower_interval)
            self.lower_interval_notification = True
            self.signals.activity.emit(caller, f'Retrieving {symbol} data for {interval_string.lower()} intervals...')

            if caller == LIVE:
                gui.lower_interval_data = Data(interval=lower_interval, symbol=symbol, update=False, limit_fetch=True)
                gui.lower_interval_data.custom_get_new_data(progress_callback=self.signals.progress, remove_first=True,
                                                            caller=LIVE)
            elif caller == SIMULATION:
                gui.simulation_lower_interval_data = Data(interval=lower_interval, symbol=symbol, update=False,
                                                          limit_fetch=True)
                gui.simulation_lower_interval_data.custom_get_new_data(progress_callback=self.signals.progress,
                                                                       remove_first=True, caller=SIMULATION)
            else:
                raise TypeError("Invalid type of caller specified.")

            lower_data = gui.lower_interval_data if caller == LIVE else gui.simulation_lower_interval_data
            if not lower_data or not lower_data.download_completed:
                raise RuntimeError("Lower interval download failed.")
            self.signals.activity.emit(caller, "Retrieved lower interval data successfully.")
        else:
            self.signals.activity.emit(caller, "There is no lower interval than 1 minute intervals.")

    def create_trader(self, caller):
        """
        Creates a trader based on caller specified.
        :param caller: Caller that determines what type of trader will be created.
        """
        gui = self.gui
        config_dict = gui.interface_dictionary[caller]['configuration']
        symbol = config_dict['ticker'].text()
        precision = parse_precision(config_dict['precision'].currentText(), symbol)
        pretty_interval = config_dict['interval'].currentText()
        interval = convert_long_interval(pretty_interval)

        if caller == SIMULATION:
            starting_balance = gui.configuration.simulationStartingBalanceSpinBox.value()
            self.signals.activity.emit(caller, f"Retrieving {symbol} data for {pretty_interval.lower()} intervals...")
            gui.simulation_trader = SimulationTrader(starting_balance=starting_balance,
                                                     symbol=symbol,
                                                     interval=interval,
                                                     load_data=True,
                                                     update_data=False,
                                                     precision=precision)
            gui.simulation_trader.data_view.custom_get_new_data(progress_callback=self.signals.progress,
                                                                remove_first=True, caller=SIMULATION)
        elif caller == LIVE:
            api_secret = gui.configuration.binanceApiSecret.text()
            api_key = gui.configuration.binanceApiKey.text()
            tld = 'com' if gui.configuration.otherRegionRadio.isChecked() else 'us'
            is_isolated = gui.configuration.isolatedMarginAccountRadio.isChecked()
            self.check_api_credentials(api_key=api_key, api_secret=api_secret)
            self.signals.activity.emit(caller, f"Retrieving {symbol} data for {pretty_interval.lower()} intervals...")
            gui.trader = RealTrader(api_secret=api_secret,
                                    api_key=api_key,
                                    interval=interval,
                                    symbol=symbol,
                                    tld=tld,
                                    is_isolated=is_isolated,
                                    load_data=True,
                                    update_data=False,
                                    precision=precision)
            gui.trader.data_view.custom_get_new_data(progress_callback=self.signals.progress, remove_first=True,
                                                     caller=LIVE)
        else:
            raise ValueError("Invalid caller.")

        self.trader: SimulationTrader = self.gui.get_trader(caller)
        self.trader.add_trade_callback = self.signals.add_trade  # Passing an add trade call black.
        self.trader.data_view.callback = self.signals.activity  # Passing activity signal to data object.
        self.trader.data_view.caller = caller  # Passing caller to data object.
        if not self.trader.data_view.download_completed:
            raise RuntimeError("Download failed.")

        self.signals.activity.emit(caller, "Retrieved data successfully.")

        if config_dict['lowerIntervalCheck'].isChecked():
            self.initialize_lower_interval_trading(caller=caller, interval=interval)

    @staticmethod
    def check_api_credentials(api_key: str, api_secret: str):
        """
        Helper function that checks API credentials specified. Needs to have more tests.
        :param api_key: API key for Binance. (for now)
        :param api_secret: API secret for Binance. (for now)
        """
        if len(api_secret) == 0:
            raise ValueError('Please specify an API secret key. No API secret key found.')

        if len(api_key) == 0:
            raise ValueError("Please specify an API key. No API key found.")

    def initialize_scheduler(self):
        """
        Initializes a scheduler for lower interval data.
        """
        gui = self.gui
        measurement = gui.configuration.schedulingTimeUnit.value()
        unit = gui.configuration.schedulingIntervalComboBox.currentText()
        self.schedule_period = f'{measurement} {unit.lower()}'

        if unit == "Seconds":
            seconds = measurement
        elif unit == "Minutes":
            seconds = measurement * 60
        elif unit == "Hours":
            seconds = measurement * 3600
        elif unit == "Days":
            seconds = measurement * 3600 * 24
        else:
            raise ValueError("Invalid type of unit.")

        message = f'Initiated periodic statistics notification every {self.schedule_period}.'
        self.gui.telegram_bot.send_message(self.telegram_chat_id, message=message)

        self.schedule_seconds = seconds
        self.next_scheduled_event = datetime.now() + timedelta(seconds=seconds)

    def handle_scheduler(self):
        """
        Handles lower data interval notification. If the current time is equal or later than the next scheduled event,
        a message is sent via Telegram.
        """
        if self.next_scheduled_event and datetime.now() >= self.next_scheduled_event:
            self.gui.telegram_bot.send_statistics_telegram(self.telegram_chat_id, self.schedule_period)
            self.next_scheduled_event = datetime.now() + timedelta(seconds=self.schedule_seconds)

    def set_parameters(self, caller: int):
        """
        Retrieves moving average options and loss settings based on caller.
        :param caller: Caller that dictates which parameters get set.
        """
        config = self.gui.configuration
        loss_dict = config.get_loss_settings(caller)
        take_profit_dict = config.get_take_profit_settings(caller)

        trader: SimulationTrader = self.gui.get_trader(caller)
        trader.apply_take_profit_settings(take_profit_dict)
        trader.apply_loss_settings(loss_dict)
        trader.setup_strategies(get_strategies(config, caller))
        trader.output_configuration()

    def setup_bot(self, caller):
        """
        Initial full bot setup based on caller.
        :param caller: Caller that will determine what type of trader will be instantiated.
        """
        self.create_trader(caller)
        self.set_parameters(caller)

        if caller == LIVE:
            if self.gui.configuration.enableTelegramTrading.isChecked():
                self.initialize_telegram_bot()
            if self.gui.configuration.schedulingStatisticsCheckBox.isChecked():
                self.initialize_scheduler()
            self.gui.running_live = True
        elif caller == SIMULATION:
            self.gui.simulation_running_live = True
        else:
            raise RuntimeError("Invalid type of caller specified.")

    def update_data(self, caller):
        """
        Updates data if updated data exists for caller object.
        :param caller: Object type that will be updated.
        """
        trader = self.gui.get_trader(caller)
        if not trader.data_view.data_is_updated():
            trader.data_view.update_data()

    def handle_trading(self, caller):
        """
        Handles trading by checking if automation mode is on or manual.
        :param caller: Object for which function will handle trading.
        """
        trader = self.gui.get_trader(caller)
        trader.main_logic(log_data=self.gui.advanced_logging)

    def handle_current_and_trailing_prices(self, caller):
        """
        Handles trailing prices for caller object.
        :param caller: Trailing prices for what caller to be handled for.
        """
        trader: SimulationTrader = self.gui.get_trader(caller)
        trader.data_view.get_current_data()
        trader.current_price = trader.data_view.current_values['close']
        trader.handle_trailing_prices()

    def handle_logging(self, caller):
        """
        Handles logging type for caller object.
        :param caller: Object those logging will be performed.
        """
        if self.gui.advanced_logging:
            self.gui.get_trader(caller).output_basic_information()

    def initialize_telegram_bot(self):
        """
        Attempts to initiate Telegram bot.
        """
        gui = self.gui
        test_telegram(config_obj=gui.configuration)
        api_key = gui.configuration.telegramApiKey.text()
        gui.telegram_bot = TelegramBot(gui=gui, token=api_key, bot_thread=self)
        gui.telegram_bot.start()
        self.signals.activity.emit(LIVE, 'Started Telegram bot.')
        if self.gui.telegram_bot and gui.configuration.chat_pass:
            self.gui.telegram_bot.send_message(self.telegram_chat_id, "Started Telegram bot.")

    def handle_lower_interval_cross(self, caller, previous_lower_trend) -> bool or None:
        """
        Handles logic and notifications for lower interval cross data.
        :param previous_lower_trend: Previous lower trend. Used to check if notification is necessary.
        :param caller: Caller for which we will check lower interval cross data.
        """
        if self.lower_interval_notification:
            trader: SimulationTrader = self.gui.get_trader(caller)
            lower_data = self.gui.get_lower_interval_data(caller)
            lower_data.get_current_data()
            lower_trend = trader.get_trend(dataObject=lower_data, log_data=self.gui.advanced_logging)
            self.lower_trend = str(lower_trend)
            if previous_lower_trend != lower_trend:
                message = f'{self.lower_trend.capitalize()} trend detected on lower interval data.'
                self.signals.activity.emit(caller, message)
                if self.gui.configuration.enableTelegramNotification.isChecked() and caller == LIVE:
                    self.gui.telegram_bot.send_message(message=message, chat_id=self.telegram_chat_id)
            return lower_trend

    def set_daily_percentages(self, trader, net):
        """
        Sets daily percentage gain or loss percentage values.
        :param trader: Trader object.
        :param net: Current new value.
        """
        if self.previous_day_time is None:  # This logic is for daily percentage yields.
            if time.time() - self.starting_time >= self.daily_interval_seconds:
                self.previous_day_time = time.time()
                self.previous_day_net = net
                self.daily_percentage = 0
            else:
                self.daily_percentage = self.percentage  # Same as current percentage because of lack of values.
        else:
            if time.time() - self.previous_day_time >= self.daily_interval_seconds:
                trader.daily_change_nets.append(trader.get_profit_percentage(self.previous_day_net, net))
                self.previous_day_time = time.time()
                self.previous_day_net = net
                self.daily_percentage = 0
            else:
                self.daily_percentage = trader.get_profit_percentage(self.previous_day_net, net)

    def get_statistics(self):
        """
        Returns current bot statistics in a dictionary.
        :return: Current statistics in a dictionary.
        """
        trader: SimulationTrader = self.trader
        net = trader.get_net()
        profit = trader.get_profit()

        self.percentage = trader.get_profit_percentage(trader.starting_balance, net)
        self.elapsed = get_elapsed_time(self.starting_time)
        self.set_daily_percentages(trader=trader, net=net)

        grouped_dict = trader.get_grouped_statistics()
        grouped_dict['general']['net'] = f'${round(net, 2)}'
        grouped_dict['general']['profit'] = f'${round(profit, 2)}'
        grouped_dict['general']['elapsed'] = self.elapsed
        grouped_dict['general']['totalPercentage'] = f'{round(self.percentage, 2)}%'
        grouped_dict['general']['dailyPercentage'] = f'{round(self.daily_percentage, 2)}%'
        grouped_dict['general']['lowerTrend'] = self.lower_trend

        value_dict = {
            'profitLossLabel': trader.get_profit_or_loss_string(profit=profit),
            'profitLossValue': f'${abs(round(profit, 2))}',
            'percentageValue': f'{round(self.percentage, 2)}%',
            'netValue': f'${round(net, 2)}',
            'tickerValue': f'${trader.current_price}',
            'tickerLabel': trader.symbol,
            'currentPositionValue': trader.get_position_string(),
            'net': net,
            'price': trader.current_price,
        }

        return value_dict, grouped_dict

    def trading_loop(self, caller):
        """
        Main loop that runs based on caller.
        :param caller: Caller object that determines which bot is running.
        """
        lower_trend = None  # This variable is used for lower trend notification logic.
        running_loop = self.gui.running_live if caller == LIVE else self.gui.simulation_running_live
        trader: SimulationTrader = self.gui.get_trader(caller=caller)

        while running_loop:
            trader.completed_loop = False  # This boolean is checked when bot is ended to ensure it finishes its loop.
            self.update_data(caller)  # Check for new updates.
            self.handle_logging(caller=caller)  # Handle logging.
            self.handle_current_and_trailing_prices(caller=caller)  # Handle trailing prices.
            self.handle_trading(caller=caller)  # Main logic function.
            self.handle_scheduler()  # Handle periodic statistics scheduler.
            lower_trend = self.handle_lower_interval_cross(caller, lower_trend)  # Check lower trend.
            value_dict, grouped_dict = self.get_statistics()  # Basic statistics of bot to update GUI.
            self.signals.updated.emit(caller, value_dict, grouped_dict)
            running_loop = self.gui.running_live if caller == LIVE else self.gui.simulation_running_live
            self.fail_count = 0  # Reset fail count as bot fixed itself.
            trader.completed_loop = True  # Set completed_loop to True. Or, there'll be an infinite loop in the GUI.

    def try_setting_up_bot(self) -> bool:
        """
        This function will try to setup the main bot for trading.
        :return: Boolean whether setup was successful or not.
        """
        try:
            self.setup_bot(caller=self.caller)
            self.signals.started.emit(self.caller)
            return True
        except Exception as e:
            error_message = traceback.format_exc()
            trader: SimulationTrader = self.gui.get_trader(self.caller)

            self.logger.critical(error_message)

            if trader:
                trader.output_message(f'Bot has crashed because of :{e}')
                trader.output_message(error_message)
            if self.gui.telegram_bot and self.gui.configuration.chat_pass:
                self.gui.telegram_bot.send_message(self.telegram_chat_id, f"Bot has crashed because of :{e}.")
                self.gui.telegram_bot.send_message(self.telegram_chat_id, error_message)

            self.fail_error = str(e)
            return False

    def handle_exception(self, e, trader):
        """
        This function will try to handle any exceptions that occur during bot run.
        :param e: Exception or error.
        :param trader: Trader object that faced the bug.
        """
        self.failed = True  # Boolean that'll let the bot know it failed.
        self.fail_count += 1  # Increment fail_count by 1. There's a default limit of 10 fails.
        self.fail_error = str(e)  # This is the fail error that led to the crash.
        error_message = traceback.format_exc()  # Get error message.

        attempts_left = self.fail_limit - self.fail_count
        fail_sleep = self.fail_sleep
        self.signals.activity.emit(self.caller, f'{e} {attempts_left} attempts left. Retrying in {fail_sleep} seconds.')
        self.logger.critical(error_message)

        if trader:  # Log this message to the trader's log.
            trader.output_message(error_message, print_message=True)
            trader.output_message(f'Bot has crashed because of :{e}', print_message=True)
            trader.output_message(f"({self.fail_count})Trying again in {self.fail_sleep} seconds.", print_message=True)

        try:
            if self.gui.telegram_bot and self.gui.configuration.chat_pass:  # Send crash information through Telegram.
                self.gui.telegram_bot.send_message(self.telegram_chat_id, f"Bot has crashed because of :{e}.")
                if self.fail_count == self.fail_limit:
                    self.gui.telegram_bot.send_message(self.telegram_chat_id, error_message)
                    self.gui.telegram_bot.send_message(self.telegram_chat_id, "Bot has died.")
                else:
                    fail_count = self.fail_count
                    gui = self.gui
                    gui.telegram_bot.send_message(self.telegram_chat_id, f"({fail_count})Trying again in "
                                                                      f"{fail_sleep} seconds.")
        except Exception as telegram_error:
            self.logger.critical(str(telegram_error))

        time.sleep(self.fail_sleep)  # Sleep for some seconds before reattempting a fix.
        trader.retrieve_margin_values()  # Update bot margin values.
        trader.check_current_position()  # Check position it's in.

    def run_loop(self, trader):
        """
        Main function that'll handle exceptions and keep the loop running.
        :param trader: Trader trading in the current loop.
        """
        while self.fail_count < self.fail_limit:
            running_loop = self.gui.running_live if self.caller == LIVE else self.gui.simulation_running_live
            if not running_loop:
                return
            try:
                self.trading_loop(self.caller)
                self.failed = False
                return
            except Exception as e:
                self.handle_exception(e, trader)

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        success = self.try_setting_up_bot()
        trader: SimulationTrader = self.gui.get_trader(self.caller)
        if success:
            self.run_loop(trader)

        if trader:
            trader.completed_loop = True  # If false, this will cause an infinite loop.
            is_simulation = trader == self.gui.simulation_trader
            trader.get_run_result(is_simulation=is_simulation)

        if self.fail_limit == self.fail_count or self.failed or not success:
            self.signals.error.emit(self.caller, str(self.fail_error))
            self.signals.restore.emit()
