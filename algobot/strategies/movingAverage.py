from typing import List, Union

from algobot.data import Data
from algobot.enums import BEARISH, BULLISH
from algobot.option import Option
from algobot.strategies.strategy import Strategy


class MovingAverageStrategy(Strategy):
    def __init__(self, parent=None, inputs: List[Option] = None, precision: int = 2):
        """
        Basic Moving Average strategy.
        """
        super().__init__(name='Moving Average', parent=parent, precision=precision)
        self.tradingOptions: List[Option] = inputs
        self.dynamic = True
        self.description = "Basic trading strategy using moving averages. If the moving average of initial is greater" \
                           " than final, a bullish trend is determined. If the moving average of final is greater, a " \
                           "bearish trend is determined. All moving averages have to have the same trend for an " \
                           "overall trend to be set."

        if parent:  # Only validate if parent exists. If no parent, this mean's we're just calling this for param types.
            self.validate_options()

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

        if not data:
            data = parent.dataView

        if type(data) == Data:
            if not data.data_is_updated():
                data.update_data()

            if data == parent.dataView:
                parent.optionDetails = []
            else:
                parent.lowerOptionDetails = []

        for option in self.tradingOptions:
            movingAverage, parameter, initialBound, finalBound = option.get_all_params()
            initialName, finalName = option.get_pretty_option()

            if type(data) == list:
                avg1 = parent.get_moving_average(data, option.movingAverage, option.initialBound, option.parameter)
                avg2 = parent.get_moving_average(data, option.movingAverage, option.finalBound, option.parameter)
            else:
                avg1 = parent.get_average(movingAverage, parameter, initialBound, data, update=False)
                avg2 = parent.get_average(movingAverage, parameter, finalBound, data, update=False)

            if type(data) == Data:
                if data == parent.dataView:
                    if log_data:
                        parent.output_message(f'Regular interval ({data.interval}) data:')
                    parent.optionDetails.append((avg1, avg2, initialName, finalName))
                else:
                    if log_data:
                        parent.output_message(f'Lower interval ({data.interval}) data:')
                    parent.lowerOptionDetails.append((avg1, avg2, initialName, finalName))

                if log_data:
                    parent.output_message(f'{option.movingAverage}({option.initialBound}) = {avg1}')
                    parent.output_message(f'{option.movingAverage}({option.finalBound}) = {avg2}')

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
