import math
from enums import *
from simulationtrader import SimulationTrader
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException


# from helpers import *


class RealTrader(SimulationTrader):
    def __init__(self, apiKey, apiSecret, interval='1h', symbol='BTCUSDT'):
        if apiKey is None or apiSecret is None:
            raise ValueError('API credentials not provided.')

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

    def transfer_spot_to_margin(self):
        """
        Transfer assets from spot account to margin account.
        """
        order = self.binanceClient.transfer_spot_to_margin(asset=self.coinName, amount=self.get_spot_coin())
        self.add_trade(message='Transferred from spot to margin',
                       initialNet=self.get_net(),
                       finalNet=self.get_net(),
                       price=self.currentPrice,
                       force=False,
                       orderID=order['clientOrderId'])

    def transfer_margin_to_spot(self):
        """
        Transfers assets from margin account to spot account.
        """
        order = self.binanceClient.transfer_margin_to_spot(asset=self.coinName, amount=self.get_margin_coin())
        self.add_trade(message='Transferred from margin to spot',
                       initialNet=self.get_net(),
                       finalNet=self.get_net(),
                       price=self.currentPrice,
                       force=False,
                       orderID=order['clientOrderId'])

    def has_enough_money(self) -> bool:
        """
        Live trading requires at least $10. This function checks if our net balance is over or equal to $10.
        :return: Boolean whether we have at least $10.
        """
        return self.get_net() >= 10

    def is_isolated(self) -> bool:
        """
        Checks whether the coin we are trying to trade is isolated or not.
        :return: A boolean whether it is isolated or not.
        """
        try:  # Attempt to get coin from regular cross margin account.
            assets = self.binanceClient.get_margin_account()['userAssets']
            _ = [asset for asset in assets if asset['asset'] == self.coinName][0]
            return False
        except IndexError:  # If not found, it most likely means it is not in the cross margin account.
            return True

    def get_starting_balance(self) -> float:
        """
        Returns the initial starting balance for bot.
        :return: initial starting balance for bot
        """
        self.currentPrice = self.dataView.get_current_price()
        usdt = self.coin * self.currentPrice + self.balance
        usdt -= self.coinOwed * self.currentPrice
        return usdt

    @staticmethod
    def round_down(num: int, digits: int = 6) -> float:
        """
        Rounds down number for trading purposes.
        :param num: Number to be rounded down.
        :param digits: Number of digits to leave for rounding.
        :return: Rounded down number.
        """
        factor = 10.0 ** digits
        return math.floor(float(num) * factor) / factor

    def check_initial_position(self):
        """
        Checks initial position to check if bot is in a long, short, or neither position.
        """
        self.currentPrice = self.dataView.get_current_price()
        if self.get_margin_coin() * self.currentPrice >= 10:
            self.currentPosition = LONG
            self.buyLongPrice = self.currentPrice
            self.longTrailingPrice = self.buyLongPrice

        elif self.get_borrowed_margin_coin() * self.currentPrice >= 10:
            self.currentPosition = SHORT
            self.sellShortPrice = self.currentPrice
            self.shortTrailingPrice = self.sellShortPrice

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

    def buy_long(self, msg, usd=None, force=False):
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        initialNet = self.get_net()
        max_buy = self.round_down(self.balance / self.currentPrice)

        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=max_buy,
            isIsolated=self.isolated
        )

        finalNet = self.get_net()
        self.add_trade(msg, initialNet, finalNet, self.currentPrice, force=force, orderID=order['clientOrderId'])
        self.coin = self.get_margin_coin()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.balance = self.get_margin_usdt()
        self.currentPosition = LONG
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.output_message(msg)

    def sell_long(self, msg, coin=None, force=False):
        initialNet = self.get_net()
        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=self.get_margin_coin(),
            isIsolated=self.isolated
        )
        finalNet = self.get_net()

        self.add_trade(msg, initialNet, finalNet, self.currentPrice, force=force, orderID=order['clientOrderId'])
        self.coin = self.get_margin_coin()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.balance = self.get_margin_usdt()
        self.currentPosition = None
        self.previousPosition = LONG
        self.buyLongPrice = None
        self.longTrailingPrice = None
        self.output_message(msg)

    def sell_short(self, msg, coin=None, force=False):
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_borrow = self.round_down(self.balance / self.currentPrice - self.get_borrowed_margin_coin())
        try:
            initialNet = self.get_net()
            if self.isolated:
                order = self.binanceClient.create_margin_loan(asset=self.coinName, amount=max_borrow,
                                                              isIsolated=self.isolated, symbol=self.symbol)
            else:
                order = self.binanceClient.create_margin_loan(asset=self.coinName, amount=max_borrow)
            finalNet = self.get_net()
            self.add_trade(msg, initialNet, finalNet, self.currentPrice, force=force, orderID=order['clientOrderId'])
        except BinanceAPIException as e:
            print(f"Borrowing failed because {e}")
            self.output_message(f'Borrowing failed because {e}')

        initialNet = self.get_net()
        order = self.binanceClient.create_margin_order(
            side=SIDE_SELL,
            symbol=self.symbol,
            type=ORDER_TYPE_MARKET,
            quantity=self.round_down(self.get_margin_coin()),
            isIsolated=self.isolated
        )
        finalNet = self.get_net()
        self.add_trade(msg, initialNet, finalNet, self.currentPrice, force=force, orderID=order['clientOrderId'])
        self.balance = self.get_margin_usdt()
        self.coinOwed = self.get_borrowed_margin_coin()
        self.coin = self.get_margin_coin()
        self.currentPosition = SHORT
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.output_message(msg)

    def buy_short(self, msg, coin=None, force=False):
        self.coinOwed = self.get_borrowed_margin_coin()
        difference = (self.coinOwed + self.get_borrowed_margin_interest()) * (1 + self.transactionFeePercentage)
        initialNet = self.get_net()
        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=self.round_down(difference),
            isIsolated=self.isolated
        )
        finalNet = self.get_net()
        self.add_trade(msg, initialNet, finalNet, self.currentPrice, force=force, orderID=order['clientOrderId'])
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
        self.currentPosition = None
        self.previousPosition = SHORT
        self.output_message(msg)
        self.sellShortPrice = None
        self.shortTrailingPrice = None
