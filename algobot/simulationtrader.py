import time
import logging

from datetime import datetime
from data import Data
from option import Option
from enums import LONG, SHORT, BEARISH, BULLISH


class SimulatedTrader:
    def __init__(self, startingBalance=1000, interval='1h', symbol='BTCUSDT', loadData=True):
        self.dataView = Data(interval=interval, symbol=symbol, loadData=loadData)  # Retrieve data-view object.
        self.binanceClient = self.dataView.binanceClient  # Retrieve Binance client.
        self.symbol = self.dataView.symbol  # Retrieve symbol from data-view object.

        # Initialize initial values.
        self.balance = startingBalance  # USDT Balance.
        self.startingBalance = self.balance  # Balance we started bot run with.
        self.coinName = self.get_coin_name()  # Retrieve primary coin to trade.
        self.coin = 0  # Amount of coin we own.
        self.coinOwed = 0  # Amount of coin we owe.
        self.transactionFeePercentage = 0.001  # Binance transaction fee percentage.
        self.trades = []  # All trades performed.

        self.tradingOptions = []  # List with Option elements. Helps specify what moving averages to trade with.
        self.trend = None  # 1 is bullish, -1 is bearish; usually handled with enums.
        self.lossPercentageDecimal = None  # Loss percentage in decimal for stop loss.
        self.startingTime = datetime.utcnow()  # Starting time in UTC.
        self.endingTime = None  # Ending time for previous bot run.

        self.buyLongPrice = None  # Price we last bought our target coin at in long position.
        self.sellShortPrice = None  # Price we last sold target coin at in short position.
        self.lossStrategy = None  # Type of loss type we are using: whether it's trailing loss or stop loss.
        self.stopLoss = None  # Price at which bot will exit trade due to stop loss limits.
        self.longTrailingPrice = None  # Price coin has to be above for long position.
        self.shortTrailingPrice = None  # Price coin has to be below for short position.
        self.currentPrice = None  # Current price of coin.

        self.inHumanControl = False  # Boolean that keeps track of whether human or bot controls transactions.
        self.waitToEnterLong = False  # Boolean that checks if bot should wait before entering long position.
        self.waitToEnterShort = False  # Boolean that checks if bot should wait before entering short position.
        self.inLongPosition = False  # Boolean that keeps track of whether bot is in a long position or not.
        self.inShortPosition = False  # Boolean that keeps track of whether bot is in a short position or not.
        self.previousPosition = None  # Previous position to validate for a cross.

    def get_net(self) -> float:
        """
        Returns net balance with current price of coin being traded. It factors in the current balance, the amount
        shorted, and the amount owned.
        :return: Net balance.
        """
        if self.currentPrice is None:
            self.currentPrice = self.dataView.get_current_price()
        return self.coin * self.currentPrice - self.coinOwed * self.currentPrice + self.balance

    def get_coin_name(self) -> str:
        """
        Returns target coin name.
        Function assumes trader is using a coin paired with USDT.
        """
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

    def add_trade(self, message, initialNet, finalNet, price, force, orderID=None):
        """
        Adds a trade to list of trades
        :param orderID: Order ID returned from Binance API.
        :param finalNet: Final net balance after trade was conducted.
        :param initialNet: Initial net balance before trade was conducted.
        :param force: Boolean that determines whether trade was conducted autonomously or by hand.
        :param price: Price trade was conducted at.
        :param message: Message used for conducting trade.
        """
        profit = finalNet - initialNet
        profitPercentage = self.get_profit_percentage(initialNet, finalNet)
        if force:
            force = 'Manual'
        else:
            force = 'Automation'

        self.trades.append({
            'date': datetime.utcnow(),
            'orderID': orderID,
            'action': message,
            'pair': self.symbol,
            'price': f'${round(price, 2)}',
            'method': force,
            'percentage': f'{round(profitPercentage, 2)}%',
            'profit': f'${round(profit, 2)}'
        })

    @staticmethod
    def get_profit_percentage(initialNet, finalNet):
        """
        Calculates net percentage from initial and final values.
        :param initialNet: Initial net value.
        :param finalNet: Final net value.
        :return:
        """
        if finalNet > initialNet:
            return finalNet / initialNet * 100
        else:
            return -1 * (100 - finalNet / initialNet * 100)

    def buy_long(self, msg, usd=None, force=False):
        """
        Buys coin at current market price with amount of USD specified. If not specified, assumes bot goes all in.
        Function also takes into account Binance's 0.1% transaction fee.
        """
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

        self.currentPrice = self.dataView.get_current_price()
        initialNet = self.get_net()
        transactionFee = usd * self.transactionFeePercentage
        self.inLongPosition = True
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.coin += (usd - transactionFee) / self.currentPrice
        self.balance -= usd
        finalNet = self.get_net()
        self.add_trade(msg, initialNet=initialNet, finalNet=finalNet, price=self.currentPrice, force=force)
        self.output_message(msg)

    def sell_long(self, msg, coin=None, force=False):
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
        initialNet = self.get_net()
        earned = coin * self.currentPrice * (1 - self.transactionFeePercentage)
        self.inLongPosition = False
        self.previousPosition = LONG
        self.coin -= coin
        self.balance += earned
        finalNet = self.get_net()
        self.add_trade(msg, initialNet=initialNet, finalNet=finalNet, price=self.currentPrice, force=force)
        self.output_message(msg)

        if self.coin == 0:
            self.buyLongPrice = None
            self.longTrailingPrice = None

    def buy_short(self, msg, coin=None, force=False):
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
        initialNet = self.get_net()
        self.coinOwed -= coin
        self.inShortPosition = False
        self.previousPosition = SHORT
        loss = self.currentPrice * coin * (1 + self.transactionFeePercentage)
        self.balance -= loss
        finalNet = self.get_net()
        self.add_trade(msg, initialNet=initialNet, finalNet=finalNet, price=self.currentPrice, force=force)
        self.output_message(msg)

        if self.coinOwed == 0:
            self.sellShortPrice = None
            self.shortTrailingPrice = None

    def sell_short(self, msg, coin=None, force=False):
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

        initialNet = self.get_net()
        self.coinOwed += coin
        self.balance += self.currentPrice * coin * (1 - self.transactionFeePercentage)
        self.inShortPosition = True
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        finalNet = self.get_net()
        self.add_trade(msg, force=force, initialNet=initialNet, finalNet=finalNet, price=self.currentPrice)
        self.output_message(msg)

    def get_profit(self):
        """
        Returns profit or loss.
        :return: A number representing profit if positive and loss if negative.
        """
        try:
            if self.inShortPosition:
                return self.coinOwed * (self.sellShortPrice - self.currentPrice)
            else:
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

    def get_average(self, movingAverage, parameter, value, dataObject=None):
        """
        Returns the moving average with parameter and value provided
        :param dataObject: Data object to be used to get moving averages.
        :param movingAverage: Moving average to get the average from the data view.
        :param parameter: Parameter for the data view to use in the moving average.
        :param value: Value for the moving average to use in the moving average.
        :return: A float value representing the moving average.
        """
        if dataObject is None:
            dataObject = self.dataView
        if movingAverage == 'SMA':
            return dataObject.get_sma(value, parameter)
        elif movingAverage == 'WMA':
            return dataObject.get_wma(value, parameter)
        elif movingAverage == 'EMA':
            return dataObject.get_ema(value, parameter)
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
                return self.shortTrailingPrice * (1 + self.lossPercentageDecimal)
            else:  # This means we use the basic stop loss.
                return self.sellShortPrice * (1 + self.lossPercentageDecimal)
        elif self.inLongPosition:  # If we are in a long position
            if self.longTrailingPrice is None:
                self.longTrailingPrice = self.dataView.get_current_price()
                self.buyLongPrice = self.longTrailingPrice
            if self.lossStrategy == 2:  # This means we use trailing loss.
                return self.longTrailingPrice * (1 - self.lossPercentageDecimal)
            else:  # This means we use the basic stop loss.
                return self.buyLongPrice * (1 - self.lossPercentageDecimal)
        else:
            return None

    def check_cross_v2(self, dataObject=None):
        if len(self.tradingOptions) == 0:  # Checking whether options exist.
            self.output_message("No trading options provided.")
            return

        trends = []

        if dataObject is None:
            dataObject = self.dataView

        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound, dataObject)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound, dataObject)

            if dataObject == self.dataView:
                self.output_message(f'Regular interval ({dataObject.interval}) data:')
            else:
                self.output_message(f'Lower interval ({dataObject.interval}) data:')

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
                longTrailingLossValue = round(self.longTrailingPrice * (1 - self.lossPercentageDecimal), 2)
                self.output_message(f'Long trailing loss: ${longTrailingLossValue}')
            else:
                self.output_message(f'Stop loss: {round(self.buyLongPrice * (1 - self.lossPercentageDecimal), 2)}')
        elif self.inShortPosition:
            self.output_message(f'\nCurrently in short position.')
            if self.lossStrategy == 2:
                shortTrailingLossValue = round(self.shortTrailingPrice * (1 + self.lossPercentageDecimal), 2)
                self.output_message(f'Short trailing loss: ${shortTrailingLossValue}')
            else:
                self.output_message(f'Stop loss: {round(self.sellShortPrice * (1 + self.lossPercentageDecimal), 2)}')
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
        self.endingTime = datetime.utcnow()
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
                 lossStrategy=None, options=None):
        """
        Starts a live simulation with given parameters.
        :param options: Argument for all trading options.
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

        self.lossPercentageDecimal = lossPercentage
        self.lossStrategy = lossStrategy
        self.trades = []
        self.sellShortPrice = None
        self.buyLongPrice = None
        self.shortTrailingPrice = None
        self.longTrailingPrice = None
        self.balance = 1000
        self.startingBalance = self.balance
        self.startingTime = datetime.utcnow()

        while self.lossStrategy not in (1, 2):
            try:
                self.lossStrategy = int(input('Enter 1 for stop loss or 2 for trailing loss strategy>>'))
            except ValueError:
                print("Please type in a valid number.")

        self.output_message("Starting simulation...")

        self.simulate_option_1()
        self.output_message("\nExiting simulation.")
        self.get_simulation_result()
        self.log_trades()

    def simulate_option_1(self):
        fail = False  # Boolean for whether there was an error that occurred.
        self.waitToEnterShort = False  # Boolean for whether we should wait to exit out of short position.
        self.waitToEnterLong = False  # Boolean for whether we should wait to exit out of long position.
        self.inHumanControl = False  # Boolean for whether the bot is in human control.
        self.stopLoss = None  # Stop loss value at which bot will exit position
        self.longTrailingPrice = None  # Variable that will keep track of long trailing price.
        self.shortTrailingPrice = None  # Variable that will keep track of short trailing price.
        self.inLongPosition = False  # Boolean that keeps track of whether we are in a long position.
        self.inShortPosition = False  # Boolean that keeps track of whether we are in a short position.

        while True:
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
            if self.check_cross_v2():  # before i get confused again, this function handles stop loss edge cases too
                if self.trend == BULLISH:  # This checks if we are bullish or bearish
                    self.buy_long("Bought long because a cross was detected.")
                else:
                    self.sell_short("Sold short because a cross was detected.")

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
