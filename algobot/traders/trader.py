"""
This will be the main Trader class that all other Traders will inherit from.
"""


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

    def get_stop_loss(self):
        pass

    def get_take_profit(self):
        pass

    def get_net(self):
        pass

    def get_trend(self):
        pass
