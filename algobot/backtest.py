from helpers import load_from_csv
from option import Option
from enums import BEARISH, BULLISH, LONG, SHORT, TRAILING_LOSS


class Backtester:
    def __init__(self, startingBalance: float, data: list, lossStrategy: int, lossPercentage: float, options: list):
        self.startingBalance = startingBalance
        self.balance = startingBalance
        self.currentPrice = None
        self.transactionFeePercentage = 0.001
        self.coin = 0
        self.coinOwed = 0
        self.profit = 0
        self.data = data
        self.lossStrategy = lossStrategy
        self.lossPercentage = lossPercentage
        self.options = options
        self.validate_options()
        self.minPeriod = self.get_min_option_period()
        self.trend = None
        self.commissionsPaid = 0
        self.trades = []

        self.inLongPosition = False
        self.inShortPosition = False
        self.previousPosition = None

        self.buyLongPrice = None
        self.longTrailingPrice = None

        self.sellShortPrice = None
        self.shortTrailingPrice = None
        self.currentPeriod = None

    def validate_options(self):
        for option in self.options:
            if type(option) != Option:
                raise TypeError(f"'{option}' is not a valid option type.")

    def get_min_option_period(self):
        minimum = 0
        for option in self.options:
            if option.finalBound > minimum:
                minimum = option.finalBound
            if option.initialBound > minimum:
                minimum = option.initialBound
        return minimum

    def get_moving_average(self, data: list, average: str, prices: int, parameter: str):
        if average == 'sma':
            return self.get_sma(data, prices, parameter)
        elif average == 'ema':
            return self.get_ema(data, prices, parameter)
        elif average == 'wma':
            return self.get_wma(data, prices, parameter)
        else:
            raise ValueError('Invalid average.')

    def check_trend(self, seenData):
        trends = []
        for option in self.options:
            avg1 = self.get_moving_average(seenData, option.movingAverage, option.initialBound, option.parameter)
            avg2 = self.get_moving_average(seenData, option.movingAverage, option.finalBound, option.parameter)
            if avg1 > avg2:
                trends.append(BULLISH)
            elif avg1 < avg2:
                trends.append(BEARISH)
            else:
                trends.append(None)

        if all(trend == BULLISH for trend in trends):
            self.trend = BULLISH
        elif all(trend == BEARISH for trend in trends):
            self.trend = BEARISH

    def go_long(self, msg):
        usd = self.balance  # current balance
        transactionFee = usd * self.transactionFeePercentage  # get commission fee
        self.commissionsPaid += transactionFee  # add commission fee to commissions paid total
        self.inLongPosition = True
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.coin += (usd - transactionFee) / self.currentPrice
        self.balance -= usd
        self.add_trade(msg)

    def exit_long(self, msg):
        coin = self.coin
        transactionFee = self.currentPrice * coin * self.transactionFeePercentage
        self.commissionsPaid += transactionFee
        self.inLongPosition = False
        self.previousPosition = LONG
        self.balance += coin * self.currentPrice - transactionFee
        self.coin -= coin
        self.add_trade(msg)

        if self.coin == 0:
            self.buyLongPrice = None
            self.longTrailingPrice = None

    def go_short(self, msg):
        transactionFee = self.balance * self.transactionFeePercentage
        coin = (self.balance - transactionFee) / self.currentPrice
        self.commissionsPaid += transactionFee
        self.coinOwed += coin
        self.balance += self.currentPrice * coin - transactionFee
        self.inShortPosition = True
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.add_trade(msg)

    def exit_short(self, msg):
        coin = self.coinOwed
        self.coinOwed -= coin
        self.inShortPosition = False
        self.previousPosition = SHORT
        loss = self.currentPrice * coin * (1 + self.transactionFeePercentage)
        self.balance -= loss
        self.add_trade(msg)

        if self.coinOwed == 0:
            self.sellShortPrice = None
            self.shortTrailingPrice = None

    def get_stop_loss(self):
        if self.inShortPosition:  # If we are in a short position
            if self.shortTrailingPrice is None:
                self.shortTrailingPrice = self.currentPrice
                self.sellShortPrice = self.shortTrailingPrice
            if self.lossStrategy == TRAILING_LOSS:  # This means we use trailing loss.
                return self.shortTrailingPrice * (1 + self.lossPercentage)
            else:  # This means we use the basic stop loss.
                return self.sellShortPrice * (1 + self.lossPercentage)
        elif self.inLongPosition:  # If we are in a long position
            if self.longTrailingPrice is None:
                self.longTrailingPrice = self.currentPrice
                self.buyLongPrice = self.longTrailingPrice
            if self.lossStrategy == TRAILING_LOSS:  # This means we use trailing loss.
                return self.longTrailingPrice * (1 - self.lossPercentage)
            else:  # This means we use the basic stop loss.
                return self.buyLongPrice * (1 - self.lossPercentage)
        else:
            return None

    def main_logic(self):
        if self.inShortPosition:  # This means we are in short position
            if self.currentPrice > self.get_stop_loss():  # If current price is greater, then exit trade.
                self.exit_short('Exited short because of a stop loss.')

            elif self.trend == BULLISH:
                self.exit_short('Exited short because a cross was detected.')
                self.go_long('Entered long because a cross was detected.')

        elif self.inLongPosition:  # This means we are in long position
            if self.currentPrice < self.get_stop_loss():  # If current price is lower, then exit trade.
                self.exit_long('Exited long because of a stop loss.')

            elif self.trend == BEARISH:
                self.exit_long('Exited long because a cross was detected.')
                self.go_short('Entered short because a cross was detected.')

        else:  # This means we are in neither position
            if self.trend == BULLISH and self.previousPosition is not LONG:
                self.go_long('Entered long because a cross was detected.')
            elif self.trend == BEARISH and self.previousPosition is not SHORT:
                self.go_short('Entered short because a cross was detected.')

    def get_net(self):
        return self.coin * self.currentPrice - self.coinOwed * self.currentPrice + self.balance

    def add_trade(self, message):
        """
        Adds a trade to list of trades
        :param message: Message used for conducting trade.
        """
        self.trades.append({
            'date': self.currentPeriod['date_utc'],
            'action': message
        })

    def print_stats(self):
        print(f'Starting balance: ${round(self.startingBalance, 2)}')
        # print(f'Balance: ${round(self.balance, 2)}')
        print(f'Net: ${round(self.get_net(), 2)}')
        difference = round(self.get_net() - self.startingBalance, 2)
        if difference > 0:
            print(f'Profit: ${difference}')
        elif difference < 0:
            print(f'Loss: ${difference}')
        else:
            print("No profit or loss incurred.")
        # print(f'Coin owed: {round(self.coinOwed, 2)}')
        # print(f'Coin owned: {round(self.coin, 2)}')
        print(f'Commissions paid: ${round(self.commissionsPaid, 2)}')
        # print(f'Trend: {self.trend}')
        print(f'Trades made: {len(self.trades)}')
        print()

    def print_trades(self):
        for trade in self.trades:
            print(trade)

    def moving_average_test(self):
        seenData = self.data[:self.minPeriod][::-1]  # Start from minimum previous period data.
        end = self.minPeriod + 10
        for period in self.data[self.minPeriod:]:
            seenData.insert(0, period)
            self.currentPeriod = period
            self.currentPrice = period['open']
            self.check_trend(seenData)
            self.main_logic()
            # self.print_stats()

        if self.inShortPosition:
            self.exit_short('Exited short because of end of backtest.')
        elif self.inLongPosition:
            self.exit_long('Exiting long because of end of backtest.')

        self.print_stats()
        # self.print_trades()

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


path = r'C:\Users\Mihir Shrestha\PycharmProjects\CryptoAlgo\CSV\BTCUSDT_data_1h.csv'
testData = load_from_csv(path)
opt = [Option('sma', 'high', 1, 2), Option('wma', 'low', 4, 5)]
a = Backtester(data=testData, startingBalance=1000, lossStrategy=2, lossPercentage=0.02, options=opt)
a.moving_average_test()
