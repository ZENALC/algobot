import math

from enums import *
from simulationtrader import SimulationTrader
from binance.client import Client
from binance.enums import *


class RealTrader(SimulationTrader):
    def __init__(
            self,
            apiKey: str,
            apiSecret: str,
            interval: str = '1h',
            symbol: str = 'BTCUSDT',
            isIsolated: bool = False,
            tld: str = 'com'):

        # from credentials import apiKey, apiSecret
        if apiKey is None or apiSecret is None:
            raise ValueError('API credentials not provided.')

        super().__init__(interval=interval, symbol=symbol, logFile='live')
        self.binanceClient = Client(apiKey, apiSecret, tld=tld)
        self.spot_usdt = self.get_spot_usdt()
        self.spot_coin = self.get_spot_coin()
        self.isolated = isIsolated
        self.check_spot_and_transfer()
        self.retrieve_margin_values()
        self.startingBalance = self.get_starting_balance()
        self.check_initial_position()
        self.netWorth = round(self.get_net(), 2)
        self.validate_minimum_funds()

    def check_spot_and_transfer(self):
        """
        Checks if spot account has more than $10. If it does, it transfers money to margin account.
        """
        if self.spot_usdt > 10:
            self.initial_transfer()

    def validate_minimum_funds(self):
        """
        Checks if account has enough funds to initiate trading.
        """
        if not self.has_enough_money():
            raise ValueError(f"You only have ${self.netWorth}. Please make sure you have at least $10 in your account.")

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

    @staticmethod
    def round_down(num: float, digits: int = 6) -> float:
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

    def retrieve_margin_values(self):
        """
        Retrieves margin values and sets them to instance variables.
        """
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

    def initial_transfer(self):
        """
        Buys long in spot then transfers it to margin account.
        """
        self.spot_buy_long()
        self.transfer_spot_to_margin()

    def spot_buy_long(self):
        """
        Enters long position in spot account.
        """
        self.spot_usdt = self.get_spot_usdt()
        self.currentPrice = self.dataView.get_current_price()
        max_buy = self.round_down(self.spot_usdt * (1 - self.transactionFeePercentage) / self.currentPrice)

        order = self.binanceClient.order_market_buy(
            symbol=self.symbol,
            quantity=max_buy
        )

        self.add_trade(message='Bought spot long.',
                       initialNet=self.get_net(),
                       finalNet=self.get_net(),
                       price=self.currentPrice,
                       force=False,
                       orderID=order['clientOrderId'])

    def spot_sell_long(self):
        """
        Exits long position in spot account.
        """
        self.spot_coin = self.get_spot_coin()
        order = self.binanceClient.order_market_sell(
            symbol=self.symbol,
            quantity=self.spot_coin
        )

        self.add_trade(message='Sold spot long.',
                       initialNet=self.get_net(),
                       finalNet=self.get_net(),
                       price=self.currentPrice,
                       force=False,
                       orderID=order['clientOrderId'])

    def get_spot_usdt(self) -> float:
        """
        Returns spot USDT amount.
        """
        return self.round_down(self.binanceClient.get_asset_balance(asset='USDT')['free'])

    def get_spot_coin(self) -> float:
        """
        Returns spot coin amount.
        """
        return self.round_down(self.binanceClient.get_asset_balance(asset=self.coinName)['free'])

    # noinspection PyProtectedMember
    def get_isolated_margin_account(self, **params) -> dict:
        """
        Retrieves margin isolated account information.
        :param params: **kwargs that normally go to binanceClient's request_margin_api function.
        :return: Margin isolated account information
        """
        return self.binanceClient._request_margin_api('get', 'margin/isolated/account', True, data=params)

    def get_starting_balance(self) -> float:
        """
        Returns the initial starting balance for bot.
        :return: initial starting balance for bot
        """
        self.currentPrice = self.dataView.get_current_price()
        usdt = self.coin * self.currentPrice + self.balance
        usdt -= self.coinOwed * self.currentPrice
        return usdt

    def get_asset(self, targetAsset: str) -> dict:
        """
        Retrieves asset specified (if exists).
        :param targetAsset: Asset to be retrieved.
        :return: The target asset (if found).
        """
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            return [asset for asset in assets if asset['baseAsset']['asset'] == targetAsset][0]['baseAsset']
        else:
            assets = self.binanceClient.get_margin_account()['userAssets']
            return [asset for asset in assets if asset['asset'] == targetAsset][0]

    def get_margin_coin_info(self) -> dict:
        """
        Retrieves margin info about coin.
        :return: Margin info about coin.
        """
        return self.get_asset(self.coinName)

    def get_margin_usdt(self) -> float:
        """
        Retrieves USDT available in margin account.
        :return: USDT available.
        """
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            for asset in assets:
                if asset['baseAsset']['asset'] == self.coinName and asset['quoteAsset']['asset'] == 'USDT':
                    return self.round_down(float(asset['quoteAsset']['free']))
        else:
            return self.round_down(float(self.get_asset('USDT')['free']))

    def get_margin_coin(self) -> float:
        """
        Retrieves margin coin amount.
        :return: Margin coin amount.
        """
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['free']))

    def get_borrowed_margin_coin(self) -> float:
        """
        Retrieves borrowed margin coin amount.
        :return: Borrowed margin coin amount.
        """
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['borrowed']))

    def get_borrowed_margin_interest(self) -> float:
        """
        Retrieves borrowed margin coin interest amount.
        :return: Borrowed margin coin interest amount.
        """
        coin = self.get_margin_coin_info()
        return self.round_down(float(coin['interest']))

    def create_margin_loan(self, amount: float, force: bool):
        """
        Creates margin loan.
        :param force: Boolean that determines whether bot executed action or human.
        :param amount: Amount to borrow in margin loan.
        :return: Order dictionary.
        """
        initialNet = self.get_net()

        if self.isolated:
            self.binanceClient.create_margin_loan(asset=self.coinName,
                                                  amount=amount,
                                                  isIsolated=True,
                                                  symbol=self.symbol)
        else:
            self.binanceClient.create_margin_loan(asset=self.coinName,
                                                  amount=amount)

        self.retrieve_margin_values()
        finalNet = self.get_net()
        self.add_trade(message='Created margin loan.',
                       initialNet=initialNet,
                       finalNet=finalNet,
                       price=self.currentPrice,
                       force=force,
                       orderID=None)

    def repay_margin_loan(self, force: bool):
        """
        Repays margin loan.
        :param force: Boolean that determines whether bot executed action or human.
        """
        initialNet = self.get_net()

        if self.isolated:
            self.binanceClient.repay_margin_loan(
                asset=self.coinName,
                amount=self.coin,
                isIsolated=self.isolated,
                symbol=self.symbol
            )
        else:
            self.binanceClient.repay_margin_loan(
                asset=self.coinName,
                amount=self.coin
            )

        self.retrieve_margin_values()
        finalNet = self.get_net()
        self.add_trade(message='Repaid margin loan.',
                       initialNet=initialNet,
                       finalNet=finalNet,
                       price=self.currentPrice,
                       force=force,
                       orderID=None)

    def buy_long(self, msg: str, usd: float or None = None, force: bool = False):
        """
        Buys coin at current market price with amount of USD specified. If not specified, assumes bot goes all in.
        :param msg: Message to be used for displaying trade information.
        :param usd: Amount used to enter long position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        initialNet = self.get_net()
        max_buy = self.round_down(self.balance / self.currentPrice * (1 - self.transactionFeePercentage))

        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=max_buy,
            isIsolated=self.isolated
        )

        self.retrieve_margin_values()
        self.currentPosition = LONG
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.output_message(msg)
        finalNet = self.get_net()
        self.add_trade(message=msg,
                       initialNet=initialNet,
                       finalNet=finalNet,
                       price=self.currentPrice,
                       force=force,
                       orderID=order['clientOrderId'])

    def sell_long(self, msg: str, coin: float or None = None, force: bool = False):
        """
        Sells specified amount of coin at current market price. If not specified, assumes bot sells all coin.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to exit long position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        initialNet = self.get_net()
        order = self.binanceClient.create_margin_order(
            symbol=self.symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=self.get_margin_coin(),
            isIsolated=self.isolated
        )

        self.retrieve_margin_values()
        self.currentPosition = None
        self.previousPosition = LONG
        self.customStopLoss = None
        self.buyLongPrice = None
        self.longTrailingPrice = None
        self.output_message(msg)
        finalNet = self.get_net()
        self.add_trade(message=msg,
                       initialNet=initialNet,
                       finalNet=finalNet,
                       price=self.currentPrice,
                       force=force,
                       orderID=order['clientOrderId'])

    def buy_short(self, msg: str, coin: float or None = None, force: bool = False):
        """
        Returns coin by buying them at current market price.
        If no coin is provided in function, bot will assume we try to pay back everything in return.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to buy back to exit short position.
        :param force: Boolean that determines whether bot executed action or human.
        """
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

        self.retrieve_margin_values()
        finalNet = self.get_net()
        self.add_trade(message=msg,
                       initialNet=initialNet,
                       finalNet=finalNet,
                       price=self.currentPrice,
                       force=force,
                       orderID=order['clientOrderId'])

        self.repay_margin_loan(force=force)
        self.currentPosition = None
        self.previousPosition = SHORT
        self.sellShortPrice = None
        self.customStopLoss = None
        self.shortTrailingPrice = None
        self.output_message(msg)

    def sell_short(self, msg: str, coin: float or None = None, force: bool = False):
        """
        Borrows coin and sells them at current market price.
        If no coin is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to enter short position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        self.balance = self.get_margin_usdt()
        self.currentPrice = self.dataView.get_current_price()
        transactionFee = self.balance * self.transactionFeePercentage
        max_borrow = self.round_down((self.balance - transactionFee) / self.currentPrice)
        # max_borrow = self.round_down(self.balance / self.currentPrice - self.get_borrowed_margin_coin())
        self.create_margin_loan(amount=max_borrow, force=force)

        initialNet = self.get_net()
        order = self.binanceClient.create_margin_order(
            side=SIDE_SELL,
            symbol=self.symbol,
            type=ORDER_TYPE_MARKET,
            quantity=self.round_down(self.get_margin_coin()),
            isIsolated=self.isolated
        )

        self.retrieve_margin_values()
        self.currentPosition = SHORT
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.output_message(msg)
        finalNet = self.get_net()
        self.add_trade(message=msg,
                       initialNet=initialNet,
                       finalNet=finalNet,
                       price=self.currentPrice,
                       force=force,
                       orderID=order['clientOrderId'])
