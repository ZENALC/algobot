"""
A super simple example of a strategy with Bollinger bands and moving averages.

Note that Algobot will NOT display this strategy as its name is "Sample." If you want to experiment with this strategy,
rename it to something other than "Sample".

This is a complete strategy that supports lower interval notifications, logging, backtest, optimizations, simulations,
and live trading. Not recommended to actually live trade with this strategy.

*** THE STRATEGY ***

    If the opening price is less than the lower band, then our trend is BULLISH. If the opening price is
    higher than the upper band, then our is trend is BEARISH.

    Next, we are leveraging moving averages too, so for that, if the 1st moving average is higher than the second one,
    we are bullish, and vice-versa.

    Note that both of the above have to have the same trend for the bot to enter a position.

    If Bollinger bands are bearish, but moving averages are bullish, no action is taken.
    If Bollinger bands are bullish, but moving averages are bearish, no action is taken.
    If Bollinger bands are bullish AND moving averages are bullish, bot will enter long.

*** END OF THE STRATEGY ***
"""

from typing import List, Union

from algobot.algorithms import get_bollinger_bands, get_moving_average
from algobot.data import Data
from algobot.enums import BEARISH, BULLISH
from algobot.helpers import get_random_color
from algobot.strategies.strategy import Strategy


class SampleStrategy(Strategy):
    """
    Sample strategy that uses Bollinger bands and moving averages.
    """
    def __init__(self, parent=None, inputs: list = (None,) * 10, precision: int = 2):

        # Call parent class. Necessary for all strategies.
        super().__init__(name='Sample', parent=parent, precision=precision)

        # The GUI will show this description.
        self.description: str = "This is a sample strategy with Bollinger Bands."

        # Moving average periods for Bollinger Bands -> this should be the number of periods, so 15 for example.
        self.moving_average_periods: int = inputs[0]

        # Moving average parameter for Bollinger Bands -> this should be high, low, open, close, etc
        self.moving_average_parameter: str = inputs[1]

        # Moving average type for Bollinger Bands -> EMA, SMA, WMA, etc
        self.moving_average_type: str = inputs[2]

        # BB coefficient for Bollinger Bands -> some float value, so maybe 1.05.
        self.bb_coefficient: float = inputs[3]

        # Volatility Type for Bollinger Bands -> Yang Zhang, Rogers Satchell, Garman-Klass, Parkinson, Basic
        self.volatility_type: str = inputs[4]

        # Volatility look back periods for Bollinger bands -> some int value, so 25 for instance.
        self.volatility_look_back_periods: int = inputs[5]

        # Moving average type for the separate moving average strategy -> SMA, WMA, EMA
        self.ma_moving_average_type: str = inputs[6]

        # Moving average parameter for the separate moving average strategy -> high, low, open, close, etc
        self.ma_moving_average_parameter: str = inputs[7]

        # Moving average 1 periods -> some int, so 13 for instance
        self.ma_moving_average_1: int = inputs[8]

        # Moving average 2 periods -> some int, so 19 for instance
        self.ma_moving_average_2: int = inputs[9]

        # Creating 2 strings to show in the statistics window and graphs. For instance, if our moving average is SMA,
        # the parameter is high, and the periods is 39, this would yield -> SMA(39) - high
        ma1 = f'{self.ma_moving_average_type}({self.ma_moving_average_1}) - {self.ma_moving_average_parameter}'
        ma2 = f'{self.ma_moving_average_type}({self.ma_moving_average_2}) - {self.ma_moving_average_parameter}'

        # Populating the plot dictionary. We want to plot the moving averages, so we use the strings from above, and
        # then populate it with a list. The list's first item should be the value, and the second should be the color.
        # The color is the line on the graph.
        self.plotDict[ma1] = [0, '00ff00']
        self.plotDict[ma2] = [0, 'FF0000']

        # Populating same as above but for Bollinger Bands.
        self.plotDict['Upper Band'] = [0, get_random_color()]
        self.plotDict['Middle Band'] = [0, get_random_color()]
        self.plotDict['Lower Band'] = [0, get_random_color()]

        # General purpose dict key/pair for the statistics window. The statistics window will populate it by key/pair.
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
        Set the inputs provided from the list. This is used extensively by the optimizer. Make sure to correctly define
        by order. Order matters!
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
        Returns the parameter types of the strategy for the GUI to initialize them. Make sure to order them in the same
        order it was initialized. Order matters!
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

        If the opening price is less than the lower band, then our trend is BULLISH. If the opening price is
        higher than the upper band, then our is trend is BEARISH.

        Next, we are leveraging moving averages too, so for that, if the 1st moving average is higher than the second
        one, we are bullish, and vice-versa.

        :param data: Data object.
        :param log_data: Boolean whether you want to log data or not.
        :return: The trend.
        """
        # Store the data object retrieved. This can either be the lower interval data object (Data), regular interval
        # data object (Data), or the data from backtests/optimizer which are lists containing dictionaries.
        data_obj = data

        if type(data) == Data:
            # Get a copy of the data + the current values. Note we create a copy because we don't want to mutate the
            # actual Data object. We limit data objects to hold 1000 items at a time, so this is not a very expensive
            # operation.
            data = data.data + [data.current_values]

        # Gathering moving average values.
        ma1 = get_moving_average(moving_average=self.ma_moving_average_type,
                                 moving_average_parameter=self.ma_moving_average_parameter,
                                 moving_average_periods=self.ma_moving_average_1,
                                 data=data)

        ma2 = get_moving_average(moving_average=self.ma_moving_average_type,
                                 moving_average_parameter=self.ma_moving_average_parameter,
                                 moving_average_periods=self.ma_moving_average_2,
                                 data=data)

        # Gathering Bollinger band values.
        lower_band, middle_band, upper_band = get_bollinger_bands(
            bb_coefficient=self.bb_coefficient,
            moving_average=self.moving_average_type,
            moving_average_parameter=self.moving_average_parameter,
            moving_average_periods=self.moving_average_periods,
            volatility=self.volatility_type,
            volatility_look_back_periods=self.volatility_look_back_periods,
            data=data
        )

        # Get the prefix and interval. We need this for the strategy interval. For lower intervals, we store data
        # inside the 'lower' key, and for regular intervals, we store data inside the 'regular' key.
        prefix, interval = self.get_prefix_and_interval_type(data_obj)

        # Now, let's throw these values in the statistics window. Note that the prefix is necessary. The prefix is
        # either blank or "Lower Interval". The lower interval and regular interval keys need to be different.
        # Otherwise, they'll just override each other which would be chaos.
        self.strategyDict[interval][f'{prefix}Lower Band'] = lower_band
        self.strategyDict[interval][f'{prefix}Middle Band'] = middle_band
        self.strategyDict[interval][f'{prefix}Upper Band'] = upper_band

        # Same example as way above, but pretty much get a prettified string.
        ma1_string = f'{self.ma_moving_average_type}({self.ma_moving_average_1}) - {self.ma_moving_average_parameter}'
        ma2_string = f'{self.ma_moving_average_type}({self.ma_moving_average_2}) - {self.ma_moving_average_parameter}'

        # Set the values to the statistics window dictionary.
        self.strategyDict[interval][f'{prefix}{ma1_string}'] = ma1
        self.strategyDict[interval][f'{prefix}{ma2_string}'] = ma2

        if interval == 'regular':  # Only plot for regular interval values.
            # Note that the value of this dictionary is a list. The first contains the value and the second contains
            # the color. We only want to change the value, so modify the first value (which is at the 0th index).
            self.plotDict['Lower Band'][0] = lower_band
            self.plotDict['Middle Band'][0] = middle_band
            self.plotDict['Upper Band'][0] = upper_band
            self.plotDict[ma1_string][0] = ma1
            self.plotDict[ma2_string][0] = ma2

        if log_data:  # If you want to log the data, set advanced logging to True. Note this will write a lot of data.
            self.parent.output_message(f'Lower Band: {lower_band}')
            self.parent.output_message(f'Middle Band: {middle_band}')
            self.parent.output_message(f'Upper Band: {upper_band}')
            self.parent.output_message(f'{ma1_string}: {ma1}')
            self.parent.output_message(f'{ma2_string}: {ma2}')

        # Now, finally, the trend itself. The final value in our data is the latest one.
        open_price = data[-1]['open']  # Get the latest open price.

        # Same logic as defined in the definition of the strategy. This will set the trend.
        if open_price < lower_band and ma1 > ma2:
            self.trend = BULLISH
        elif open_price > upper_band and ma1 < ma2:
            self.trend = BEARISH
        else:
            self.trend = None

        return self.trend
