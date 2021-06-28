"""
A super simple sample example of a strategy with Bollinger bands and moving averages.
"""

from typing import List, Union

from algobot.algorithms import get_bollinger_bands, get_moving_average
from algobot.data import Data
from algobot.enums import BEARISH, BULLISH
from algobot.helpers import get_random_color
from algobot.strategies.strategy import Strategy


class SampleStrategy(Strategy):
    def __init__(self, parent=None, inputs: list = (None,) * 10, precision: int = 2):
        super().__init__(name='Sample', parent=parent, precision=precision)
        self.description = "This is a sample strategy with Bollinger Bands."
        self.moving_average_periods = inputs[0]
        self.moving_average_parameter = inputs[1]
        self.moving_average_type = inputs[2]
        self.bb_coefficient = inputs[3]
        self.volatility_type = inputs[4]
        self.volatility_look_back_periods = inputs[5]
        self.ma_moving_average_type = inputs[6]
        self.ma_moving_average_parameter = inputs[7]
        self.ma_moving_average_1 = inputs[8]
        self.ma_moving_average_2 = inputs[9]

        ma1 = f'{self.ma_moving_average_type}({self.ma_moving_average_1}) - {self.ma_moving_average_parameter}'
        ma2 = f'{self.ma_moving_average_type}({self.ma_moving_average_2}) - {self.ma_moving_average_parameter}'

        self.plotDict[ma1] = [0, '00ff00']
        self.plotDict[ma2] = [0, 'FF0000']

        self.plotDict['Upper Band'] = [0, get_random_color()]
        self.plotDict['Middle Band'] = [0, get_random_color()]
        self.plotDict['Lower Band'] = [0, get_random_color()]

        self.strategyDict['general'] = {
            'Moving Average Periods BB': self.moving_average_periods,
            'Moving Average Type BB': self.moving_average_type,
            'Moving Average parameter': self.moving_average_parameter,
            'BB Coefficient': self.bb_coefficient,
            'Volatility Type': self.volatility_type,
            'Volatility Look Back Periods': self.volatility_look_back_periods,
            'Moving Average Type MA': self.ma_moving_average_type,
            'Moving Average Parameter MA': self.ma_moving_average_parameter,
        }

    def set_inputs(self, inputs: list) -> None:
        """
        Set the inputs provided from the list.
        :param inputs: List of inputs.
        :return: None
        """
        self.moving_average_periods = inputs[0]
        self.moving_average_parameter = inputs[1]
        self.moving_average_type = inputs[2]
        self.bb_coefficient = inputs[3]
        self.volatility_type = inputs[4]
        self.volatility_look_back_periods = inputs[5]
        self.ma_moving_average_type = inputs[6]
        self.ma_moving_average_parameter = inputs[7]
        self.ma_moving_average_1 = inputs[8]
        self.ma_moving_average_2 = inputs[9]

    def get_params(self) -> list:
        """
        Returns parameters of the strategy.
        :return: Parameters of the strategy.
        """
        return [
            self.moving_average_periods,
            self.moving_average_parameter,
            self.moving_average_type,
            self.bb_coefficient,
            self.volatility_type,
            self.volatility_look_back_periods,
            self.ma_moving_average_type,
            self.ma_moving_average_parameter,
            self.ma_moving_average_1,
            self.ma_moving_average_2
        ]

    @staticmethod
    def get_param_types():
        """
        Returns the parameter types of the strategy for the GUI to initialize them.
        :return: List of parameter types in a tuple.
        """
        moving_averages = ['SMA', 'EMA', 'WMA']
        moving_average_parameters = ['High', 'Low', 'Open', 'Close', 'High/Low', 'Open/Close']
        volatility_types = ['Yang Zhang (ZH)', 'Rogers Satchell (RS)', 'Garman-Klass (GK)', 'Parkinson', 'Basic']

        return [
            ('Volatility Moving Average Periods', int),
            ('Volatility Moving Average Parameter', tuple, moving_average_parameters),
            ('Volatility Moving Average Type', tuple, moving_averages),
            ('BB Coefficient', float),
            ('Volatility Type', tuple, volatility_types),
            ('Volatility Look Back Periods', int),
            ('Moving Average', tuple, moving_averages),
            ('Moving Average Parameter', tuple, moving_average_parameters),
            ('Moving Average 1', int),
            ('Moving Average 2', int),
        ]

    def get_min_option_period(self) -> int:
        """
        Returns the minimum amount of periods required for the strategy to start.
        :return: Minimum amount of periods required.
        """
        return max([
            self.moving_average_periods,
            self.ma_moving_average_1,
            self.ma_moving_average_2,
            self.volatility_look_back_periods
        ])

    def get_trend(self, data: Union[List[dict], Data] = None, log_data: bool = False):
        """
        Main function. This will determine the trend and set the plot and statistics window values.
        :param data: Data object.
        :param log_data: Boolean whether you want to log data or not.
        :return: The trend.
        """
        data_obj = data

        if type(data) == Data:
            data = data.data + [data.current_values]

        # Gathering the actual indicator values here.
        ma1 = get_moving_average(moving_average=self.ma_moving_average_type,
                                 moving_average_parameter=self.ma_moving_average_parameter,
                                 moving_average_periods=self.ma_moving_average_1,
                                 data=data)

        ma2 = get_moving_average(moving_average=self.ma_moving_average_type,
                                 moving_average_parameter=self.ma_moving_average_parameter,
                                 moving_average_periods=self.ma_moving_average_2,
                                 data=data)

        lower_band, middle_band, upper_band = get_bollinger_bands(
            bb_coefficient=self.bb_coefficient,
            moving_average=self.moving_average_type,
            moving_average_parameter=self.moving_average_parameter,
            moving_average_periods=self.moving_average_periods,
            volatility=self.volatility_type,
            volatility_look_back_periods=self.volatility_look_back_periods,
            data=data
        )

        prefix, interval = self.get_prefix_and_interval_type(data_obj)

        # Note that we use the interval key, because we also have support for lower intervals.

        # Now, let's these values in the statistics window.
        self.strategyDict[interval][f'{prefix}Lower Band'] = lower_band
        self.strategyDict[interval][f'{prefix}Middle Band'] = middle_band
        self.strategyDict[interval][f'{prefix}Upper Band'] = upper_band

        ma1_string = f'{self.ma_moving_average_type}({self.ma_moving_average_1}) - {self.ma_moving_average_parameter}'
        ma2_string = f'{self.ma_moving_average_type}({self.ma_moving_average_2}) - {self.ma_moving_average_parameter}'

        self.strategyDict[interval][ma1_string] = ma1
        self.strategyDict[interval][ma2_string] = ma2

        if interval == 'regular':  # Only plot for regular interval values.
            # Note that the value of this dictionary is a list. The first contains the value and the second contains
            # the color. We only want to change the value, so modify the first value (which is at the 0th index).
            self.plotDict['Lower Band'][0] = lower_band
            self.plotDict['Middle Band'][0] = middle_band
            self.plotDict['Upper Band'][0] = upper_band
            self.plotDict[ma1_string][0] = ma1
            self.plotDict[ma2_string][0] = ma2

        # Now, finally, the trend itself. The final value in our data is the latest one.

        open_price = data[-1]['open']  # Get the latest open price.

        if open_price < lower_band and ma1 > ma2:
            self.trend = BULLISH
        elif open_price > upper_band and ma1 < ma2:
            self.trend = BEARISH
        else:
            self.trend = None

        return self.trend
