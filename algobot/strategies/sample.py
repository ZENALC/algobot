"""
A super simple example of a strategy with Bollinger bands and moving averages.

This is a complete strategy that supports lower interval notifications, logging, backtest, optimizations, simulations,
and live trading. Not recommended to actually live trade with this strategy.

*** THE STRATEGY ***

    If the opening price is less than the lower band, then our trend is BULLISH. If the opening price is
    higher than the upper band, then our is trend is BEARISH.

*** END OF THE STRATEGY ***

"""

from algobot.enums import BEARISH, BULLISH
from algobot.helpers import get_random_color
from algobot.strategies import TALIB_MAP_SINGLETON
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
        self.bb_period: int = inputs[0]

        # Moving average parameter for Bollinger Bands -> this should be high, low, open, close, open/close, high/low
        self.bb_parameter: str = inputs[1].lower() if isinstance(inputs[1], str) else None

        self.nb_dev_up: int = inputs[2]
        self.nb_dev_down: int = inputs[3]

        # Moving average type for Bollinger Bands -> EMA, SMA, WMA, etc
        self.bb_ma: int = 0

        # Populating the plot dictionary. We want to plot the Bollinger Bands, so we use the values from above, and
        # then populate it with a list. The list's first item should be the value, and the second should be the color.
        # The color is the line on the graph.
        self.plot_dict['Upper Band'] = [self.get_current_trader_price(), get_random_color()]
        self.plot_dict['Middle Band'] = [self.get_current_trader_price(), get_random_color()]
        self.plot_dict['Lower Band'] = [self.get_current_trader_price(), get_random_color()]

        # General purpose dict key/pair for the statistics window. The statistics window will populate it by key/pair.
        self.strategy_dict['general'] = {
            'BB Periods': self.bb_period,
            'BB Parameter': self.bb_parameter,
            'NB Dev Up': self.nb_dev_up,
            'NB Dev Down': self.nb_dev_down,
            'Moving Average': self.bb_ma
        }

    def set_inputs(self, inputs: list) -> None:
        """
        Set the inputs provided from the list. This is used extensively by the optimizer. Make sure to correctly define
        by order. Order matters!
        :param inputs: List of inputs.
        :return: None
        """
        self.bb_period = inputs[0]
        self.bb_parameter = inputs[1]
        self.nb_dev_up = inputs[2]
        self.nb_dev_down = inputs[3]
        # self.bb_ma = inputs[4]  TODO: FIXME

    def get_params(self) -> list:
        """
        Returns parameters of the strategy.
        :return: Parameters of the strategy.
        """
        return [
            self.bb_period,
            self.bb_parameter,
            self.nb_dev_up,
            self.nb_dev_down,
            self.bb_ma,
        ]

    @staticmethod
    def get_param_types():
        """
        Returns the parameter types of the strategy for the GUI to initialize them. Make sure to order them in the same
        order it was initialized. Order matters!
        :return: List of parameter types in a tuple.
        """
        moving_averages = TALIB_MAP_SINGLETON.MA
        moving_average_parameters = ['High', 'Low', 'Open', 'Close', 'High/Low', 'Open/Close']

        return [
            ('BB Period', int),
            ('Moving Average Parameter', tuple, moving_average_parameters),
            ('NB Dev Up', int),
            ('NB Dev Down', int),
            ('Moving Average', tuple, moving_averages),
        ]

    def get_min_option_period(self) -> int:
        """
        Returns the minimum amount of periods required for the strategy to start.
        :return: Minimum amount of periods required.
        """
        return self.bb_period

    def get_trend(self, df, data, log_data: bool = False):
        """
        Main function. This will determine the trend and set the plot and statistics window values.

        If the opening price is less than the lower band, then our trend is BULLISH. If the opening price is
        higher than the upper band, then our is trend is BEARISH.

        Next, we are leveraging moving averages too, so for that, if the 1st moving average is higher than the second
        one, we are bullish, and vice-versa.

        :param df: Dataframe containing data.
        :param data: Data object.
        :param log_data: Boolean whether you want to log data or not.
        :return: The trend.
        """
        # Store the data object retrieved. This can either be the lower interval data object (Data), regular interval
        # data object (Data), or the data from backtests/optimizer which are lists containing dictionaries.

        # Gathering Bollinger band values.
        upper_band, middle_band, lower_band = TALIB_MAP_SINGLETON.bbands.stream(
            df[self.bb_parameter], self.bb_period, self.nb_dev_up, self.nb_dev_down)

        # Get the prefix and interval. We need this for the strategy interval. For lower intervals, we store data
        # inside the 'lower' key, and for regular intervals, we store data inside the 'regular' key.
        prefix, interval = self.get_prefix_and_interval_type(data)

        # Now, let's throw these values in the statistics window. Note that the prefix is necessary. The prefix is
        # either blank or "Lower Interval". The lower interval and regular interval keys need to be different.
        # Otherwise, they'll just override each other which would be chaos.
        self.strategy_dict[interval][f'{prefix}Lower Band'] = lower_band
        self.strategy_dict[interval][f'{prefix}Middle Band'] = middle_band
        self.strategy_dict[interval][f'{prefix}Upper Band'] = upper_band

        if interval == 'regular' and not isinstance(data, list):  # Only plot for regular interval values.
            # Note that the value of this dictionary is a list. The first contains the value and the second contains
            # the color. We only want to change the value, so modify the first value (which is at the 0th index).
            self.plot_dict['Lower Band'][0] = lower_band
            self.plot_dict['Middle Band'][0] = middle_band
            self.plot_dict['Upper Band'][0] = upper_band

        if log_data:  # If you want to log the data, set advanced logging to True. Note this will write a lot of data.
            self.parent.output_message(f'Lower Band: {lower_band}')
            self.parent.output_message(f'Middle Band: {middle_band}')
            self.parent.output_message(f'Upper Band: {upper_band}')

        # Now, finally, the trend itself. The final value in our data is the latest one.
        open_price = df.iloc[-1]['open']  # Get the latest open price.

        # Same logic as defined in the definition of the strategy. This will set the trend.
        if open_price < lower_band:
            self.trend = BULLISH
        elif open_price > upper_band:
            self.trend = BEARISH
        else:
            self.trend = None

        return self.trend
