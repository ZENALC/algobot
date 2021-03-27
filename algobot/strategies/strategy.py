"""
Create your strategies from this base class here then import them to configuration.py to load them to the GUI.
Please make sure that they have some default values for the GUI to initialize them.
"""

from typing import List, Union

from algobot.data import Data


class Strategy:
    def __init__(self, name: str, parent, precision: int = 2):
        """
        Create all your strategies from this parent strategy class.
        :param name: Name of strategy.
        :param parent: Parent object that'll use this strategy. This will be a trader of some sort e.g. backtester.
        """
        self.name = name
        self.parent = parent
        self.precision = precision
        self.trend = None
        self.dynamic = False  # Set this to true if you want to have additional slots.
        self.description = "No strategy description found. You can setup your strategy description in strategies.py."
        self.strategyDict = {}
        self.lowerIntervalDict = {}

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
        self.strategyDict = {}

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
                return self.strategyDict
            else:
                return self.lowerIntervalDict
        else:
            raise ValueError("Invalid type of data object.")

    def get_min_option_period(self):
        """
        This function should return the minimum amount of periods required to get a trend.
        """
        pass
