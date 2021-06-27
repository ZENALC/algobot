"""
Create your strategies from this base class here in this folder. You don't have to import anything.
Please make sure that they have some default values like None for the GUI to initialize them.

Visit https://github.com/ZENALC/algobot/wiki/Strategies for documentation.
"""

from typing import Any, Dict, List, Union

from algobot.data import Data


class Strategy:
    def __init__(self, name: str = None, parent=None, precision: int = 2):
        """
        Create all your strategies from this parent strategy class.
        :param name: Name of strategy.
        :param parent: Parent object that'll use this strategy. This will be a trader of some sort e.g. backtester.
        :param precision: Precision to which to round float values to.
        """
        self.name = name
        self.parent = parent
        self.precision = precision

        # Whatever description you want to pop in in the GUI.
        self.description = "No strategy description found. You can setup your strategy description in strategies.py."

        # This should hold the trend the strategy currently holds (e.g. BULLISH, BEARISH, ENTER LONG, etc)
        self.trend = None

        # Set this to true if you want to have additional slots. As an example, check out the moving average strategy.
        self.dynamic = False

        # Dictionary for plotting values in graphs. This should hold string keys and float values. If a value is
        # non-numeric, the program will crash.
        self.plotDict = {}

        # Dictionary for the what's going on in the strategy. This needs two keys: one which is 'regular' and another
        # which is 'lower'. The two keys will then hold dictionaries for the strategies' values in lower and regular
        # interval data.
        self.strategyDict = {'regular': {}, 'lower': {}}

    def set_inputs(self, *args, **kwargs):
        """
        This function is used extensively by the optimizer. Your inputs argument will reset the strategy's inputs.
        """
        raise NotImplementedError("Implement a function to set new inputs to your strategy.")

    def get_trend(self, data: Union[List[dict], Data] = None, log_data: bool = False) -> int:
        """
        Implement your strategy here. Based on the strategy's algorithm, this should return a trend.
        A trend can be either bullish, bearish, or neither.
        :return: Enum representing the trend.
        """
        raise NotImplementedError("Implement a strategy to get trend.")

    def get_params(self) -> list:
        """
        This function should return the parameters of the strategy being used.
        """
        raise NotImplementedError("Implement a function to return parameters.")

    def get_plot_data(self) -> dict:
        """
        This function should return plot data for bot. By default, it'll return an empty dictionary.
        :return: Plot data dictionary.
        """
        return self.plotDict

    @staticmethod
    def get_param_types():
        """
        This function should return the parameter types of the strategy being used for the GUI to initialize them.
        """
        raise NotImplementedError("Implement a function to return input types.")

    def reset_strategy_dictionary(self):
        """
        Clears strategy dictionary.
        """
        self.strategyDict = {'regular': {}, 'lower': {}}

    def get_appropriate_dictionary(self, data: Union[list, Data]) -> dict:
        """
        Returns dictionary regarding the strategy. If the data type is a list, it's a backtester, so we just return
        the strategy dict; if it's a Data type that's equal to the parent's data-view, then return the strategy dict;
        finally, if none of them are selected, then it's most likely the lower interval's dictionary.
        """
        if type(data) == list:
            return self.strategyDict
        elif type(data) == Data:
            if data == self.parent.dataView:
                return self.strategyDict['regular']
            else:
                return self.strategyDict['lower']
        else:
            raise ValueError("Invalid type of data object.")

    def get_min_option_period(self):
        """
        This function should return the minimum amount of periods required to get a trend. It's 0 by default.
        """
        return 0

    def populate_grouped_dict(self, grouped_dict: Dict[str, Dict[str, Any]]):
        """
        Populate grouped dictionary for the simulation/live trader. Note that only the key where this strategy exists
        will be provided. Not the entire grouped dictionary.
        :param grouped_dict: Grouped dictionary (strategy key) to populate.
        :return: None
        """
        for interval_dict in self.strategyDict.values():
            for key, value in interval_dict.items():
                grouped_dict[key] = value if type(value) != float else round(value, self.precision)
