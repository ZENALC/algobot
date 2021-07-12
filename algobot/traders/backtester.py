import copy
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from itertools import product
from logging import Logger
from typing import Dict, Union

import pandas as pd
from dateutil import parser

from algobot.enums import (BACKTEST, BEARISH, BULLISH, ENTER_LONG, ENTER_SHORT,
                           EXIT_LONG, EXIT_SHORT, LONG, OPTIMIZER, SHORT)
from algobot.helpers import (LOG_FOLDER, ROOT_DIR,
                             convert_all_dates_to_datetime,
                             convert_small_interval, get_interval_minutes,
                             get_ups_and_downs, parse_strategy_name)
from algobot.interface.config_utils.strategy_utils import \
    get_strategies_dictionary
from algobot.strategies.strategy import Strategy
from algobot.traders.trader import Trader
from algobot.typing_hints import DATA_TYPE, DICT_TYPE


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
                 drawdownPercentage: int = 100,
                 precision: int = 4,
                 outputTrades: bool = True,
                 logger: Logger = None):
        super().__init__(symbol=symbol,
                         precision=precision,
                         startingBalance=startingBalance,
                         marginEnabled=marginEnabled)
        convert_all_dates_to_datetime(data)
        self.data = data
        self.check_data()
        self.outputTrades: bool = outputTrades  # Boolean that'll determine whether trades are outputted to file or not.
        self.interval = self.get_interval()
        self.intervalMinutes = get_interval_minutes(self.interval)
        self.pastActivity = []  # We'll add previous data here when hovering through graph in GUI.
        self.drawdownPercentageDecimal = drawdownPercentage / 100  # Percentage of loss at which bot exits backtest.
        self.optimizerRows = []
        self.logger = logger

        if len(strategyInterval.split()) == 1:
            strategyInterval = convert_small_interval(strategyInterval)

        self.allStrategies = get_strategies_dictionary(Strategy.__subclasses__())
        self.strategyInterval = self.interval if strategyInterval is None else strategyInterval
        self.strategyIntervalMinutes = get_interval_minutes(self.strategyInterval)
        self.intervalGapMinutes = self.strategyIntervalMinutes - self.intervalMinutes
        self.intervalGapMultiplier = self.strategyIntervalMinutes // self.intervalMinutes
        if self.intervalMinutes > self.strategyIntervalMinutes:
            raise RuntimeError(f"Your strategy interval ({self.strategyIntervalMinutes} minute(s)) can't be smaller "
                               f"than the data interval ({self.intervalMinutes} minute(s)).")

        self.ema_dict = {}
        self.rsi_dictionary = {}
        self.setup_strategies(strategies)
        self.startDateIndex = self.get_start_index(startDate)
        self.endDateIndex = self.get_end_index(endDate)

    def change_strategy_interval(self, interval: str):
        """
        Changes strategy interval to the one provided.
        :param interval: Interval to update strategy interval with.
        """
        if len(interval.split()) == 1:
            interval = convert_small_interval(interval)

        self.strategyInterval = self.interval if interval is None else interval
        self.strategyIntervalMinutes = get_interval_minutes(self.strategyInterval)
        self.intervalGapMinutes = self.strategyIntervalMinutes - self.intervalMinutes
        self.intervalGapMultiplier = self.strategyIntervalMinutes // self.intervalMinutes
        if self.intervalMinutes > self.strategyIntervalMinutes:
            raise RuntimeError("Your strategy interval can't be smaller than the data interval.")

    def get_gap_data(self, data: DATA_TYPE, check: bool = True) -> DICT_TYPE:
        """
        Returns gap interval data from data list provided.
        :param check: Check values to match with strategy interval minutes.
        :param data: Data to get total interval data from.
        :return: Dictionary of interval data of gap minutes.
        """
        if check:
            expected_length = self.strategyIntervalMinutes / self.intervalMinutes
            if expected_length != len(data):
                raise AssertionError(f"Expected {expected_length} data length. Received {len(data)} data.")

        return {
            'date_utc': data[0]['date_utc'],
            'open': data[0]['open'],
            'high': max([d['high'] for d in data]),
            'low': min([d['low'] for d in data]),
            'close': data[-1]['close'],
            'volume': sum([d['volume'] for d in data])
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
        if isinstance(targetDate, datetime):
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
            if endDateIndex < 1:
                raise IndexError("You need at least one data period.")
            if endDateIndex <= self.startDateIndex:
                raise IndexError("Ending date index cannot be less than or equal to start date index.")

            return endDateIndex
        else:
            return len(self.data) - 1

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

    @staticmethod
    def generate_error_message(error: Exception, strategy: Strategy) -> str:
        msg = f'It looks like your strategy has crashed because of: "{str(error)}". Try using' \
              f' different parameters, rewriting your strategy, or taking a look at ' \
              f'your strategy code again. The strategy that caused this crash is: ' \
              f'{strategy.name}. You can find more details about the crash in the ' \
              f'logs file at {os.path.join(ROOT_DIR, LOG_FOLDER)}.'
        return msg

    def strategy_loop(self, strategyData, thread) -> Union[None, str]:
        for strategy in self.strategies.values():
            try:
                strategy.get_trend(strategyData)
            except Exception as e:
                if thread and thread.caller == OPTIMIZER:
                    error_message = traceback.format_exc()
                    if self.logger is not None:
                        self.logger.exception(error_message)
                    return 'CRASHED'  # We don't want optimizer to stop.
                else:
                    if thread:
                        thread.signals.updateGraphLimits.emit(len(self.pastActivity))
                    raise RuntimeError(self.generate_error_message(e, strategy)) from e

    def start_backtest(self, thread=None):
        """
        Main function to start a backtest.
        :param thread: Thread to pass to other functions to emit signals to.
        """
        testLength = self.endDateIndex - self.startDateIndex
        divisor = max(testLength // 100, 1)

        if thread and thread.caller == BACKTEST:
            thread.signals.updateGraphLimits.emit(testLength // divisor + 1)

        self.startingTime = time.time()
        if len(self.strategies) == 0:
            result = self.simulate_hold(testLength, divisor, thread)
        else:
            result = self.strategy_backtest(testLength, divisor, thread)
        self.endingTime = time.time()
        return result

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

    def simulate_hold(self, testLength: int, divisor: int, thread=None) -> str:
        """
        Simulate a long hold position if no strategies are provided.
        :param divisor: Divisor where when remainder of test length and divisor is 0, a signal is emitted to GUI.
        :param testLength: Length of backtest.
        :param thread: Thread to emit signals back to if provided.
        """
        for index in range(self.startDateIndex, self.endDateIndex, divisor):
            if thread and not thread.running:
                if thread.caller == BACKTEST:
                    raise RuntimeError("Backtest was canceled.")
                if thread.caller == OPTIMIZER:
                    raise RuntimeError("Optimizer was canceled.")

            self.currentPeriod = self.data[index]
            self.currentPrice = self.currentPeriod['open']

            if self.currentPosition != LONG:
                self.buy_long("Entered long to simulate a hold.")

            if thread and thread.caller == BACKTEST:
                thread.signals.activity.emit(thread.get_activity_dictionary(self.currentPeriod, index, testLength))

        self.exit_backtest()
        return 'HOLD'

    def strategy_backtest(self, testLength: int, divisor: int, thread=None) -> str:
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
                if thread.caller == BACKTEST:
                    raise RuntimeError("Backtest was canceled.")
                if thread.caller == OPTIMIZER:
                    raise RuntimeError("Optimizer was canceled.")

            self.set_indexed_current_price_and_period(index)
            seenData.append(self.currentPeriod)

            self.main_logic()
            if self.get_net() < 10:
                if thread and thread.caller == BACKTEST:
                    thread.signals.message.emit("Backtester ran out of money. Change your strategy or date interval.")
                self.exit_backtest(index)
                return 'OUT OF MONEY'
            elif self.get_net() < (1 - self.drawdownPercentageDecimal) * self.startingBalance:
                return 'DRAWDOWN'

            result = None  # Result of strategy loop to ensure nothing crashed -> None is good, anything else is bad.
            if strategyData is seenData:
                if len(strategyData) >= self.minPeriod:
                    result = self.strategy_loop(strategyData=strategyData, thread=thread)
            else:
                if len(strategyData) + 1 >= self.minPeriod:
                    strategyData.append(self.currentPeriod)
                    result = self.strategy_loop(strategyData=strategyData, thread=thread)
                    strategyData.pop()

            if result is not None:
                return result

            if seenData is not strategyData and self.currentPeriod['date_utc'] >= nextInsertion:
                nextInsertion = self.currentPeriod['date_utc'] + timedelta(minutes=self.strategyIntervalMinutes)
                gapData = self.get_gap_data(seenData[-self.intervalGapMultiplier - 1: -1])
                strategyData.append(gapData)

            if thread and thread.caller == BACKTEST and index % divisor == 0:
                thread.signals.activity.emit(thread.get_activity_dictionary(self.currentPeriod, index, testLength))

        self.exit_backtest(index)
        return 'PASSED'

    @staticmethod
    def extend_helper(x_tuple: tuple, temp_dict: Dict[str, list], temp_key: str):
        """
        Helper function to get all permutations.
        :param x_tuple: Tuple containing start, end, and step values i.e -> (5, 15, 1). Kind of like range().
        :param temp_dict: Dictionary to modify.
        :param temp_key: The key to add value to in the dictionary provided.
        """
        start, end, step = x_tuple
        if start > end:
            raise ValueError("Your start can't have a bigger value than the end.")

        if step > 0:
            if isinstance(step, int):
                temp = list(range(start, end + 1, step))
            elif isinstance(step, float):
                temp = [start]
                current = start
                while current < end:
                    current += step
                    if current <= end:
                        temp.append(current)
            else:
                raise ValueError("Step values can only be integers or floats.")

            temp_dict[temp_key] = temp
        else:
            raise ValueError("Step value cannot be 0.")

    def get_all_permutations(self, combos: dict):
        """
        Returns a list of setting permutations from combos provided.
        :param combos: Combos with ranges for the permutations.
        :return: List of all permutations.
        """
        for key, value_range in combos.items():  # This will handle steps -> (5, 10, 1) start = 5, end = 10, step = 1
            if isinstance(value_range, tuple) and len(value_range) == 3:
                self.extend_helper(value_range, combos, key)
            elif key == "strategies":
                for strategyKey, strategyDict in value_range.items():
                    for inputKey, step_tuple in strategyDict.items():
                        if isinstance(step_tuple, tuple) and len(step_tuple) == 3:
                            self.extend_helper(step_tuple, strategyDict, inputKey)
            elif isinstance(value_range, list):
                continue
            else:
                raise ValueError("Invalid type of value provided to combos. Make sure to use a list or a tuple.")

        for strategyKey, strategyItems in combos['strategies'].items():  # Create cartesian product of strategies
            combos['strategies'][strategyKey] = [dict(zip(strategyItems, v)) for v in product(*strategyItems.values())]

        permutations = []
        strategies = combos.pop('strategies')
        for v in product(*combos.values()):
            permutations_dict = dict(zip(combos, v))
            for z in product(*strategies.values()):
                permutations_dict['strategies'] = dict(zip(strategies, z))
                permutations.append(copy.deepcopy(permutations_dict))
        return permutations

    def optimize(self, combos: Dict, thread=None):
        """
        This function will run a brute-force optimization test to figure out the best inputs.
        Sample combos should look something like: {
            'lossTypes': [TRAILING] -> use a list for predefined values.
            'lossPercentage': (5, 15, 3) -> use a tuple with 3 values for steps i.e. -> 5, 8, 11, 14.
        }
        """
        settings_list = self.get_all_permutations(combos)
        was_thread = thread is not None
        if thread:
            thread.signals.started.emit()

        for index, settings in enumerate(settings_list, start=1):
            if thread and not thread.running:
                break
            if was_thread and not thread:
                break  # Bug fix for optimizer keeping on running even after it was stopped.

            self.apply_general_settings(settings)
            if not self.has_moving_average_redundancy():
                result = self.start_backtest(thread)
            else:
                self.currentPrice = 0  # Or else it'll crash.
                result = 'SKIPPED'

            if thread:
                thread.signals.activity.emit(self.get_basic_optimize_info(index, len(settings_list), result=result))

            self.restore()

    def has_moving_average_redundancy(self):
        """
        Simple check to see if a moving average strategy needs to be run or not. If the initial bound is greater than
        or equal to the final bound, then it should be skipped.
        """
        if 'movingAverage' in self.strategies:
            for option in self.strategies['movingAverage'].get_params():
                if option.initialBound >= option.finalBound:
                    return True
        return False

    def get_basic_optimize_info(self, run: int, totalRuns: int, result: str = 'PASSED') -> tuple:
        """
        Return basic information in a tuple for emitting to the trades table in the GUI.
        """
        row = (
            round(self.get_net() / self.startingBalance * 100 - 100, 2),
            self.get_stop_loss_strategy_string(),
            self.get_safe_rounded_string(self.lossPercentageDecimal, multiplier=100, symbol='%'),
            self.get_trailing_or_stop_type_string(self.takeProfitType),
            self.get_safe_rounded_string(self.takeProfitPercentageDecimal, multiplier=100, symbol='%'),
            self.symbol,
            self.interval,
            self.strategyInterval,
            len(self.trades),
            f'{run}/{totalRuns}',
            result,  # PASSED / DRAWDOWN / CRASHED
            self.get_strategies_info_string(left=' ', right=' ')
        )
        self.optimizerRows.append(row)
        return row

    def export_optimizer_rows(self, file_path: str, file_type: str):
        """
        Exports optimizer rows to file path provided using Pandas.
        """
        headers = ['Profit Percentage', 'Stop Loss Strategy', 'Stop Loss Percentage', 'Take Profit Strategy',
                   'Take Profit Percentage', 'Ticker', 'Interval', 'Strategy Interval', 'Trades', 'Run',
                   'Result', 'Strategy']
        df = pd.DataFrame(self.optimizerRows)
        df.columns = headers
        df.set_index('Run', inplace=True)

        if file_type == 'CSV':
            df.to_csv(file_path)
        elif file_type == 'XLSX':
            df.to_excel(file_path)
        else:
            raise TypeError("Invalid type of file type provided.")

    def apply_general_settings(self, settings: Dict[str, Union[float, str, dict]]):
        """
        Apples settings provided from the settings argument to the backtester object.
        :param settings: Dictionary with keys and values to set.
        """
        if 'takeProfitType' in settings:
            self.takeProfitType = self.get_enum_from_str(settings['takeProfitType'])
            self.takeProfitPercentageDecimal = settings['takeProfitPercentage'] / 100

        if 'lossType' in settings:
            self.lossStrategy = self.get_enum_from_str(settings['lossType'])
            self.lossPercentageDecimal = settings['lossPercentage'] / 100

            if 'stopLossCounter' in settings:
                self.smartStopLossCounter = settings['stopLossCounter']

        self.change_strategy_interval(settings['strategyIntervals'])
        for strategy_name, strategy_values in settings['strategies'].items():
            pretty_strategy_name = strategy_name
            strategy_name = parse_strategy_name(strategy_name)

            if strategy_name not in self.strategies:
                if isinstance(strategy_values, dict):
                    strategy_values = list(strategy_values.values())

                temp_strategy_tuple = (
                    self.allStrategies[pretty_strategy_name],
                    strategy_values,
                    pretty_strategy_name
                )
                self.setup_strategies([temp_strategy_tuple])
                continue

            # TODO: Leverage kwargs instead of using indexed lists.

            loop_strategy = self.strategies[strategy_name]
            loop_strategy.reset_strategy_dictionary()  # Mandatory for bugs in optimizer.
            loop_strategy.trend = None  # Annoying bug fix for optimizer.
            loop_strategy.set_inputs(list(strategy_values.values()))
            self.minPeriod = max(loop_strategy.get_min_option_period(), self.minPeriod)

    def restore(self):
        """
        Restore backtester to initial values.
        """
        self.reset_trades()
        self.reset_smart_stop_loss()
        self.balance = self.startingBalance
        self.coin = self.coinOwed = 0
        self.currentPosition = self.currentPeriod = None
        self.previousStopLoss = self.previousPosition = None
        self.stopLossExit = False
        self.smartStopLossEnter = False
        self.ema_dict = {}
        self.rsi_dictionary = {}

    def get_interval(self) -> str:
        """
        Attempts to parse interval from loaded data.
        :return: Interval in str format.
        """
        assert len(self.data) >= 2, "Not enough data gathered. Change your data interval."
        period1 = self.data[0]['date_utc']
        period2 = self.data[1]['date_utc']

        if isinstance(period1, str):
            period1 = parser.parse(period1)
        if isinstance(period2, str):
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
        Main logic that dictates how backtest works.
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
            elif trend == EXIT_SHORT:
                self.buy_short('Bought short because an exit-short trend was detected.')
        elif self.currentPosition == LONG:
            if self.lossStrategy is not None and self.currentPrice < self.get_stop_loss():
                self.sell_long('Exited long because a stop loss was triggered.', stopLossExit=True)
            elif self.takeProfitType is not None and self.currentPrice >= self.get_take_profit():
                self.sell_long("Exited long because of take profit.")
            elif trend == BEARISH:
                self.sell_long('Exited long because a bearish trend was detected.')
                if self.marginEnabled:
                    self.sell_short('Entered short because a bearish trend was detected.')
            elif trend == EXIT_LONG:
                self.sell_long("Exited long because an exit-long trend was detected.")
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
            elif trend == ENTER_LONG:
                self.buy_long("Entered long because an enter-long trend was detected.")
                self.reset_smart_stop_loss()
            elif trend == ENTER_SHORT:
                self.sell_short("Entered short because an enter-short trend was detected.")
                self.reset_smart_stop_loss()
            else:
                if self.previousPosition == LONG and self.stopLossExit:
                    if self.currentPrice > self.previousStopLoss and self.smartStopLossCounter > 0:
                        self.buy_long("Reentered long because of smart stop loss.", smartEnter=True)
                        self.smartStopLossCounter -= 1
                elif self.previousPosition == SHORT and self.stopLossExit:
                    if self.currentPrice < self.previousStopLoss and self.smartStopLossCounter > 0:
                        self.sell_short("Reentered short because of smart stop loss.", smartEnter=True)
                        self.smartStopLossCounter -= 1

    def print_configuration_parameters(self, stdout=None):
        """
        Prints out configuration parameters.
        """
        previous_stdout = sys.stdout
        if stdout is not None:  # Temporarily redirects output to stdout provided.
            sys.stdout = stdout

        print("Backtest configuration:")
        print(f'\tInterval: {self.interval}')
        print(f'\tDrawdown Percentage: {self.drawdownPercentageDecimal * 100}')
        print(f'\tMargin Enabled: {self.marginEnabled}')
        print(f"\tStarting Balance: ${self.startingBalance}")

        if self.takeProfitType is not None:
            print(f'\tTake Profit Percentage: {round(self.takeProfitPercentageDecimal * 100, 2)}%')

        if self.lossStrategy is not None:
            print(f'\tStop Loss Strategy: {self.get_stop_loss_strategy_string()}')
            print(f'\tStop Loss Percentage: {round(self.lossPercentageDecimal * 100, 2)}%')
            print(f"\tSmart Stop Loss Counter: {self.smartStopLossInitialCounter}")

        print(self.get_strategies_info_string())
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

    def get_default_result_file_name(self, name: str = 'backtest', ext: str = 'txt'):
        """
        Returns a default backtest/optimizer result file name.
        :return: String filename.
        """
        resultsFolder = os.path.join(ROOT_DIR, f'{name.capitalize()} Results')
        symbol = 'Imported' if not self.symbol else self.symbol
        dateString = datetime.now().strftime("%Y-%m-%d_%H-%M")
        resultFile = f'{symbol}_{name}_results_{"_".join(self.interval.lower().split())}-{dateString}.{ext}'

        if not os.path.exists(resultsFolder):
            return resultFile

        innerFolder = os.path.join(resultsFolder, self.symbol)
        if not os.path.exists(innerFolder):
            return resultFile

        counter = 0
        previousFile = resultFile

        while os.path.exists(os.path.join(innerFolder, resultFile)):
            resultFile = f'({counter}){previousFile}'  # (1), (2)
            counter += 1

        return resultFile

    def write_results(self, resultFile: str = None) -> str:
        """
        Writes backtest results to resultFile provided. If none is provided, it'll write to a default file name.
        :param resultFile: File to write results in.
        :return: Path to file.
        """
        if not resultFile:
            resultFile = self.get_default_result_file_name()

        with open(resultFile, 'w') as f:
            self.print_configuration_parameters(f)
            self.print_backtest_results(f)

            if self.outputTrades:
                self.print_trades(f)

        return os.path.join(os.getcwd(), resultFile)
