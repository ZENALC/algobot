"""
This will be the main Trader class that all other Traders will inherit from.
"""


class Trader:
    def __init__(self, symbol, precision):
        self.symbol = symbol
        self.precision = precision

    def add_trade(self):
        pass

    def buy_long(self):
        pass

    def sell_long(self):
        pass

    def sell_short(self):
        pass

    def buy_short(self):
        pass

    def get_stop_loss(self):
        pass

    def get_take_profit(self):
        pass

    def get_net(self):
        pass

    def get_trend(self):
        pass
