import time
import traceback
from datetime import datetime, timedelta

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

import algobot.helpers as helpers
from algobot.data import Data
from algobot.enums import BEARISH, BULLISH, LIVE, SIMULATION
from algobot.telegramBot import TelegramBot
from algobot.traders.realtrader import RealTrader
from algobot.traders.simulationtrader import SimulationTrader


class BotSignals(QObject):
    smallError = pyqtSignal(str)  # Signal emitted when small errors such as internet losses occur.
    started = pyqtSignal(int)  # Signal emitted when bot first starts.
    activity = pyqtSignal(int, str)  # Signal emitted to broadcast current activity.
    updated = pyqtSignal(int, dict, dict)  # Signal emitted when bot is updated.
    finished = pyqtSignal()  # Signal emitted when bot is ended.
    error = pyqtSignal(int, str)  # Signal emitted when a critical error occurs.
    restore = pyqtSignal()  # Signal emitted to restore GUI.
    progress = pyqtSignal(int, str, int)  # Signal emitted to broadcast progress.
    addTrade = pyqtSignal(dict)  # Signal emitted when a transaction occurs.

    # All of these below are for Telegram integration.
    forceLong = pyqtSignal()  # Signal emitted to force a long position.
    forceShort = pyqtSignal()  # Signal emitted to force a short position.
    exitPosition = pyqtSignal()  # Signal emitted to force exit a position.
    waitOverride = pyqtSignal()  # Signal emitted to wait override a position.
    resume = pyqtSignal()  # Signal emitted to resume bot logic.
    pause = pyqtSignal()  # Signal emitted to pause bot logic.
    removeCustomStopLoss = pyqtSignal()  # Signal emitted to remove custom stop loss.
    setCustomStopLoss = pyqtSignal(int, bool, float)  # Signal emitted to set a custom stop loss.


class BotThread(QRunnable):
    def __init__(self, caller: int, gui, logger):
        super(BotThread, self).__init__()
        self.signals = BotSignals()
        self.logger = logger
        self.gui = gui
        self.startingTime = time.time()
        self.elapsed = '1 second'  # Total elapsed run time.
        self.percentage = None  # Total percentage gain or loss.
        self.optionDetails = []  # This list will contain all the moving averages' information.
        self.lowerOptionDetails = []  # This list will contain all the lower interval's moving average information.

        self.dailyIntervalSeconds = 86400  # Interval for daily percentage.
        self.dailyPercentage = 0  # Initial change percentage.
        self.previousDayTime = None  # Previous day net time to compare to.
        self.previousDayNet = None  # Previous day net value to compare to.

        self.schedulePeriod = None  # Next schedule period in string format.
        self.nextScheduledEvent = None  # These are for periodic scheduling. This variable holds next schedule event.
        self.scheduleSeconds = None  # Amount of seconds to schedule in.

        self.lowerIntervalNotification = False
        self.lowerTrend = 'None'
        self.telegramChatID = gui.configuration.telegramChatID.text()
        self.caller = caller
        self.trader = None

        self.failed = False  # All these variables pertain to bot failures.
        self.failCount = 0
        self.failLimit = 10
        self.failSleep = 6
        self.failError = ''

    def initialize_lower_interval_trading(self, caller, interval: str):
        """
        Initializes lower interval trading data object.
        :param caller: Caller that determines whether lower interval is for simulation or live bot.
        :param interval: Current interval for simulation or live bot.
        """
        sortedIntervals = ('1m', '3m', '5m', '15m', '30m', '1h', '2h', '12h', '4h', '6h', '8h', '1d', '3d')
        gui = self.gui
        symbol = self.trader.symbol

        if interval != '1m':
            lowerInterval = sortedIntervals[sortedIntervals.index(interval) - 1]
            intervalString = helpers.convert_small_interval(lowerInterval)
            self.lowerIntervalNotification = True
            self.signals.activity.emit(caller, f'Retrieving {symbol} data for {intervalString.lower()} intervals...')

            if caller == LIVE:
                gui.lowerIntervalData = Data(interval=lowerInterval, symbol=symbol, updateData=False)
                gui.lowerIntervalData.custom_get_new_data(progress_callback=self.signals.progress, removeFirst=True,
                                                          caller=LIVE)
            elif caller == SIMULATION:
                gui.simulationLowerIntervalData = Data(interval=lowerInterval, symbol=symbol, updateData=False)
                gui.simulationLowerIntervalData.custom_get_new_data(progress_callback=self.signals.progress,
                                                                    removeFirst=True, caller=SIMULATION)
            else:
                raise TypeError("Invalid type of caller specified.")

            lowerData = gui.lowerIntervalData if caller == LIVE else gui.simulationLowerIntervalData
            if not lowerData or not lowerData.downloadCompleted:
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
        configDict = gui.interfaceDictionary[caller]['configuration']
        symbol = configDict['ticker'].currentText()
        precision = configDict['precision'].value()
        prettyInterval = configDict['interval'].currentText()
        interval = helpers.convert_long_interval(prettyInterval)

        if caller == SIMULATION:
            startingBalance = gui.configuration.simulationStartingBalanceSpinBox.value()
            self.signals.activity.emit(caller, f"Retrieving {symbol} data for {prettyInterval.lower()} intervals...")
            gui.simulationTrader = SimulationTrader(startingBalance=startingBalance,
                                                    symbol=symbol,
                                                    interval=interval,
                                                    loadData=True,
                                                    updateData=False,
                                                    precision=precision)
            gui.simulationTrader.dataView.custom_get_new_data(progress_callback=self.signals.progress, removeFirst=True,
                                                              caller=SIMULATION)
        elif caller == LIVE:
            apiSecret = gui.configuration.binanceApiSecret.text()
            apiKey = gui.configuration.binanceApiKey.text()
            tld = 'com' if gui.configuration.otherRegionRadio.isChecked() else 'us'
            isIsolated = gui.configuration.isolatedMarginAccountRadio.isChecked()
            self.check_api_credentials(apiKey=apiKey, apiSecret=apiSecret)
            self.signals.activity.emit(caller, f"Retrieving {symbol} data for {prettyInterval.lower()} intervals...")
            gui.trader = RealTrader(apiSecret=apiSecret,
                                    apiKey=apiKey,
                                    interval=interval,
                                    symbol=symbol,
                                    tld=tld,
                                    isIsolated=isIsolated,
                                    loadData=True,
                                    updateData=False,
                                    precision=precision)
            gui.trader.dataView.custom_get_new_data(progress_callback=self.signals.progress, removeFirst=True,
                                                    caller=LIVE)
        else:
            raise ValueError("Invalid caller.")

        self.trader: SimulationTrader = self.gui.get_trader(caller)
        self.trader.addTradeCallback = self.signals.addTrade  # Passing an add trade call black.
        self.trader.dataView.callback = self.signals.activity  # Passing activity signal to data object.
        self.trader.dataView.caller = caller  # Passing caller to data object.
        if not self.trader.dataView.downloadCompleted:
            raise RuntimeError("Download failed.")

        self.signals.activity.emit(caller, "Retrieved data successfully.")

        if configDict['lowerIntervalCheck'].isChecked():
            self.initialize_lower_interval_trading(caller=caller, interval=interval)

    @staticmethod
    def check_api_credentials(apiKey: str, apiSecret: str):
        """
        Helper function that checks API credentials specified. Needs to have more tests.
        :param apiKey: API key for Binance. (for now)
        :param apiSecret: API secret for Binance. (for now)
        """
        if len(apiSecret) == 0:
            raise ValueError('Please specify an API secret key. No API secret key found.')
        elif len(apiKey) == 0:
            raise ValueError("Please specify an API key. No API key found.")

    def initialize_scheduler(self):
        """
        Initializes a scheduler for lower interval data.
        """
        gui = self.gui
        measurement = gui.configuration.schedulingTimeUnit.value()
        unit = gui.configuration.schedulingIntervalComboBox.currentText()
        self.schedulePeriod = f'{measurement} {unit.lower()}'

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

        message = f'Initiated periodic statistics notification every {self.schedulePeriod}.'
        self.gui.telegramBot.send_message(self.telegramChatID, message=message)

        self.scheduleSeconds = seconds
        self.nextScheduledEvent = datetime.now() + timedelta(seconds=seconds)

    def handle_scheduler(self):
        """
        Handles lower data interval notification. If the current time is equal or later than the next scheduled event,
        a message is sent via Telegram.
        """
        if self.nextScheduledEvent and datetime.now() >= self.nextScheduledEvent:
            self.gui.telegramBot.send_statistics_telegram(self.telegramChatID, self.schedulePeriod)
            self.nextScheduledEvent = datetime.now() + timedelta(seconds=self.scheduleSeconds)

    def set_parameters(self, caller: int):
        """
        Retrieves moving average options and loss settings based on caller.
        :param caller: Caller that dictates which parameters get set.
        """
        lossDict = self.gui.get_loss_settings(caller)
        takeProfitDict = self.gui.configuration.get_take_profit_settings(caller)

        trader: SimulationTrader = self.gui.get_trader(caller)
        trader.apply_take_profit_settings(takeProfitDict)
        trader.apply_loss_settings(lossDict)
        trader.setup_strategies(self.gui.configuration.get_strategies(caller))
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
            self.gui.runningLive = True
        elif caller == SIMULATION:
            self.gui.simulationRunningLive = True
        else:
            raise RuntimeError("Invalid type of caller specified.")

    def update_data(self, caller):
        """
        Updates data if updated data exists for caller object.
        :param caller: Object type that will be updated.
        """
        trader = self.gui.get_trader(caller)
        if not trader.dataView.data_is_updated():
            trader.dataView.update_data()

    def handle_trading(self, caller):
        """
        Handles trading by checking if automation mode is on or manual.
        :param caller: Object for which function will handle trading.
        """
        trader = self.gui.get_trader(caller)
        trader.main_logic(log_data=self.gui.advancedLogging)

    def handle_current_and_trailing_prices(self, caller):
        """
        Handles trailing prices for caller object.
        :param caller: Trailing prices for what caller to be handled for.
        """
        trader: SimulationTrader = self.gui.get_trader(caller)
        trader.dataView.get_current_data()
        trader.currentPrice = trader.dataView.current_values['close']
        if trader.longTrailingPrice is not None and trader.currentPrice > trader.longTrailingPrice:
            trader.longTrailingPrice = trader.currentPrice
        if trader.shortTrailingPrice is not None and trader.currentPrice < trader.shortTrailingPrice:
            trader.shortTrailingPrice = trader.currentPrice

    def handle_logging(self, caller):
        """
        Handles logging type for caller object.
        :param caller: Object those logging will be performed.
        """
        if self.gui.advancedLogging:
            self.gui.get_trader(caller).output_basic_information()

    def initialize_telegram_bot(self):
        """
        Attempts to initiate Telegram bot.
        """
        gui = self.gui
        gui.configuration.test_telegram()
        apiKey = gui.configuration.telegramApiKey.text()
        gui.telegramBot = TelegramBot(gui=gui, token=apiKey, botThread=self)
        gui.telegramBot.start()
        self.signals.activity.emit(LIVE, 'Started Telegram bot.')
        if self.gui.telegramBot and gui.configuration.chatPass:
            self.gui.telegramBot.send_message(self.telegramChatID, "Started Telegram bot.")

    def handle_lower_interval_cross(self, caller, previousLowerTrend) -> bool or None:
        """
        Handles logic and notifications for lower interval cross data.
        :param previousLowerTrend: Previous lower trend. Used to check if notification is necessary.
        :param caller: Caller for which we will check lower interval cross data.
        """
        if self.lowerIntervalNotification:
            trader: SimulationTrader = self.gui.get_trader(caller)
            lowerData = self.gui.get_lower_interval_data(caller)
            lowerData.get_current_data()
            lowerTrend = trader.get_trend(dataObject=lowerData, log_data=self.gui.advancedLogging)
            self.lowerTrend = trader.get_trend_string(lowerTrend)
            if previousLowerTrend != lowerTrend:
                trends = {BEARISH: 'Bearish', BULLISH: 'Bullish', None: 'No'}
                message = f'{trends[lowerTrend]} trend detected on lower interval data.'
                self.signals.activity.emit(caller, message)
                if self.gui.configuration.enableTelegramNotification.isChecked() and caller == LIVE:
                    self.gui.telegramBot.send_message(message=message, chatID=self.telegramChatID)
            return lowerTrend

    def set_daily_percentages(self, trader, net):
        """
        Sets daily percentage gain or loss percentage values.
        :param trader: Trader object.
        :param net: Current new value.
        """
        if self.previousDayTime is None:  # This logic is for daily percentage yields.
            if time.time() - self.startingTime >= self.dailyIntervalSeconds:
                self.previousDayTime = time.time()
                self.previousDayNet = net
                self.dailyPercentage = 0
            else:
                self.dailyPercentage = self.percentage  # Same as current percentage because of lack of values.
        else:
            if time.time() - self.previousDayTime >= self.dailyIntervalSeconds:
                trader.dailyChangeNets.append(trader.get_profit_percentage(self.previousDayNet, net))
                self.previousDayTime = time.time()
                self.previousDayNet = net
                self.dailyPercentage = 0
            else:
                self.dailyPercentage = trader.get_profit_percentage(self.previousDayNet, net)

    def get_statistics(self):
        """
        Returns current bot statistics in a dictionary.
        :return: Current statistics in a dictionary.
        """
        trader: SimulationTrader = self.trader
        net = trader.get_net()
        profit = trader.get_profit()

        self.percentage = trader.get_profit_percentage(trader.startingBalance, net)
        self.elapsed = helpers.get_elapsed_time(self.startingTime)
        self.optionDetails = trader.optionDetails
        self.lowerOptionDetails = trader.lowerOptionDetails
        self.set_daily_percentages(trader=trader, net=net)

        groupedDict = trader.get_grouped_statistics()
        groupedDict['general']['net'] = f'${round(net, 2)}'
        groupedDict['general']['profit'] = f'${round(profit, 2)}'
        groupedDict['general']['elapsed'] = self.elapsed
        groupedDict['general']['totalPercentage'] = f'{round(self.percentage, 2)}%'
        groupedDict['general']['dailyPercentage'] = f'{round(self.dailyPercentage, 2)}%'

        if trader.lowerOptionDetails:
            groupedDict['general']['lowerTrend'] = self.lowerTrend

        valueDict = {
            'profitLossLabel': trader.get_profit_or_loss_string(profit=profit),
            'profitLossValue': f'${abs(round(profit, 2))}',
            'percentageValue': f'{round(self.percentage, 2)}%',
            'netValue': f'${round(net, 2)}',
            'tickerValue': f'${trader.currentPrice}',
            'tickerLabel': trader.symbol,
            'currentPositionValue': trader.get_position_string(),
            'net': net,
            'price': trader.currentPrice,
            'optionDetails': self.optionDetails,
        }

        return valueDict, groupedDict

    def trading_loop(self, caller):
        """
        Main loop that runs based on caller.
        :param caller: Caller object that determines which bot is running.
        """
        lowerTrend = None  # This variable is used for lower trend notification logic.
        runningLoop = self.gui.runningLive if caller == LIVE else self.gui.simulationRunningLive
        trader: SimulationTrader = self.gui.get_trader(caller=caller)

        while runningLoop:
            trader.completedLoop = False  # This boolean is checked when bot is ended to ensure it finishes its loop.
            self.update_data(caller)  # Check for new updates.
            self.handle_logging(caller=caller)  # Handle logging.
            self.handle_current_and_trailing_prices(caller=caller)  # Handle trailing prices.
            self.handle_trading(caller=caller)  # Main logic function.
            self.handle_scheduler()  # Handle periodic statistics scheduler.
            lowerTrend = self.handle_lower_interval_cross(caller, lowerTrend)  # Check lower trend.
            valueDict, groupedDict = self.get_statistics()  # Basic statistics of bot to update GUI.
            self.signals.updated.emit(caller, valueDict, groupedDict)
            runningLoop = self.gui.runningLive if caller == LIVE else self.gui.simulationRunningLive
            self.failCount = 0  # Reset fail count as bot fixed itself.
            trader.completedLoop = True  # Set completedLoop to True. Or else, there'll be an infinite loop in the GUI.

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
                trader.output_message(f'Bot has crashed because of :{e}', printMessage=True)
                trader.output_message(error_message, printMessage=False)
            if self.gui.telegramBot and self.gui.configuration.chatPass:
                self.gui.telegramBot.send_message(self.telegramChatID, f"Bot has crashed because of :{e}.")
                self.gui.telegramBot.send_message(self.telegramChatID, error_message)

            self.failError = str(e)
            return False

    def handle_exception(self, e, trader):
        """
        This function will try to handle any exceptions that occur during bot run.
        :param e: Exception or error.
        :param trader: Trader object that faced the bug.
        """
        self.failed = True  # Boolean that'll let the bot know it failed.
        self.failCount += 1  # Increment failCount by 1. There's a default limit of 10 fails.
        self.failError = str(e)  # This is the fail error that led to the crash.
        error_message = traceback.format_exc()  # Get error message.

        attemptsLeft = self.failLimit - self.failCount
        s = self.failSleep
        self.signals.activity.emit(self.caller, f'{e} {attemptsLeft} attempts left. Retrying in {s} seconds.')
        self.logger.critical(error_message)

        if trader:  # Log this message to the trader's log.
            trader.output_message(error_message, printMessage=True)
            trader.output_message(f'Bot has crashed because of :{e}', printMessage=True)
            trader.output_message(f"({self.failCount})Trying again in {self.failSleep} seconds.", printMessage=True)

        try:
            if self.gui.telegramBot and self.gui.configuration.chatPass:  # Send crash information through Telegram.
                self.gui.telegramBot.send_message(self.telegramChatID, f"Bot has crashed because of :{e}.")
                if self.failCount == self.failLimit:
                    self.gui.telegramBot.send_message(self.telegramChatID, error_message)
                    self.gui.telegramBot.send_message(self.telegramChatID, "Bot has died.")
                else:
                    failCount = self.failCount
                    self.gui.telegramBot.send_message(self.telegramChatID, f"({failCount})Trying again in {s} seconds.")
        except Exception as e:
            self.logger.critical(str(e))

        time.sleep(self.failSleep)  # Sleep for some seconds before reattempting a fix.
        trader.retrieve_margin_values()  # Update bot margin values.
        trader.check_current_position()  # Check position it's in.

    def run_loop(self, trader):
        """
        Main function that'll handle exceptions and keep the loop running.
        :param trader: Trader trading in the current loop.
        """
        while self.failCount < self.failLimit:
            runningLoop = self.gui.runningLive if self.caller == LIVE else self.gui.simulationRunningLive
            if not runningLoop:
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
            trader.completedLoop = True  # If false, this will cause an infinite loop.
            if trader == self.gui.simulationTrader:
                trader.get_simulation_result()

        if self.failLimit == self.failCount or self.failed or not success:
            self.signals.error.emit(self.caller, str(self.failError))
            self.signals.restore.emit()
