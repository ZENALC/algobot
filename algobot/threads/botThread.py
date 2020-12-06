import traceback
import helpers
import time

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot

from data import Data
from datetime import datetime, timedelta
from enums import LIVE, SIMULATION, BEARISH, BULLISH
from realtrader import RealTrader
from simulationtrader import SimulationTrader
from telegramBot import TelegramBot


class BotSignals(QObject):
    started = pyqtSignal(int)
    activity = pyqtSignal(int, str)
    updated = pyqtSignal(int, dict)
    finished = pyqtSignal()
    error = pyqtSignal(int, str)

    # All of these below are for Telegram integration.
    forceLong = pyqtSignal()
    forceShort = pyqtSignal()
    exitPosition = pyqtSignal()
    waitOverride = pyqtSignal()
    resume = pyqtSignal()
    pause = pyqtSignal()
    removeCustomStopLoss = pyqtSignal()
    setCustomStopLoss = pyqtSignal(int, bool, float)


class BotThread(QRunnable):
    def __init__(self, caller: int, gui):
        super(BotThread, self).__init__()
        self.signals = BotSignals()
        self.gui = gui
        self.startingTime = time.time()
        self.elapsed = '1 second'
        self.percentage = None
        self.optionDetails = []
        self.lowerOptionDetails = []

        self.intervalSeconds = 86400  # Every 24 hours
        self.dailyPercentage = 0  # Initial change percentage.
        self.previousDayTime = None  # Previous day net time to compare to.
        self.previousDayNet = None  # Previous day net value to compare to.

        self.schedulePeriod = None  # Next period schedule in string format.
        self.nextScheduledEvent = None  # These are for periodic scheduling. This variable holds next schedule event.
        self.scheduleSeconds = None  # Amount of seconds to schedule in.

        self.lowerIntervalNotification = False
        self.lowerTrend = 'None'
        self.telegramChatID = gui.configuration.telegramChatID.text()
        self.caller = caller
        self.trader = None

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
            intervalString = helpers.convert_interval_to_string(lowerInterval)
            self.signals.activity.emit(caller, f'Retrieving {symbol} data for {intervalString.lower()} intervals...')
            if caller == LIVE:
                gui.lowerIntervalData = Data(interval=lowerInterval, symbol=symbol)
            elif caller == SIMULATION:
                gui.simulationLowerIntervalData = Data(interval=lowerInterval, symbol=symbol)
            else:
                raise TypeError("Invalid type of caller specified.")
            self.signals.activity.emit(caller, "Retrieved lower interval data successfully.")

    def create_trader(self, caller):
        """
        Creates a trader based on caller specified.
        :param caller: Caller that determines what type of trader will be created.
        """
        gui = self.gui
        configDict = gui.interfaceDictionary[caller]['configuration']
        symbol = configDict['ticker'].currentText()
        prettyInterval = configDict['interval'].currentText()
        interval = helpers.convert_interval(prettyInterval)

        if caller == SIMULATION:
            startingBalance = gui.configuration.simulationStartingBalanceSpinBox.value()
            self.signals.activity.emit(caller, f"Retrieving {symbol} data for {prettyInterval.lower()} intervals...")
            gui.simulationTrader = SimulationTrader(startingBalance=startingBalance,
                                                    symbol=symbol,
                                                    interval=interval,
                                                    loadData=True)
        elif caller == LIVE:
            apiSecret = gui.configuration.binanceApiSecret.text()
            apiKey = gui.configuration.binanceApiKey.text()
            tld = 'com' if gui.configuration.otherRegionRadio.isChecked() else 'us'
            isIsolated = gui.configuration.isolatedMarginAccountRadio.isChecked()
            self.check_api_credentials(apiKey=apiKey, apiSecret=apiSecret)
            self.signals.activity.emit(caller, f"Retrieving {symbol} data for {prettyInterval.lower()} intervals...")
            gui.trader = RealTrader(apiSecret=apiSecret, apiKey=apiKey, interval=interval, symbol=symbol, tld=tld,
                                    isIsolated=isIsolated)
        else:
            raise ValueError("Invalid caller.")

        self.signals.activity.emit(caller, "Retrieved data successfully.")
        self.trader = self.gui.get_trader(caller)

        if configDict['lowerIntervalCheck'].isChecked():
            self.lowerIntervalNotification = True
            self.initialize_lower_interval_trading(caller=caller, interval=interval)

    @staticmethod
    def check_api_credentials(apiKey, apiSecret):
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
        if self.nextScheduledEvent is not None and datetime.now() >= self.nextScheduledEvent:
            self.gui.telegramBot.send_statistics_telegram(self.telegramChatID, self.schedulePeriod)
            self.nextScheduledEvent = datetime.now() + timedelta(seconds=self.scheduleSeconds)

    def setup_bot(self, caller):
        """
        Initial full bot setup based on caller.
        :param caller: Caller that will determine what type of trader will be instantiated.
        """
        self.create_trader(caller)
        self.gui.set_parameters(caller)

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
            # self.signals.activity.emit(caller, 'New data found. Updating...')
            trader.dataView.update_data()
            # self.signals.activity.emit(caller, 'Updated data successfully.')

    def handle_trading(self, caller):
        """
        Handles trading by checking if automation mode is on or manual.
        :param caller: Object for which function will handle trading.
        """
        trader = self.gui.get_trader(caller)
        trader.main_logic()

    def handle_current_and_trailing_prices(self, caller):
        """
        Handles trailing prices for caller object.
        :param caller: Trailing prices for what caller to be handled for.
        """
        trader = self.gui.get_trader(caller)
        trader.currentPrice = trader.dataView.get_current_price()
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
        if gui.telegramBot is None:
            apiKey = gui.configuration.telegramApiKey.text()
            gui.telegramBot = TelegramBot(gui=gui, token=apiKey, botThread=self)
        gui.telegramBot.start()
        self.signals.activity.emit(LIVE, 'Started Telegram bot.')
        # try:
        #     gui = self.gui
        #     if gui.telegramBot is None:
        #         apiKey = gui.configuration.telegramApiKey.text()
        #         gui.telegramBot = TelegramBot(gui=gui, token=apiKey)
        #     gui.telegramBot.start()
        #     self.signals.activity.emit(LIVE, 'Started Telegram bot.')
        # except InvalidToken:
        #     self.signals.activity.emit(LIVE, 'Invalid token for Telegram. Please recheck credentials in settings.')

    def handle_lower_interval_cross(self, caller, previousLowerTrend) -> bool or None:
        """
        Handles logic and notifications for lower interval cross data.
        :param previousLowerTrend: Previous lower trend. Used to check if notification is necessary.
        :param caller: Caller for which we will check lower interval cross data.
        """
        if not self.lowerIntervalNotification:
            return None
        trader: SimulationTrader = self.gui.get_trader(caller)
        lowerData = self.gui.get_lower_interval_data(caller)
        lowerTrend = trader.get_trend(dataObject=lowerData)
        self.lowerTrend = trader.get_trend_string(lowerTrend)
        trend = trader.trend
        if previousLowerTrend == lowerTrend or lowerTrend == trend:
            return lowerTrend
        else:
            trends = {BEARISH: 'Bearish', BULLISH: 'Bullish', None: 'No'}
            message = f'{trends[lowerTrend]} trend detected on lower interval data.'
            self.signals.activity.emit(caller, message)
            if self.gui.configuration.enableTelegramNotification.isChecked() and caller == LIVE:
                self.gui.telegramBot.send_message(message=message, chatID=self.telegramChatID)
            return lowerTrend

    # to fix
    def handle_cross_notification(self, caller, notification):
        """
        Handles cross notifications.
        :param caller: Caller object for whom function will handle cross notifications.
        :param notification: Notification boolean whether it is time to notify or not.
        :return: Boolean whether cross should be notified on next function call.
        """
        gui = self.gui
        if caller == SIMULATION:
            if gui.simulationTrader.currentPosition is None:
                if not gui.simulationTrader.inHumanControl and notification:
                    gui.add_to_simulation_activity_monitor("Waiting for a cross.")
                    return False
            else:
                return False
        elif caller == LIVE:
            if gui.trader.currentPosition is not None:
                return False
            else:
                if not notification and not gui.trader.inHumanControl:
                    gui.add_to_live_activity_monitor("Waiting for a cross.")
                    return False
        else:
            raise ValueError("Invalid type of caller or cross notification specified.")

    def get_statistics(self):
        """
        Returns current bot statistics in a dictionary.
        :return: Current statistics in a dictionary.
        """
        trader: SimulationTrader = self.trader
        net = trader.get_net()
        profit = trader.get_profit()
        stopLoss = trader.get_stop_loss()
        profitLabel = trader.get_profit_or_loss_string(profit=profit)
        stoicTrend = trader.get_trend_string(trader.stoicTrend)
        movingAverageTrend = trader.get_trend_string(trader.trend)
        stoicInputs = trader.get_stoic_inputs()
        self.percentage = trader.get_profit_percentage(trader.startingBalance, net)
        self.elapsed = helpers.get_elapsed_time(self.startingTime)

        if self.previousDayTime is None:
            if time.time() - self.startingTime >= self.intervalSeconds:
                self.previousDayTime = time.time()
                self.previousDayNet = net
                self.dailyPercentage = 0
            else:
                self.dailyPercentage = self.percentage  # Same as current percentage because of lack of values.
        else:
            if time.time() - self.previousDayTime >= self.intervalSeconds:
                trader.dailyChangeNets.append(trader.get_profit_percentage(self.previousDayNet, net))
                self.previousDayTime = time.time()
                self.previousDayNet = net
                self.dailyPercentage = 0
            else:
                self.dailyPercentage = trader.get_profit_percentage(self.previousDayNet, net)

        # self.optionDetails = [self.gui.get_option_info(option, trader) for option in trader.tradingOptions]
        self.optionDetails = trader.optionDetails
        self.lowerOptionDetails = trader.lowerOptionDetails
        rsi_details = [(key, trader.dataView.rsi_data[key]) for key in trader.dataView.rsi_data]

        updateDict = {
            # Statistics window
            'net': net,
            'interval': helpers.convert_interval_to_string(trader.dataView.interval),
            'lowerIntervalTrend': self.lowerTrend,
            'startingBalanceValue': f'${round(trader.startingBalance, 2)}',
            'currentBalanceValue': f'${round(trader.balance, 2)}',
            'netValue': f'${round(net, 2)}',
            'profitLossLabel': profitLabel,
            'profitLossValue': f'${abs(round(profit, 2))}',
            'percentageValue': f'{round(self.percentage, 2)}%',
            'tradesMadeValue': str(len(trader.trades)),
            'coinOwnedLabel': f'{trader.coinName} Owned',
            'coinOwnedValue': f'{round(trader.coin, 6)}',
            'coinOwedLabel': f'{trader.coinName} Owed',
            'coinOwedValue': f'{round(trader.coinOwed, 6)}',
            'lossPointLabel': trader.get_stop_loss_strategy_string(),
            'lossPointValue': trader.get_safe_rounded_string(stopLoss),
            'customStopPointValue': trader.get_safe_rounded_string(trader.customStopLoss),
            'currentPositionValue': trader.get_position_string(),
            'autonomousValue': str(not trader.inHumanControl),
            'tickerLabel': trader.symbol,
            'tickerValue': f'${trader.currentPrice}',
            'currentPrice': trader.currentPrice,
            'optionDetails': self.optionDetails,
            'lowerOptionDetails': self.lowerOptionDetails,
            'elapsedValue': self.elapsed,
            'dailyPercentageValue': f'{round(self.dailyPercentage, 2)}%',
            'stoicTrend': stoicTrend,
            'stoicEnabled': str(trader.stoicEnabled),
            'stoicInputs': stoicInputs,
            'movingAverageTrend': movingAverageTrend,
            'rsiDetails': rsi_details,
        }

        return updateDict

    def trading_loop(self, caller):
        """
        Main loop that runs based on caller.
        :param caller: Caller object that determines which bot is running.
        """
        lowerTrend = None
        runningLoop = self.gui.runningLive if caller == LIVE else self.gui.simulationRunningLive

        while runningLoop:
            self.update_data(caller)
            self.handle_logging(caller=caller)
            self.handle_current_and_trailing_prices(caller=caller)
            self.handle_trading(caller=caller)
            self.handle_scheduler()
            # crossNotification = self.handle_cross_notification(caller=caller, notification=crossNotification)
            lowerTrend = self.handle_lower_interval_cross(caller, lowerTrend)
            statDict = self.get_statistics()
            self.signals.updated.emit(caller, statDict)
            runningLoop = self.gui.runningLive if caller == LIVE else self.gui.simulationRunningLive

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            caller = self.caller
            self.setup_bot(caller=caller)
            self.signals.started.emit(caller)
            self.trading_loop(caller)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()
            self.signals.error.emit(self.caller, str(e))
