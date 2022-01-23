"""
This will be the main Trader class that all other Traders will inherit from.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from algobot.enums import BEARISH, BULLISH, ENTER_LONG, ENTER_SHORT, EXIT_LONG, EXIT_SHORT, LONG, SHORT, STOP, TRAILING
from algobot.helpers import get_label_string
from algobot.strategies.custom import CustomStrategy


class Trader:
    """
    Main Trader class that all other traders (sim, live, backtester) will subclass.
    """
    def __init__(self, symbol, precision, starting_balance, margin_enabled: bool = True):
        # Initialize initial values.
        self.starting_balance = starting_balance  # Balance we started bot with.
        self.balance = starting_balance  # USDT Balance.
        self.previous_net = starting_balance  # Our previous net will just be the starting balance in the beginning.
        self.coin = 0  # Amount of coin we own.
        self.coin_owed = 0  # Amount of coin we owe.
        self.transaction_fee_percentage_decimal = 0.001  # Binance transaction fee percentage.
        self.symbol = symbol.strip()  # Symbol of ticker used for trading.
        self.commissions_paid = 0  # Total commissions paid this bot run.
        self.precision = precision  # Precision to round data to.
        self.trades = []  # All trades performed.
        self.strategies: Dict[str, CustomStrategy] = {}

        self.starting_time = datetime.utcnow()  # Starting time in UTC.
        self.ending_time = None  # Ending time for previous bot run.
        self.current_period = None  # Current time period the bot is in used for backtesting.
        self.current_position: Optional[str] = None  # Current position value.
        self.min_period = 0  # Minimum amount of periods required for trend retrieval.
        self.previous_position = None  # Previous position to validate for a new trend.
        self.trend = None  # Current trend information.
        self.margin_enabled = margin_enabled  # Boolean for whether margin trading is enabled or not.

        self.take_profit_point = None  # Price at which bot will exit trade to secure profits.
        self.trailing_take_profit_activated = False  # Boolean that'll turn true if a stop order is activated.
        self.take_profit_type: Optional[int] = None  # Type of take profit: trailing or stop.
        self.take_profit_percentage_decimal: Optional[float] = None  # Percentage of profit to exit trade at.

        # Prices information.
        self.current_price: Optional[float] = None  # Current price of coin.
        self.buy_long_price: Optional[float] = None  # Price we last bought our target coin at in long position.
        self.sell_short_price: Optional[float] = None  # Price we last sold target coin at in short position.
        self.long_trailing_price: Optional[float] = None  # Price coin has to be above for long position.
        self.short_trailing_price: Optional[float] = None  # Price coin has to be below for short position.

        # Stop loss information.
        self.smart_stop_loss_initial_counter = 0  # Smart stop loss initial counter.
        self.smart_stop_loss_counter = 0  # Smart stop loss counter.
        self.smart_stop_loss_enter = False  # Boolean that'll determine whether position is from a smart stop loss.
        self.custom_stop_loss = None  # Custom stop loss to use if we want to exit trade before trailing or stop loss.
        self.previous_stop_loss = None  # Previous stop loss for smart stop loss.
        self.stop_loss = None  # Price at which bot will exit trade due to stop loss limits.
        self.stop_loss_exit = False  # Boolean that'll determine whether last position was exited from a stop loss.
        self.loss_percentage_decimal = None  # Loss percentage in decimal for stop loss.
        # Type of loss type we are using: whether it's trailing loss or stop loss.
        self.loss_strategy: Optional[str] = None
        self.safety_timer = None  # Timer to check if there's a true trend towards stop loss.
        self.scheduled_safety_timer = None  # Next time to check if it's a true stop loss.

    def add_trade(self, message: str, stop_loss_exit: bool = False, smart_enter: bool = False):
        """
        Adds a trade to list of trades
        :param smart_enter: Boolean that'll determine whether backtester is entering from a smart stop loss or not.
        :param stop_loss_exit: Boolean that'll determine where this trade occurred from a stop loss.
        :param message: Message used for conducting trade.
        """
        self.stop_loss_exit = stop_loss_exit
        self.smart_stop_loss_enter = smart_enter
        self.trades.append({
            'date': self.current_period['date_utc'],  # pylint: disable=unsubscriptable-object
            'action': message,
            'net': round(self.get_net(), self.precision)
        })

    def reset_trades(self):
        """
        Clears trades list.
        """
        self.trades = []

    def buy_long(self, message: str, smart_enter: bool = False):
        """
        Executes long position.
        :param smart_enter: Boolean that'll determine whether backtester is entering from a smart stop loss or not.
        :param message: Message that specifies why it entered long.
        """
        usd = self.balance
        transaction_fee = self.transaction_fee_percentage_decimal * usd
        self.commissions_paid += transaction_fee
        self.current_position = LONG
        self.coin += (usd - transaction_fee) / self.current_price
        self.balance -= usd
        self.buy_long_price = self.long_trailing_price = self.current_price
        self.add_trade(message, smart_enter=smart_enter)

    def sell_long(self, message: str, stop_loss_exit: bool = False):
        """
        Exits long position.
        :param stop_loss_exit: Boolean that'll determine whether a position was exited from a stop loss.
        :param message: Message that specifies why it exited long.
        """
        coin = self.coin
        transaction_fee = self.current_price * coin * self.transaction_fee_percentage_decimal
        self.commissions_paid += transaction_fee
        self.current_position = None
        self.previous_position = LONG
        self.coin -= coin
        self.balance += coin * self.current_price - transaction_fee
        self.buy_long_price = self.long_trailing_price = None
        self.add_trade(message, stop_loss_exit=stop_loss_exit)

    def sell_short(self, message: str, smart_enter: bool = False):
        """
        Executes short position.
        :param smart_enter: Boolean that'll determine whether backtester is entering from a smart stop loss or not.
        :param message: Message that specifies why it entered short.
        """
        transaction_fee = self.balance * self.transaction_fee_percentage_decimal
        coin = self.balance / self.current_price
        self.commissions_paid += transaction_fee
        self.current_position = SHORT
        self.coin_owed += coin
        self.balance += self.current_price * coin - transaction_fee
        self.sell_short_price = self.short_trailing_price = self.current_price
        self.add_trade(message, smart_enter=smart_enter)

    def buy_short(self, message: str, stop_loss_exit: bool = False):
        """
        Exits short position.
        :param stop_loss_exit: Boolean that'll determine whether a position was exited from a stop loss.
        :param message: Message that specifies why it exited short.
        """
        transaction_fee = self.coin_owed * self.current_price * self.transaction_fee_percentage_decimal
        coin = self.coin_owed
        self.commissions_paid += transaction_fee
        self.current_position = None
        self.previous_position = SHORT
        self.coin_owed -= coin
        self.balance -= self.current_price * coin + transaction_fee
        self.sell_short_price = self.short_trailing_price = None
        self.add_trade(message, stop_loss_exit=stop_loss_exit)

    def reset_smart_stop_loss(self):
        """
        Resets smart stop loss and sets it equal to initial stop loss counter.
        """
        self.smart_stop_loss_counter = self.smart_stop_loss_initial_counter

    def set_smart_stop_loss_counter(self, counter):
        """
        Sets smart stop loss counter to argument provided.
        :param counter: Initial value to set counter at. Bot will reenter its previous position that many times.
        """
        self.smart_stop_loss_counter = self.smart_stop_loss_initial_counter = counter

    def set_safety_timer(self, safety_timer: int):
        """
        Sets safety timer for bot to evaluate whether a stop loss is still apparent after the safety timer.
        :param safety_timer: Amount of seconds to wait after a stop loss is reached before exiting position.
        """
        if safety_timer == 0:
            self.safety_timer = None
        else:
            self.safety_timer = safety_timer

    def apply_take_profit_settings(self, take_profit_dict: Dict[str, int]):
        """
        Applies take profit settings based on take profit dictionary provided.
        :param take_profit_dict: Take profit settings dictionary.
        :return: None
        """
        self.take_profit_percentage_decimal = take_profit_dict["takeProfitPercentage"] / 100
        self.take_profit_type = take_profit_dict["takeProfitType"]

    def apply_loss_settings(self, loss_dict: Dict[str, int]):
        """
        Applies loss settings based on loss dictionary provided.
        :param loss_dict: Loss settings dictionary.
        :return: None
        """
        self.loss_strategy = loss_dict["lossType"]
        self.loss_percentage_decimal = loss_dict["lossPercentage"] / 100

        if 'smartStopLossCounter' in loss_dict:
            self.set_smart_stop_loss_counter(loss_dict['smartStopLossCounter'])

        if 'safetyTimer' in loss_dict:
            self.set_safety_timer(loss_dict['safetyTimer'])

    def setup_strategies(self, strategies: List[Dict[str, Any]], short_circuit: bool = False):
        """
        Sets up strategies from list of strategies provided.
        :param strategies: List of strategies to set up and apply to bot.
        :param short_circuit: Whether you want to short circuit strategy or not. More documentation can be found in
         the Custom strategy class.
        """
        if not isinstance(strategies, list):
            strategies = [strategies]

        for strategy_item in strategies:
            name = strategy_item['name']  # noqa
            self.strategies[name] = CustomStrategy(
                trader=self, values=strategy_item, short_circuit=short_circuit, precision=self.precision  # noqa
            )

            self.min_period = max(self.strategies[name].get_min_option_period(), self.min_period)

    def handle_trailing_prices(self):
        """
        Handles trailing prices based on the current price.
        """
        if self.long_trailing_price is not None and self.current_price > self.long_trailing_price:
            self.long_trailing_price = self.current_price
        if self.short_trailing_price is not None and self.current_price < self.short_trailing_price:
            self.short_trailing_price = self.current_price

    def get_stop_loss(self):
        """
        This function will return the stop loss for the current position the bot is in.
        :return: Stop loss value.
        """
        if self.loss_strategy is None or self.current_price is None or self.current_position is None:
            return None

        self.handle_trailing_prices()
        if self.current_position == SHORT:
            if self.smart_stop_loss_enter and self.previous_stop_loss > self.current_price:
                self.stop_loss = self.previous_stop_loss
            elif self.loss_strategy == TRAILING:
                self.stop_loss = self.short_trailing_price * (1 + self.loss_percentage_decimal)
            elif self.loss_strategy == STOP:
                self.stop_loss = self.sell_short_price * (1 + self.loss_percentage_decimal)
        elif self.current_position == LONG:
            if self.smart_stop_loss_enter and self.previous_stop_loss < self.current_price:
                self.stop_loss = self.previous_stop_loss
            elif self.loss_strategy == TRAILING:
                self.stop_loss = self.long_trailing_price * (1 - self.loss_percentage_decimal)
            elif self.loss_strategy == STOP:
                self.stop_loss = self.buy_long_price * (1 - self.loss_percentage_decimal)

        if self.stop_loss is not None:  # This is for the smart stop loss to reenter position.
            self.previous_stop_loss = self.stop_loss

        return self.stop_loss

    def get_stop_loss_strategy_string(self) -> str:
        """
        Returns stop loss strategy in string format, instead of integer enum.
        :return: Stop loss strategy in string format.
        """
        if self.loss_strategy == STOP:
            return 'Stop Loss'
        elif self.loss_strategy == TRAILING:
            return 'Trailing Loss'
        elif self.loss_strategy is None:
            return 'None'
        else:
            raise ValueError("Unknown type of loss strategy.")

    def get_net(self) -> float:
        """
        Returns net balance with current price of coin being traded. It factors in the current balance, the amount
        shorted, and the amount owned.
        :return: Net balance.
        """
        return self.coin * self.current_price - self.coin_owed * self.current_price + self.balance

    def get_strategy_inputs(self, strategy_name: str):
        """
        Returns provided strategy's inputs if it exists.
        """
        if strategy_name not in self.strategies:
            return 'Strategy not found.'
        else:
            return self.strategies[strategy_name].values

    def get_strategies_info_string(self, left: str = '\t', right: str = '\n'):
        """
        Returns a formatted string with strategies information.
        :param left: Character to add before each new line in strategies information.
        :param right: Character to add after each new line in strategies information.
        """
        string = f'Strategies:{right}'
        for strategy_name in self.strategies:
            string += f'{left}{get_label_string(strategy_name)}: {self.get_strategy_inputs(strategy_name)}{right}'

        return string.rstrip()  # Remove new line in the very end.

    @staticmethod
    def get_cumulative_trend(trends: List[int]) -> Union[int, None]:
        """
        Returns cumulative trend based on the trends provided.
        :return: Integer trend in the form of an enum.
        """
        # pylint: disable=too-many-return-statements
        if len(trends) == 0:
            return None
        if all(trend == BEARISH for trend in trends):
            return BEARISH
        if all(trend == BULLISH for trend in trends):
            return BULLISH
        if all(trend in (BULLISH, ENTER_LONG) for trend in trends):
            return ENTER_LONG
        if all(trend in (BEARISH, EXIT_LONG) for trend in trends):
            return EXIT_LONG
        if all(trend in (BULLISH, EXIT_SHORT) for trend in trends):
            return EXIT_SHORT
        if all(trend in (BEARISH, ENTER_SHORT) for trend in trends):
            return ENTER_SHORT
        return None

    @staticmethod
    def get_profit_percentage(initial_net: float, final_net: float) -> float:
        """
        Calculates net percentage from initial and final values and returns it.
        :param initial_net: Initial net value.
        :param final_net: Final net value.
        :return: Profit percentage.
        """
        if final_net >= initial_net:
            return final_net / initial_net * 100 - 100
        else:
            return -1 * (100 - final_net / initial_net * 100)

    @staticmethod
    def get_enum_from_str(string: str):
        """
        Get enum from string. # TODO: Deprecate. (inverse will handle this).
        :param string: String to convert to an enum.
        :return: Enum from string provided.
        """
        if string.lower() == "trailing":
            return TRAILING
        elif string.lower() == 'stop':
            return STOP

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
        Returns position in string format instead of an enum.
        :return: Position in string format.
        """
        return str(self.current_position)

    def get_position(self) -> int:
        """
        Returns current position.
        :return: Current position integer bot is in.
        """
        return self.current_position

    def get_safe_rounded_percentage(self, decimal_value: float) -> str:
        """
        Converts decimal value provided to a percentage.
        :param decimal_value: Percentage in decimal format.
        :return: Rounded percentage value in a string format.
        """
        return self.get_safe_rounded_string(decimal_value, direction='right', multiplier=100, symbol='%')

    def get_safe_rounded_string(self, value: Optional[float],
                                round_digits: int = None,
                                symbol: str = '$',
                                direction: str = 'left',
                                multiplier: float = 1) -> str:
        """
        Helper function that will, if exists, return value rounded with symbol provided.
        :param multiplier: Optional value to multiply final value with before return.
        :param direction: Direction to add the safe rounded string: left or right.
        :param round_digits: Number of digits to round value.
        :param symbol: Symbol to insert to beginning of return string.
        :param value: Value that will be safety checked.
        :return: Rounded value (if not none) in string format.
        """
        if round_digits is None:
            round_digits = self.precision

        if value is None:
            return "None"
        else:
            if direction == 'left':
                return f'{symbol}{round(value * multiplier, round_digits)}'
            else:
                return f'{round(value * multiplier, round_digits)}{symbol}'

    def get_take_profit(self) -> Union[float, None]:
        """
        Returns price at which position will be exited to secure profits.
        :return: Price at which to exit position.
        """
        if self.take_profit_type is None:
            return None

        if self.current_position == SHORT:
            if self.take_profit_type == STOP:
                self.take_profit_point = self.sell_short_price * (1 - self.take_profit_percentage_decimal)
            else:
                raise ValueError("Invalid type of take profit type provided.")
        elif self.current_position == LONG:
            if self.take_profit_type == STOP:
                self.take_profit_point = self.buy_long_price * (1 + self.take_profit_percentage_decimal)
            else:
                raise ValueError("Invalid type of take profit type provided.")
        else:
            self.take_profit_point = None

        return self.take_profit_point

    def get_trend(self) -> Union[int, None]:
        """
        Returns trend based on the strategies provided.
        :return: Integer in the form of an enum.
        """
        trends = [strategy.trend for strategy in self.strategies.values()]
        return self.get_cumulative_trend(trends)
