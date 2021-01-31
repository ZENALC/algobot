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
    smallError = pyqtSignal(str)
    started = pyqtSignal(int)
    activity = pyqtSignal(int, str)
    updated = pyqtSignal(int, dict, dict)
    finished = pyqtSignal()
    error = pyqtSignal(int, str)
    restore = pyqtSignal()
    progress = pyqtSignal(int, str, int)

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
        self.elapsed = '1 second'  # Total elapsed run time.
        self.percentage = None  # Total percentage gain or loss.
        self.optionDetails = []  # This list will contain all the moving average information.
        self.lowerOptionDetails = []  # This list will contain all the lower interval's moving average information.

        self.dailyIntervalSeconds = 86400  # Every 24 hours
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
            if not lowerData.downloadCompleted:
                raise RuntimeError("Download failed.")
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
        interval = helpers.convert_interval(prettyInterval)

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
        if not self.trader.dataView.downloadCompleted:
            raise RuntimeError("Download failed.")

        self.signals.activity.emit(caller, "Retrieved data successfully.")

        if configDict['lowerIntervalCheck'].isChecked():
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
        trader.main_logic(log_data=self.gui.advancedLogging)

    def handle_current_and_trailing_prices(self, caller):
        """
        Handles trailing prices for caller object.
        :param caller: Trailing prices for what caller to be handled for.
        """
        trader = self.gui.get_trader(caller)
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

    def set_daily_percentages(self, trader, net):
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
            groupedDict['movingAverages']['lowerTrend'] = self.lowerTrend

        valueDict = {
            'profitLossLabel': trader.get_profit_or_loss_string(profit=profit),
            'profitLossValue': f'${abs(round(profit, 2))}',
            'percentageValue': f'{round(self.percentage, 2)}%',
            'netValue': f'${round(net, 2)}',
            'tickerValue': f'${round(trader.currentPrice, trader.precision)}',
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
            trader.completedLoop = False
            self.update_data(caller)
            self.handle_logging(caller=caller)
            self.handle_current_and_trailing_prices(caller=caller)
            self.handle_trading(caller=caller)
            self.handle_scheduler()
            lowerTrend = self.handle_lower_interval_cross(caller, lowerTrend)
            valueDict, groupedDict = self.get_statistics()
            self.signals.updated.emit(caller, valueDict, groupedDict)
            runningLoop = self.gui.runningLive if caller == LIVE else self.gui.simulationRunningLive
            trader.completedLoop = True

    def try_setting_up_bot(self) -> bool:
        try:
            self.setup_bot(caller=self.caller)
            self.signals.started.emit(self.caller)
            return True
        except Exception as e:
            error_message = traceback.format_exc()
            trader: SimulationTrader = self.gui.get_trader(self.caller)
            if trader:
                trader.output_message(f'Bot has crashed because of :{e}', printMessage=True)
                trader.output_message(error_message, printMessage=True)
            if self.gui.telegramBot and self.gui.configuration.chatPass:
                self.gui.telegramBot.send_message(self.telegramChatID, f"Bot has crashed because of :{e}.")
                self.gui.telegramBot.send_message(self.telegramChatID, error_message)
            self.signals.error.emit(self.caller, str(e))
            return False

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        failed = False
        failCount = 0
        failLimit = 10
        sleepTime = 5
        error = ''

        success = self.try_setting_up_bot()
        if success:
            while failCount < failLimit:
                try:
                    self.trading_loop(self.caller)
                    failed = False
                except Exception as e:
                    failed = True
                    failCount += 1
                    error = e
                    error_message = traceback.format_exc()
                    trader: SimulationTrader = self.gui.get_trader(self.caller)

                    self.signals.smallError.emit(str(e))

                    if trader:
                        trader.output_message(error_message, printMessage=True)
                        trader.output_message(f'Bot has crashed because of :{e}', printMessage=True)
                        trader.output_message(f"({failCount})Trying again in {sleepTime} seconds..", printMessage=True)

                    if self.gui.telegramBot and self.gui.configuration.chatPass:
                        self.gui.telegramBot.send_message(self.telegramChatID, error_message)
                        self.gui.telegramBot.send_message(self.telegramChatID, f"Bot has crashed because of :{e}.")
                        self.gui.telegramBot.send_message(self.telegramChatID, f"({failCount})Trying again in "
                                                                               f"{sleepTime} seconds..")

                    runningLoop = self.gui.runningLive if self.caller == LIVE else self.gui.simulationRunningLive
                    if not runningLoop:
                        break
                    time.sleep(sleepTime)
                    trader.retrieve_margin_values()
                    trader.check_initial_position()

                runningLoop = self.gui.runningLive if self.caller == LIVE else self.gui.simulationRunningLive
                if not failed or not runningLoop:
                    break

        if failLimit == failCount or failed:
            self.signals.error.emit(self.caller, str(error))
        self.signals.restore.emit()
