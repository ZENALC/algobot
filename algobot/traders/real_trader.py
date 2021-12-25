"""
File for real trader. TODO: Add support for CCXT.
"""

import math
import time
from typing import Any, Dict

from binance.client import Client
from binance.enums import ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL

from algobot.enums import LONG, SHORT
from algobot.traders.simulation_trader import SimulationTrader


class RealTrader(SimulationTrader):
    """
    Class for real traders.
    """
    def __init__(
            self,
            api_key: str,
            api_secret: str,
            interval: str = '1h',
            symbol: str = 'BTCUSDT',
            load_data: bool = True,
            update_data: bool = True,
            is_isolated: bool = False,
            tld: str = 'com',
            precision: int = 2,
    ):
        """
        :param api_key: API key to start trading bot with.
        :param api_secret: API secret to start trading bot with.
        :param interval: Data interval to trade at.
        :param symbol: Symbol to trade in.
        :param load_data: Boolean that'll determine whether data object is loaded or not.
        :param update_data: Boolean that'll determine where data object is updated or not.
        :param is_isolated: Boolean that'll determine whether margin asset is isolated or not.
        :param tld: Top level domain. If based in the us, it'll be us; else it'll be com.
        """
        if api_key is None or api_secret is None:
            raise ValueError('API credentials not provided.')

        super().__init__(interval=interval, symbol=symbol, log_file='live', load_data=load_data,
                         update_data=update_data,
                         precision=precision)

        self.binance_client = Client(api_key, api_secret, tld=tld)
        self.transaction_fee_percentage = 0.002  # Added 0.001 for volatility safety.
        self.isolated = is_isolated

        symbol_info = self.binance_client.get_symbol_info(self.symbol)
        self.purchase_precision = self.get_purchase_precision(symbol_info)
        self.min_notional = self.get_min_notional(symbol_info)

        self.spot_usdt = self.get_spot_usdt()
        self.spot_coin = self.get_spot_coin()
        # self.check_spot_and_transfer()

        self.retrieve_margin_values()
        self.previous_net = self.get_net()
        self.starting_balance = self.get_starting_balance()
        self.check_current_position()
        self.net_worth = round(self.get_net(), self.precision)
        self.validate_minimum_funds()

    @staticmethod
    def get_min_notional(symbol_info: Dict[str, Any]) -> float:
        """
        Get the minimum notional based on the symbol provided.
        :param symbol_info: Dictionary containing symbol info.
        :return: Minimum notional in a float.
        """
        filters = symbol_info['filters']
        for filter_dict in filters:
            if 'minNotional' in filter_dict:
                min_notional = float(filter_dict['minNotional'])
                return min_notional  # Get the default min_notional value from Binance if found.
        return 10  # Default value of $10.

    @staticmethod
    def get_purchase_precision(symbol_info: Dict[str, Any]) -> int:
        """
        Get precision required for purchases.
        :param symbol_info: Dictionary containing symbol info.
        :return: Integer containing purchase precision required.
        """
        filters = symbol_info['filters']
        for filter_dict in filters:
            if 'stepSize' in filter_dict:
                step_size = float(filter_dict['stepSize'])
                return int(round(-math.log(step_size, 10), 0))
        return 6  # Default value if no step size found.

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
            raise ValueError(f"You have ${self.net_worth}. Please make sure you have at least $10 in your account.")

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
            assets = self.binance_client.get_margin_account()['userAssets']
            _ = [asset for asset in assets if asset['asset'] == self.coin_name][0]
            return False
        except IndexError:  # If not found, it most likely means it is not in the cross margin account.
            return True

    def round_down(self, num: float) -> float:
        """
        Rounds down number for trading purposes.
        :param num: Number to be rounded down.
        :return: Rounded down number.
        """
        factor = 10.0 ** self.purchase_precision
        return math.floor(float(num) * factor) / factor

    def check_current_position(self):
        """
        Checks current position to check if bot is in a long, short, or neither position.
        """
        self.current_price = self.data_view.get_current_price()
        if self.get_margin_coin() * self.current_price >= 10:
            self.current_position = LONG
            self.buy_long_price = self.current_price
            self.long_trailing_price = self.buy_long_price

        elif self.get_borrowed_margin_coin() * self.current_price >= 10:
            self.current_position = SHORT
            self.sell_short_price = self.current_price
            self.short_trailing_price = self.sell_short_price

    def retrieve_margin_values(self):
        """
        Retrieves margin values and sets them to instance variables.
        """
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            coin = [asset for asset in assets if asset['baseAsset']['asset'] == self.coin_name][0]['baseAsset']
            usdt = [asset for asset in assets if asset['baseAsset']['asset'] == self.coin_name and
                    asset['quoteAsset']['asset'] == 'USDT'][0]['quoteAsset']
        else:
            assets = self.binance_client.get_margin_account()['userAssets']
            coin = [asset for asset in assets if asset['asset'] == self.coin_name][0]
            usdt = [asset for asset in assets if asset['asset'] == 'USDT'][0]

        self.balance = self.round_down(float(usdt['free']))
        self.coin = self.round_down(float(coin['free']))
        self.coin_owed = self.round_down(float(coin['borrowed']))

    def transfer_spot_to_margin(self):
        """
        Transfer assets from spot account to margin account.
        """
        self.binance_client.transfer_spot_to_margin(asset=self.coin_name, amount=self.get_spot_coin())
        self.add_trade(message='Transferred from spot to margin',
                       force=False,
                       orderID="TRANSFER SPOT TO MARGIN")

    def transfer_margin_to_spot(self):
        """
        Transfers assets from margin account to spot account.
        """
        order = self.binance_client.transfer_margin_to_spot(asset=self.coin_name, amount=self.get_margin_coin())
        self.add_trade(message='Transferred from margin to spot',
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
        self.current_price = self.data_view.get_current_price()
        max_buy = self.round_down(self.spot_usdt * (1 - self.transaction_fee_percentage) / self.current_price)

        order = self.binance_client.order_market_buy(
            symbol=self.symbol,
            quantity=max_buy
        )

        self.add_trade(message='Bought spot long.',
                       force=False,
                       orderID=order['clientOrderId'])

    def spot_sell_long(self):
        """
        Exits long position in spot account.
        """
        self.spot_coin = self.get_spot_coin()
        order = self.binance_client.order_market_sell(
            symbol=self.symbol,
            quantity=self.spot_coin
        )

        self.add_trade(message='Sold spot long.',
                       force=False,
                       orderID=order['clientOrderId'])

    def get_spot_usdt(self) -> float:
        """
        Returns spot USDT amount.
        """
        return self.round_down(self.binance_client.get_asset_balance(asset='USDT')['free'])

    def get_spot_coin(self) -> float:
        """
        Returns spot coin amount.
        """
        return self.round_down(self.binance_client.get_asset_balance(asset=self.coin_name)['free'])

    # noinspection PyProtectedMember
    def get_isolated_margin_account(self, **params) -> dict:
        """
        Retrieves margin isolated account information.
        :param params: **kwargs that normally go to binance_client's request_margin_api function.
        :return: Margin isolated account information
        """
        # pylint: disable=protected-access
        return self.binance_client._request_margin_api('get', 'margin/isolated/account', True, data=params)

    def get_starting_balance(self) -> float:
        """
        Returns the initial starting balance for bot.
        :return: initial starting balance for bot
        """
        self.current_price = self.data_view.get_current_price()
        usdt = self.coin * self.current_price + self.balance
        usdt -= self.coin_owed * self.current_price
        return usdt

    def get_asset(self, target_asset: str) -> dict:
        """
        Retrieves asset specified (if exists).
        :param target_asset: Asset to be retrieved.
        :return: The target asset (if found).
        """
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            return [asset for asset in assets if asset['baseAsset']['asset'] == target_asset][0]['baseAsset']
        else:
            assets = self.binance_client.get_margin_account()['userAssets']
            return [asset for asset in assets if asset['asset'] == target_asset][0]

    def get_margin_coin_info(self) -> dict:
        """
        Retrieves margin info about coin.
        :return: Margin info about coin.
        """
        return self.get_asset(self.coin_name)

    def get_margin_usdt(self) -> float:
        """
        Retrieves USDT available in margin account.
        :return: USDT available.
        """
        if self.isolated:
            assets = self.get_isolated_margin_account()['assets']
            for asset in assets:
                if asset['baseAsset']['asset'] == self.coin_name and asset['quoteAsset']['asset'] == 'USDT':
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
        if self.isolated:
            self.binance_client.create_margin_loan(asset=self.coin_name,
                                                   amount=amount,
                                                   isIsolated=True,
                                                   symbol=self.symbol)
        else:
            self.binance_client.create_margin_loan(asset=self.coin_name,
                                                   amount=amount)

        self.retrieve_margin_values()
        self.add_trade(message='Created margin loan.',
                       force=force,
                       orderID=None)

    def repay_margin_loan(self, force: bool):
        """
        Repays margin loan.
        :param force: Boolean that determines whether bot executed action or human.
        """
        if self.isolated:
            self.binance_client.repay_margin_loan(
                asset=self.coin_name,
                amount=self.coin,
                isIsolated=self.isolated,
                symbol=self.symbol
            )
        else:
            self.binance_client.repay_margin_loan(
                asset=self.coin_name,
                amount=self.coin
            )

        self.retrieve_margin_values()
        self.add_trade(message='Repaid margin loan.',
                       force=force,
                       orderID=None)

    def buy_long(self, msg: str, coin: float or None = None, force: bool = False, smart_enter=False):
        """
        Buys coin at current market price with amount of coin specified. If not specified, assumes bot goes all in.
        :param smart_enter: Boolean that'll determine whether current position is entered from a smart enter or not.
        :param msg: Message to be used for displaying trade information.
        :param coin: Amount used to enter long position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        # TODO: Refactor to get rid of this pylint disable.
        # pylint: disable=arguments-renamed
        with self.lock:
            if self.current_position == LONG:
                return

            self.balance = self.get_margin_usdt()
            self.current_price = self.data_view.get_current_price()
            if coin is None:
                coin = self.balance / self.current_price * (1 - self.transaction_fee_percentage)

            self.output_message(f'Attempting to enter long by buying {coin} coins...')

            order = self.binance_client.create_margin_order(
                symbol=self.symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=self.round_down(coin),
                isIsolated=self.isolated
            )

            time.sleep(2)  # Sleep for a second so that the bot registers new margin values.
            self.retrieve_margin_values()
            self.current_position = LONG
            self.buy_long_price = self.current_price
            self.long_trailing_price = self.current_price
            self.add_trade(message=msg,
                           force=force,
                           orderID=order['clientOrderId'],
                           smart_enter=smart_enter)

    def sell_long(self, msg: str, coin: float or None = None, force: bool = False, stop_loss_exit=False):
        """
        Sells specified amount of coin at current market price. If not specified, assumes bot sells all coin.
        :param stop_loss_exit: Boolean for whether last position was exited because of a stop loss.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to exit long position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.current_position != LONG:
                return

            if coin is None:
                coin = self.get_margin_coin()

            self.output_message(f"Attempting to exit long by selling {coin} coins...")

            order = self.binance_client.create_margin_order(
                symbol=self.symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=coin,
                isIsolated=self.isolated
            )

            time.sleep(2)  # Sleep for a second so that the bot registers new margin values.
            self.retrieve_margin_values()
            self.previous_position = LONG
            self.current_position = None
            self.custom_stop_loss = None
            self.buy_long_price = None
            self.long_trailing_price = None
            self.add_trade(message=msg,
                           force=force,
                           orderID=order['clientOrderId'], stop_loss_exit=stop_loss_exit)

    def buy_short(self, msg: str, coin: float or None = None, force: bool = False, stop_loss_exit=False):
        """
        Returns coin by buying them at current market price.
        If no coin is provided in function, bot will assume we try to pay back everything in return.
        :param stop_loss_exit: Boolean for whether last position was exited because of a stop loss.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to buy back to exit short position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.current_position != SHORT:
                return

            # self.coin_owed = self.get_borrowed_margin_coin()
            # difference = (self.coin_owed + self.get_borrowed_margin_interest()) *
            # (1 + self.transaction_fee_percentage)
            asset = self.get_asset(self.coin_name)
            coin = (float(asset['borrowed']) + float(asset['interest'])) * (1 + self.transaction_fee_percentage)

            self.output_message(f'Attempting to exit short by returning {coin} coins...')

            order = self.binance_client.create_margin_order(
                side=SIDE_BUY,
                symbol=self.symbol,
                quantity=self.round_down(coin),
                type=ORDER_TYPE_MARKET,
                isIsolated=self.isolated,
                sideEffectType="AUTO_REPAY"
            )

            # order = self.binance_client.create_margin_order(
            #     symbol=self.symbol,
            #     side=SIDE_BUY,
            #     type=ORDER_TYPE_MARKET,
            #     quantity=self.round_down(difference),
            #     is_isolated=self.isolated
            # )

            time.sleep(2)  # Sleep for a second so that the bot registers new margin values.
            self.retrieve_margin_values()
            self.add_trade(message=msg,
                           force=force,
                           orderID=order['clientOrderId'],
                           stop_loss_exit=stop_loss_exit)

            # self.repay_margin_loan(force=force)
            self.previous_position = SHORT
            self.current_position = None
            self.sell_short_price = None
            self.custom_stop_loss = None
            self.short_trailing_price = None

    def sell_short(self, msg: str, coin: float or None = None, force: bool = False, smart_enter=False):
        """
        Borrows coin and sells them at current market price.
        If no coin is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        :param smart_enter: Boolean that'll determine whether current position is entered from a smart enter or not.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to enter short position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.current_position == SHORT:
                return

            self.current_price = self.data_view.get_current_price()
            self.balance = self.get_margin_usdt()
            transaction_fee = self.balance * self.transaction_fee_percentage * 2

            if coin is None:
                coin = (self.balance - transaction_fee) / self.current_price
            # max_borrow = self.round_down(self.balance / self.current_price - self.get_borrowed_margin_coin())
            # self.create_margin_loan(amount=max_borrow, force=force)
            self.output_message(f'Attempting to enter short by selling {coin} coins...')

            order = self.binance_client.create_margin_order(
                side=SIDE_SELL,
                symbol=self.symbol,
                type=ORDER_TYPE_MARKET,
                quantity=self.round_down(coin),
                isIsolated=self.isolated,
                sideEffectType="MARGIN_BUY"
            )

            time.sleep(2)  # Sleep for a second so that the bot registers new margin values.
            self.current_position = SHORT
            self.sell_short_price = self.current_price
            self.short_trailing_price = self.current_price
            self.retrieve_margin_values()
            self.add_trade(message=msg,
                           force=force,
                           orderID=order['clientOrderId'],
                           smart_enter=smart_enter)
