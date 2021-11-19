"""
Custom strategy built from strategy builder.
"""
from typing import Any, Dict, List, Union

import numpy as np
from PyQt5.QtWidgets import QWidget
from talib import abstract

from algobot.enums import ENTER_LONG, ENTER_SHORT, EXIT_LONG, EXIT_SHORT
from algobot.helpers import get_random_color
from algobot.interface.configuration_helpers import get_input_widget_value
from algobot.interface.utils import MOVING_AVERAGE_TYPES_BY_NAME


class CustomStrategy:
    def __init__(self, trader, values: dict, precision: int = 2):
        """
        Initialize a custom strategy built off the strategy builder. This strategy should soon replace the actual
         Strategy class.
        :param trader: Trader that'll leverage this strategy.
        :param precision: Precision with which to show values.
        :param values: Values for custom strategy.
        """
        self.trader = trader
        self.precision = precision
        self.short_circuit = False

        self.values: Dict[str, Any] = self.parse_values(values)
        self.name = self.values['name']
        self.cache = {}

        self.plot_dict: Dict[str, List[Union[float, str]]] = {}

        # Current overall trend. In order for a strategy to have a trend, only one singular trend should reign. If
        #  multiple trends are showing signs, nothing will execute.
        self.trend = None

        # Dictionary for holding params and their values.
        self.params = {}

        # Dictionary for plotting values in graphs. This should hold string keys and float values. If a value is
        # non-numeric, the program will crash. This should hold the key of the value and then a list containing
        # the value then the color.

        # For example -> self.plot_dict['SMA(5)'] = [13, 'ffffff'] -> SMA(5) value of 13 with a hex color of white.
        self.plot_dict: Dict[str, List[Union[float, str]]] = {}

        # Dictionary for what's going on in the strategy. This needs two keys: one which is 'regular' and another
        # which is 'lower'. The two keys will then hold dictionaries for the strategies' values in lower and regular
        # interval data.
        self.strategy_dict: Dict[str, Dict[str, Any]] = {'regular': {}, 'lower': {}}
        self.initialize_plot_dict()

    def initialize_plot_dict(self):
        # TODO: Make trends consistent with variable names.
        trends = {"Buy Long", "Sell Long", "Sell Short", "Buy Short"}
        for trend, indicators in self.values.items():
            if trend not in trends:
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

    def get_indicator_val_and_label(self, operation, input_arrays_dict, get_arr: bool = False):
        kwargs = self.get_func_kwargs(operation)
        label = self.get_pretty_label(operation=operation, func_kwargs=kwargs)

        if label in self.cache:
            return self.cache[label], label

        func = abstract.Function(operation['indicator'])
        val = func(input_arrays_dict, price=operation['price'], **kwargs)

        output_index, output_verbose = operation['output']
        if output_index is None:
            if get_arr:
                return val, label

            self.cache[label] = val[-1]
            return val[-1], label
        else:
            if get_arr:
                return val[output_index], label

            self.cache[label] = val[output_index][-1]
            return val[output_index][-1], label

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

    def parse_values(self, values):
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
        for k, v in values.items():
            if isinstance(v, QWidget):
                if k == 'output':
                    # In this case, we just want the index. If the value is 'real', we'll just set the index to None.
                    output = get_input_widget_value(v, verbose=True)
                    if output == 'real':
                        new_dict[k] = (None, 'real')
                    else:
                        new_dict[k] = (get_input_widget_value(v, verbose=False), output)
                else:
                    new_dict[k] = get_input_widget_value(v, verbose=True)

                    # Lower all prices upstream.
                    if k == 'price':
                        new_dict[k] = new_dict[k].lower()
            elif isinstance(v, dict):
                new_dict[k] = self.parse_values(v)
            else:
                new_dict[k] = v

        return new_dict

    def get_params(self):
        return ['lol']

    @staticmethod
    def get_func_kwargs(kwargs) -> dict:
        """
        We just want **kwargs to feed into TALIB. To do this, we'll just use the current dictionary minus the ignored
         keys.
        :param kwargs: Kwargs to filter out.
        :return: Filtered kwargs.
        """
        ignored_keys = {'against', 'indicator', 'operator', 'price', 'output'}

        p = {k: v for k, v in kwargs.items() if k not in ignored_keys}

        for k, v in p.items():
            if 'matype' in k:
                p[k] = MOVING_AVERAGE_TYPES_BY_NAME[v]

        return p

    @staticmethod
    def get_pretty_label(operation, func_kwargs):
        output_index, output_verbose = operation['output']

        if output_index is None:
            return f'{operation["indicator"]}({func_kwargs["timeperiod"]}) - {operation["price"]}'

        return f'{output_verbose}({func_kwargs["timeperiod"]})'

    def get_trend_by_key(self, key: str, input_arrays_dict):
        indicators = self.values[key]
        if not indicators:  # Nothing provided as an input for this trend.
            return False

        trends = []
        for uuid, operation in indicators.items():
            val, label = self.get_indicator_val_and_label(operation, input_arrays_dict)
            self.strategy_dict['regular'][label] = val
            self.plot_dict[label][0] = val

            if operation['against'] == 'current_price':
                against_val = self.get_current_trader_price()
            elif isinstance(operation['against'], (float, int)):
                against_val = operation['against']
            else:
                against_val, against_label = self.get_indicator_val_and_label(operation['against'], input_arrays_dict)
                self.strategy_dict['regular'][against_label] = against_val
                self.plot_dict[against_label][0] = against_val

            result = eval(f'{val} {operation["operator"]} {against_val}')
            trends.append(result)

            if self.short_circuit and result is False:
                return False

        trend_sentiment = all(trends)
        self.strategy_dict['regular'][key] = str(trend_sentiment)
        # Return true if all trends are true, else false.
        return trend_sentiment

    def get_trend(self, df, cache=None):
        """
        There must be only one trend. If multiple trends are true, then return no trend.
        :param cache: Cache to use to avoid reevaluating trends.
        :param df: Dataframe to use to get trend.
        :return: Trend.
        """
        if cache is None:
            self.cache = {}
        else:
            self.cache = cache

        df.columns = [c.lower() for c in df.columns]
        input_arrays_dict = df.to_dict('series')

        trends = {
            ENTER_LONG: self.get_trend_by_key('Buy Long', input_arrays_dict),
            EXIT_LONG: self.get_trend_by_key('Sell Long', input_arrays_dict),
            ENTER_SHORT: self.get_trend_by_key('Sell Short', input_arrays_dict),
            EXIT_SHORT: self.get_trend_by_key('Buy Short', input_arrays_dict),
        }

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
        periods required. To find the minimum, we find the maximum number.
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

        # TODO: Make trends consistent with variable names.
        trends = {"Buy Long", "Sell Long", "Sell Short", "Buy Short"}

        for trend, indicators in self.values.items():
            if trend not in trends:
                continue

            for operation in indicators.values():
                val, _ = self.get_indicator_val_and_label(operation, test_dict, get_arr=True)
                first_non_nan = np.where(np.isnan(val))[0][-1] + 2
                current_minimum = max(first_non_nan, current_minimum)

        return current_minimum
