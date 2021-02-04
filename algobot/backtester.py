import os
import sys
import time

from dateutil import parser
from datetime import datetime
from helpers import load_from_csv, get_ups_and_downs
from option import Option
from enums import BEARISH, BULLISH, LONG, SHORT, TRAILING_LOSS, STOP_LOSS
from algorithms import get_sma, get_wma, get_ema


class Backtester:
    def __init__(self, startingBalance: float, data: list, lossStrategy: int, lossPercentage: float, options: list,
                 marginEnabled: bool = True, startDate: datetime = None, endDate: datetime = None, symbol: str = None,
                 stoicOptions=None, shrekOptions=None, precision: int = 2):
        self.startingBalance = startingBalance
        self.symbol = symbol
        self.balance = startingBalance
        self.coin = 0
        self.coinOwed = 0
        self.commissionsPaid = 0
        self.trades = []
        self.currentPrice = None
        self.transactionFeePercentage = 0.001
        self.profit = 0
        self.marginEnabled = marginEnabled
        self.precision = precision

        self.data = data
        self.check_data()
        self.interval = self.get_interval()
        self.lossStrategy = lossStrategy
        self.lossPercentageDecimal = lossPercentage / 100
        self.tradingOptions = options
        self.validate_options()

        self.minPeriod = self.get_min_option_period()
        self.trend = None

        if shrekOptions:
            self.shrekOptions = shrekOptions
            self.shrekEnabled = True
        else:
            self.shrekOptions = [None] * 4
            self.shrekEnabled = False

        self.shrekDictionary = {}
        self.rsi_dictionary = {}
        self.stoicDictionary = {}
        self.shrekTrend = None
        self.stoicTrend = None

        if stoicOptions is None:
            self.stoicOptions = [None, None, None]
            self.stoicEnabled = False
        else:
            self.stoicOptions = stoicOptions
            self.stoicEnabled = True
        self.ema_dict = {}

        self.movingAverageTestStartTime = None
        self.movingAverageTestEndTime = None
        self.startDateIndex = self.get_start_date_index(startDate)
        self.endDateIndex = self.get_end_date_index(endDate)

        self.inLongPosition = False
        self.inShortPosition = False
        self.previousPosition = None

        self.buyLongPrice = None
        self.longTrailingPrice = None

        self.sellShortPrice = None
        self.shortTrailingPrice = None
        self.currentPeriod = None

        self.previousStopLoss = None
        self.initialStopLossCounter = 0
        self.stopLossCounter = 0
        self.stopLossExit = False

    def check_data(self):
        """
        Checks data sorting. If descending, it reverses data, so we can mimic backtest as if we are starting from the
        beginning.
        """
        if type(self.data[0]['date_utc']) == str:
            self.convert_all_date_to_datetime()

        firstDate = self.data[0]['date_utc']
        lastDate = self.data[-1]['date_utc']

        if firstDate > lastDate:
            self.data = self.data[::-1]

    def validate_options(self):
        """
        Validates options provided. If the list of options provided does not contain all options, an error is raised.
        """
        for option in self.tradingOptions:
            if type(option) != Option:
                raise TypeError(f"'{option}' is not a valid option type.")

    def convert_all_date_to_datetime(self):
        """
        Converts all available dates to datetime objects.
        """
        for data in self.data:
            data['date_utc'] = parser.parse(data['date_utc'])

    def find_date_index(self, datetimeObject):
        """
        Finds index of date from datetimeObject if exists in data loaded.
        :param datetimeObject: Object to compare date-time with.
        :return: Index from self.data if found, else -1.
        """
        for data in self.data:
            if data['date_utc'].date() == datetimeObject:
                return self.data.index(data)
        return -1

    def get_start_date_index(self, startDate):
        """
        Returns index of start date based on startDate argument.
        :param startDate: Datetime object to compare index with.
        :return: Index of start date.
        """
        if startDate:
            if type(startDate) == datetime:
                startDate = startDate.date()
            startDateIndex = self.find_date_index(startDate)
            if startDateIndex == -1:
                raise IndexError("Date not found.")
            elif startDateIndex < self.minPeriod:
                raise IndexError(f"Start requires more periods than minimum period amount {self.minPeriod}.")
            else:
                return startDateIndex
        else:
            return self.minPeriod

    def get_end_date_index(self, endDate):
        """
        Returns index of end date based on endDate argument.
        :param endDate: Datetime object to compare index with.
        :return: Index of end date.
        """
        if endDate:
            if type(endDate) == datetime:
                endDate = endDate.date()
            endDateIndex = self.find_date_index(endDate)
            if endDateIndex == -1:
                raise IndexError("Date not found.")
            if endDateIndex < self.minPeriod:
                raise IndexError(f"End date requires more periods than minimum period amount {self.minPeriod}")
            if endDateIndex <= self.startDateIndex:
                raise IndexError("End date cannot be equal to or less than start date.")
            else:
                return endDateIndex
        else:
            return -1

    def get_min_option_period(self) -> int:
        """
        Returns the minimum period required to perform moving average calculations. For instance, if we needed to
        calculate SMA(25), we need at least 25 periods of data, and we'll only be able to start from the 26th period.
        :return: Minimum period of days required.
        """
        minimum = 0
        for option in self.tradingOptions:
            minimum = max(minimum, option.finalBound, option.initialBound)
        return minimum

    def get_moving_average(self, data: list, average: str, prices: int, parameter: str) -> float:
        """
        Returns moving average of given parameters.
        :param data: Data to get moving averages from.
        :param average: Type of average to retrieve, i.e. -> SMA, WMA, EMA
        :param prices: Amount of prices to get moving averages of.
        :param parameter: Parameter to use to get moving average, i.e. - HIGH, LOW, CLOSE, OPEN
        :return: Moving average.
        """
        if average.lower() == 'sma':
            return self.get_sma(data, prices, parameter)
        elif average.lower() == 'ema':
            return self.get_ema(data, prices, parameter)
        elif average.lower() == 'wma':
            return self.get_wma(data, prices, parameter)
        else:
            raise ValueError('Invalid average provided.')

    def check_trend(self, seenData):
        """
        Checks if there is a bullish or bearish trend with data provided and then sets object variable trend variable
        respectively.
        :param seenData: Data to use to check for trend.
        """
        trends = []  # trends seen so far; can be either BULLISH or BEARISH; they all have to be the same for a trend
        for option in self.tradingOptions:
            avg1 = self.get_moving_average(seenData, option.movingAverage, option.initialBound, option.parameter)
            avg2 = self.get_moving_average(seenData, option.movingAverage, option.finalBound, option.parameter)
            if avg1 > avg2:
                trends.append(BULLISH)
            elif avg1 < avg2:
                trends.append(BEARISH)
            else:  # this assumes they're equal
                trends.append(None)

        if all(trend == BULLISH for trend in trends):
            self.trend = BULLISH
        elif all(trend == BEARISH for trend in trends):
            self.trend = BEARISH
        else:
            self.trend = None

    def go_long(self, msg):
        """
        Executes long position.
        :param msg: Message that specifies why it entered long.
        """
        usd = self.balance  # current balance
        transactionFee = usd * self.transactionFeePercentage  # get commission fee
        self.commissionsPaid += transactionFee  # add commission fee to commissions paid total
        self.inLongPosition = True
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.coin += (usd - transactionFee) / self.currentPrice
        self.balance -= usd
        self.add_trade(msg)

    def exit_long(self, msg, stopLossExit=False):
        """
        Exits long position.
        :param stopLossExit: Boolean that'll determine whether a position was exited from a stop loss.
        :param msg: Message that specifies why it exited long.
        """
        coin = self.coin
        transactionFee = self.currentPrice * coin * self.transactionFeePercentage
        self.commissionsPaid += transactionFee
        self.inLongPosition = False
        self.previousPosition = LONG
        self.balance += coin * self.currentPrice - transactionFee
        self.coin -= coin
        self.add_trade(msg, stopLossExit=stopLossExit)

        if self.coin == 0:
            self.buyLongPrice = None
            self.longTrailingPrice = None

    def go_short(self, msg):
        """
        Executes short position.
        :param msg: Message that specifies why it entered short.
        """
        transactionFee = self.balance * self.transactionFeePercentage
        coin = (self.balance - transactionFee) / self.currentPrice
        self.commissionsPaid += transactionFee
        self.coinOwed += coin
        self.balance += self.currentPrice * coin - transactionFee
        self.inShortPosition = True
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.add_trade(msg)

    def exit_short(self, msg, stopLossExit=False):
        """
        Exits short position.
        :param stopLossExit: Boolean that'll determine whether a position was exited from a stop loss.
        :param msg: Message that specifies why it exited short.
        """
        coin = self.coinOwed
        self.coinOwed -= coin
        self.inShortPosition = False
        self.previousPosition = SHORT
        self.balance -= self.currentPrice * coin * (1 + self.transactionFeePercentage)
        self.add_trade(msg, stopLossExit=stopLossExit)

        if self.coinOwed == 0:
            self.sellShortPrice = None
            self.shortTrailingPrice = None

    def add_trade(self, message, stopLossExit=False):
        """
        Adds a trade to list of trades
        :param stopLossExit: Boolean that'll determine where this trade occurred from a stop loss.
        :param message: Message used for conducting trade.
        """
        self.stopLossExit = stopLossExit
        self.trades.append({
            'date': self.currentPeriod['date_utc'],
            'action': message,
            'net': round(self.get_net(), self.precision)
        })

    def get_short_stop_loss(self) -> float:
        """
        Returns stop loss for short position.
        :return: Stop loss for short position.
        """
        if self.shortTrailingPrice is None:
            self.shortTrailingPrice = self.currentPrice
            self.sellShortPrice = self.shortTrailingPrice
        if self.lossStrategy == TRAILING_LOSS:  # This means we use trailing loss.
            return self.shortTrailingPrice * (1 + self.lossPercentageDecimal)
        elif self.lossStrategy == STOP_LOSS:  # This means we use the basic stop loss.
            return self.sellShortPrice * (1 + self.lossPercentageDecimal)

    def get_long_stop_loss(self) -> float:
        """
        Returns stop loss for long position.
        :return: Stop loss for long position.
        """
        if self.longTrailingPrice is None:
            self.longTrailingPrice = self.currentPrice
            self.buyLongPrice = self.longTrailingPrice
        if self.lossStrategy == TRAILING_LOSS:  # This means we use trailing loss.
            return self.longTrailingPrice * (1 - self.lossPercentageDecimal)
        elif self.lossStrategy == STOP_LOSS:  # This means we use the basic stop loss.
            return self.buyLongPrice * (1 - self.lossPercentageDecimal)

    def get_stop_loss(self) -> float or None:
        """
        Returns stop loss value.
        :return: Stop loss value.
        """
        if self.inShortPosition:  # If we are in a short position
            self.previousStopLoss = self.get_short_stop_loss()
            return self.previousStopLoss
        elif self.inLongPosition:  # If we are in a long position
            self.previousStopLoss = self.get_long_stop_loss()
            return self.previousStopLoss
        else:  # This means we are not in a position.
            return None

    def get_net(self) -> float:
        """
        Returns net balance with current price of coin being traded. It factors in the current balance, the amount
        shorted, and the amount owned.
        :return: Net balance.
        """
        return self.coin * self.currentPrice - self.coinOwed * self.currentPrice + self.balance

    def get_interval(self) -> str:
        """
        Attempts to parse interval from loaded data.
        :return: Interval in str format.
        """
        period1 = self.data[0]['date_utc']
        period2 = self.data[1]['date_utc']

        if type(period1) == str:
            period1 = parser.parse(period1)
        if type(period2) == str:
            period2 = parser.parse(period2)

        difference = period2 - period1
        seconds = difference.total_seconds()
        if seconds < 3600:  # this is 60 minutes
            minutes = seconds / 60
            return f'{int(minutes)} Minute'
        elif seconds < 86400:  # this is 24 hours
            hours = seconds / 3600
            return f'{int(hours)} Hour'
        else:  # this assumes it's day
            days = seconds / 86400
            return f'{int(days)} Day'

    def set_stop_loss_counter(self, counter):
        """
        Sets stop loss equal to the counter provided.
        :param counter: Value to set counter to.
        """
        self.stopLossCounter = self.initialStopLossCounter = counter

    def reset_smart_stop_loss(self):
        self.stopLossCounter = self.initialStopLossCounter

    def reset_stoic_dictionary(self):
        self.stoicDictionary = {}

    def reset_everything(self):
        """
        Resets all data in backtest object.
        """
        self.balance = self.startingBalance
        self.coin = 0
        self.coinOwed = 0
        self.commissionsPaid = 0
        self.trades = []
        self.currentPrice = None
        self.transactionFeePercentage = 0.001
        self.profit = 0
        self.inLongPosition = False
        self.inShortPosition = False
        self.previousPosition = None
        self.buyLongPrice = None
        self.longTrailingPrice = None
        self.sellShortPrice = None
        self.shortTrailingPrice = None
        self.currentPeriod = None

    # noinspection DuplicatedCode
    def shrek_strategy(self, data, one: int, two: int, three: int, four: int):
        """
        New custom strategy.
        :param data: Data to use for strategy.
        :param one: Input 1.
        :param two: Input 2.
        :param three: Input 3.
        :param four: Input 4.
        :return: Strategy's current trend.
        """
        data = [rsi for rsi in [self.get_rsi(data, two, shift=x) for x in range(two + 1)]]
        rsi_two = data[0]

        apple = max(data) - min(data)
        beetle = rsi_two - min(data)

        if 'apple' in self.shrekDictionary:
            self.shrekDictionary['apple'].append(apple)
        else:
            self.shrekDictionary['apple'] = [apple]

        if 'beetle' in self.shrekDictionary:
            self.shrekDictionary['beetle'].append(beetle)
        else:
            self.shrekDictionary['beetle'] = [beetle]

        if len(self.shrekDictionary['apple']) < three + 1:
            return
        else:
            carrot = sum(self.shrekDictionary['beetle'][:three + 1])
            donkey = sum(self.shrekDictionary['apple'][:three + 1])
            self.shrekDictionary['beetle'] = self.shrekDictionary['beetle'][1:]
            self.shrekDictionary['apple'] = self.shrekDictionary['apple'][1:]
            onion = carrot / donkey * 100

            if one > onion:
                self.shrekTrend = BULLISH
            elif onion > four:
                self.shrekTrend = BEARISH
            else:
                self.shrekTrend = None

    # noinspection DuplicatedCode
    def stoic_strategy(self, data, input1: int, input2: int, input3: int, s: int = 0):
        """
        Custom strategy.
        :param data: Data list.
        :param input1: Custom input 1 for the stoic strategy.
        :param input2: Custom input 2 for the stoic strategy.
        :param input3: Custom input 3 for the stoic strategy.
        :param s: Shift data to get previous values.
        """
        rsi_values_one = [self.get_rsi(data, input1, shift=shift) for shift in range(s, input1 + s)]
        rsi_values_two = [self.get_rsi(data, input2, shift=shift) for shift in range(s, input2 + s)]

        seneca = max(rsi_values_one) - min(rsi_values_one)
        if 'seneca' in self.stoicDictionary:
            self.stoicDictionary['seneca'].insert(0, seneca)
        else:
            self.stoicDictionary['seneca'] = [seneca]

        zeno = rsi_values_one[0] - min(rsi_values_one)
        if 'zeno' in self.stoicDictionary:
            self.stoicDictionary['zeno'].insert(0, zeno)
        else:
            self.stoicDictionary['zeno'] = [zeno]

        gaius = rsi_values_two[0] - min(rsi_values_two)
        if 'gaius' in self.stoicDictionary:
            self.stoicDictionary['gaius'].insert(0, gaius)
        else:
            self.stoicDictionary['gaius'] = [gaius]

        philo = max(rsi_values_two) - min(rsi_values_two)
        if 'philo' in self.stoicDictionary:
            self.stoicDictionary['philo'].insert(0, philo)
        else:
            self.stoicDictionary['philo'] = [philo]

        if len(self.stoicDictionary['gaius']) < 3:
            return None

        hadot = sum(self.stoicDictionary['gaius'][:3]) / sum(self.stoicDictionary['philo'][:3]) * 100
        if 'hadot' in self.stoicDictionary:
            self.stoicDictionary['hadot'].insert(0, hadot)
        else:
            self.stoicDictionary['hadot'] = [hadot]

        if len(self.stoicDictionary['hadot']) < 3:
            return None

        stoic = sum(self.stoicDictionary['zeno'][:3]) / sum(self.stoicDictionary['seneca'][:3]) * 100
        marcus = sum(self.stoicDictionary['hadot'][:input3]) / input3

        if marcus > stoic:
            self.stoicTrend = BEARISH
        elif marcus < stoic:
            self.stoicTrend = BULLISH
        else:
            self.stoicTrend = None

    def helper_get_ema(self, up_data: list, down_data: list, periods: int) -> float:
        """
        Helper function to get the EMA for relative strength index and return the RSI.
        :param down_data: Other data to get EMA of.
        :param up_data: Data to get EMA of.
        :param periods: Number of periods to iterate through.
        :return: RSI
        """
        emaUp = up_data[0]
        emaDown = down_data[0]
        alpha = 1 / periods
        rsi_values = []

        for index in range(1, len(up_data)):
            emaUp = up_data[index] * alpha + emaUp * (1 - alpha)
            emaDown = down_data[index] * alpha + emaDown * (1 - alpha)
            rsi = 100 if emaDown == 0 else 100 - 100 / (1 + emaUp / emaDown)
            rsi_values.append((rsi, emaUp, emaDown))

        if periods in self.rsi_dictionary:
            rsi_values = self.rsi_dictionary[periods]['close'] + rsi_values

        self.rsi_dictionary[periods] = {'close': rsi_values}

        return rsi_values[-1][0]

    # noinspection DuplicatedCode
    def get_rsi(self, data: list, prices: int = 14, parameter: str = 'close',
                shift: int = 0, round_value: bool = True) -> float:
        """
        Returns relative strength index.
        :param data: Data values.
        :param prices: Amount of prices to iterate through.
        :param parameter: Parameter to use for iterations. By default, it's close.
        :param shift: Amount of prices to shift prices by.
        :param round_value: Boolean that determines whether final value is rounded or not.
        :return: Final relative strength index.
        """
        if shift > 0 and prices in self.rsi_dictionary:
            return self.rsi_dictionary[prices]['close'][-shift][0]
        elif prices in self.rsi_dictionary:
            alpha = 1 / prices
            difference = data[0][parameter] - data[1][parameter]
            if difference > 0:
                up = difference * alpha + self.rsi_dictionary[prices]['close'][-1][1] * (1 - alpha)
                down = self.rsi_dictionary[prices]['close'][-1][2] * (1 - alpha)
            else:
                up = self.rsi_dictionary[prices]['close'][-1][1] * (1 - alpha)
                down = -difference * alpha + self.rsi_dictionary[prices]['close'][-1][2] * (1 - alpha)

            rsi = 100 if down == 0 else 100 - 100 / (1 + up / down)
            self.rsi_dictionary[prices]['close'].append((round(rsi, self.precision), up, down))
            return rsi

        data = data
        start = 500 + prices + shift if len(data) > 500 + prices + shift else len(data)
        data = data[shift:start]
        data = data[:]
        data.reverse()

        ups, downs = get_ups_and_downs(data=data, parameter=parameter)
        rsi = self.helper_get_ema(ups, downs, prices)

        if round_value:
            return round(rsi, self.precision)
        return rsi

    def get_sma(self, data: list, prices: int, parameter: str, round_value=True) -> float:
        data = data[0: prices]
        sma = get_sma(data, prices, parameter)

        if round_value:
            return round(sma, self.precision)
        return sma

    def get_wma(self, data: list, prices: int, parameter: str, round_value=True) -> float:
        data = data[0: prices]
        wma = get_wma(data, prices, parameter)

        if round_value:
            return round(wma, self.precision)
        return wma

    def get_ema(self, data: list, prices: int, parameter: str, sma_prices: int = 5, round_value=True) -> float:
        if sma_prices <= 0:
            raise ValueError("Initial amount of SMA values for initial EMA must be greater than 0.")
        elif sma_prices > len(data):
            sma_prices = len(data) - 1

        ema, self.ema_dict = get_ema(data, prices, parameter, sma_prices, self.ema_dict)

        if round_value:
            return round(ema, self.precision)
        return ema

    def main_logic(self):
        """
        Main logic that dictates how backtest works. It checks for stop losses and then moving averages to check for
        upcoming trends.
        """
        if self.inShortPosition:  # This means we are in short position
            if self.currentPrice > self.get_stop_loss():  # If current price is greater, then exit trade.
                self.exit_short('Exited short because of a stop loss.', stopLossExit=True)

            elif self.trend == BULLISH:
                if self.stoicEnabled:
                    if self.stoicTrend == BULLISH:
                        if not self.shrekEnabled:
                            self.exit_short(f'Exited short because a cross and stoicism were detected.')
                            self.go_long(f'Entered long because a cross and stoicism were detected.')
                        elif self.shrekEnabled and self.shrekTrend == BULLISH:
                            self.exit_short(f'Exited short because a cross, shrek, and stoicism were detected.')
                            self.go_long(f'Entered long because a cross, shrek, and stoicism were detected.')
                elif self.shrekEnabled:
                    if self.shrekTrend == BULLISH:
                        self.exit_short('Exited short because a cross and shrek was detected.')
                        self.go_long('Entered long because a cross and shrek was detected.')
                else:
                    self.exit_short('Exited short because a cross was detected.')
                    self.go_long('Entered long because a cross was detected.')
        elif self.inLongPosition:  # This means we are in long position
            if self.currentPrice < self.get_stop_loss():  # If current price is lower, then exit trade.
                self.exit_long('Exited long because of a stop loss.', stopLossExit=True)
            elif self.trend == BEARISH:
                if self.stoicEnabled:
                    if self.stoicTrend == BEARISH:
                        if not self.shrekEnabled:
                            self.exit_long('Exited long because a cross and stoicism were detected.')
                            if self.marginEnabled:
                                self.go_short('Entered short because a cross and stoicism were detected.')
                        elif self.shrekEnabled and self.shrekTrend == BEARISH:
                            self.exit_long('Exited long because a cross, shrek, and stoicism were detected.')
                            if self.marginEnabled:
                                self.go_short('Entered short because a cross, shrek, and stoicism were detected.')
                elif self.shrekEnabled:
                    if self.shrekTrend == BEARISH:
                        self.exit_long('Exited long because a cross and shrek was detected.')
                        if self.marginEnabled:
                            self.go_short('Entered short because a cross and shrek was detected.')
                else:
                    self.exit_long('Exited long because a cross was detected.')
                    if self.marginEnabled:
                        self.go_short('Entered short because a cross was detected.')
        else:  # This means we are in neither position
            if self.trend == BULLISH and self.previousPosition != LONG:
                if self.stoicEnabled:
                    if self.stoicTrend == BULLISH:
                        if not self.shrekEnabled:
                            self.go_long('Entered long because a cross and stoicism were detected.')
                            self.reset_smart_stop_loss()
                        elif self.shrekEnabled and self.shrekTrend == BULLISH:
                            self.go_long('Entered long because a cross, shrek, and stoicism were detected.')
                            self.reset_smart_stop_loss()
                elif self.shrekEnabled:
                    if self.shrekTrend == BULLISH:
                        self.go_long('Entered long because a cross and shrek were detected.')
                        self.reset_smart_stop_loss()
                else:
                    self.go_long('Entered long because a cross was detected.')
                    self.reset_smart_stop_loss()
            elif self.marginEnabled and self.trend == BEARISH and self.previousPosition != SHORT:
                if self.stoicEnabled:
                    if self.stoicTrend == BEARISH:
                        if not self.shrekEnabled:
                            self.go_short('Entered short because a cross and stoicism were detected.')
                            self.reset_smart_stop_loss()
                        elif self.shrekEnabled and self.shrekTrend == BEARISH:
                            self.go_short('Entered short because a cross, shrek, and stoicism were detected.')
                            self.reset_smart_stop_loss()
                elif self.shrekEnabled:
                    if self.shrekTrend == BEARISH:
                        self.go_short('Entered short because a cross and shrek were detected.')
                        self.reset_smart_stop_loss()
                else:
                    self.go_short('Entered short because a cross was detected.')
                    self.reset_smart_stop_loss()
            else:
                if self.previousPosition == LONG and self.stopLossExit:
                    if self.currentPrice > self.previousStopLoss and self.stopLossCounter > 0:
                        self.go_long("Reentered long because of smart stop loss.")
                        self.stopLossCounter -= 1
                elif self.previousPosition == SHORT and self.stopLossExit:
                    if self.currentPrice < self.previousStopLoss and self.stopLossCounter > 0:
                        self.go_short("Reentered short because of smart stop loss.")
                        self.stopLossCounter -= 1

    def moving_average_test(self):
        """
        Performs a moving average test with given configurations.
        """
        self.movingAverageTestStartTime = time.time()
        seenData = self.data[:self.minPeriod][::-1]  # Start from minimum previous period data.
        s1, s2, s3 = self.stoicOptions
        for period in self.data[self.startDateIndex:self.endDateIndex]:
            seenData.insert(0, period)
            self.currentPeriod = period
            self.currentPrice = period['open']
            self.main_logic()
            self.check_trend(seenData)
            if self.stoicEnabled and len(seenData) > max((s1, s2, s3)):
                self.stoic_strategy(seenData, s1, s2, s3)

        if self.inShortPosition:
            self.exit_short('Exited short because of end of backtest.')
        elif self.inLongPosition:
            self.exit_long('Exiting long because of end of backtest.')

        self.movingAverageTestEndTime = time.time()
        # self.print_stats()
        # self.print_trades()

        # for period in self.data[5:]:
        #     seenData.append(period)
        #     avg1 = self.get_sma(seenData, 2, 'close')
        #     avg2 = self.get_wma(seenData, 5, 'open')
        #     print(avg1)

    def find_optimal_moving_average(self, averageStart: int, averageLimit: int):
        """
        Runs extensive moving average tests and returns the one with best return percentages.
        :return: A dictionary of values for the test.
        """
        self.balance = 0
        results = []
        movingAverages = ('wma', 'sma', 'ema')
        params = ('high', 'low', 'open', 'close')
        total = (averageLimit - averageStart + 1) ** 2 * 4 * 3
        done = 0

        t1 = time.time()

        for limit1 in range(averageStart, averageLimit + 1):
            for limit2 in range(averageStart, averageLimit + 1):
                for movingAverage in movingAverages:
                    for param in params:
                        options = [Option(movingAverage, param, limit1, limit2)]
                        self.reset_everything()
                        self.tradingOptions = options
                        self.moving_average_test()
                        results.append((self.profit, options))
                        done += 1
                print(f'Done {round(done / total * 100, 2)}%')

        print(time.time() - t1)

        results.sort(key=lambda x: x[0], reverse=True)
        print(results[:20])

    def print_options(self):
        """
        Prints out options provided in configuration.
        """
        # print("Options:")
        for index, option in enumerate(self.tradingOptions):
            print(f'\tOption {index + 1}) {option.movingAverage.upper()}{option.initialBound, option.finalBound}'
                  f' - {option.parameter}')

    def print_configuration_parameters(self, stdout=None):
        """
        Prints out configuration parameters.
        """
        previous_stdout = sys.stdout
        if stdout is not None:  # Temporarily redirects output to stdout provided.
            sys.stdout = stdout

        print("Backtest configuration:")
        print(f"\tSmart Stop Loss Counter: {self.initialStopLossCounter}")
        print(f'\tInterval: {self.interval}')
        print(f'\tMargin Enabled: {self.marginEnabled}')
        print(f"\tStarting Balance: ${self.startingBalance}")
        self.print_options()
        # print("Loss options:")
        print(f'\tStop Loss Percentage: {round(self.lossPercentageDecimal * 100, 2)}%')
        if self.lossStrategy == TRAILING_LOSS:
            print(f"\tLoss Strategy: Trailing")
        else:
            print("\tLoss Strategy: Stop")

        sys.stdout = previous_stdout  # revert stdout back to normal

    def print_backtest_results(self, stdout=None):
        """
        Prints out backtest results.
        """
        previous_stdout = sys.stdout
        if stdout is not None:  # Temporarily redirects output to stdout provided.
            sys.stdout = stdout

        print("\nBacktest results:")
        print(f'\tSymbol: {"Unknown/Imported Data" if self.symbol is None else self.symbol}')
        print(f'\tElapsed: {round(self.movingAverageTestEndTime - self.movingAverageTestStartTime, 2)} seconds')
        print(f'\tShrek Enabled: {self.shrekEnabled}')
        print(f'\tShrek Options: {self.shrekOptions}')
        print(f'\tStoicism enabled: {self.stoicEnabled}')
        print(f'\tStoicism options: {self.stoicOptions}')
        print(f'\tStart Period: {self.data[self.startDateIndex]["date_utc"]}')
        print(f"\tEnd Period: {self.currentPeriod['date_utc']}")
        print(f'\tStarting balance: ${round(self.startingBalance, self.precision)}')
        print(f'\tNet: ${round(self.get_net(), self.precision)}')
        print(f'\tCommissions paid: ${round(self.commissionsPaid, self.precision)}')
        print(f'\tTrades made: {len(self.trades)}')
        net = self.get_net()
        difference = round(net - self.startingBalance, self.precision)
        if difference > 0:
            print(f'\tProfit: ${difference}')
            print(f'\tProfit Percentage: {round(net / self.startingBalance * 100 - 100, 2)}%')
        elif difference < 0:
            print(f'\tLoss: ${-difference}')
            print(f'\tLoss Percentage: {round(100 - net / self.startingBalance * 100, 2)}%')
        else:
            print("\tNo profit or loss incurred.")
        # print(f'Balance: ${round(self.balance, 2)}')
        # print(f'Coin owed: {round(self.coinOwed, 2)}')
        # print(f'Coin owned: {round(self.coin, 2)}')
        # print(f'Trend: {self.trend}')

        sys.stdout = previous_stdout  # revert stdout back to normal

    def print_stats(self):
        """
        Prints basic statistics.
        """
        self.print_configuration_parameters()
        self.print_backtest_results()

    def print_trades(self, stdout=sys.__stdout__):
        """
        Prints out all the trades conducted so far.
        """
        previous_stdout = sys.stdout
        if stdout is not None:  # Temporarily redirects output to stdout provided.
            sys.stdout = stdout

        print("\nTrades made:")
        for trade in self.trades:
            print(f'\t{trade["date"].strftime("%Y-%m-%d %H:%M")}: (${trade["net"]}) {trade["action"]}')

        sys.stdout = previous_stdout  # revert stdout back to normal

    def get_default_result_file_name(self):
        """
        Returns a default backtest result file name.
        :return: String filename.
        """
        backtestResultsFolder = 'Backtest Results'
        symbol = 'Imported' if not self.symbol else self.symbol
        dateString = datetime.now().strftime("%Y-%m-%d_%H-%M")
        resultFile = f'{symbol}_backtest_results_{"_".join(self.interval.lower().split())}-{dateString}.txt'
        os.chdir('../')

        if not os.path.exists(backtestResultsFolder):
            os.mkdir(backtestResultsFolder)
        os.chdir(backtestResultsFolder)

        counter = 0
        previousFile = resultFile

        while os.path.exists(resultFile):
            resultFile = f'({counter}){previousFile}'
            counter += 1

        return resultFile

    def write_results(self, resultFile=None) -> str:
        """
        Writes backtest results to resultFile provided. If none is provided, it'll write to a default file name.
        :param resultFile: File to write results in.
        :return: Path to file.
        """
        currentPath = os.getcwd()

        if not resultFile:
            resultFile = self.get_default_result_file_name()

        with open(resultFile, 'w') as f:
            self.print_configuration_parameters(f)
            self.print_backtest_results(f)
            self.print_trades(f)

        filePath = os.path.join(os.getcwd(), resultFile)

        os.chdir(currentPath)
        return filePath


if __name__ == '__main__':
    path = r'C:\Users\Mihir Shrestha\PycharmProjects\CryptoAlgo\CSV\BTCUSDT\BTCUSDT_data_1d.csv'
    testData = load_from_csv(path)
    opt = [Option('sma', 'high', 18, 24), Option('wma', 'low', 19, 23)]
    a = Backtester(data=testData, startingBalance=1000, lossStrategy=STOP_LOSS, lossPercentage=99, options=opt,
                   marginEnabled=True, startDate=datetime(2018, 1, 1), symbol="BTCUSDT")
    # a.find_optimal_moving_average(15, 20)
    a.moving_average_test()
    a.print_trades()
    # # a.print_stats()
    a.write_results()
