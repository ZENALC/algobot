"""
Backtester object.
"""

import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from itertools import product
from logging import Logger
from typing import Dict, List, Optional

import pandas as pd
from dateutil import parser

from algobot.enums import (BACKTEST, BEARISH, BULLISH, ENTER_LONG, ENTER_SHORT, EXIT_LONG, EXIT_SHORT, LONG, OPTIMIZER,
                           SHORT)
from algobot.helpers import (LOG_FOLDER, ROOT_DIR, convert_all_dates_to_datetime, convert_small_interval,
                             get_interval_minutes, is_number)
from algobot.traders.trader import Trader
from algobot.typing_hints import DataType, DictType


class Backtester(Trader):
    """
    Backtester class.
    """

    def __init__(self,
                 starting_balance: float,
                 data: list,
                 strategies: list,
                 strategy_interval: Optional[str] = None,
                 symbol: str = None,
                 margin_enabled: bool = True,
                 start_date: datetime = None,
                 end_date: datetime = None,
                 drawdown_percentage: int = 100,
                 precision: int = 4,
                 output_trades: bool = True,
                 logger: Logger = None):

        super().__init__(
            symbol=symbol,
            precision=precision,
            starting_balance=starting_balance,
            margin_enabled=margin_enabled
        )

        convert_all_dates_to_datetime(data)

        self.data = data
        self.check_data()

        self.interval = self.get_interval()
        self.interval_minutes = get_interval_minutes(self.interval)

        # Boolean that'll determine whether trades are outputted to file or not.
        self.output_trades: bool = output_trades

        # We'll add previous data here when hovering through graph in GUI.
        self.past_activity = []

        # Percentage of loss at which bot exits backtest.
        self.drawdown_percentage_decimal = drawdown_percentage / 100

        self.optimizer_rows = []
        self.logger = logger

        if len(strategy_interval.split()) == 1:
            strategy_interval = convert_small_interval(strategy_interval)

        self.all_strategies = {}

        self.strategy_interval = self.interval if strategy_interval is None else strategy_interval
        self.strategy_interval_minutes = get_interval_minutes(self.strategy_interval)

        self.interval_gap_minutes = self.strategy_interval_minutes - self.interval_minutes
        self.interval_gap_multiplier = self.strategy_interval_minutes // self.interval_minutes

        if self.interval_minutes > self.strategy_interval_minutes:
            raise RuntimeError(f"Your strategy interval ({self.strategy_interval_minutes} minute(s)) can't be smaller "
                               f"than the data interval ({self.interval_minutes} minute(s)).")

        self.setup_strategies(strategies, short_circuit=True)

        self.start_date_index = self.get_start_index(start_date)
        self.end_date_index = self.get_end_index(end_date)

    def change_strategy_interval(self, interval: str):
        """
        Changes strategy interval to the one provided.
        :param interval: Interval to update strategy interval with.
        """
        if len(interval.split()) == 1:
            interval = convert_small_interval(interval)

        self.strategy_interval = interval
        self.strategy_interval_minutes = get_interval_minutes(interval)

        self.interval_gap_minutes = self.strategy_interval_minutes - self.interval_minutes
        self.interval_gap_multiplier = self.strategy_interval_minutes // self.interval_minutes

        if self.interval_minutes > self.strategy_interval_minutes:
            raise RuntimeError("Your strategy interval can't be smaller than the data interval.")

    def get_gap_data(self, data: DataType, check: bool = True) -> DictType:
        """
        Returns gap interval data from data list provided.
        :param check: Check values to match with strategy interval minutes.
        :param data: Data to get total interval data from.
        :return: Dictionary of interval data of gap minutes.
        """
        if check:
            expected_length = self.strategy_interval_minutes / self.interval_minutes
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
        first_date = self.data[0]['date_utc']
        last_date = self.data[-1]['date_utc']

        if first_date > last_date:
            self.data = self.data[::-1]

    def find_date_index(self, target_date: datetime.date, starting: bool = True) -> int:
        """
        Finds starting or ending index of date from targetDate if it exists in data loaded.
        :param starting: Boolean if true will find the first found index. If used for end index, set to False.
        :param target_date: Object to compare date-time with.
        :return: Index from self.data if found, else -1.
        """
        if isinstance(target_date, datetime):
            target_date = target_date.date()

        iterator = list(enumerate(self.data))

        if not starting:
            iterator = reversed(list(enumerate(self.data)))

        for index, data in iterator:
            if data['date_utc'].date() == target_date:
                return index

        raise IndexError("Date not found.")

    def get_start_index(self, start_date: datetime.date) -> int:
        """
        Returns index of start date based on start_date argument.
        :param start_date: Datetime object to compare index with.
        :return: Index of start date.
        """
        return self.find_date_index(start_date) if start_date else 0

    def get_end_index(self, end_date: datetime.date) -> int:
        """
        Returns index of end date based on endDate argument.
        :param end_date: Datetime object to compare index with.
        :return: Index of end date.
        """
        if end_date:
            end_date_index = self.find_date_index(end_date, starting=False)

            if end_date_index < 1:
                raise IndexError("You need at least one data period.")
            if end_date_index <= self.start_date_index:
                raise IndexError("Ending date index cannot be less than or equal to start date index.")

            return end_date_index
        return len(self.data) - 1

    def set_indexed_current_price_and_period(self, index: int):
        """
        Sets the current backtester price and period based on index provided.
        :param index: Index of data to set as current period.
        """
        self.current_period = self.data[index]
        self.current_price = self.data[index]['open']

    @staticmethod
    def generate_error_message(error: Exception, strategy) -> str:
        """
        Error message generator when running a backtest.
        :param error: Error object.
        :param strategy: Strategy that caused this error.
        :return: String containing error message.
        """
        return f'It looks like your strategy has crashed because of: "{str(error)}". Try using' \
               f' different parameters, rewriting your strategy, or taking a look at ' \
               f'your strategy code again. The strategy that caused this crash is: ' \
               f'{strategy.name}. You can find more details about the crash in the ' \
               f'logs file at {os.path.join(ROOT_DIR, LOG_FOLDER)}.'

    def strategy_loop(self, strategy_data, thread) -> Optional[str]:
        """
        This will traverse through all strategies and attempt to get their trends.
        :param strategy_data: Data to use to get the strategy trend.
        :param thread: Thread object (if exists).
        :return: String "CRASHED" if an error is raised, else None if everything goes smoothly.
        """
        cache = {}
        df = pd.DataFrame(strategy_data[-250:])
        df['high/low'] = (df['high'] + df['low']) / 2
        df['open/close'] = (df['open'] + df['close']) / 2
        df.columns = [c.lower() for c in df.columns]
        input_arrays_dict = df.to_dict('series')

        for strategy in self.strategies.values():
            try:
                strategy.get_trend(input_arrays_dict, cache)
            except Exception as e:
                if thread and thread.caller == OPTIMIZER:
                    error_message = traceback.format_exc()

                    if self.logger is not None:
                        self.logger.exception(error_message)

                    return 'CRASHED'  # We don't want optimizer to stop.
                else:
                    if thread:
                        thread.signals.updateGraphLimits.emit(len(self.past_activity))

                    raise RuntimeError(self.generate_error_message(e, strategy)) from e

    def start_backtest(self, thread=None):
        """
        Main function to start a backtest.
        :param thread: Thread to pass to other functions to emit signals to.
        """
        test_length = self.end_date_index - self.start_date_index
        divisor = max(test_length // 100, 1)

        if thread and thread.caller == BACKTEST:
            thread.signals.updateGraphLimits.emit(test_length // divisor + 1)

        self.starting_time = time.time()
        if len(self.strategies) == 0:
            result = self.simulate_hold(test_length, divisor, thread)
        else:
            result = self.strategy_backtest(test_length, divisor, thread)
        self.ending_time = time.time()
        return result

    def exit_backtest(self, index: int = None):
        """
        Ends a backtest by exiting out of a position if needed.
        """
        if index is None:
            index = self.end_date_index

        self.current_period = self.data[index]
        self.current_price = self.current_period['close']

        if self.current_position == SHORT:
            self.buy_short("Exited short position because backtest ended.")
        elif self.current_position == LONG:
            self.sell_long("Exited long position because backtest ended.")

    def simulate_hold(self, test_length: int, divisor: int, thread=None) -> str:
        """
        Simulate a long hold position if no strategies are provided.
        :param divisor: Divisor where when remainder of test length and divisor is 0, a signal is emitted to GUI.
        :param test_length: Length of backtest.
        :param thread: Thread to emit signals back to if provided.
        """
        for index in range(self.start_date_index, self.end_date_index, divisor):
            if thread and not thread.running:
                if thread.caller == BACKTEST:
                    raise RuntimeError("Backtest was canceled.")
                if thread.caller == OPTIMIZER:
                    raise RuntimeError("Optimizer was canceled.")

            self.current_period = self.data[index]
            self.current_price = self.current_period['open']

            if self.current_position != LONG:
                self.buy_long("Entered long to simulate a hold.")

            if thread and thread.caller == BACKTEST:
                thread.signals.activity.emit(thread.get_activity_dictionary(self.current_period, index, test_length))

        self.exit_backtest()
        return 'HOLD'

    def strategy_backtest(self, test_length: int, divisor: int, thread=None) -> str:
        """
        Perform a backtest with provided strategies to backtester object.
        :param divisor: Divisor where when remainder of test length and divisor is 0, a signal is emitted to GUI.
        :param test_length: Length of backtest.
        :param thread: Optional thread that called this function that'll be used for emitting signals.
        """
        seen_data = self.data[:self.start_date_index]
        strategy_data = seen_data if self.strategy_interval_minutes == self.interval_minutes else []
        next_insertion = self.data[self.start_date_index]['date_utc'] + timedelta(
            minutes=self.strategy_interval_minutes)
        index = None
        for index in range(self.start_date_index, self.end_date_index + 1):
            if thread and not thread.running:
                if thread.caller == BACKTEST:
                    raise RuntimeError("Backtest was canceled.")
                if thread.caller == OPTIMIZER:
                    raise RuntimeError("Optimizer was canceled.")

            self.set_indexed_current_price_and_period(index)
            seen_data.append(self.current_period)

            self.main_logic()
            if self.get_net() < 10:
                if thread and thread.caller == BACKTEST:
                    thread.signals.message.emit("Backtester ran out of money. Change your strategy or date interval.")
                self.exit_backtest(index)
                return 'OUT OF MONEY'
            elif self.get_net() < (1 - self.drawdown_percentage_decimal) * self.starting_balance:
                return 'DRAWDOWN'

            result = None  # Result of strategy loop to ensure nothing crashed -> None is good, anything else is bad.
            if strategy_data is seen_data:
                if len(strategy_data) >= self.min_period:
                    result = self.strategy_loop(strategy_data=strategy_data, thread=thread)
            else:
                if len(strategy_data) + 1 >= self.min_period:
                    strategy_data.append(self.current_period)
                    result = self.strategy_loop(strategy_data=strategy_data, thread=thread)
                    strategy_data.pop()

            if result is not None:
                return result

            if seen_data is not strategy_data and self.current_period['date_utc'] >= next_insertion:
                next_insertion = self.current_period['date_utc'] + timedelta(minutes=self.strategy_interval_minutes)
                gap_data = self.get_gap_data(seen_data[-self.interval_gap_multiplier - 1: -1])
                strategy_data.append(gap_data)

            if thread and thread.caller == BACKTEST and index % divisor == 0:
                thread.signals.activity.emit(thread.get_activity_dictionary(self.current_period, index, test_length))

        self.exit_backtest(index)
        return 'PASSED'

    @staticmethod
    def extend_helper(x_tuple: list, temp_dict: Dict[str, list], temp_key: str):
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

    def convert_start_end_step(self, combos: dict) -> dict:
        """
        Convert start, end, and step values to appropriate list.
            For example, a start, end, step of [1, 10, 3] would yield -> [1, 4, 7, 10]
        :param combos: Dictionary to convert start, end, and steps of.
        :return: Modified combos dictionary.
        """
        for k, v in combos.items():
            if isinstance(v, dict):
                combos[k] = self.convert_start_end_step(v)
            elif isinstance(v, list) and len(v) == 3 and all(is_number(str(char)) for char in v):
                self.extend_helper(v, combos, k)

        return combos

    def get_all_permutations(self, combos: dict) -> List[dict]:
        """
        Returns a list of setting permutations from combos provided.
        :param combos: Combos with ranges for the permutations.
        :return: List of all dictionary permutations.
        """
        # pylint: disable=too-many-nested-blocks
        # TODO: Clean up the function to make it less convoluted.
        self.convert_start_end_step(combos)
        strategies = combos.pop('strategies')

        for strategy_name, strategy_items in strategies.items():
            for trend, trend_items in strategy_items.items():
                if trend == 'name':  # Must cast to list here, or product will be of string characters.
                    strategy_items[trend] = [trend_items]
                    continue  # This is not needed.

                for uuid, uuid_items in trend_items.items():
                    for indicator, indicator_value in uuid_items.items():

                        # This means it's an against indicator.
                        if isinstance(indicator_value, dict):
                            for against_item_key, against_item in indicator_value.items():
                                if not isinstance(against_item, list):
                                    indicator_value[against_item_key] = [against_item]

                            uuid_items[indicator] = [
                                dict(zip(indicator_value, v)) for v in product(*indicator_value.values())
                            ]
                            continue

                        if not isinstance(indicator_value, list):  # Cast everything to a list to use product.
                            uuid_items[indicator] = [indicator_value]

                    trend_items[uuid] = [
                        dict(zip(uuid_items, v)) for v in product(*uuid_items.values())
                    ]

                strategy_items[trend] = [
                    dict(zip(trend_items, v)) for v in product(*trend_items.values())
                ]

            strategies[strategy_name] = [
                dict(zip(strategy_items, v)) for v in product(*strategy_items.values())
            ]

        strategy_keys = strategies.keys()
        strategy_possibilities = [dict(zip(strategy_keys, v)) for v in product(*strategies.values())]
        combos['strategies'] = strategy_possibilities

        return [dict(zip(combos.keys(), v)) for v in product(*combos.values())]

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
            result = self.start_backtest(thread)

            if thread:
                thread.signals.activity.emit(self.get_basic_optimize_info(index, len(settings_list), result=result))

            self.restore()

    def get_basic_optimize_info(self, run: int, total_runs: int, result: str = 'PASSED') -> tuple:
        """
        Return basic information in a tuple for emitting to the trades table in the GUI.
        """
        row = (
            round(self.get_net() / self.starting_balance * 100 - 100, 2),
            self.get_stop_loss_strategy_string(),
            self.get_safe_rounded_string(self.loss_percentage_decimal, multiplier=100, symbol='%'),
            str(self.take_profit_type),
            self.get_safe_rounded_string(self.take_profit_percentage_decimal, multiplier=100, symbol='%'),
            self.symbol,
            self.interval,
            self.strategy_interval,
            len(self.trades),
            f'{run}/{total_runs}',
            result,  # PASSED / DRAWDOWN / CRASHED
            self.get_strategies_info_string(left=' ', right=' ')
        )
        self.optimizer_rows.append(row)
        return row

    def export_optimizer_rows(self, file_path: str, file_type: str):
        """
        Exports optimizer rows to file path provided using Pandas.
        """
        headers = ['Profit Percentage', 'Stop Loss Strategy', 'Stop Loss Percentage', 'Take Profit Strategy',
                   'Take Profit Percentage', 'Ticker', 'Interval', 'Strategy Interval', 'Trades', 'Run',
                   'Result', 'Strategy']
        df = pd.DataFrame(self.optimizer_rows)
        df.columns = headers
        df.set_index('Run', inplace=True)

        if file_type == 'CSV':
            df.to_csv(file_path)  # noqa
        elif file_type == 'XLSX':
            df.to_excel(file_path)
        else:
            raise TypeError("Invalid type of file type provided.")

    def apply_general_settings(self, settings: dict):
        """
        Apples settings provided from the settings argument to the backtester object.
        :param settings: Dictionary with keys and values to set.
        """
        if 'takeProfitType' in settings:
            self.take_profit_type = self.get_enum_from_str(settings['takeProfitType'])
            self.take_profit_percentage_decimal = settings['takeProfitPercentage'] / 100

        if 'lossType' in settings:
            self.loss_strategy = self.get_enum_from_str(settings['lossType'])
            self.loss_percentage_decimal = settings['lossPercentage'] / 100

            if 'stopLossCounter' in settings:
                self.smart_stop_loss_counter = settings['stopLossCounter']

        self.change_strategy_interval(settings['strategyIntervals'])
        self.setup_strategies(list(settings['strategies'].values()), short_circuit=True)

    def restore(self):
        """
        Restore backtester to initial values.
        """
        self.reset_trades()
        self.reset_smart_stop_loss()
        self.balance = self.starting_balance
        self.coin = self.coin_owed = 0
        self.current_position = self.current_period = None
        self.previous_stop_loss = self.previous_position = None
        self.stop_loss_exit = False
        self.smart_stop_loss_enter = False

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
            unit = seconds / 60
            result = f'{int(unit)} Minute'
        elif seconds < 86400:  # This will assume the interval is in hours.
            unit = seconds / 3600
            result = f'{int(unit)} Hour'
        else:  # This will assume the interval is in days.
            unit = seconds / 86400
            result = f'{int(unit)} Day'

        if unit > 1:
            result += 's'

        return result

    def main_logic(self):
        """
        Main logic that dictates how backtest works.
        """
        trend = self.get_trend()
        if self.current_position == SHORT:
            if self.loss_strategy is not None and self.current_price > self.get_stop_loss():
                self.buy_short('Exited short because a stop loss was triggered.', stop_loss_exit=True)
            elif self.take_profit_type is not None and self.current_price <= self.get_take_profit():
                self.buy_short("Exited short because of take profit.")
            elif trend == BULLISH:
                self.buy_short('Exited short because a bullish trend was detected.')
                self.buy_long('Entered long because a bullish trend was detected.')
            elif trend == EXIT_SHORT:
                self.buy_short('Bought short because an exit-short trend was detected.')
        elif self.current_position == LONG:
            if self.loss_strategy is not None and self.current_price < self.get_stop_loss():
                self.sell_long('Exited long because a stop loss was triggered.', stop_loss_exit=True)
            elif self.take_profit_type is not None and self.current_price >= self.get_take_profit():
                self.sell_long("Exited long because of take profit.")
            elif trend == BEARISH:
                self.sell_long('Exited long because a bearish trend was detected.')
                if self.margin_enabled:
                    self.sell_short('Entered short because a bearish trend was detected.')
            elif trend == EXIT_LONG:
                self.sell_long("Exited long because an exit-long trend was detected.")
        else:
            if not self.margin_enabled and self.previous_stop_loss is not None and self.current_price is not None:
                if self.previous_stop_loss < self.current_price:
                    self.stop_loss_exit = False  # Hotfix for margin-disabled backtests.

            if trend == BULLISH and (self.previous_position != LONG or not self.stop_loss_exit):
                self.buy_long('Entered long because a bullish trend was detected.')
                self.reset_smart_stop_loss()
            elif self.margin_enabled and trend == BEARISH and self.previous_position != SHORT:
                self.sell_short('Entered short because a bearish trend was detected.')
                self.reset_smart_stop_loss()
            elif trend == ENTER_LONG:
                self.buy_long("Entered long because an enter-long trend was detected.")
                self.reset_smart_stop_loss()
            elif trend == ENTER_SHORT:
                self.sell_short("Entered short because an enter-short trend was detected.")
                self.reset_smart_stop_loss()
            else:
                if self.previous_position == LONG and self.stop_loss_exit:
                    if self.current_price > self.previous_stop_loss and self.smart_stop_loss_counter > 0:
                        self.buy_long("Reentered long because of smart stop loss.", smart_enter=True)
                        self.smart_stop_loss_counter -= 1
                elif self.previous_position == SHORT and self.stop_loss_exit:
                    if self.current_price < self.previous_stop_loss and self.smart_stop_loss_counter > 0:
                        self.sell_short("Reentered short because of smart stop loss.", smart_enter=True)
                        self.smart_stop_loss_counter -= 1

    def print_configuration_parameters(self, stdout=None):
        """
        Prints out configuration parameters.
        """
        previous_stdout = sys.stdout
        if stdout is not None:  # Temporarily redirects output to stdout provided.
            sys.stdout = stdout

        print("Backtest configuration:")
        print(f'\tInterval: {self.interval}')
        print(f'\tDrawdown Percentage: {self.drawdown_percentage_decimal * 100}')
        print(f'\tMargin Enabled: {self.margin_enabled}')
        print(f"\tStarting Balance: ${self.starting_balance}")

        if self.take_profit_type is not None:
            print(f'\tTake Profit Percentage: {round(self.take_profit_percentage_decimal * 100, 2)}%')

        if self.loss_strategy is not None:
            print(f'\tStop Loss Strategy: {self.get_stop_loss_strategy_string()}')
            print(f'\tStop Loss Percentage: {round(self.loss_percentage_decimal * 100, 2)}%')
            print(f"\tSmart Stop Loss Counter: {self.smart_stop_loss_initial_counter}")

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
        print(f'\tElapsed: {round(self.ending_time - self.starting_time, 2)} seconds')
        print(f'\tStart Period: {self.data[self.start_date_index]["date_utc"]}')
        print(f"\tEnd Period: {self.current_period['date_utc']}")
        print(f'\tStarting balance: ${round(self.starting_balance, self.precision)}')
        print(f'\tNet: ${round(self.get_net(), self.precision)}')
        print(f'\tCommissions paid: ${round(self.commissions_paid, self.precision)}')
        print(f'\tTrades made: {len(self.trades)}')
        net = self.get_net()
        difference = round(net - self.starting_balance, self.precision)
        if difference > 0:
            print(f'\tProfit: ${difference}')
            print(f'\tProfit Percentage: {round(net / self.starting_balance * 100 - 100, 2)}%')
        elif difference < 0:
            print(f'\tLoss: ${-difference}')
            print(f'\tLoss Percentage: {round(100 - net / self.starting_balance * 100, 2)}%')
        else:
            print("\tNo profit or loss incurred.")
        # print(f'Balance: ${round(self.balance, 2)}')
        # print(f'Coin owed: {round(self.coin_owed, 2)}')
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
        results_folder = os.path.join(ROOT_DIR, f'{name.capitalize()} Results')
        symbol = 'Imported' if not self.symbol else self.symbol
        date_string = datetime.now().strftime("%Y-%m-%d_%H-%M")
        result_file = f'{symbol}_{name}_results_{"_".join(self.interval.lower().split())}-{date_string}.{ext}'

        if not os.path.exists(results_folder):
            return result_file

        inner_folder = os.path.join(results_folder, self.symbol)
        if not os.path.exists(inner_folder):
            return result_file

        counter = 0
        previous_file = result_file

        while os.path.exists(os.path.join(inner_folder, result_file)):
            result_file = f'({counter}){previous_file}'  # (1), (2)
            counter += 1

        return result_file

    def write_results(self, result_file: str = None) -> str:
        """
        Writes backtest results to resultFile provided. If none is provided, it'll write to a default file name.
        :param result_file: File to write results in.
        :return: Path to file.
        """
        if not result_file:
            result_file = self.get_default_result_file_name()

        with open(result_file, 'w', encoding='utf-8') as f:
            self.print_configuration_parameters(f)
            self.print_backtest_results(f)

            if self.output_trades:
                self.print_trades(f)

        return os.path.join(os.getcwd(), result_file)
