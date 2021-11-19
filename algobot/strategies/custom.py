"""
Custom strategy built from strategy builder.
"""
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from algobot.traders.trader import Trader

import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QWidget
from talib import abstract

from algobot.enums import TRENDS
from algobot.helpers import get_random_color
from algobot.interface.configuration_helpers import get_input_widget_value
from algobot.interface.utils import MOVING_AVERAGE_TYPES_BY_NAME


class CustomStrategy:
    """
    Custom strategy built from JSON files created by the strategy builder.
    """

    def __init__(self, trader: 'Trader', values: dict, precision: int = 2, short_circuit: bool = False):
        """
        Initialize a custom strategy built off the strategy builder. This strategy should soon replace the actual
         Strategy class.
        :param trader: Trader that'll leverage this strategy.
        :param precision: Precision with which to show values.
        :param values: Values for custom strategy.
        :param short_circuit: Whether you want to short circuit a trend or not. Immediately not perform calculations
         for remaining indicators in a trend when one indicator in that trend is already false. One drawback of this is
         that the user will lose support for viewing non-calculated statistics.
        """
        self.trader = trader
        self.precision = precision
        self.short_circuit = short_circuit
        self.values: Dict[str, Any] = self.parse_values(values)

        # Store cache to avoid calculating again.
        self.cache = {}

        # Dictionary for plotting values in graphs. This should hold string keys and float values. If a value is
        #  non-numeric, the program will crash. This should hold the key of the value and then a list containing
        #  the value then the color.
        #  For example -> self.plot_dict['SMA(5)'] = [13, 'ffffff'] -> SMA(5) value of 13 with a hex color of white.
        self.plot_dict: Dict[str, List[Union[float, str]]] = {}
        self.initialize_plot_dict()

        # Current overall trend. In order for a strategy to have a trend, only one singular trend should reign. If
        #  multiple trends are showing signs, nothing will execute.
        self.trend = None

        # Dictionary for holding params and their values.
        self.params = {}

        # Dictionary for what's going on in the strategy. This needs two keys: one which is 'regular' and another
        #  which is 'lower'. The two keys will then hold dictionaries for the strategies' values in lower and regular
        #  interval data.
        self.strategy_dict: Dict[str, Dict[str, Any]] = {'regular': {}, 'lower': {}}

    def initialize_plot_dict(self):
        """
        Initialize plot dictionary for custom strategies. This will loop through each indicator, gather outputs and
         labels, and then create a dictionary with label/value pairs.
        """
        for trend, indicators in self.values.items():
            if trend not in TRENDS:
                continue

            for operation in indicators.values():
                label = self.get_pretty_label(operation, self.get_func_kwargs(operation))
                self.plot_dict[label] = [self.get_current_trader_price(), get_random_color()]

                against = operation['against']
                if isinstance(against, dict):
                    label = self.get_pretty_label(against, self.get_func_kwargs(against))
                    self.plot_dict[label] = [self.get_current_trader_price(), get_random_color()]

    def get_plot_data(self) -> Dict[str, Union[List[Union[float, str]], int]]:
        """
        This function should return plot data for bot. By default, it'll return an empty dictionary.
        :return: Plot data dictionary.
        """
        return self.plot_dict

    def get_indicator_val_and_label(
            self,
            operation: dict,
            input_arrays_dict: Dict[str, pd.Series],
            get_arr: bool = False
    ) -> Tuple[Union[pd.Series, int, float], str]:
        """
        Create indicator value and label.
        :param operation: Dictionary containing indicator operation information in a dictionary.
        :param input_arrays_dict: Dictionary containing price type as key and price values as value.
        :param get_arr: Boolean whether to get entire array of results from TALIB or singular result value.
        :return:
        """
        kwargs = self.get_func_kwargs(operation)
        label = self.get_pretty_label(operation=operation, func_kwargs=kwargs)

        # We have this value in our cache, so just quick-return.
        if label in self.cache:
            return self.cache[label], label

        func = abstract.Function(operation['indicator'])
        val = func(input_arrays_dict, price=operation['price'], **kwargs)

        output_index, _output_verbose = operation['output']
        if output_index is not None:
            val = val[output_index]

        if get_arr:
            return val, label

        self.cache[label] = val[-1]
        return val[-1], label

    def populate_grouped_dict(self, grouped_dict: Dict[str, Dict[str, Any]]):
        """
        Populate grouped dictionary for the simulation/live trader. Note that only the key where this strategy exists
        will be provided. Not the entire grouped dictionary.
        :param grouped_dict: Grouped dictionary (strategy key) to populate.
        :return: None
        """
        for interval_dict in self.strategy_dict.values():
            for key, value in interval_dict.items():
                grouped_dict[key] = value if not isinstance(value, float) else round(value, self.precision)

    def parse_values(self, values: dict):
        """
        Parse values from QWidgets into regular values for TALIB.

        Example data:

            'Sell Long': {
                '74ec21ed-5a21-4ae4-8c00-fd1161b858cf': {
                'against': <PyQt5.QtWidgets.QDoubleSpinBox object at 0x0000024A03E8CC10>,
                'indicator': 'MFI',
                'operator': <PyQt5.QtWidgets.QComboBox object at 0x0000024A03E8CAF0>,
                'price': <PyQt5.QtWidgets.QComboBox object at 0x0000024A03E8C820>,
                'timeperiod': <PyQt5.QtWidgets.QSpinBox object at 0x0000024A03E8C9D0>
                }
            },

        Would become:

            'Sell Long': {
                '74ec21ed-5a21-4ae4-8c00-fd1161b858cf': {
                'against': 5.90,
                'indicator': 'MFI',
                'operator': '>=',
                'price': 'High',
                'timeperiod': 36
                }
            },

        :return: Parsed values.
        """
        new_dict = {}
        for key, value in values.items():
            if isinstance(value, QWidget):
                if key == 'output':
                    # In this case, we just want the index. If the value is 'real', we'll just set the index to None.
                    output = get_input_widget_value(value, verbose=True)
                    if output == 'real':
                        new_dict[key] = (None, 'real')
                    else:
                        new_dict[key] = (get_input_widget_value(value, verbose=False), output)
                else:
                    new_dict[key] = get_input_widget_value(value, verbose=True)

                    # Lower all prices upstream.
                    if key == 'price':
                        new_dict[key] = new_dict[key].lower()
            elif isinstance(value, dict):
                new_dict[key] = self.parse_values(value)
            else:
                new_dict[key] = value

        return new_dict

    @staticmethod
    def get_params():
        """TODO: DEPRECATE"""
        return ['']

    @staticmethod
    def get_func_kwargs(kwargs: dict) -> dict:
        """
        We just want **kwargs to feed into TALIB. To do this, we'll just use the current dictionary minus the ignored
         keys.
        :param kwargs: Kwargs to filter out.
        :return: Filtered kwargs.
        """
        ignored_keys = {'against', 'indicator', 'operator', 'price', 'output'}

        parsed = {key: value for key, value in kwargs.items() if key not in ignored_keys}
        for key, value in parsed.items():
            # We display verbosely, but we must cast back to numeric for TALIB to understand the moving average.
            if 'matype' in key:
                parsed[key] = MOVING_AVERAGE_TYPES_BY_NAME[value]

        return parsed

    @staticmethod
    def get_pretty_label(operation: dict, func_kwargs: dict) -> str:
        """
        Get prettified label for plots and statistics windows.
        :param operation: Operation dictionary containing indicator, operator, and against information.
        :param func_kwargs: Function keyword arguments. We use this to get the timeperiod.
        :return: Prettified label.
        """
        output_index, output_verbose = operation['output']

        # If there's no output index, we get the "real" value. The real value is nothing but the indicator, so we'll
        #  use leverage that for the label. However, if it does have an index, we'll get the verbose output from above.
        if output_index is None:
            return f'{operation["indicator"]}({func_kwargs["timeperiod"]}) - {operation["price"]}'

        return f'{output_verbose}({func_kwargs["timeperiod"]})'

    def get_trend_by_key(self, key: str, input_arrays_dict: Dict[str, pd.Series]) -> bool:
        """
        Get trend by key.
        :param key: Key to get trend of.
        :param input_arrays_dict: Dictionary containing price type as key and price values as value.
        :return: Boolean regarding trend. If True is returned, this key trend is true, else false.
        """
        indicators = self.values[key]
        if not indicators:  # Nothing provided as an input for this trend.
            return False

        trends = []
        for operation in indicators.values():
            val, label = self.get_indicator_val_and_label(operation, input_arrays_dict)
            self.strategy_dict['regular'][label] = val
            self.plot_dict[label][0] = val  # The 2nd value is the color, so we only update the value.

            if operation['against'] == 'current_price':
                against_val = self.get_current_trader_price()
            elif isinstance(operation['against'], (float, int)):
                against_val = operation['against']
            else:
                against_val, against_label = self.get_indicator_val_and_label(operation['against'], input_arrays_dict)
                self.strategy_dict['regular'][against_label] = against_val
                self.plot_dict[against_label][0] = against_val

            result = eval(f'{val} {operation["operator"]} {against_val}')  # pylint: disable=eval-used
            trends.append(result)

            if self.short_circuit and result is False:
                break

        trend_sentiment = all(trends)
        self.strategy_dict['regular'][key] = str(trend_sentiment)
        # Return true if all trends are true, else false.
        return trend_sentiment

    def get_trend(self, input_arrays_dict: Dict[str, pd.Series], cache: Optional[Dict[str, Any]] = None):
        """
        There must be only one trend. If multiple trends are true, then return no trend.
        :param cache: Cache to use to avoid reevaluating trends.
        :param input_arrays_dict: Dictionary containing price as key and price values as value.
        :return: Trend.
        """
        self.cache = {} if cache is None else cache
        trends = {trend: self.get_trend_by_key(trend, input_arrays_dict) for trend in TRENDS}

        true_trends = []
        for trend_name, trend_status in trends.items():
            if trend_status is True:
                true_trends.append(trend_name)

        if len(true_trends) == 1:
            self.trend = true_trends.pop()
            return self.trend

        # There was more than 1 trend or 0 trends, so return no trend.
        self.trend = None
        return None

    def get_current_trader_price(self):
        """
        Helper function to get the current trader price for live/sims. This is mainly used for setting up auxiliary
        graph plots for misc strategies' plot dicts.
        :return: Current trader price.
        """
        if hasattr(self.trader, 'data_view'):
            if self.trader.current_price is None:
                self.trader.current_price = self.trader.data_view.get_current_price()

            return self.trader.current_price

        # This means it's the backtester, so return 0. TODO: Why return 0?
        return 0

    def set_params(self, updated_params: dict):
        """
        Given a dictionary, update each key in the current params dictionary. This updated params dictionary show
        be a dictionary containing the trend as the most-outer key, uuid inside the key with the trend, and then the
        appropriate values themselves.
        """
        self.params = updated_params

    def reset_strategy_dictionary(self):
        """
        Clears strategy dictionary.
        """
        self.strategy_dict = {'regular': {}, 'lower': {}}

    def get_min_option_period(self) -> int:
        """
        Get minimum periods required. This will traverse through the current selected parameters and get the minimum
         periods required. To find the minimum, we find the maximum number. To use a dummy placeholder, we'll
         initialize a dummy numpy array with 500 random values for each price type.

        :return: Minimum periods required.
        """
        np_arr = np.random.random(500)
        test_dict = {
            'high': np_arr,
            'low': np_arr,
            'open': np_arr,
            'close': np_arr,
            'open/close': np_arr,
            'high/low': np_arr
        }

        current_minimum = 0

        for trend, indicators in self.values.items():
            if trend not in TRENDS:
                continue

            for operation in indicators.values():
                val, _label = self.get_indicator_val_and_label(operation, test_dict, get_arr=True)
                first_non_nan = np.where(np.isnan(val))[0][-1] + 2
                current_minimum = max(first_non_nan, current_minimum)

                # Check for the against indicator too if it exists.
                against = operation['against']
                if isinstance(against, dict):
                    val, _label = self.get_indicator_val_and_label(against, test_dict, get_arr=True)
                    first_non_nan = np.where(np.isnan(val))[0][-1] + 2
                    current_minimum = max(first_non_nan, current_minimum)

        return current_minimum
