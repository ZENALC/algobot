import os
import sys

from typing import Dict, Union, List, Any
from dateutil import parser
from datetime import datetime, timedelta
from helpers import get_ups_and_downs, get_label_string, set_up_strategies, get_interval_minutes
from enums import BEARISH, BULLISH, LONG, SHORT, TRAILING, STOP
from strategies.strategy import Strategy
from algorithms import get_sma, get_wma, get_ema


class Backtester:
    def __init__(self,
                 startingBalance: float,
                 data: list,
                 lossStrategy: int,
                 lossPercentage: float,
                 takeProfitType: int,
                 takeProfitPercentage: float,
                 strategies: list,
                 strategyInterval: Union[str, None] = None,
                 symbol: str = None,
                 marginEnabled: bool = True,
                 startDate: datetime = None,
                 endDate: datetime = None,
                 precision: int = 2,
                 outputTrades: bool = True):
        self.startingBalance = startingBalance
        self.symbol = symbol
        self.balance = startingBalance
        self.coin = 0
        self.coinOwed = 0
        self.commissionsPaid = 0
        self.transactionFeePercentage = 0.001
        self.trades = []
        self.marginEnabled = marginEnabled
        self.precision = precision
        self.lossStrategy = lossStrategy
        self.lossPercentageDecimal = lossPercentage / 100
        self.outputTrades: bool = outputTrades  # Boolean that'll determine whether trades are outputted to file or not.

        self.data = data
        self.check_data()
        self.interval = self.get_interval()
        self.intervalMinutes = get_interval_minutes(self.interval)

        self.previousStopLoss = None
        self.initialStopLossCounter = 0
        self.stopLossCounter = 0
        self.stopLossExit = False

        self.takeProfitType = takeProfitType
        self.takeProfitPercentageDecimal = takeProfitPercentage / 100

        self.currentPrice = None
        self.buyLongPrice = None
        self.sellShortPrice = None
        self.longTrailingPrice = None
        self.shortTrailingPrice = None
        self.profit = 0

        self.startTime = None
        self.endTime = None
        self.inLongPosition = False
        self.inShortPosition = False
        self.previousPosition = None
        self.currentPeriod = None
        self.minPeriod = 1
        self.startDateIndex = self.get_start_date_index(startDate)
        self.endDateIndex = self.get_end_date_index(endDate)

        self.strategyInterval = self.interval if strategyInterval is None else strategyInterval
        self.strategyIntervalMinutes = get_interval_minutes(self.strategyInterval)
        self.intervalGapMinutes = self.strategyIntervalMinutes - self.intervalMinutes
        self.intervalGapMultiplier = self.strategyIntervalMinutes // self.intervalMinutes
        if self.intervalMinutes > self.strategyIntervalMinutes:
            raise RuntimeError("Your strategy interval can't be smaller than the data interval.")

        self.ema_dict = {}
        self.rsi_dictionary = {}
        self.strategies: Dict[str, Strategy] = {}
        set_up_strategies(self, strategies)

    @staticmethod
    def get_gap_data(data: List[dict], gap: int) -> Dict[str, Any]:
        """
        Returns gap interval data from data list provided.
        :param data: Data to get total interval data from.
        :param gap: Amount of minutes to collect data of and merge to one in a dictionary.
        :return: Dictionary of interval data of gap minutes.
        """
        return {
            'date_utc': data[0]['date_utc'] + timedelta(minutes=1),
            'open': data[-gap + 1]['open'],
            'high': max([d['high'] for d in data]),
            'low': min([d['low'] for d in data]),
            'close': data[0]['close'],
        }

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

    def convert_all_date_to_datetime(self):
        """
        Converts all available dates to datetime objects.
        """
        for data in self.data:
            data['date_utc'] = parser.parse(data['date_utc'])

    def find_date_index(self, targetDate: datetime) -> int:
        """
        Finds index of date from targetDate if it exists in data loaded.
        :param targetDate: Object to compare date-time with.
        :return: Index from self.data if found, else -1.
        """
        for data in self.data:
            if data['date_utc'].date() == targetDate:
                return self.data.index(data)
        return -1

    def get_start_date_index(self, startDate: datetime) -> int:
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
                raise IndexError(f"Invalid start date. Please select a date that's {self.minPeriod} periods away.")
            else:
                return startDateIndex
        else:
            return self.minPeriod

    def get_end_date_index(self, endDate: datetime):
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
                raise IndexError(f"Invalid end date. Please make sure you have at least {self.minPeriod} periods.")
            if endDateIndex < self.startDateIndex:
                raise IndexError("End date cannot be earlier than start date.")
            else:
                return endDateIndex
        else:
            return -1

    def buy_long(self, message: str):
        """
        Executes long position.
        :param message: Message that specifies why it entered long.
        """
        usd = self.balance
        transactionFee = self.transactionFeePercentage * usd
        self.commissionsPaid += transactionFee
        self.inLongPosition = True
        self.coin += (usd - transactionFee) / self.currentPrice
        self.balance -= usd
        self.buyLongPrice = self.longTrailingPrice = self.currentPrice
        self.add_trade(message)

    def sell_long(self, message: str, stopLossExit: bool = False):
        """
        Exits long position.
        :param stopLossExit: Boolean that'll determine whether a position was exited from a stop loss.
        :param message: Message that specifies why it exited long.
        """
        coin = self.coin
        transactionFee = self.currentPrice * coin * self.transactionFeePercentage
        self.commissionsPaid += transactionFee
        self.inLongPosition = False
        self.previousPosition = LONG
        self.coin -= coin
        self.balance += coin * self.currentPrice - transactionFee
        self.buyLongPrice = self.longTrailingPrice = None
        self.add_trade(message, stopLossExit=stopLossExit)

    def sell_short(self, message: str):
        """
        Executes short position.
        :param message: Message that specifies why it entered short.
        """
        transactionFee = self.balance * self.transactionFeePercentage
        coin = (self.balance - transactionFee) / self.currentPrice
        self.commissionsPaid += transactionFee
        self.inShortPosition = True
        self.coinOwed += coin
        self.balance += self.currentPrice * coin - transactionFee
        self.sellShortPrice = self.shortTrailingPrice = self.currentPrice
        self.add_trade(message)

    def buy_short(self, message: str, stopLossExit: bool = False):
        """
        Exits short position.
        :param stopLossExit: Boolean that'll determine whether a position was exited from a stop loss.
        :param message: Message that specifies why it exited short.
        """
        transactionFee = self.coinOwed * self.currentPrice * self.transactionFeePercentage
        coin = self.coinOwed
        self.commissionsPaid += transactionFee
        self.inShortPosition = False
        self.previousPosition = SHORT
        self.coinOwed -= coin
        self.balance -= self.currentPrice * coin + transactionFee
        self.sellShortPrice = self.shortTrailingPrice = None
        self.add_trade(message, stopLossExit=stopLossExit)

    def add_trade(self, message: str, stopLossExit: bool = False):
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

    def set_stop_loss_counter(self, counter: int):
        """
        Sets stop loss equal to the counter provided.
        :param counter: Value to set counter to.
        """
        self.stopLossCounter = self.initialStopLossCounter = counter

    def reset_smart_stop_loss(self):
        """
        Resets smart stop loss and sets it equal to initial stop loss counter.
        """
        self.stopLossCounter = self.initialStopLossCounter

    def get_short_stop_loss(self) -> float:
        """
        Returns stop loss for short position.
        :return: Stop loss for short position.
        """
        if self.lossStrategy == TRAILING:
            return self.shortTrailingPrice * (1 + self.lossPercentageDecimal)
        elif self.lossStrategy == STOP:
            return self.sellShortPrice * (1 + self.lossPercentageDecimal)
        else:
            raise ValueError("Invalid type of loss strategy provided.")

    def get_long_stop_loss(self) -> float:
        """
        Returns stop loss for long position.
        :return: Stop loss for long position.
        """
        if self.lossStrategy == TRAILING:
            return self.longTrailingPrice * (1 - self.lossPercentageDecimal)
        elif self.lossStrategy == STOP:
            return self.buyLongPrice * (1 - self.lossPercentageDecimal)
        else:
            raise ValueError("Invalid type of loss strategy provided.")

    def get_stop_loss(self) -> Union[float, None]:
        """
        Returns stop loss value.
        :return: Stop loss value.
        """
        if self.inShortPosition:
            self.previousStopLoss = self.get_short_stop_loss()
            return self.previousStopLoss
        elif self.inLongPosition:
            self.previousStopLoss = self.get_long_stop_loss()
            return self.previousStopLoss
        else:
            return None

    def get_take_profit(self) -> Union[float, None]:
        """
        Returns price at which position will be exited to secure profits.
        :return: Price at which to exit position.
        """
        if self.inShortPosition:
            return self.sellShortPrice * (1 - self.takeProfitPercentageDecimal)
        elif self.inLongPosition:
            return self.buyLongPrice * (1 + self.takeProfitPercentageDecimal)
        else:
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
        if seconds < 3600:  # This will assume the interval is in minutes.
            minutes = seconds / 60
            result = f'{int(minutes)} Minute'
            if minutes > 1:
                result += 's'
        elif seconds < 86400:  # This will assume the interval is in hours.
            hours = seconds / 3600
            result = f'{int(hours)} Hour'
            if hours > 1:
                result += 's'
        else:  # This will assume the interval is in days.
            days = seconds / 86400
            result = f'{int(days)} Day'
            if days > 1:
                result += 's'
        return result

    def get_trend(self) -> Union[int, None]:
        """
        Returns trend based on the strategies provided.
        :return: Integer in the form of an enum.
        """
        trends = [strategy.trend for strategy in self.strategies.values()]

        if len(trends) == 0:
            return None

        if all(trend == BEARISH for trend in trends):
            return BEARISH
        elif all(trend == BULLISH for trend in trends):
            return BULLISH
        else:
            return None

    def get_moving_average(self, data: list, average: str, prices: int, parameter: str, round_value=False) -> float:
        """
        Returns moving average of given parameters.
        :param round_value: Boolean to round final value or not.
        :param data: Data to get moving averages from.
        :param average: Type of average to retrieve, i.e. -> SMA, WMA, EMA
        :param prices: Amount of prices to get moving averages of.
        :param parameter: Parameter to use to get moving average, i.e. - HIGH, LOW, CLOSE, OPEN
        :return: Moving average.
        """
        if average.lower() == 'sma':
            return self.get_sma(data, prices, parameter, round_value=round_value)
        elif average.lower() == 'ema':
            return self.get_ema(data, prices, parameter, round_value=round_value)
        elif average.lower() == 'wma':
            return self.get_wma(data, prices, parameter, round_value=round_value)
        else:
            raise ValueError('Invalid average provided.')

    def get_sma(self, data: list, prices: int, parameter: str, round_value=True) -> float:
        data = data[0: prices]
        sma = get_sma(data, prices, parameter)

        return round(sma, self.precision) if round_value else sma

    def get_wma(self, data: list, prices: int, parameter: str, round_value=True) -> float:
        data = data[0: prices]
        wma = get_wma(data, prices, parameter)

        return round(wma, self.precision) if round_value else wma

    def get_ema(self, data: list, prices: int, parameter: str, sma_prices: int = 5, round_value=True) -> float:
        if sma_prices <= 0:
            raise ValueError("Initial amount of SMA values for initial EMA must be greater than 0.")
        elif sma_prices > len(data):
            sma_prices = len(data) - 1

        ema, self.ema_dict = get_ema(data, prices, parameter, sma_prices, self.ema_dict)
        return round(ema, self.precision) if round_value else ema

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
            rsi = self.rsi_dictionary[prices]['close'][-shift][0]
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
            self.rsi_dictionary[prices]['close'].append((rsi, up, down))
        else:
            start = 500 + prices + shift if len(data) > 500 + prices + shift else len(data)
            data = data[shift:start]
            data = data[:]
            data.reverse()

            ups, downs = get_ups_and_downs(data=data, parameter=parameter)
            rsi = self.helper_get_ema(ups, downs, prices)

        return round(rsi, self.precision) if round_value else rsi

    def main_logic(self):
        """
        Main logic that dictates how backtest works. It checks for stop losses and then moving averages to check for
        upcoming trends.
        """
        trend = self.get_trend()
        if self.inShortPosition:
            if self.currentPrice > self.get_stop_loss():
                self.buy_short('Exited short because a stop loss was triggered.', stopLossExit=True)
            elif self.currentPrice <= self.get_take_profit():
                self.buy_short("Exited short because of take profit.")
            elif trend == BULLISH:
                self.buy_short(f'Exited short because a bullish trend was detected.')
                self.buy_long(f'Entered long because a bullish trend was detected.')
        elif self.inLongPosition:
            if self.currentPrice < self.get_stop_loss():
                self.sell_long('Exited long because a stop loss was triggered.', stopLossExit=True)
            elif self.currentPrice >= self.get_take_profit():
                self.sell_long("Exited long because of take profit.")
            elif trend == BEARISH:
                self.sell_long('Exited long because a bearish trend was detected.')
                if self.marginEnabled:
                    self.sell_short('Entered short because a bearish trend was detected.')
        else:
            if not self.marginEnabled and self.previousStopLoss is not None and self.currentPrice is not None:
                if self.previousStopLoss < self.currentPrice:
                    self.stopLossExit = False  # Hotfix for margin-disabled backtests.

            if trend == BULLISH and (self.previousPosition != LONG or not self.stopLossExit):
                self.buy_long('Entered long because a bullish trend was detected.')
                self.reset_smart_stop_loss()
            elif self.marginEnabled and trend == BEARISH and self.previousPosition != SHORT:
                self.sell_short('Entered short because a bearish trend was detected.')
                self.reset_smart_stop_loss()
            else:
                if self.previousPosition == LONG and self.stopLossExit:
                    if self.currentPrice > self.previousStopLoss and self.stopLossCounter > 0:
                        self.buy_long("Reentered long because of smart stop loss.")
                        self.stopLossCounter -= 1
                elif self.previousPosition == SHORT and self.stopLossExit:
                    if self.currentPrice < self.previousStopLoss and self.stopLossCounter > 0:
                        self.sell_short("Reentered short because of smart stop loss.")
                        self.stopLossCounter -= 1

    def print_options(self):
        """
        Prints out options provided in configuration.
        """
        if 'movingAverage' not in self.strategies:
            return

        print("\tMoving Averages Options:")
        for index, option in enumerate(self.strategies['movingAverage'].get_params()):
            print(f'\t\tOption {index + 1}) {option.movingAverage.upper()}{option.initialBound, option.finalBound}'
                  f' - {option.parameter}')

    def print_strategies(self):
        for strategyName, strategy in self.strategies.items():
            print(f'\t{get_label_string(strategyName)}: {strategy.get_params()}')

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
        print(f'\tTake Profit Percentage: {round(self.takeProfitPercentageDecimal * 100, 2)}%')
        print(f'\tStop Loss Percentage: {round(self.lossPercentageDecimal * 100, 2)}%')
        if self.lossStrategy == TRAILING:
            print(f"\tLoss Strategy: Trailing")
        else:
            print("\tLoss Strategy: Stop")
        self.print_strategies()

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
        print(f'\tElapsed: {round(self.endTime - self.startTime, 2)} seconds')
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

            if self.outputTrades:
                self.print_trades(f)

        filePath = os.path.join(os.getcwd(), resultFile)

        os.chdir(currentPath)
        return filePath
