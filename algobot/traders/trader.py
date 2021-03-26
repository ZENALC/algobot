"""
This will be the main Trader class that all other Traders will inherit from.
"""
from typing import Dict

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

        self.previousPosition = None  # Previous position to validate for a new trend.

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

    def get_stop_loss(self):
        pass

    def get_take_profit(self):
        pass

    def get_net(self):
        pass

    def get_trend(self):
        pass
