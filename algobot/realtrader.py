import math
# import credentials
from enums import *
from simulationtrader import SimulatedTrader
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from helpers import *


class RealTrader(SimulatedTrader):
    def __init__(self, apiKey=None, apiSecret=None, interval='1h', symbol='BTCUSDT'):
        apiKey = credentials.apiKey
        apiSecret = credentials.apiSecret
        if apiKey is None or apiSecret is None:
            self.output_message('API details incorrect.', 5)
            return

        super().__init__(interval=interval, symbol=symbol)
        self.binanceClient = Client(apiKey, apiSecret)
        self.spot_usdt = self.get_spot_usdt()
        self.spot_coin = self.get_spot_coin()
        self.isolated = self.is_isolated()

        if self.spot_usdt > 10:
            self.initial_transfer()

        self.set_margin_values()

        self.startingBalance = self.get_starting_balance()
        self.check_initial_position()
        self.netWorth = round(self.coin * self.currentPrice - self.coinOwed * self.currentPrice + self.balance, 2)

        if not self.has_enough_money():
            raise ValueError(f"You only have ${self.netWorth}. Please make sure you have at least $10 in your account.")

    def has_enough_money(self):
        if self.netWorth < 10:
            return False
        return True

    def is_isolated(self):
        try:  # Attempt to get coin from regular cross margin account.
            assets = self.binanceClient.get_margin_account()['userAssets']
            coin = [asset for asset in assets if asset['asset'] == self.coinName][0]
            return False
        except IndexError:
            return True

    def get_starting_balance(self):
        """
        Returns the initial starting balance for bot.
        :return: initial starting balance for bot
        """
        self.currentPrice = self.dataView.get_current_price()
        usdt = self.coin * self.currentPrice + self.balance
        usdt -= self.coinOwed * self.currentPrice
        return usdt

    @staticmethod
    def round_down(num, digits=6):
        factor = 10.0 ** digits
        return math.floor(float(num) * factor) / factor

    def add_trade(self, message, order=None):
        """
        Adds a trade to list of trades
        :param order: Optional order from Binance API.
        :param message: Message used for conducting trade.
        """
        self.trades.append({
            'date': datetime.utcnow(),
            'action': message,
            'order': order
        })

    def main_logic(self):
        if self.inShortPosition:  # This means we are in short position
            if self.currentPrice > self.get_stop_loss():  # If current price is greater, then exit trade.
                self.buy_short(f'Bought short because of stop loss.', stopLoss=True)
                self.waitToEnterShort = True

            if self.check_cross_v2():
                self.buy_short(f'Bought short because a cross was detected.')
                self.buy_long(f'Bought long because a cross was detected.')

        elif self.inLongPosition:  # This means we are in long position
            if self.currentPrice < self.get_stop_loss():  # If current price is lower, then exit trade.
                self.sell_long(f'Sold long because of stop loss.', stopLoss=True)
                self.waitToEnterLong = True

            if self.check_cross_v2():
                self.sell_long(f'Sold long because a cross was detected.')
                self.sell_short('Sold short because a cross was detected.')

        else:  # This means we are in neither position
            if self.check_cross_v2():
                if self.trend == BULLISH:  # This checks if we are bullish or bearish
                    self.buy_long("Bought long because a cross was detected.")
                else:
                    self.sell_short("Sold short because a cross was detected.")

    def check_initial_position(self):
        self.currentPrice = self.dataView.get_current_price()
        if self.get_margin_coin() * self.currentPrice >= 10:
            self.inLongPosition = True
            self.currentPrice = self.dataView.get_current_price()
            self.buyLongPrice = self.currentPrice
            self.longTrailingPrice = self.buyLongPrice
            self.add_trade('Was in long position from start of bot.')

        elif self.get_borrowed_margin_coin() * self.currentPrice >= 10:
            self.inShortPosition = True
            self.currentPrice = self.dataView.get_current_price()
            self.sellShortPrice = self.currentPrice
            self.shortTrailingPrice = self.sellShortPrice
            self.add_trade('Was in short position from start of bot.')

    def get(self, target):
        assets = self.binanceClient.get_margin_account()['userAssets']
        coin = [asset for asset in assets if asset['asset'] == target][0]
        return coin

    def get_spot_usdt(self):
        return self.round_down(self.binanceClient.get_asset_balance(asset='USDT')['free'])

    def get_spot_coin(self):
        return self.round_down(self.binanceClient.get_asset_balance(asset=self.coinName)['free'])

    def spot_buy_long(self):
        self.spot_usdt = self.get_spot_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_buy = self.round_down(self.spot_usdt * (1 - 0.001) / self.currentPrice)

        order = self.binanceClient.order_market_buy(
            symbol=self.symbol,
            quantity=max_buy
        )

        self.add_trade('Bought spot long', order=order)

    def spot_sell_long(self):
        self.spot_coin = self.get_spot_coin()
        order = self.binanceClient.order_market_sell(
            symbol=self.symbol,
            quantity=self.spot_coin
        )

        self.add_trade('Sold spot long', order=order)

    def initial_transfer(self):
        self.spot_buy_long()
        self.transfer_spot_to_margin()

    def transfer_spot_to_margin(self):
        order = self.binanceClient.transfer_spot_to_margin(asset=self.coinName, amount=self.get_spot_coin())
        self.add_trade('Transferred from spot to margin', order=order)

    def transfer_margin_to_spot(self):
        order = self.binanceClient.transfer_margin_to_spot(asset=self.coinName, amount=self.get_margin_coin())
        self.add_trade('Transferred from margin to spot', order=order)

    def get_isolated_margin_account(self, **params):
        return self.binanceClient._request_margin_api('get', 'margin/isolated/account', True, data=params)

    def set_margin_values(self):
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            coin = [asset for asset in assets if asset['baseAsset']['asset'] == self.coinName][0]['baseAsset']
            usdt = [asset for asset in assets if asset['baseAsset']['asset'] == self.coinName and
                    asset['quoteAsset']['asset'] == 'USDT'][0]['quoteAsset']
        else:
            assets = self.binanceClient.get_margin_account()['userAssets']
            coin = [asset for asset in assets if asset['asset'] == self.coinName][0]
            usdt = [asset for asset in assets if asset['asset'] == 'USDT'][0]

        self.balance = self.round_down(float(usdt['free']))
        self.coin = self.round_down(float(coin['free']))
        self.coinOwed = self.round_down(float(coin['borrowed']))

    def get_margin_usdt(self):
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            for asset in assets:
                if asset['baseAsset']['asset'] == self.coinName and asset['quoteAsset']['asset'] == 'USDT':
                    return self.round_down(float(asset['quoteAsset']['free']))
        else:
            assets = self.binanceClient.get_margin_account()['userAssets']
            return self.round_down(float([asset for asset in assets if asset['asset'] == 'USDT'][0]))

    def get_margin_coin_info(self):
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            return [asset for asset in assets if asset['baseAsset']['asset'] == self.coinName][0]['baseAsset']
        else:
            assets = self.binanceClient.get_margin_account()['userAssets']
            return [asset for asset in assets if asset['asset'] == self.coinName][0]

    def get_margin_coin(self):
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['free']))

    def get_borrowed_margin_coin(self):
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['borrowed']))

    def get_borrowed_margin_interest(self):
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['interest']))

    def buy_long(self, msg, usd=None):
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_buy = self.round_down(self.balance / self.currentPrice)

        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=max_buy,
            isIsolated=self.isolated
        )

        self.add_trade(msg, order=order)
        self.coin = self.get_margin_coin()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.balance = self.get_margin_usdt()
        self.inLongPosition = True
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.output_message(msg)

    def sell_long(self, msg, coin=None, stopLoss=False):
        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=self.get_margin_coin(),
            isIsolated=self.isolated
        )

        self.add_trade(msg, order=order)
        self.coin = self.get_margin_coin()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.balance = self.get_margin_usdt()
        self.inLongPosition = False
        self.previousPosition = LONG
        self.buyLongPrice = None
        self.longTrailingPrice = None
        self.output_message(msg)

    def sell_short(self, msg, coin=None):
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_borrow = self.round_down(self.balance / self.currentPrice - self.get_borrowed_margin_coin())
        try:
            if self.isolated:
                order = self.binanceClient.create_margin_loan(asset=self.coinName, amount=max_borrow,
                                                              isIsolated=self.isolated, symbol=self.symbol)
            else:
                order = self.binanceClient.create_margin_loan(asset=self.coinName, amount=max_borrow)
            self.add_trade(f'Borrowed {self.coinName}.', order=order)
        except BinanceAPIException as e:
            print(f"Borrowing failed because {e}")
            self.output_message(f'Borrowing failed because {e}')

        order = self.binanceClient.create_margin_order(
            side=SIDE_SELL,
            symbol=self.symbol,
            type=ORDER_TYPE_MARKET,
            quantity=self.round_down(self.get_margin_coin()),
            isIsolated=self.isolated
        )

        self.add_trade(msg, order=order)
        self.balance = self.get_margin_usdt()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.coin = self.get_margin_coin()
        self.inShortPosition = True
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.output_message(msg)

    def buy_short(self, msg, coin=None, stopLoss=False):
        self.coinOwed = self.get_borrowed_margin_coin()
        difference = (self.coinOwed + self.get_borrowed_margin_interest()) * (1 + self.transactionFeePercentage)

        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=self.round_down(difference),
            isIsolated=self.isolated
        )
        self.add_trade(f'Bought {self.coinName} to repay loan', order=order)
        self.coin = self.get_margin_coin()

        try:
            if self.isolated:
                order = self.binanceClient.repay_margin_loan(
                    asset=self.coinName,
                    amount=self.coin,
                    isIsolated=self.isolated,
                    symbol=self.symbol
                )
            else:
                order = self.binanceClient.repay_margin_loan(
                    asset=self.coinName,
                    amount=self.coin
                )
            self.add_trade(msg, order=order)
        except BinanceAPIException as e:
            print(e)
            self.output_message(f"Repaying Failed because of {e}.")

        self.coinOwed = self.get_borrowed_margin_coin()
        self.coin = self.get_margin_coin()
        self.balance = self.get_margin_usdt()
        self.inShortPosition = False
        self.previousPosition = SHORT
        self.output_message(msg)
        self.sellShortPrice = None
        self.shortTrailingPrice = None
