"""
Custom strategy built from strategy builder.

TODO: Remove JSON logic. We are no longer using that. This should only accept strategy items.
"""
import json
from typing import Any, Dict, List, Optional, Union

from talib import abstract


class CustomStrategy:
    def __init__(self, trader=None, json_file: Optional[str] = None, precision: int = 2):
        """
        Initialize a custom strategy built off the strategy builder. This strategy should soon replace the actual
         Strategy class.
        :param trader: Trader that'll leverage this strategy. If it's None, we'll assume Algobot is calling it to ask
         for parameters and inputs.
        :param json_file: JSON file to create the strategy from. This contains the parameters, inputs, operands, and
         operators.
        :param precision: Precision with which to show values.
        """
        self.trader = trader
        self.precision = precision

        self.json_file = json_file
        self.parsed_json = self.load_custom_strategy_json()

        self.strategy_name = self.parsed_json['name']

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

    def load_custom_strategy_json(self):
        """
        Load JSON for strategy.
        :return: Parsed JSON.
        """
        with open(self.json_file, 'r', encoding='utf-8') as f:
            loaded_dict = json.load(f)

        for trend_items in loaded_dict.values():
            for uuid in trend_items:
                indicator = trend_items['name']
                abstract_info = {abstract.Function(indicator)}
                trend_items[uuid] = {**trend_items[uuid], **abstract_info}

        return loaded_dict

    def get_current_trader_price(self):
        """
        Helper function to get the current trader price for live/sims. This is mainly used for setting up auxiliary
        graph plots for misc strategies' plot dicts.
        :return: Current trader price.
        """
        # noinspection PyUnresolvedReferences
        if isinstance(self.trader, algobot.traders.simulation_trader.SimulationTrader):
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

    def get_param_types(self) -> dict:
        """
        Get parameter types to populate with in the Algobot GUI interface. Note that we delegate the GUI to handle
        population of the widgets. This will just return the parameter types.

        The GUI should then decide what type of widgets to use. The main reason we do this is because we don't want to
        be stuck with the possibility of multiple bot runs with the same widget. That is, it may be possible for a
        backtester and a simulation trader to reference the same widget; thus causing incorrect parameters to be
        returned.

        :return: Parameter types.
        """
        param_types = {}

        for trend, trend_items in self.parsed_json.items():
            param_types[trend] = {}

            for uuid, uuid_items in trend_items.items():
                param_types[trend][uuid] = uuid_items['parameters']

        return param_types

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
