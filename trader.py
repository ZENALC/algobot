import math
import credentials
from data import Data
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from helpers import *

BULLISH = 1
BEARISH = -1
LONG = 1
SHORT = -1
TRAILING_LOSS = 2
STOP_LOSS = 1


class SimulatedTrader:
    def __init__(self, startingBalance=1000, interval='1h', symbol='BTCUSDT', loadData=True):
        self.dataView = Data(interval=interval, symbol=symbol, loadData=loadData)  # Retrieve data-view object
        self.binanceClient = self.dataView.binanceClient  # Retrieve Binance client
        self.symbol = self.dataView.symbol

        try:  # Attempt to parse startingBalance
            startingBalance = float(startingBalance)
        except (ValueError, ArithmeticError, ZeroDivisionError):
            print("Invalid starting balance. Using default value of $1,000.")
            startingBalance = 1000

        # Initialize initial values
        self.balance = startingBalance  # USD Balance
        self.coinName = self.get_coin_name()
        self.coin = 0  # Amount of coin we own
        self.coinOwed = 0  # Amount of coin we owe
        self.transactionFeePercentage = 0.001  # Binance transaction fee
        self.totalTrades = []  # All trades conducted
        self.trades = []  # Amount of trades in previous run

        self.tradingOptions = []
        self.trend = None  # 1 is bullish, -1 is bearish
        self.lossPercentage = None  # Loss percentage for stop loss
        self.startingTime = None  # Starting time for previous bot run
        self.endingTime = None  # Ending time for previous bot run
        self.buyLongPrice = None  # Price we last bought our target coin at in long position
        self.sellShortPrice = None  # Price we last sold target coin at in short position
        self.lossStrategy = None  # Type of loss type we are using: whether it's trailing loss or stop loss
        self.stopLoss = None  # Price at which bot will exit trade due to stop loss limits
        self.longTrailingPrice = None  # Price coin has to be above for long position
        self.shortTrailingPrice = None  # Price coin has to be below for short position
        self.startingBalance = self.balance  # Balance we started bot run with
        self.currentPrice = None  # Current price of coin

        self.safetyMargin = None  # Margin percentage bot will check to validate cross
        self.safetyTimer = None  # Amount of seconds bot will wait to validate cross

        self.inHumanControl = False  # Boolean that keeps track of whether human or bot controls transactions
        self.waitToEnterLong = False  # Boolean that checks if bot should wait before entering long position
        self.waitToEnterShort = False  # Boolean that checks if bot should wait before entering short position
        self.inLongPosition = False  # Boolean that keeps track of whether bot is in a long position or not
        self.inShortPosition = False  # Boolean that keeps track of whether bot is in a short position or not
        self.previousPosition = None  # Previous position to validate for a cross

    def get_coin_name(self):
        temp = self.dataView.symbol.upper().split('USDT')
        temp.remove('')
        return temp[0]

    @staticmethod
    def output_message(message, level=2):
        """Prints out and logs message"""
        # print(message)
        if level == 2:
            logging.info(message)
        elif level == 3:
            logging.debug(message)
        elif level == 4:
            logging.warning(message)
        elif level == 5:
            logging.critical(message)

    def add_trade(self, message):
        """
        Adds a trade to list of trades
        :param message: Message used for conducting trade.
        """
        self.trades.append({
            'date': datetime.utcnow(),
            'action': message
        })

    def buy_long(self, msg, usd=None):
        """
        Buys coin at current market price with amount of USD specified. If not specified, assumes bot goes all in.
        Function also takes into account Binance's 0.1% transaction fee.
        """
        self.currentPrice = self.dataView.get_current_price()

        if usd is None:
            usd = self.balance

        if usd <= 0:
            self.output_message("You cannot buy with $0 or less.")
            if self.balance <= 0:
                self.output_message("Looks like you have run out of money.", 4)
            return
        elif usd > self.balance:
            self.output_message(f'You currently have ${self.balance}. You cannot invest ${usd}.')
            return

        transactionFee = usd * self.transactionFeePercentage
        self.inLongPosition = True
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.coin += (usd - transactionFee) / self.currentPrice
        self.balance -= usd
        self.add_trade(msg)
        self.output_message(msg)

    def sell_long(self, msg, coin=None, stopLoss=None):
        """
        Sells specified amount of coin at current market price. If not specified, assumes bot sells all coin.
        Function also takes into account Binance's 0.1% transaction fee.
        """
        if coin is None:
            coin = self.coin

        if coin <= 0:
            self.output_message(f"You cannot sell 0 or negative {self.coinName}.")
            if self.coin <= 0:
                self.output_message(f"Looks like you do not have any {self.coinName}.", 4)
            return
        elif coin > self.coin:
            self.output_message(f'You have {self.coin} {self.coinName}. You cannot sell {coin} {self.coinName}.')
            return

        self.currentPrice = self.dataView.get_current_price()
        earned = coin * self.currentPrice * (1 - self.transactionFeePercentage)
        self.inLongPosition = False
        self.previousPosition = LONG
        self.coin -= coin
        self.balance += earned
        self.add_trade(msg)
        self.output_message(msg)

        if self.coin == 0:
            self.buyLongPrice = None
            self.longTrailingPrice = None

    def buy_short(self, msg, coin=None, stopLoss=None):
        """
        Buys borrowed coin at current market price and returns to market.
        Function also takes into account Binance's 0.1% transaction fee.
        If coin amount is not specified, bot will assume to buy all owed back
        coin.
        """
        if coin is None:
            coin = self.coinOwed

        if coin <= 0:
            self.output_message(f"You cannot buy 0 or less {self.coinName}.")
            return

        self.currentPrice = self.dataView.get_current_price()
        self.coinOwed -= coin
        self.inShortPosition = False
        self.previousPosition = SHORT
        loss = self.currentPrice * coin * (1 + self.transactionFeePercentage)
        self.balance -= loss
        self.add_trade(msg)
        self.output_message(msg)

        if self.coinOwed == 0:
            self.sellShortPrice = None
            self.shortTrailingPrice = None

    def sell_short(self, msg, coin=None):
        """
        Borrows coin and sells them at current market price.
        Function also takes into account Binance's 0.1% transaction fee.
        If no coin is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        """
        self.currentPrice = self.dataView.get_current_price()

        if coin is None:
            transactionFee = self.balance * self.transactionFeePercentage
            coin = (self.balance - transactionFee) / self.currentPrice

        if coin <= 0:
            self.output_message(f"You cannot borrow 0 or less {self.coinName}.")
            return

        self.coinOwed += coin
        self.balance += self.currentPrice * coin * (1 - self.transactionFeePercentage)
        self.inShortPosition = True
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.add_trade(msg)
        self.output_message(msg)

    def get_profit(self):
        """
        Returns profit or loss.
        :return: A number representing profit if positive and loss if negative.
        """
        try:
            if self.inShortPosition:
                return self.coinOwed * (self.sellShortPrice - self.currentPrice)
            balance = self.balance
            balance += self.coin * self.currentPrice * (1 - self.transactionFeePercentage)
            balance -= self.coinOwed * self.currentPrice * (1 + self.transactionFeePercentage)
            return balance - self.startingBalance
        except TypeError:
            return 0

    def get_position(self):
        if self.inLongPosition:
            return LONG
        elif self.inShortPosition:
            return SHORT
        else:
            return None

    def get_average(self, movingAverage, parameter, value):
        """
        Returns the moving average with parameter and value provided
        :param movingAverage: Moving average to get the average from the data view.
        :param parameter: Parameter for the data view to use in the moving average.
        :param value: Value for the moving average to use in the moving average.
        :return: A float value representing the moving average.
        """
        if movingAverage == 'SMA':
            return self.dataView.get_sma(value, parameter)
        elif movingAverage == 'WMA':
            return self.dataView.get_wma(value, parameter)
        elif movingAverage == 'EMA':
            return self.dataView.get_ema(value, parameter)
        else:
            self.output_message(f'Unknown moving average {movingAverage}.', 4)
            return None

    def get_stop_loss(self):
        """
        Returns a stop loss for the position.
        :return: Stop loss value.
        """
        if self.inShortPosition:  # If we are in a short position
            if self.shortTrailingPrice is None:
                self.shortTrailingPrice = self.dataView.get_current_price()
                self.sellShortPrice = self.shortTrailingPrice
            if self.lossStrategy == 2:  # This means we use trailing loss.
                return self.shortTrailingPrice * (1 + self.lossPercentage)
            else:  # This means we use the basic stop loss.
                return self.sellShortPrice * (1 + self.lossPercentage)
        elif self.inLongPosition:  # If we are in a long position
            if self.longTrailingPrice is None:
                self.longTrailingPrice = self.dataView.get_current_price()
                self.buyLongPrice = self.longTrailingPrice
            if self.lossStrategy == 2:  # This means we use trailing loss.
                return self.longTrailingPrice * (1 - self.lossPercentage)
            else:  # This means we use the basic stop loss.
                return self.buyLongPrice * (1 - self.lossPercentage)
        else:
            return None

    def check_cross_v2(self):
        if len(self.tradingOptions) == 0:  # Checking whether options exist.
            self.output_message("No trading options provided.")
            return

        trends = []

        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.output_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
            self.output_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')

            if initialAverage > finalAverage:
                trends.append(BULLISH)
            else:
                trends.append(BEARISH)

        if all(trend == BULLISH for trend in trends):
            self.trend = BULLISH
        elif all(trend == BEARISH for trend in trends):
            self.trend = BEARISH
        else:
            return False

        position = self.get_position()

        if self.trend == BULLISH:
            if position == LONG:
                return False
            elif position is None and self.previousPosition == LONG:  # This means stop loss occurred.
                return False
            else:
                return True
        elif self.trend == BEARISH:
            if position == SHORT:
                return False
            elif position is None and self.previousPosition == SHORT:  # This means stop loss occurred.
                return False
            else:
                return True
        return False

        # if self.previousPosition != LONG and self.trend == BULLISH:
        #     if not self.inLongPosition:
        #         return True
        # elif self.previousPosition != SHORT and self.trend == BEARISH:
        #     if not self.inShortPosition:
        #         return True
        # else:
        #     return False

    def check_cross(self):
        """
        Checks if there is a cross
        :return: A boolean whether there is a cross or not.
        """
        if len(self.tradingOptions) == 0:  # Checking whether options exist.
            self.output_message("No trading options provided.")
            return

        cross = True

        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

            if option.previousFinalAverage is None or option.previousInitialAverage is None:
                option.previousInitialAverage = initialAverage
                option.previousFinalAverage = finalAverage
                cross = False
                continue

            if initialAverage > finalAverage:
                self.trend = BULLISH  # This means we are bullish
            else:
                self.trend = BEARISH  # This means we are bearish

            if option.previousInitialAverage >= option.previousFinalAverage:
                if initialAverage >= finalAverage:
                    cross = False

            if option.previousInitialAverage <= option.previousFinalAverage:
                if initialAverage <= finalAverage:
                    cross = False

            option.previousFinalAverage = finalAverage
            option.previousInitialAverage = initialAverage

        return cross

    def output_trade_options(self):
        """
        Outputs general information about current trade options.
        """
        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.output_message(f'Parameter: {option.parameter}')
            self.output_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
            self.output_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')

    def output_basic_information(self):
        """
        Prints out basic information about trades.
        """
        self.output_message('---------------------------------------------------')
        self.output_message(f'Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        if self.inHumanControl:
            self.output_message(f'Currently in human control. Bot is waiting for human input to continue.')
        else:
            self.output_message(f'Currently in autonomous mode.')

        if self.coin > 0.0001:
            self.output_message(f'{self.coinName} owned: {self.coin}')
            self.output_message(f'Price bot bought {self.coinName} long for: ${self.buyLongPrice}')

        if self.coinOwed > 0.0001:
            self.output_message(f'{self.coinName} owed: {self.coinOwed}')
            self.output_message(f'Price bot sold {self.coinName} short for: ${self.sellShortPrice}')

        if self.inLongPosition:
            self.output_message(f'\nCurrently in long position.')
            if self.lossStrategy == 2:
                longTrailingLossValue = round(self.longTrailingPrice * (1 - self.lossPercentage), 2)
                self.output_message(f'Long trailing loss: ${longTrailingLossValue}')
            else:
                self.output_message(f'Stop loss: {round(self.buyLongPrice * (1 - self.lossPercentage), 2)}')
        elif self.inShortPosition:
            self.output_message(f'\nCurrently in short position.')
            if self.lossStrategy == 2:
                shortTrailingLossValue = round(self.shortTrailingPrice * (1 + self.lossPercentage), 2)
                self.output_message(f'Short trailing loss: ${shortTrailingLossValue}')
            else:
                self.output_message(f'Stop loss: {round(self.sellShortPrice * (1 + self.lossPercentage), 2)}')
        else:
            if not self.inHumanControl:
                self.output_message(f'\nCurrently not a in short or long position. Waiting for next cross.')
            else:
                self.output_message(f'\nCurrently not a in short or long position. Waiting for human intervention.')

        self.output_message(f'\nCurrent {self.coinName} price: ${self.dataView.get_current_price()}')
        self.output_message(f'Balance: ${round(self.balance, 2)}')
        if self.__class__.__name__ == 'SimulatedTrader':
            self.output_message(f'\nTrades conducted this simulation: {len(self.trades)}')
        else:
            self.output_message(f'\nTrades conducted in live market: {len(self.trades)}')

        profit = round(self.get_profit(), 2)
        if profit > 0:
            self.output_message(f'Profit: ${profit}')
        elif profit < 0:
            self.output_message(f'Loss: ${-profit}')
        else:
            self.output_message(f'No profit or loss currently.')
        self.output_message('')

    def get_simulation_result(self):
        """
        Gets end result of simulation.
        """
        self.endingTime = datetime.now()
        if self.coin > 0:
            self.output_message(f"Selling all {self.coinName}...")
            self.sell_long(f'Sold long as simulation ended.')

        if self.coinOwed > 0:
            self.output_message(f"Returning all borrowed {self.coinName}...")
            self.buy_short(f'Bought short as simulation ended.')

        self.output_message("\nResults:")
        self.output_message(f'Starting time: {self.startingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'End time: {self.endingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'Elapsed time: {self.endingTime - self.startingTime}')
        self.output_message(f'Starting balance: ${self.startingBalance}')
        self.output_message(f'Ending balance: ${round(self.balance, 2)}')
        self.output_message(f'Trades conducted: {len(self.trades)}')
        if self.balance > self.startingBalance:
            profit = self.balance - self.startingBalance
            self.output_message(f"Profit: ${round(profit, 2)}")
        elif self.balance < self.startingBalance:
            loss = self.startingBalance - self.balance
            self.output_message(f'Loss: ${round(loss, 2)}')
        else:
            self.output_message("No profit or loss occurred.")

    def log_trades(self):
        """
        Logs trades.
        """
        logging.info(f'\n\nTotal trade(s) in previous simulation: {len(self.trades)}')
        for counter, trade in enumerate(self.trades, 1):
            logging.info(f'\n{counter}. Date in UTC: {trade["date"]}')
            logging.info(f'\nAction taken: {trade["action"]}')

    def simulate(self, movingAverage="WMA", parameter="high", initialBound=20, finalBound=24, lossPercentage=0.015,
                 lossStrategy=None, safetyTimer=None, safetyMargin=None, options=None):
        """
        Starts a live simulation with given parameters.
        :param options: Argument for all trading options.
        :param safetyMargin: Margin percentage to validate cross
        :param safetyTimer: Amount of seconds to sleep to validate cross
        :param lossStrategy: Type of loss strategy to use
        :param parameter: Type of parameter to use for averages. e.g close, open, high, low.
        :param movingAverage: Type of trade. e.g. SMA, WMA, EMA.
        :param initialBound: Initial bound. e.g SMA(9) > SMA(11), initial bound would be 9.
        :param finalBound: Final bound. e.g SMA(9) > SMA(11), final bound would be 11.
        :param lossPercentage: Loss percentage at which we sell long or buy short.
        """
        if options is not None:
            self.tradingOptions = options
        else:
            tradingOption = Option(movingAverage, parameter, initialBound, finalBound)
            self.tradingOptions = [tradingOption]

        self.lossPercentage = lossPercentage
        self.lossStrategy = lossStrategy
        self.safetyTimer = safetyTimer
        self.safetyMargin = safetyMargin
        self.trades = []
        self.sellShortPrice = None
        self.buyLongPrice = None
        self.shortTrailingPrice = None
        self.longTrailingPrice = None
        self.balance = 1000
        self.startingBalance = self.balance
        self.startingTime = datetime.now()

        easter_egg()

        while self.lossStrategy not in (1, 2):
            try:
                self.lossStrategy = int(input('Enter 1 for stop loss or 2 for trailing loss strategy>>'))
            except ValueError:
                print("Please type in a valid number.")

        while self.safetyTimer is None:
            try:
                self.safetyTimer = int(input("Type in your safety timer (or 0 for no timer)>>"))
            except ValueError:
                print("Please type in a valid number.")

        while self.safetyMargin is None:
            try:
                self.safetyMargin = float(input("Type in your safety margin (for 2% type 0.02 or 0 for no margin)>>"))
            except ValueError:
                print("Please type in a valid number.")

        self.output_message("Starting simulation...")

        self.simulate_option_1()
        self.output_message("\nExiting simulation.")
        self.get_simulation_result()
        self.log_trades()

    def simulate_option_1(self):
        fail = False  # Boolean for whether there was an error that occurred.
        waitTime = self.safetyTimer  # Integer that describes how much bot will sleep to recheck if there is a cross.
        self.safetyTimer = 0  # Initially the safetyTimer will be 0 until a first trade is made.
        self.waitToEnterShort = False  # Boolean for whether we should wait to exit out of short position.
        self.waitToEnterLong = False  # Boolean for whether we should wait to exit out of long position.
        self.inHumanControl = False  # Boolean for whether the bot is in human control.
        self.stopLoss = None  # Stop loss value at which bot will exit position
        self.longTrailingPrice = None  # Variable that will keep track of long trailing price.
        self.shortTrailingPrice = None  # Variable that will keep track of short trailing price.
        self.inLongPosition = False  # Boolean that keeps track of whether we are in a long position.
        self.inShortPosition = False  # Boolean that keeps track of whether we are in a short position.

        while True:
            if len(self.trades) > 0:
                self.safetyTimer = waitTime  # Once the first trade is conducted, then only we wait to validate crosses.
            try:
                self.output_basic_information()

                if fail:
                    self.output_message("Successfully fixed error.")
                    fail = False

                if not self.dataView.data_is_updated():
                    self.dataView.update_data()

                self.output_trade_options()

                self.currentPrice = self.dataView.get_current_price()
                if self.longTrailingPrice is not None and self.currentPrice > self.longTrailingPrice:
                    self.longTrailingPrice = self.currentPrice
                elif self.shortTrailingPrice is not None and self.currentPrice < self.shortTrailingPrice:
                    self.shortTrailingPrice = self.currentPrice

                if not self.inHumanControl:
                    self.main_logic()

                # print("Type CTRL-C to cancel or override the simulation at any time.")
                time.sleep(1)
            except KeyboardInterrupt:
                action = None
                print('\nDo you want to end simulation or override? If this was an accident, enter nothing.')
                while action not in ('o', 's', ''):
                    action = input("Type 'o' to override, 's' to stop, or nothing to continue>>").lower()
                if action.lower().startswith('o'):
                    self.override()
                elif action.lower().startswith('s'):
                    return
            except Exception as e:
                if not fail:
                    self.output_message(f'ERROR: {e}')
                    self.output_message("Something went wrong. Trying again in 10 seconds.")
                time.sleep(10)
                self.output_message("Attempting to fix error...")
                fail = True

    def main_logic(self):
        if self.inShortPosition:  # This means we are in short position
            if self.currentPrice > self.get_stop_loss():  # If current price is greater, then exit trade.
                self.buy_short(f'Bought short because of stop loss.')
                self.waitToEnterShort = True

            if self.check_cross_v2():
                self.buy_short(f'Bought short because a cross was detected.')
                self.buy_long(f'Bought long because a cross was detected.')

        elif self.inLongPosition:  # This means we are in long position
            if self.currentPrice < self.get_stop_loss():  # If current price is lower, then exit trade.
                self.sell_long(f'Sold long because of stop loss.')
                self.waitToEnterLong = True

            if self.check_cross_v2():
                self.sell_long(f'Sold long because a cross was detected.')
                self.sell_short('Sold short because a cross was detected.')

        else:  # This means we are in neither position
            if self.check_cross_v2():
                if self.trend == BULLISH:  # This checks if we are bullish or bearish
                    self.buy_long("Bought long because a cross was detected.")
                else:
                    self.sell_short("Sold short because a cross was detected.")

    def validate_trade(self):
        """
        Checks if bot should go ahead with trade by comparing initial and final averages.
        :return: A boolean whether trade should be performed or not.
        """
        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

            if initialAverage is None or finalAverage is None:
                return False  # This means something went wrong with the moving average calculation.

            initialAverageWithMargin = initialAverage + initialAverage * self.safetyMargin

            if self.inLongPosition:
                if not initialAverageWithMargin > finalAverage:
                    return False
            elif self.inShortPosition:
                if not initialAverageWithMargin < finalAverage:
                    return False
            else:
                if initialAverageWithMargin > finalAverage:
                    self.inLongPosition = True
                elif initialAverageWithMargin < finalAverage:
                    self.inShortPosition = True

        return True

    def validate_cross(self):
        """
        Validates if cross is true by waiting then rechecking cross values.
        :return: Boolean whether cross is real or fake.
        """
        if self.safetyTimer > 0:
            self.output_message(f'Cross detected. Waiting {self.safetyTimer} seconds to validate...')
            time.sleep(self.safetyTimer)
        if not self.validate_trade():
            self.output_message("Irregular averages occurred. Not taking any action.")
            return False
        return True

    def override(self):
        action = None
        if not self.inHumanControl:
            while action not in ('w', ''):
                action = input("Type 'w' to pause the bot or nothing to close and wait for next cross>>")
            if action == 'w':
                self.output_message("Pausing the bot.")
                self.inHumanControl = True
            if self.inShortPosition:
                self.buy_short('Bought short because of override.')
                if action == '':
                    self.waitToEnterShort = True
            elif self.inLongPosition:
                self.sell_long('Sold long because of override.')
                if action == '':
                    self.waitToEnterLong = True
            else:
                self.output_message("Was not in a long or short position. Resuming simulation.")
        else:
            while action not in ('long', 'short', ''):
                self.output_message("Type 'long' to go long, 'short' to go short, or nothing to resume bot.")
                action = input('>>').lower()
            if action == 'long':
                self.buy_long("Buying long because of override.")
                self.waitToEnterLong = True
            elif action == 'short':
                self.sell_short(f'Sold short because of override.')
                self.waitToEnterShort = True
            self.inHumanControl = False


class RealTrader(SimulatedTrader):
    def __init__(self, apiKey=None, apiSecret=None, interval='1h', symbol='BTCUSDT'):
        apiKey = credentials.apiKey
        apiSecret = credentials.apiSecret
        if apiKey is None or apiSecret is None:
            self.output_message('API details incorrect.', 5)
            return

        super().__init__(interval=interval, symbol=symbol)
        self.binanceClient = Client(apiKey, apiSecret)
        self.spot_usdt = self.get_spot_usdt()
        self.spot_coin = self.get_spot_coin()
        self.isolated = self.is_isolated()

        if self.spot_usdt > 10:
            self.initial_transfer()

        self.set_margin_values()

        self.startingBalance = self.get_starting_balance()
        self.check_initial_position()

    def is_isolated(self):
        try:  # Attempt to get coin from regular cross margin account.
            assets = self.binanceClient.get_margin_account()['userAssets']
            coin = [asset for asset in assets if asset['asset'] == self.coinName][0]
            return False
        except IndexError:
            return True

    def get_starting_balance(self):
        """
        Returns the initial starting balance for bot.
        :return: initial starting balance for bot
        """
        self.currentPrice = self.dataView.get_current_price()
        usdt = self.coin * self.currentPrice + self.balance
        usdt -= self.coinOwed * self.currentPrice
        return usdt

    @staticmethod
    def round_down(num, digits=6):
        factor = 10.0 ** digits
        return math.floor(float(num) * factor) / factor

    def add_trade(self, message, order=None):
        """
        Adds a trade to list of trades
        :param order: Optional order from Binance API.
        :param message: Message used for conducting trade.
        """
        self.trades.append({
            'date': datetime.utcnow(),
            'action': message,
            'order': order
        })

    def main_logic(self):
        if self.inShortPosition:  # This means we are in short position
            if self.currentPrice > self.get_stop_loss():  # If current price is greater, then exit trade.
                self.buy_short(f'Bought short because of stop loss.', stopLoss=True)
                self.waitToEnterShort = True

            if self.check_cross_v2():
                self.buy_short(f'Bought short because a cross was detected.')
                self.buy_long(f'Bought long because a cross was detected.')

        elif self.inLongPosition:  # This means we are in long position
            if self.currentPrice < self.get_stop_loss():  # If current price is lower, then exit trade.
                self.sell_long(f'Sold long because of stop loss.', stopLoss=True)
                self.waitToEnterLong = True

            if self.check_cross_v2():
                self.sell_long(f'Sold long because a cross was detected.')
                self.sell_short('Sold short because a cross was detected.')

        else:  # This means we are in neither position
            if self.check_cross_v2():
                if self.trend == BULLISH:  # This checks if we are bullish or bearish
                    self.buy_long("Bought long because a cross was detected.")
                else:
                    self.sell_short("Sold short because a cross was detected.")

    def check_initial_position(self):
        if self.get_margin_coin() > 0.001:
            self.inLongPosition = True
            self.currentPrice = self.dataView.get_current_price()
            self.buyLongPrice = self.currentPrice
            self.longTrailingPrice = self.buyLongPrice
            self.add_trade('Was in long position from start of bot.')

        elif self.get_borrowed_margin_coin() > 0.001:
            self.inShortPosition = True
            self.currentPrice = self.dataView.get_current_price()
            self.sellShortPrice = self.currentPrice
            self.shortTrailingPrice = self.sellShortPrice
            self.add_trade('Was in short position from start of bot.')

    def get(self, target):
        assets = self.binanceClient.get_margin_account()['userAssets']
        coin = [asset for asset in assets if asset['asset'] == target][0]
        return coin

    def get_spot_usdt(self):
        return self.round_down(self.binanceClient.get_asset_balance(asset='USDT')['free'])

    def get_spot_coin(self):
        return self.round_down(self.binanceClient.get_asset_balance(asset=self.coinName)['free'])

    def spot_buy_long(self):
        self.spot_usdt = self.get_spot_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_buy = self.round_down(self.spot_usdt * (1 - 0.001) / self.currentPrice)

        order = self.binanceClient.order_market_buy(
            symbol=self.symbol,
            quantity=max_buy
        )

        self.add_trade('Bought spot long', order=order)

    def spot_sell_long(self):
        self.spot_coin = self.get_spot_coin()
        order = self.binanceClient.order_market_sell(
            symbol=self.symbol,
            quantity=self.spot_coin
        )

        self.add_trade('Sold spot long', order=order)

    def initial_transfer(self):
        self.spot_buy_long()
        self.transfer_spot_to_margin()

    def transfer_spot_to_margin(self):
        order = self.binanceClient.transfer_spot_to_margin(asset=self.coinName, amount=self.get_spot_coin())
        self.add_trade('Transferred from spot to margin', order=order)

    def transfer_margin_to_spot(self):
        order = self.binanceClient.transfer_margin_to_spot(asset=self.coinName, amount=self.get_margin_coin())
        self.add_trade('Transferred from margin to spot', order=order)

    def get_isolated_margin_account(self, **params):
        return self.binanceClient._request_margin_api('get', 'margin/isolated/account', True, data=params)

    def set_margin_values(self):
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            coin = [asset for asset in assets if asset['baseAsset']['asset'] == self.coinName][0]['baseAsset']
            usdt = [asset for asset in assets if asset['baseAsset']['asset'] == self.coinName and
                    asset['quoteAsset']['asset'] == 'USDT'][0]['quoteAsset']
        else:
            assets = self.binanceClient.get_margin_account()['userAssets']
            coin = [asset for asset in assets if asset['asset'] == self.coinName][0]
            usdt = [asset for asset in assets if asset['asset'] == 'USDT'][0]

        self.balance = self.round_down(float(usdt['free']))
        self.coin = self.round_down(float(coin['free']))
        self.coinOwed = self.round_down(float(coin['borrowed']))

    def get_margin_usdt(self):
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            for asset in assets:
                if asset['baseAsset']['asset'] == self.coinName and asset['quoteAsset']['asset'] == 'USDT':
                    return self.round_down(float(asset['quoteAsset']['free']))
        else:
            assets = self.binanceClient.get_margin_account()['userAssets']
            return self.round_down(float([asset for asset in assets if asset['asset'] == 'USDT'][0]))

    def get_margin_coin_info(self):
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            return [asset for asset in assets if asset['baseAsset']['asset'] == self.coinName][0]['baseAsset']
        else:
            assets = self.binanceClient.get_margin_account()['userAssets']
            return [asset for asset in assets if asset['asset'] == self.coinName][0]

    def get_margin_coin(self):
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['free']))

    def get_borrowed_margin_coin(self):
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['borrowed']))

    def get_borrowed_margin_interest(self):
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['interest']))

    def buy_long(self, msg, usd=None):
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_buy = self.round_down(self.balance / self.currentPrice)

        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=max_buy,
            isIsolated=self.isolated
        )

        self.add_trade(msg, order=order)
        self.coin = self.get_margin_coin()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.balance = self.get_margin_usdt()
        self.inLongPosition = True
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.output_message(msg)

    def sell_long(self, msg, coin=None, stopLoss=False):
        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=self.get_margin_coin(),
            isIsolated=self.isolated
        )

        self.add_trade(msg, order=order)
        self.coin = self.get_margin_coin()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.balance = self.get_margin_usdt()
        self.inLongPosition = False
        self.previousPosition = LONG
        self.buyLongPrice = None
        self.longTrailingPrice = None
        self.output_message(msg)

    def sell_short(self, msg, coin=None):
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_borrow = self.round_down(self.balance / self.currentPrice - self.get_borrowed_margin_coin())
        try:
            if self.isolated:
                order = self.binanceClient.create_margin_loan(asset=self.coinName, amount=max_borrow,
                                                              isIsolated=self.isolated, symbol=self.symbol)
            else:
                order = self.binanceClient.create_margin_loan(asset=self.coinName, amount=max_borrow)
            self.add_trade(f'Borrowed {self.coinName}.', order=order)
        except BinanceAPIException as e:
            print(f"Borrowing failed because {e}")
            self.output_message(f'Borrowing failed because {e}')

        order = self.binanceClient.create_margin_order(
            side=SIDE_SELL,
            symbol=self.symbol,
            type=ORDER_TYPE_MARKET,
            quantity=self.round_down(self.get_margin_coin()),
            isIsolated=self.isolated
        )

        self.add_trade(msg, order=order)
        self.balance = self.get_margin_usdt()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.coin = self.get_margin_coin()
        self.inShortPosition = True
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.output_message(msg)

    def buy_short(self, msg, coin=None, stopLoss=False):
        self.coinOwed = self.get_borrowed_margin_coin()
        difference = (self.coinOwed + self.get_borrowed_margin_interest()) * (1 + self.transactionFeePercentage)

        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=self.round_down(difference),
            isIsolated=self.isolated
        )
        self.add_trade(f'Bought {self.coinName} to repay loan', order=order)
        self.coin = self.get_margin_coin()

        try:
            if self.isolated:
                order = self.binanceClient.repay_margin_loan(
                    asset=self.coinName,
                    amount=self.coin,
                    isIsolated=self.isolated,
                    symbol=self.symbol
                )
            else:
                order = self.binanceClient.repay_margin_loan(
                    asset=self.coinName,
                    amount=self.coin
                )
            self.add_trade(msg, order=order)
        except BinanceAPIException as e:
            print(e)
            self.output_message(f"Repaying Failed because of {e}.")

        self.coinOwed = self.get_borrowed_margin_coin()
        self.coin = self.get_margin_coin()
        self.balance = self.get_margin_usdt()
        self.inShortPosition = False
        self.previousPosition = SHORT
        self.output_message(msg)
        self.sellShortPrice = None
        self.shortTrailingPrice = None


class Option:
    """
    Helper class object for trading objects
    """

    def __init__(self, movingAverage, parameter, initialBound, finalBound):
        self.movingAverage = movingAverage
        self.parameter = parameter
        self.initialBound = initialBound
        self.finalBound = finalBound
        self.previousInitialAverage = None
        self.previousFinalAverage = None

    def set_previous_initial_average(self, previousInitialAverage):
        self.previousInitialAverage = previousInitialAverage

    def set_previous_final_average(self, previousFinalAverage):
        self.previousFinalAverage = previousFinalAverage

    def set_moving_average(self, movingAverage):
        self.movingAverage = movingAverage

    def set_parameter(self, parameter):
        self.parameter = parameter

    def set_initial_bound(self, initialBound):
        self.initialBound = initialBound

    def set_final_bound(self, initialBound):
        self.initialBound = initialBound

    def get_moving_average(self):
        return self.movingAverage

    def get_parameter(self):
        return self.parameter

    def get_initial_bound(self):
        return self.initialBound

    def get_final_bound(self):
        return self.finalBound

    def __repr__(self):
        return f'Option({self.movingAverage}, {self.parameter}, {self.initialBound}, {self.finalBound})'


def main():
    pass


if __name__ == 'main':
    main()
