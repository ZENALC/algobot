from typing import List, Union

from algobot.data import Data
from algobot.enums import BEARISH, BULLISH
from algobot.option import Option
from algobot.strategies.strategy import Strategy


class MovingAverageStrategy(Strategy):
    def __init__(self, parent=None, inputs: list = ("", "", "", ""), precision: int = 2):
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
            self.strategyDict = {'lower': [], 'regular': []}

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
        movingAverages = ['SMA', 'EMA', 'WMA']
        parameters = ['High', 'Low', 'Open', 'Close', 'High/Low', 'Open/Close']
        return [('Moving Average', tuple, movingAverages),
                ('Parameter', tuple, parameters),
                ('Initial', int),
                ('Final', int)
                ]

    def get_params(self) -> List[Option]:
        """
        This function will return all the parameters used for the Moving Average strategy.
        """
        return self.tradingOptions

    def get_trend(self, data: Union[List[dict], Data] = None, log_data: bool = False) -> int:
        """
        This function should return the current trend for the Moving Average strategy with the provided data.
        :param data: Data container to get trend from - it can either be a list or a Data object.
        :param log_data: Boolean specifying whether current information regarding strategy should be logged or not.
        """
        parent = self.parent
        trends = []  # Current option trends. They all have to be the same to register a trend.

        interval_type = 'regular' if data == parent.dataView else 'lower'
        self.strategyDict[interval_type] = []

        if not data:  # This means that a sim or a live trader called this get trend function.
            data = parent.dataView

        for option in self.tradingOptions:
            movingAverage, parameter, initialBound, finalBound = option.get_all_params()
            initialName, finalName = option.get_pretty_option()

            if type(data) == list:  # This means it was called by the optimizer/backtester.
                avg1 = parent.get_moving_average(data, movingAverage, initialBound, parameter)
                avg2 = parent.get_moving_average(data, movingAverage, finalBound, parameter)
            else:  # This means it was called by the live bot / simulation.
                avg1 = parent.get_average(movingAverage, parameter, initialBound, data, update=False)
                avg2 = parent.get_average(movingAverage, parameter, finalBound, data, update=False)

            if type(data) == Data:
                if log_data:
                    parent.output_message(f'{interval_type.capitalize()} interval ({data.interval}) data:')
                    parent.output_message(f'{movingAverage}({initialBound}) {parameter} = {avg1}')
                    parent.output_message(f'{movingAverage}({finalBound}) {parameter} = {avg2}')

                self.strategyDict[interval_type].append((avg1, avg2, initialName, finalName))

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
            if type(option) != Option:
                raise TypeError(f"'{option}' is not a valid option type.")
