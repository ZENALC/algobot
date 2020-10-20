import os
import sys
import time
from dateutil import parser
from datetime import datetime
from helpers import load_from_csv
from option import Option
from enums import BEARISH, BULLISH, LONG, SHORT, TRAILING_LOSS, STOP_LOSS


class Backtester:
    def __init__(self, startingBalance: float, data: list, lossStrategy: int, lossPercentage: float, options: list,
                 marginEnabled: bool = True, startDate: datetime = None, endDate: datetime = None):
        self.startingBalance = startingBalance
        self.balance = startingBalance
        self.coin = 0
        self.coinOwed = 0
        self.commissionsPaid = 0
        self.trades = []
        self.currentPrice = None
        self.transactionFeePercentage = 0.001
        self.profit = 0
        self.marginEnabled = marginEnabled

        self.data = data
        self.interval = self.get_interval()
        self.lossStrategy = lossStrategy
        self.lossPercentage = lossPercentage / 100
        self.options = options
        self.validate_options()
        self.minPeriod = self.get_min_option_period()
        self.trend = None

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

    def validate_options(self):
        """
        Validates options provided. If the list of options provided does not contain all options, an error is raised.
        """
        for option in self.options:
            if type(option) != Option:
                raise TypeError(f"'{option}' is not a valid option type.")

    def get_start_date_index(self, startDate):
        if startDate:
            startDateIndex = self.find_date_index(startDate)
            if startDateIndex == -1:
                raise IndexError("Date not found.")
            elif startDateIndex < self.minPeriod:
                raise IndexError(f"Start requires more periods than minimum period amount {self.minPeriod}")
            else:
                return startDateIndex
        else:
            return self.minPeriod

    def get_end_date_index(self, endDate):
        if endDate:
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
        for option in self.options:
            if option.finalBound > minimum:
                minimum = option.finalBound
            if option.initialBound > minimum:
                minimum = option.initialBound
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
        if average == 'sma':
            return self.get_sma(data, prices, parameter)
        elif average == 'ema':
            return self.get_ema(data, prices, parameter)
        elif average == 'wma':
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
        for option in self.options:
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

    def find_date_index(self, datetimeObject):
        for data in self.data:
            if parser.parse(data['date_utc']) == datetimeObject:
                return self.data.index(data)
        return -1

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

    def exit_long(self, msg):
        """
        Exits long position.
        :param msg: Message that specifies why it exited long.
        """
        coin = self.coin
        transactionFee = self.currentPrice * coin * self.transactionFeePercentage
        self.commissionsPaid += transactionFee
        self.inLongPosition = False
        self.previousPosition = LONG
        self.balance += coin * self.currentPrice - transactionFee
        self.coin -= coin
        self.add_trade(msg)

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

    def exit_short(self, msg):
        """
        Exits short position.
        :param msg: Message that specifies why it exited short.
        """
        coin = self.coinOwed
        self.coinOwed -= coin
        self.inShortPosition = False
        self.previousPosition = SHORT
        loss = self.currentPrice * coin * (1 + self.transactionFeePercentage)
        self.balance -= loss
        self.add_trade(msg)

        if self.coinOwed == 0:
            self.sellShortPrice = None
            self.shortTrailingPrice = None

    def get_short_stop_loss(self) -> float:
        """
        Returns stop loss for short position.
        :return: Stop loss for short position.
        """
        if self.shortTrailingPrice is None:
            self.shortTrailingPrice = self.currentPrice
            self.sellShortPrice = self.shortTrailingPrice
        if self.lossStrategy == TRAILING_LOSS:  # This means we use trailing loss.
            return self.shortTrailingPrice * (1 + self.lossPercentage)
        elif self.lossStrategy == STOP_LOSS:  # This means we use the basic stop loss.
            return self.sellShortPrice * (1 + self.lossPercentage)

    def get_long_stop_loss(self) -> float:
        """
        Returns stop loss for long position.
        :return: Stop loss for long position.
        """
        if self.longTrailingPrice is None:
            self.longTrailingPrice = self.currentPrice
            self.buyLongPrice = self.longTrailingPrice
        if self.lossStrategy == TRAILING_LOSS:  # This means we use trailing loss.
            return self.longTrailingPrice * (1 - self.lossPercentage)
        elif self.lossStrategy == STOP_LOSS:  # This means we use the basic stop loss.
            return self.buyLongPrice * (1 - self.lossPercentage)

    def get_stop_loss(self):
        """
        Returns stop loss value.
        :return: Stop loss value.
        """
        if self.inShortPosition:  # If we are in a short position
            return self.get_short_stop_loss()
        elif self.inLongPosition:  # If we are in a long position
            return self.get_long_stop_loss()
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
        period1 = parser.parse(self.data[0]['date_utc'])
        period2 = parser.parse(self.data[1]['date_utc'])
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

    @staticmethod
    def get_sma(data: list, prices: int, parameter: str, round_value=True) -> float:
        data = data[0: prices]
        sma = sum([period[parameter] for period in data]) / prices
        if round_value:
            return round(sma, 2)
        return sma

    @staticmethod
    def get_wma(data: list, prices: int, parameter: str, round_value=True) -> float:
        total = data[0][parameter] * prices  # Current total is first data period multiplied by prices.
        data = data[1: prices]  # Data now does not include the first shift period.

        index = 0
        for x in range(prices - 1, 0, -1):
            total += x * data[index][parameter]
            index += 1

        divisor = prices * (prices + 1) / 2
        wma = total / divisor
        if round_value:
            return round(wma, 2)
        return wma

    def get_ema(self, data: list, prices: int, parameter: str, sma_prices: int = 5, round_value=True) -> float:
        if sma_prices <= 0:
            raise ValueError("Initial amount of SMA values for initial EMA must be greater than 0.")
        elif sma_prices > len(data):
            sma_prices = len(data) - 1

        ema = self.get_sma(data, sma_prices, parameter, round_value=False)
        multiplier = 2 / (prices + 1)

        for day in range(len(data) - sma_prices):
            current_index = len(data) - sma_prices - day - 1
            current_price = data[current_index][parameter]
            ema = current_price * multiplier + ema * (1 - multiplier)

        if round_value:
            return round(ema, 2)
        return ema

    def add_trade(self, message):
        """
        Adds a trade to list of trades
        :param message: Message used for conducting trade.
        """
        self.trades.append({
            'date': self.currentPeriod['date_utc'],
            'action': message
        })

    def main_logic(self):
        """
        Main logic that dictates how backtest works. It checks for stop losses and then moving averages to check for
        upcoming trends.
        """
        if self.inShortPosition:  # This means we are in short position
            if self.currentPrice > self.get_stop_loss():  # If current price is greater, then exit trade.
                # print(f"{self.currentPeriod['date_utc']}: Stop loss causing exit short.")
                self.exit_short('Exited short because of a stop loss.')

            elif self.trend == BULLISH:
                self.exit_short('Exited short because a cross was detected.')
                self.go_long('Entered long because a cross was detected.')

        elif self.inLongPosition:  # This means we are in long position
            if self.currentPrice < self.get_stop_loss():  # If current price is lower, then exit trade.
                # print(f"{self.currentPeriod['date_utc']}: Stop loss causing exit long.")
                self.exit_long('Exited long because of a stop loss.')

            elif self.trend == BEARISH:
                self.exit_long('Exited long because a cross was detected.')
                if self.marginEnabled:
                    self.go_short('Entered short because a cross was detected.')

        else:  # This means we are in neither position
            if self.trend == BULLISH and self.previousPosition is not LONG:
                self.go_long('Entered long because a cross was detected.')
            elif self.marginEnabled and self.trend == BEARISH and self.previousPosition is not SHORT:
                self.go_short('Entered short because a cross was detected.')
            elif self.trend == BEARISH:
                self.previousPosition = None

    def moving_average_test(self):
        """
        Performs a moving average test with given configurations.
        """
        self.movingAverageTestStartTime = time.time()
        seenData = self.data[:self.minPeriod][::-1]  # Start from minimum previous period data.
        for period in self.data[self.startDateIndex:self.endDateIndex]:
            seenData.insert(0, period)
            self.currentPeriod = period
            self.currentPrice = period['open']
            self.main_logic()
            self.check_trend(seenData)

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

    def find_optimal_moving_average(self):
        """
        Runs extensive moving average tests and returns the one with best return percentages.
        :return: A dictionary of values for the test.
        """
        pass

    def print_options(self):
        """
        Prints out options provided in configuration.
        """
        # print("Options:")
        for index, option in enumerate(self.options):
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
        print(f'\tInterval: {self.interval}')
        print(f'\tMargin Enabled: {self.marginEnabled}')
        print(f"\tStarting Balance: ${self.startingBalance}")
        self.print_options()
        # print("Loss options:")
        print(f'\tStop Loss Percentage: {round(self.lossPercentage * 100, 2)}%')
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
        print(f'\tElapsed: {round(self.movingAverageTestEndTime - self.movingAverageTestStartTime, 2)} seconds')
        print(f'\tStart Period: {self.data[self.startDateIndex]["date_utc"]}')
        print(f"\tEnd Period: {self.currentPeriod['date_utc']}")
        print(f'\tStarting balance: ${round(self.startingBalance, 2)}')
        print(f'\tNet: ${round(self.get_net(), 2)}')
        print(f'\tCommissions paid: ${round(self.commissionsPaid, 2)}')
        print(f'\tTrades made: {len(self.trades)}')
        difference = round(self.get_net() - self.startingBalance, 2)
        if difference > 0:
            print(f'\tProfit: ${difference}')
            print(f'\tProfit Percentage: {round(self.get_net() / self.startingBalance * 100, 2)}%')
        elif difference < 0:
            print(f'\tLoss: ${-difference}')
            print(f'\tLoss Percentage: {round(100 - self.get_net() / self.startingBalance * 100, 2)}%')
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

    def print_trades(self, stdout):
        """
        Prints out all the trades conducted so far.
        """
        previous_stdout = sys.stdout
        if stdout is not None:  # Temporarily redirects output to stdout provided.
            sys.stdout = stdout

        print("\nTrades made:")
        for trade in self.trades:
            print(f'\t{trade}')

        sys.stdout = previous_stdout  # revert stdout back to normal

    def write_results(self):
        currentPath = os.getcwd()
        backtestResultsFolder = 'Backtest Results'
        resultFile = f'backtest_results_{"_".join(self.interval.lower().split())}.txt'
        os.chdir('../')

        if not os.path.exists(backtestResultsFolder):
            os.mkdir(backtestResultsFolder)
        os.chdir(backtestResultsFolder)

        with open(resultFile, 'w') as f:
            self.print_configuration_parameters(f)
            self.print_backtest_results(f)
            self.print_trades(f)
        filePath = os.path.join(os.getcwd(), resultFile)
        print(f'Backtest results saved successfully to {filePath}.')
        os.chdir(currentPath)


path = r'C:\Users\Mihir Shrestha\PycharmProjects\CryptoAlgo\CSV\BTCUSDT_data_15m.csv'
testData = load_from_csv(path)
opt = [Option('sma', 'high', 10, 20), Option('sma', 'low', 10, 20)]
a = Backtester(data=testData, startingBalance=1000, lossStrategy=STOP_LOSS, lossPercentage=2, options=opt,
               marginEnabled=True, startDate=datetime(2020, 1, 1))
a.moving_average_test()
# a.print_stats()
a.write_results()
