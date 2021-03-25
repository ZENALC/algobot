"""
This will be the main Trader class that all other Traders will inherit from.
"""


class Trader:
    def __init__(self, symbol, precision):
        self.symbol = symbol
        self.precision = precision

    def add_trade(self):
        raise NotImplementedError("Please implement a function for adding trades.")

    def buy_long(self):
        raise NotImplementedError("Please implement a function for buying long.")

    def sell_long(self):
        raise NotImplementedError("Please implement a function for selling long.")

    def sell_short(self):
        raise NotImplementedError("Please implement a function for selling short.")

    def buy_short(self):
        raise NotImplementedError("Please implement a function for buying short.")

    def get_stop_loss(self):
        pass

    def get_take_profit(self):
        pass

    def get_net(self):
        pass

    def get_trend(self):
        pass
