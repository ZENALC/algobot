"""
Custom strategy built from strategy builder.
"""
from typing import Any, Dict, List, Union
from talib import abstract

from PyQt5.QtWidgets import QWidget

from algobot.enums import ENTER_LONG, EXIT_LONG, ENTER_SHORT, EXIT_SHORT
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

        self.values = self.parse_values(values)
        self.strategy_name = self.values['name']

        self.plot_dict: Dict[str, List[Union[float, str]]] = {}

        # The GUI will show this description.
        # TODO: Add support for descriptions in the strategy builder.
        self.description: str = f"This is a custom strategy named '{self.strategy_name}' built with the " \
                                f"strategy builder."

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

    def get_plot_data(self) -> Dict[str, Union[List[Union[float, str]], int]]:
        """
        This function should return plot data for bot. By default, it'll return an empty dictionary.
        :return: Plot data dictionary.
        """
        return self.plot_dict

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
        for k, v in values.items():
            if isinstance(v, QWidget):
                if k == 'output':
                    # In this case, we just want the index.
                    output = get_input_widget_value(v, verbose=True)
                    if output == 'real':
                        values[k] = None
                    else:
                        values[k] = get_input_widget_value(v, verbose=False)
                else:
                    values[k] = get_input_widget_value(v, verbose=True)
            elif isinstance(v, dict):
                self.parse_values(v)

        return values

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

    def get_trend_by_key(self, key: str, input_arrays_dict):
        indicators = self.values[key]
        if not indicators:
            # Nothing provided as an input for this trend.
            return False

        trends = []
        for uuid, operation in indicators.items():
            price = operation['price'].lower()
            indicator = operation['indicator']
            with_func = abstract.Function(indicator)
            with_kwargs = self.get_func_kwargs(operation)
            with_val = with_func(input_arrays_dict, price=price, **with_kwargs)

            with_output = operation['output']
            if with_output is None:
                with_val = with_val[-1]
            else:
                with_val = with_val[with_output][-1]

            against_kwargs = ""
            if operation['against'] == 'current_price':
                against_val = self.get_current_trader_price()
                against_label = 'current price'
            elif isinstance(operation['against'], (float, int)):
                against_val = operation['against']
                against_label = 'static price'
            else:
                against_indicator = operation['against']['indicator']
                against_price = operation['against']['price'].lower()
                against_func = abstract.Function(against_indicator)

                against_kwargs = self.get_func_kwargs(operation['against'])
                against_val = against_func(input_arrays_dict, price=against_price, **against_kwargs)

                against_output = operation['against']['output']
                if against_output is None:
                    against_val = against_val[-1]
                else:
                    against_val = against_val[against_output][-1]

                against_label = against_indicator

            operator = operation['operator']
            # TODO: Not sure why literal_eval doesn't work? Investigate.
            result = eval(f'{with_val} {operator} {against_val}')
            trends.append(result)

            with_label = f'{indicator} {with_kwargs}'
            against_label = f'{against_label} {against_kwargs}'
            result_label = f'{key}'

            self.strategy_dict['regular'][with_label] = with_val
            self.strategy_dict['regular'][against_label] = against_val
            self.strategy_dict['regular'][result_label] = str(result)

            # k = [(with_label, with_val), (against_label, against_val)]
            # for label, val in k:
            #     if label not in self.plot_dict:
            #         self.plot_dict[label] = [val, get_random_color()]

            if self.short_circuit and result is False:
                return False

        # Return true if all trends are true, else false.
        return all(trends)

    def get_trend(self, df):
        """
        There must be only one trend. If multiple trends are true, then return no trend.
        :param df: Dataframe to use to get trend.
        :return: Trend.
        """
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

    def get_minimum_periods_required(self) -> int:
        """
        Get minimum periods required. This will traverse through the current selected parameters and get the minimum
        periods required. To find the minimum, we find the maximum number.
        :return: Minimum periods required.
        """
        current_minimum = 0

        for trend_items in self.params.values():
            for params in trend_items.values():
                for param_name, param in params.items():
                    if param_name.lower() == 'timeperiod' and isinstance(param, (int, float)):
                        current_minimum = max(current_minimum, param)

        return current_minimum
