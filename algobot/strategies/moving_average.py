"""
Moving Average strategy.
"""

from typing import List, Union

import pandas as pd

from algobot.algorithms import MA_MAP, MA_PARAMS
from algobot.data import Data
from algobot.enums import BEARISH, BULLISH
from algobot.helpers import get_random_color
from algobot.option import Option
from algobot.strategies.strategy import Strategy


class MovingAverageStrategy(Strategy):
    """
    Moving Average Strategy class.
    """
    def __init__(self, parent=None, inputs: list = ('',) * 4, precision: int = 2):
        """
        Basic Moving Average strategy.
        """
        super().__init__(name='Moving Average', parent=parent, precision=precision)
        self.tradingOptions: List[Option] = self.parse_inputs(inputs)
        self.dynamic = True
        self.description = "Basic trading strategy using moving averages. If the moving average of initial is greater" \
                           " than final, a bullish trend is determined. If the moving average of final is greater, a " \
                           "bearish trend is determined. All moving averages have to have the same trend for an " \
                           "overall trend to be set."

        if parent:  # Only validate if parent exists. If no parent, this mean's we're just calling this for param types.
            self.validate_options()
            self.initialize_plot_dict()

    def initialize_plot_dict(self):
        """
        Initializes plot dictionary for the Moving Average class.
        """
        # TODO: Add support for colors in the actual program.
        for option in self.tradingOptions:
            initial_name, final_name = option.get_pretty_option()
            self.plotDict[initial_name] = [0, get_random_color()]
            self.plotDict[final_name] = [0, get_random_color()]

    @staticmethod
    def parse_inputs(inputs):
        """
        Parses the inputs into options acceptable by the strategy.
        :param inputs: List of inputs to parse.
        :return: Parsed strategy inputs.
        """
        return [Option(*inputs[x:x + 4]) for x in range(0, len(inputs), 4)]

    def set_inputs(self, inputs: list):
        """
        Sets trading options provided.
        """
        self.tradingOptions = self.parse_inputs(inputs)

    def get_min_option_period(self) -> int:
        """
        Returns the minimum period required to perform moving average calculations. For instance, if we needed to
        calculate SMA(25), we need at least 25 periods of data, and we'll only be able to start from the 26th period.
        :return: Minimum period of days required.
        """
        minimum = 0
        for option in self.tradingOptions:
            minimum = max(minimum, option.finalBound, option.initialBound)
        return minimum

    @staticmethod
    def get_param_types() -> List[tuple]:
        """
        This function will return all the parameter types of the Moving Average strategy for the GUI.
        The moving average tuple will return a tuple type with all the supported moving averages.
        The parameter tuple will return a tuple type with all the supported parameters.
        The initial value will return the int type.
        The final value will return the int type.
        """
        return [
            ('Moving Average', tuple, MA_MAP.keys()),
            ('Parameter', tuple, MA_PARAMS),
            ('Initial', int),
            ('Final', int)
        ]

    def get_params(self) -> List[Option]:
        """
        This function will return all the parameters used for the Moving Average strategy.
        """
        return self.tradingOptions

    def get_trend(self, data: Union[List[dict], Data], log_data: bool = False) -> int:
        """
        This function should return the current trend for the Moving Average strategy with the provided data.
        :param data: Data container to get trend from - it can either be a list or a Data object.
        :param log_data: Boolean specifying whether current information regarding strategy should be logged or not.
        """
        parent = self.parent
        data_object = data
        trends = []  # Current option trends. They all have to be the same to register a trend.

        run_data = data_object.data + [data_object.current_values] if isinstance(data_object, Data) else data_object

        df = pd.DataFrame(run_data)
        df['high/low'] = (df['high'] + df['low']) / 2
        df['open/close'] = (df['open'] + df['close']) / 2

        for option in self.tradingOptions:
            movingAverage, parameter, initialBound, finalBound = option.get_all_params()
            initial_name, final_name = option.get_pretty_option()

            func = MA_MAP[movingAverage.upper()]
            avg1 = func(df[parameter], initialBound)
            avg2 = func(df[parameter], finalBound)

            prefix, interval_type = self.get_prefix_and_interval_type(data)

            if log_data:
                parent.output_message(f'{interval_type.capitalize()} interval ({data.interval}) data:')
                parent.output_message(f'{movingAverage}({initialBound}) {parameter} = {avg1}')
                parent.output_message(f'{movingAverage}({finalBound}) {parameter} = {avg2}')

            self.strategyDict[interval_type][f'{prefix}{initial_name}'] = avg1
            self.strategyDict[interval_type][f'{prefix}{final_name}'] = avg2

            if interval_type == 'regular' and not isinstance(data_object, list):
                self.plotDict[initial_name][0] = avg1
                self.plotDict[final_name][0] = avg2

            if avg1 > avg2:
                trends.append(BULLISH)
            elif avg1 < avg2:
                trends.append(BEARISH)
            else:  # If they're the same, that means no trend.
                trends.append(None)

        if all(trend == BULLISH for trend in trends):
            self.trend = BULLISH
        elif all(trend == BEARISH for trend in trends):
            self.trend = BEARISH
        else:
            self.trend = None

        return self.trend

    def validate_options(self):
        """
        Validates options provided. If the list of options provided does not contain all options, an error is raised.
        """
        if len(self.tradingOptions) == 0:  # Checking whether options exist.
            raise ValueError("No trading options provided.")

        for option in self.tradingOptions:
            if not isinstance(option, Option):
                raise TypeError(f"'{option}' is not a valid option type.")
