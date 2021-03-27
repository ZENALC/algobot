import os
import sys
import time
from datetime import datetime, timedelta
from itertools import product
from typing import Dict, Union

from dateutil import parser

from algobot.algorithms import get_ema, get_sma, get_wma
from algobot.enums import BEARISH, BULLISH, LONG, SHORT, STOP, TRAILING
from algobot.helpers import (convert_all_dates_to_datetime,
                             convert_small_interval, get_interval_minutes,
                             get_label_string, get_ups_and_downs,
                             set_up_strategies)
from algobot.traders.trader import Trader
from algobot.typeHints import DATA_TYPE, DICT_TYPE


class Backtester(Trader):
    def __init__(self,
                 startingBalance: float,
                 data: list,
                 strategies: list,
                 strategyInterval: Union[str, None] = None,
                 symbol: str = None,
                 marginEnabled: bool = True,
                 startDate: datetime = None,
                 endDate: datetime = None,
                 precision: int = 4,
                 outputTrades: bool = True):
        super().__init__(symbol=symbol, precision=precision, startingBalance=startingBalance)
        self.commissionsPaid = 0
        self.marginEnabled = marginEnabled
        self.outputTrades: bool = outputTrades  # Boolean that'll determine whether trades are outputted to file or not.

        convert_all_dates_to_datetime(data)
        self.data = data
        self.check_data()
        self.interval = self.get_interval()
        self.intervalMinutes = get_interval_minutes(self.interval)
        self.profit = 0

        self.currentPeriod = None
        self.pastActivity = []  # We'll add previous data here when hovering through graph in GUI.

        if len(strategyInterval.split()) == 1:
            strategyInterval = convert_small_interval(strategyInterval)

        self.strategyInterval = self.interval if strategyInterval is None else strategyInterval
        self.strategyIntervalMinutes = get_interval_minutes(self.strategyInterval)
        self.intervalGapMinutes = self.strategyIntervalMinutes - self.intervalMinutes
        self.intervalGapMultiplier = self.strategyIntervalMinutes // self.intervalMinutes
        if self.intervalMinutes > self.strategyIntervalMinutes:
            raise RuntimeError("Your strategy interval can't be smaller than the data interval.")

        self.ema_dict = {}
        self.rsi_dictionary = {}
        set_up_strategies(self, strategies)

        self.startDateIndex = self.get_start_index(startDate)
        self.endDateIndex = self.get_end_index(endDate)

    def get_gap_data(self, data: DATA_TYPE, check: bool = True) -> DICT_TYPE:
        """
        Returns gap interval data from data list provided.
        :param check: Check values to match with strategy interval minutes.
        :param data: Data to get total interval data from.
        :return: Dictionary of interval data of gap minutes.
        """
        if check and len(data) != self.strategyIntervalMinutes:
            raise AssertionError(f"Expected {self.strategyIntervalMinutes} data length. Received {len(data)} data.")

        return {
            'date_utc': data[0]['date_utc'],
            'open': data[0]['open'],
            'high': max([d['high'] for d in data]),
            'low': min([d['low'] for d in data]),
            'close': data[-1]['close'],
        }

    def check_data(self):
        """
        Checks data sorting. If descending, it reverses data, so we can mimic backtest as if we are starting from the
        beginning.
        """
        firstDate = self.data[0]['date_utc']
        lastDate = self.data[-1]['date_utc']

        if firstDate > lastDate:
            self.data = self.data[::-1]

    def find_date_index(self, targetDate: datetime.date, starting: bool = True) -> int:
        """
        Finds starting or ending index of date from targetDate if it exists in data loaded.
        :param starting: Boolean if true will find the first found index. If used for end index, set to False.
        :param targetDate: Object to compare date-time with.
        :return: Index from self.data if found, else -1.
        """
        if type(targetDate) == datetime:
            targetDate = targetDate.date()

        if starting:
            iterator = list(enumerate(self.data))
        else:
            iterator = reversed(list(enumerate(self.data)))

        for index, data in iterator:
            if data['date_utc'].date() == targetDate:
                return index
        return -1

    def get_start_index(self, startDate: datetime.date) -> int:
        """
        Returns index of start date based on startDate argument.
        :param startDate: Datetime object to compare index with.
        :return: Index of start date.
        """
        if startDate:
            startDateIndex = self.find_date_index(startDate)
            if startDateIndex == -1:
                raise IndexError("Date not found.")
            else:
                return startDateIndex
        else:
            return 0

    def get_end_index(self, endDate: datetime.date) -> int:
        """
        Returns index of end date based on endDate argument.
        :param endDate: Datetime object to compare index with.
        :return: Index of end date.
        """
        if endDate:
            endDateIndex = self.find_date_index(endDate, starting=False)
            if endDateIndex == -1:
                raise IndexError("Date not found.")
            elif endDateIndex < 1:
                raise IndexError("You need at least one data period.")
            elif endDateIndex <= self.startDateIndex:
                raise IndexError("Ending date index cannot be less than or equal to start date index.")
            else:
                return endDateIndex
        else:
            return len(self.data) - 1

    def buy_long(self, message: str):
        """
        Executes long position.
        :param message: Message that specifies why it entered long.
        """
        usd = self.balance
        transactionFee = self.transactionFeePercentage * usd
        self.commissionsPaid += transactionFee
        self.currentPosition = LONG
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
        self.currentPosition = None
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
        self.currentPosition = SHORT
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
        self.currentPosition = None
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

    def reset_trades(self):
        """
        Clears trades list.
        """
        self.trades = []

    def set_indexed_current_price_and_period(self, index: int):
        """
        Sets the current backtester price and period based on index provided.
        :param index: Index of data to set as current period.
        """
        self.currentPeriod = self.data[index]
        self.currentPrice = self.data[index]['open']

    def set_priced_current_price_and_period(self, price):
        """
        Auxiliary function to set current period and price to price provided.
        :param price: Price to set to current period and price.
        """
        self.currentPeriod = {
            'date_utc': None,
            'open': price,
            'close': price,
            'high': price,
            'low': price
        }
        self.currentPrice = price

    def start_backtest(self, thread=None):
        """
        Main function to start a backtest.
        :param thread: Thread to pass to other functions to emit signals to.
        """
        testLength = self.endDateIndex - self.startDateIndex
        divisor = testLength // 100
        if divisor < 1:
            divisor = 1

        if thread:
            thread.signals.updateGraphLimits.emit(testLength // divisor + 1)

        self.startingTime = time.time()
        if len(self.strategies) == 0:
            self.simulate_hold(testLength, divisor, thread)
        else:
            self.strategy_backtest(testLength, divisor, thread)
        self.endingTime = time.time()

    def exit_backtest(self, index: int = None):
        """
        Ends a backtest by exiting out of a position if needed.
        """
        if index is None:
            index = self.endDateIndex

        self.currentPeriod = self.data[index]
        self.currentPrice = self.currentPeriod['close']

        if self.currentPosition == SHORT:
            self.buy_short("Exited short position because backtest ended.")
        elif self.currentPosition == LONG:
            self.sell_long("Exited long position because backtest ended.")

    def simulate_hold(self, testLength: int, divisor: int, thread=None):
        """
        Simulate a long hold position if no strategies are provided.
        :param divisor: Divisor where when remainder of test length and divisor is 0, a signal is emitted to GUI.
        :param testLength: Length of backtest.
        :param thread: Thread to emit signals back to if provided.
        """
        for index in range(self.startDateIndex, self.endDateIndex, divisor):
            if thread and not thread.running:
                raise RuntimeError("Backtest was canceled.")

            self.currentPeriod = self.data[index]
            self.currentPrice = self.currentPeriod['open']

            if self.currentPosition != LONG:
                self.buy_long("Entered long to simulate a hold.")

            thread.signals.activity.emit(thread.get_activity_dictionary(self.currentPeriod, index, testLength))

        self.exit_backtest()

    def strategy_backtest(self, testLength: int, divisor: int, thread=None):
        """
        Perform a backtest with provided strategies to backtester object.
        :param divisor: Divisor where when remainder of test length and divisor is 0, a signal is emitted to GUI.
        :param testLength: Length of backtest.
        :param thread: Optional thread that called this function that'll be used for emitting signals.
        """
        seenData = self.data[:self.startDateIndex]
        strategyData = seenData if self.strategyIntervalMinutes == self.intervalMinutes else []
        nextInsertion = self.data[self.startDateIndex]['date_utc'] + timedelta(minutes=self.strategyIntervalMinutes)
        index = None

        for index in range(self.startDateIndex, self.endDateIndex + 1):
            if thread and not thread.running:
                raise RuntimeError("Backtest was canceled.")

            self.set_indexed_current_price_and_period(index)
            seenData.append(self.currentPeriod)

            self.main_logic()
            if self.get_net() < 0.5:
                thread.signals.updateGraphLimits.emit(index // divisor + 1)
                thread.signals.message.emit("Backtester ran out of money. Try changing your strategy or date interval.")
                break

            if strategyData is seenData:
                if len(strategyData) >= self.minPeriod:
                    for strategy in self.strategies.values():
                        strategy.get_trend(strategyData)
            else:
                if len(strategyData) + 1 >= self.minPeriod:
                    strategyData.append(self.currentPeriod)
                    for strategy in self.strategies.values():
                        strategy.get_trend(strategyData)
                    strategyData.pop()

            if seenData is not strategyData and self.currentPeriod['date_utc'] >= nextInsertion:
                nextInsertion = self.currentPeriod['date_utc'] + timedelta(minutes=self.strategyIntervalMinutes)
                gapData = self.get_gap_data(seenData[-self.intervalGapMultiplier - 1: -1])
                strategyData.append(gapData)

            if thread and index % divisor == 0:
                thread.signals.activity.emit(thread.get_activity_dictionary(self.currentPeriod, index, testLength))

        self.exit_backtest(index)

    @staticmethod
    def get_all_permutations(combos: dict):
        """
        Returns a list of setting permutations from combos provided.
        :param combos: Combos with ranges for the permutations.
        :return: List of all permutations.
        """
        for key, value_range in combos.items():
            if type(value_range) == tuple:
                continue
            elif type(value_range) == list:
                temp = [x for x in range(value_range[0], value_range[1] + 1, value_range[2])]
                combos[key] = temp
            else:
                raise ValueError("Invalid type of value provided to combos. Make sure to provide a tuple or list.")

        return [dict(zip(combos, v)) for v in product(*combos.values())]

    def optimizer(self, combos: Dict, thread=None):
        """
        This function will run a brute-force optimization test to figure out the best inputs.
        """
        settings_list = self.get_all_permutations(combos)

        for settings in settings_list:
            self.apply_settings(settings)
            self.start_backtest(thread)

    def apply_settings(self, settings: dict):
        self.takeProfitType = settings['takeProfitType']
        self.takeProfitPercentageDecimal = settings['takeProfitPercentage'] / 100
        self.lossStrategy = settings['lossType']
        self.lossPercentageDecimal = settings['lossPercentage'] / 100

    def restore(self):
        pass

    def handle_trailing_prices(self):
        """
        Handles trailing prices based on the current price.
        """
        if self.longTrailingPrice is not None and self.currentPrice > self.longTrailingPrice:
            self.longTrailingPrice = self.currentPrice
        if self.shortTrailingPrice is not None and self.currentPrice < self.shortTrailingPrice:
            self.shortTrailingPrice = self.currentPrice

    def _get_short_stop_loss(self) -> Union[float, None]:
        """
        Returns stop loss for short position.
        :return: Stop loss for short position.
        """
        if self.lossStrategy == TRAILING:
            return self.shortTrailingPrice * (1 + self.lossPercentageDecimal)
        elif self.lossStrategy == STOP:
            return self.sellShortPrice * (1 + self.lossPercentageDecimal)
        elif self.lossStrategy is None:
            return None
        else:
            raise ValueError("Invalid type of loss strategy provided.")

    def _get_long_stop_loss(self) -> Union[float, None]:
        """
        Returns stop loss for long position.
        :return: Stop loss for long position.
        """
        if self.lossStrategy == TRAILING:
            return self.longTrailingPrice * (1 - self.lossPercentageDecimal)
        elif self.lossStrategy == STOP:
            return self.buyLongPrice * (1 - self.lossPercentageDecimal)
        elif self.lossStrategy is None:
            return None
        else:
            raise ValueError("Invalid type of loss strategy provided.")

    def get_stop_loss(self) -> Union[float, None]:
        """
        Returns stop loss value.
        :return: Stop loss value.
        """
        self.handle_trailing_prices()
        if self.currentPosition == SHORT:
            self.previousStopLoss = self._get_short_stop_loss()
            return self.previousStopLoss
        elif self.currentPosition == LONG:
            self.previousStopLoss = self._get_long_stop_loss()
            return self.previousStopLoss
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
        return self.get_cumulative_trend(trends)

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

    def get_sma(self, data: list, prices: int, parameter: str, round_value: bool = True) -> float:
        data = data[len(data) - prices:]
        sma = get_sma(data, prices, parameter)
        return round(sma, self.precision) if round_value else sma

    def get_wma(self, data: list, prices: int, parameter: str, round_value: bool = True) -> float:
        data = data[len(data) - prices:]
        wma = get_wma(data, prices, parameter, desc=False)
        return round(wma, self.precision) if round_value else wma

    def get_ema(self, data: list, prices: int, parameter: str, sma_prices: int = 5, round_value: bool = True) -> float:
        if sma_prices <= 0:
            raise ValueError("Initial amount of SMA values for initial EMA must be greater than 0.")
        elif sma_prices > len(data):
            sma_prices = len(data) - 1

        ema, self.ema_dict = get_ema(data, prices, parameter, sma_prices, self.ema_dict, desc=False)
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
    def get_rsi(self, data: list, prices: int, parameter: str = 'close', shift: int = 0,
                round_value: bool = False) -> float:
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
            difference = data[-1][parameter] - data[-2][parameter]
            if difference > 0:
                up = difference * alpha + self.rsi_dictionary[prices]['close'][-1][1] * (1 - alpha)
                down = self.rsi_dictionary[prices]['close'][-1][2] * (1 - alpha)
            else:
                up = self.rsi_dictionary[prices]['close'][-1][1] * (1 - alpha)
                down = -difference * alpha + self.rsi_dictionary[prices]['close'][-1][2] * (1 - alpha)

            rsi = 100 if down == 0 else 100 - 100 / (1 + up / down)
            self.rsi_dictionary[prices]['close'].append((rsi, up, down))
        else:
            if shift > 0:
                data = data[:-shift]
            ups, downs = get_ups_and_downs(data=data, parameter=parameter)
            rsi = self.helper_get_ema(ups, downs, prices)

        return round(rsi, self.precision) if round_value else rsi

    def main_logic(self):
        """
        Main logic that dictates how backtest works. It checks for stop losses and then moving averages to check for
        upcoming trends.
        """
        trend = self.get_trend()
        if self.currentPosition == SHORT:
            if self.lossStrategy is not None and self.currentPrice > self.get_stop_loss():
                self.buy_short('Exited short because a stop loss was triggered.', stopLossExit=True)
            elif self.takeProfitType is not None and self.currentPrice <= self.get_take_profit():
                self.buy_short("Exited short because of take profit.")
            elif trend == BULLISH:
                self.buy_short('Exited short because a bullish trend was detected.')
                self.buy_long('Entered long because a bullish trend was detected.')
        elif self.currentPosition == LONG:
            if self.lossStrategy is not None and self.currentPrice < self.get_stop_loss():
                self.sell_long('Exited long because a stop loss was triggered.', stopLossExit=True)
            elif self.takeProfitType is not None and self.currentPrice >= self.get_take_profit():
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
                    if self.currentPrice > self.previousStopLoss and self.smartStopLossCounter > 0:
                        self.buy_long("Reentered long because of smart stop loss.")
                        self.smartStopLossCounter -= 1
                elif self.previousPosition == SHORT and self.stopLossExit:
                    if self.currentPrice < self.previousStopLoss and self.smartStopLossCounter > 0:
                        self.sell_short("Reentered short because of smart stop loss.")
                        self.smartStopLossCounter -= 1

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
        """
        Prints out strategies provided in configuration.
        """
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
        print(f"\tSmart Stop Loss Counter: {self.smartStopLossInitialCounter}")
        print(f'\tInterval: {self.interval}')
        print(f'\tMargin Enabled: {self.marginEnabled}')
        print(f"\tStarting Balance: ${self.startingBalance}")
        print(f'\tTake Profit Percentage: {round(self.takeProfitPercentageDecimal * 100, 2)}%')
        print(f'\tStop Loss Percentage: {round(self.lossPercentageDecimal * 100, 2)}%')
        if self.lossStrategy == TRAILING:
            print("\tLoss Strategy: Trailing")
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
        print(f'\tElapsed: {round(self.endingTime - self.startingTime, 2)} seconds')
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
