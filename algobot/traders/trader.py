"""
This will be the main Trader class that all other Traders will inherit from.
"""
from datetime import datetime
from typing import Dict, List, Union

from algobot.enums import BEARISH, BULLISH, LONG, SHORT, STOP, TRAILING
from algobot.helpers import get_label_string, parse_strategy_name
from algobot.option import Option
from algobot.strategies.strategy import Strategy


class Trader:
    def __init__(self, symbol, precision, startingBalance):
        # Initialize initial values.
        self.startingBalance = startingBalance  # Balance we started bot with.
        self.balance = startingBalance  # USDT Balance.
        self.coin = 0  # Amount of coin we own.
        self.coinOwed = 0  # Amount of coin we owe.
        self.transactionFeePercentage = 0.001  # Binance transaction fee percentage.
        self.symbol = symbol  # Symbol of ticker used for trading.
        self.precision = precision  # Precision to round data to.
        self.trades = []  # All trades performed.
        self.strategies: Dict[str, Strategy] = {}

        self.startingTime = datetime.utcnow()  # Starting time in UTC.
        self.endingTime = None  # Ending time for previous bot run.
        self.currentPosition = None  # Current position value.
        self.minPeriod = 0  # Minimum amount of periods required for trend retrieval.
        self.previousPosition = None  # Previous position to validate for a new trend.

        self.takeProfitPoint = None  # Price at which bot will exit trade to secure profits.
        self.trailingTakeProfitActivated = False  # Boolean that'll turn true if a stop order is activated.
        self.takeProfitType = None  # Type of take profit: trailing or stop.
        self.takeProfitPercentageDecimal = None  # Percentage of profit to exit trade at.

        # Prices information.
        self.currentPrice = None  # Current price of coin.
        self.buyLongPrice = None  # Price we last bought our target coin at in long position.
        self.sellShortPrice = None  # Price we last sold target coin at in short position.
        self.longTrailingPrice = None  # Price coin has to be above for long position.
        self.shortTrailingPrice = None  # Price coin has to be below for short position.

        # Stop loss information.
        self.smartStopLossInitialCounter = 0  # Smart stop loss initial counter.
        self.smartStopLossCounter = 0  # Smart stop loss counter.
        self.previousStopLoss = None  # Previous stop loss for smart stop loss.
        self.stopLossExit = False  # Boolean that'll determine whether last position was exited from a stop loss.
        self.lossPercentageDecimal = None  # Loss percentage in decimal for stop loss.
        self.lossStrategy = None  # Type of loss type we are using: whether it's trailing loss or stop loss.
        self.safetyTimer = None  # Timer to check if there's a true trend towards stop loss.

    def add_trade(self, **kwargs):
        raise NotImplementedError("Please implement a function for adding trades.")

    def buy_long(self, **kwargs):
        raise NotImplementedError("Please implement a function for buying long.")

    def sell_long(self, **kwargs):
        raise NotImplementedError("Please implement a function for selling long.")

    def sell_short(self, **kwargs):
        raise NotImplementedError("Please implement a function for selling short.")

    def buy_short(self, **kwargs):
        raise NotImplementedError("Please implement a function for buying short.")

    def reset_smart_stop_loss(self):
        """
        Resets smart stop loss and sets it equal to initial stop loss counter.
        """
        self.smartStopLossCounter = self.smartStopLossInitialCounter

    def set_smart_stop_loss_counter(self, counter):
        """
        Sets smart stop loss counter to argument provided.
        :param counter: Initial value to set counter at. Bot will reenter its previous position that many times.
        """
        self.smartStopLossCounter = self.smartStopLossInitialCounter = counter

    def set_safety_timer(self, safetyTimer: int):
        """
        Sets safety timer for bot to evaluate whether a stop loss is still apparent after the safety timer.
        :param safetyTimer: Amount of seconds to wait after a stop loss is reached before exiting position.
        """
        if safetyTimer == 0:
            self.safetyTimer = None
        else:
            self.safetyTimer = safetyTimer

    def apply_take_profit_settings(self, takeProfitDict: Dict[str, int]):
        """
        Applies take profit settings based on take profit dictionary provided.
        :param takeProfitDict: Take profit settings dictionary.
        :return: None
        """
        self.takeProfitPercentageDecimal = takeProfitDict["takeProfitPercentage"] / 100
        self.takeProfitType = takeProfitDict["takeProfitType"]

    def apply_loss_settings(self, lossDict: Dict[str, int]):
        """
        Applies loss settings based on loss dictionary provided.
        :param lossDict: Loss settings dictionary.
        :return: None
        """
        self.lossStrategy = lossDict["lossType"]
        self.lossPercentageDecimal = lossDict["lossPercentage"] / 100

        if 'smartStopLossCounter' in lossDict:
            self.set_smart_stop_loss_counter(lossDict['smartStopLossCounter'])

        if 'safetyTimer' in lossDict:
            self.set_safety_timer(lossDict['safetyTimer'])

    def setup_strategies(self, strategies: list):
        """
        Sets up strategies from list of strategies provided.
        :param strategies: List of strategies to set up and apply to bot.
        """
        for strategyTuple in strategies:
            strategyClass = strategyTuple[0]
            values = strategyTuple[1]
            name = parse_strategy_name(strategyTuple[2])

            if name != 'movingAverage':
                self.strategies[name] = strategyClass(self, inputs=values, precision=self.precision)
            else:
                values = [Option(*values[x:x + 4]) for x in range(0, len(values), 4)]
                self.strategies[name] = strategyClass(self, inputs=values, precision=self.precision)
                self.minPeriod = self.strategies[name].get_min_option_period()

    def get_stop_loss(self):
        raise NotImplementedError("Please make sure to implement a function for getting the stop loss.")

    def get_stop_loss_strategy_string(self) -> str:
        """
        Returns stop loss strategy in string format, instead of integer enum.
        :return: Stop loss strategy in string format.
        """
        if self.lossStrategy == STOP:
            return 'Stop Loss'
        elif self.lossStrategy == TRAILING:
            return 'Trailing Loss'
        elif self.lossStrategy is None:
            return 'None'
        else:
            raise ValueError("Unknown type of loss strategy.")

    def get_strategy_inputs(self, strategy_name: str):
        """
        Returns provided strategy's inputs if it exists.
        """
        if strategy_name not in self.strategies:
            return 'Strategy not found.'
        else:
            return f"{', '.join(map(str, self.strategies[strategy_name].get_params()))}"

    def get_strategies_info_string(self, left: str = ''):
        """
        Returns a formatted string with strategies information.
        :param left: Character to add before each new line in strategies information.
        """
        string = '\nStrategies:\n'
        for strategyName, strategy in self.strategies.items():
            string += f'{left}\t{get_label_string(strategyName)}: {strategy.get_params()}\n'

        return string.rstrip()  # Remove new line in the very end.

    @staticmethod
    def get_cumulative_trend(trends: List[int]) -> Union[int, None]:
        """
        Returns cumulative trend based on the trends provided.
        :return: Integer trend in the form of an enum.
        """
        if len(trends) == 0:
            return None

        if all(trend == BEARISH for trend in trends):
            return BEARISH
        elif all(trend == BULLISH for trend in trends):
            return BULLISH
        else:
            return None

    @staticmethod
    def get_profit_percentage(initialNet: float, finalNet: float) -> float:
        """
        Calculates net percentage from initial and final values and returns it.
        :param initialNet: Initial net value.
        :param finalNet: Final net value.
        :return: Profit percentage.
        """
        if finalNet >= initialNet:
            return finalNet / initialNet * 100 - 100
        else:
            return -1 * (100 - finalNet / initialNet * 100)

    @staticmethod
    def get_trailing_or_stop_type_string(stopType: Union[int, None]) -> str:
        """
        Returns stop type in string format instead of integer enum.
        :return: Stop type in string format.
        """
        if stopType == STOP:
            return 'Stop'
        elif stopType == TRAILING:
            return 'Trailing'
        elif stopType is None:
            return 'None'
        else:
            raise ValueError("Unknown type of exit position type.")

    @staticmethod
    def get_trend_string(trend) -> str:
        """
        Returns current market trend in a string format.
        :param trend: Current trend enum.
        :return: Current trend in a string format.
        """
        if trend == BULLISH:
            return "Bullish"
        elif trend == BEARISH:
            return 'Bearish'
        elif trend is None:
            return 'None'
        else:
            raise ValueError('Unknown type of trend.')

    @staticmethod
    def get_profit_or_loss_string(profit: float) -> str:
        """
        Helper function that returns where profit specified is profit or loss. Profit is positive; loss if negative.
        :param profit: Amount to be checked for negativity or positivity.
        :return: String value of whether profit ir positive or negative.
        """
        return "Profit" if profit >= 0 else "Loss"

    def get_position_string(self) -> str:
        """
        Returns position in string format, instead of integer enum.
        :return: Position in string format.
        """
        if self.currentPosition == LONG:
            return 'Long'
        elif self.currentPosition == SHORT:
            return 'Short'
        elif self.currentPosition is None:
            return 'None'
        else:
            raise ValueError("Invalid type of current position.")

    def get_position(self) -> int:
        """
        Returns current position.
        :return: Current position integer bot is in.
        """
        return self.currentPosition

    def get_safe_rounded_percentage(self, decimalValue: float) -> str:
        """
        Converts decimal value provided to a percentage.
        :param decimalValue: Percentage in decimal format.
        :return: Rounded percentage value in a string format.
        """
        return self.get_safe_rounded_string(decimalValue, direction='right', multiplier=100, symbol='%')

    def get_safe_rounded_string(self, value: float, roundDigits: int = None, symbol: str = '$', direction: str = 'left',
                                multiplier: float = 1) -> str:
        """
        Helper function that will, if exists, return value rounded with symbol provided.
        :param multiplier: Optional value to final value with before return.
        :param direction: Direction to add the safe rounded string: left or right.
        :param roundDigits: Number of digits to round value.
        :param symbol: Symbol to insert to beginning of return string.
        :param value: Value that will be safety checked.
        :return: Rounded value (if not none) in string format.
        """
        if roundDigits is None:
            roundDigits = self.precision

        if value is None:
            return "None"
        else:
            if direction == 'left':
                return f'{symbol}{round(value * multiplier, roundDigits)}'
            else:
                return f'{round(value * multiplier, roundDigits)}{symbol}'

    def get_take_profit(self) -> Union[float, None]:
        """
        Returns price at which position will be exited to secure profits.
        :return: Price at which to exit position.
        """
        if self.takeProfitType is None:
            return None

        if self.currentPosition == SHORT:
            if self.takeProfitType == STOP:
                self.takeProfitPoint = self.sellShortPrice * (1 - self.takeProfitPercentageDecimal)
            else:
                raise ValueError("Invalid type of take profit type provided.")
        elif self.currentPosition == LONG:
            if self.takeProfitType == STOP:
                self.takeProfitPoint = self.buyLongPrice * (1 + self.takeProfitPercentageDecimal)
            else:
                raise ValueError("Invalid type of take profit type provided.")
        else:
            self.takeProfitPoint = None

        return self.takeProfitPoint

    def get_net(self):
        pass

    def get_trend(self):
        raise NotImplementedError("Please implement a function for getting a trend for your Trader class.")
