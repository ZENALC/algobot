class Backtester:
    def __init__(self, startingBalance, data):
        self.startingBalance = startingBalance
        self.data = data
        self.coin = 0
        self.coinOwed = 0
        self.profit = 0

    def moving_average_test(self, options):
        for data in self.data:
            pass


