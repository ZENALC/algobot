# to implement
from helpers import load_from_csv
from option import Option


class Backtester:
    def __init__(self, startingBalance, data, lossStrategy, lossPercentage, options):
        self.startingBalance = startingBalance
        self.coin = 0
        self.coinOwed = 0
        self.profit = 0
        self.data = data
        self.lossStrategy = lossStrategy
        self.lossPercentage = lossPercentage
        self.options = options
        self.minPeriod = self.get_min_option_period()

    def get_min_option_period(self):
        minimum = 0
        for option in self.options:
            if option.finalBound > minimum:
                minimum = option.finalBound
            if option.initialBound > minimum:
                minimum = option.initialBound
        return minimum

    def moving_average_test(self, options=None):
        seenData = self.data[:self.minPeriod][::-1]  # Start from minimum previous period data.
        for period in self.data[self.minPeriod:10]:
            seenData.insert(0, period)
            avg1 = self.get_ema(seenData, prices=2, parameter='close')
            avg2 = self.get_sma(seenData, prices=2, parameter='close')
            avg3 = self.get_wma(seenData, prices=2, parameter='close')
            for x in seenData:
                print(x)
            print(f'ema: {avg1}')
            print(f'sma: {avg2}')
            print(f'wma: {avg3}\n')

        # for period in self.data[5:]:
        #     seenData.append(period)
        #     avg1 = self.get_sma(seenData, 2, 'close')
        #     avg2 = self.get_wma(seenData, 5, 'open')
        #     print(avg1)

    @staticmethod
    def get_sma(data: list, prices: int, parameter: str, round_value=True) -> float:
        data = data[0: prices]
        sma = sum([period[parameter] for period in data]) / prices
        if round_value:
            return round(sma, 2)
        return sma

    @staticmethod
    def get_wma(data: list, prices: int, parameter: str, round_value=True) -> float:
        total = data[0][parameter] * prices  # Current total is first data period multiplied by prices.
        data = data[1: prices]  # Data now does not include the first shift period.

        index = 0
        for x in range(prices - 1, 0, -1):
            total += x * data[index][parameter]
            index += 1

        divisor = prices * (prices + 1) / 2
        wma = total / divisor
        if round_value:
            return round(wma, 2)
        return wma

    def get_ema(self, data: list, prices: int, parameter: str, sma_prices: int = 5, round_value=True) -> float:
        if sma_prices <= 0:
            raise ValueError("Initial amount of SMA values for initial EMA must be greater than 0.")
        elif sma_prices > len(data):
            sma_prices = len(data) - 1

        ema = self.get_sma(data, sma_prices, parameter, round_value=False)
        multiplier = 2 / (prices + 1)

        for day in range(len(data) - sma_prices):
            current_index = len(data) - sma_prices - day - 1
            current_price = data[current_index][parameter]
            ema = current_price * multiplier + ema * (1 - multiplier)

        if round_value:
            return round(ema, 2)
        return ema


path = '/Users/mihirshrestha/PycharmProjects/CryptoAlgo/CSV/btc_data_1h.csv'
testData = load_from_csv(path)
opt = (Option('wma', 'close', 1, 2), Option('wma', 'close', 1, 2), )
a = Backtester(data=testData, startingBalance=1000, lossStrategy=2, lossPercentage=0.02, options=opt)
a.moving_average_test()
