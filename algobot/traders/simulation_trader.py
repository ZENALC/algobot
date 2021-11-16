"""
Simulation Trader file. Real Trader will create a subclass out of this.
"""

import time
from datetime import datetime
from threading import Lock
from typing import Union

import pandas as pd

from algobot.data import Data
from algobot.enums import BEARISH, BULLISH, ENTER_LONG, ENTER_SHORT, EXIT_LONG, EXIT_SHORT, LONG, SHORT
from algobot.helpers import convert_small_interval, get_logger
from algobot.strategies.custom import CustomStrategy
from algobot.traders.trader import Trader


class SimulationTrader(Trader):
    """
    Simulation trader class.
    """
    def __init__(self,
                 starting_balance: float = 1000,
                 interval: str = '1h',
                 symbol: str = 'BTCUSDT',
                 load_data: bool = True,
                 update_data: bool = True,
                 log_file: str = 'simulation',
                 precision: int = 2,
                 add_trade_callback=None):
        """
        SimulationTrader object that will mimic real live market trades.
        :param starting_balance: Balance to start simulation trader with.
        :param interval: Interval to start trading on.
        :param symbol: Symbol to start trading with.
        :param load_data: Boolean whether we load data from data object or not.
        :param update_data: Boolean for whether data will be updated if it is loaded.
        :param log_file: Filename that logger will log to.
        :param precision: Precision to round data to.
        :param add_trade_callback: Callback signal to emit to (if provided) to reflect a new transaction.
        """
        super().__init__(precision=precision, symbol=symbol, starting_balance=starting_balance)
        self.logger = get_logger(log_file=log_file, logger_name=log_file)  # Get logger.
        self.data_view: Data = Data(interval=interval, symbol=symbol, load_data=load_data,
                                    update=update_data, log_object=self.logger, precision=precision, limit_fetch=True)
        self.binance_client = self.data_view.binance_client  # Retrieve Binance client.
        self.symbol = self.data_view.symbol  # Retrieve symbol from data-view object.
        self.coin_name = self.get_coin_name()  # Retrieve primary coin to trade.
        self.commission_paid = 0  # Total commission paid to broker.
        self.completed_loop = True  # Loop that'll keep track of bot. We wait for this to turn False before some action.
        self.in_human_control = False  # Boolean that keeps track of whether human or bot controls transactions.
        self.lock = Lock()  # Lock to ensure a transaction doesn't occur when another one is taking place.
        self.add_trade_callback = add_trade_callback  # Callback for GUI to add trades.
        self.daily_change_nets = []  # Daily change net list. Will contain list of all nets.

    def output_message(self, message: str, level: int = 2, print_message: bool = False):
        """
        Prints out and logs message provided.
        :param message: Message to be logged and/or outputted.
        :param level: Level to be debugged at.
        :param print_message: Boolean that determines whether messaged will be printed or not.
        """
        if print_message:
            print(message)
        if level == 2:
            self.logger.info(message)
        elif level == 3:
            self.logger.debug(message)
        elif level == 4:
            self.logger.warning(message)
        elif level == 5:
            self.logger.critical(message)

    def get_grouped_statistics(self) -> dict:
        """
        Returns dictionary of grouped statistics for the statistics window in the GUI.
        """
        grouped_dict = {
            'general': {
                'currentBalance': f'${round(self.balance, 2)}',
                'startingBalance': f'${round(self.starting_balance, 2)}',
                'tradesMade': str(len(self.trades)),
                'coinOwned': f'{round(self.coin, 6)}',
                'coinOwed': f'{round(self.coin_owed, 6)}',
                'ticker': self.symbol,
                'tickerPrice': f'${self.current_price}',
                'interval': f'{convert_small_interval(self.data_view.interval)}',
                'position': self.get_position_string(),
                'autonomous': str(not self.in_human_control),
                'precision': str(self.precision),
                'trend': str(self.trend),
                'marginEnabled': str(self.margin_enabled),
            }
        }

        if self.loss_strategy is not None:
            grouped_dict['stopLoss'] = {
                'stopLossType': self.get_stop_loss_strategy_string(),
                'stopLossPercentage': self.get_safe_rounded_percentage(self.loss_percentage_decimal),
                'stopLossPoint': self.get_safe_rounded_string(self.get_stop_loss()),
                self.symbol: f'${self.current_price}',
                'customStopPointValue': self.get_safe_rounded_string(self.custom_stop_loss),
                'initialSmartStopLossCounter': str(self.smart_stop_loss_initial_counter),
                'smartStopLossCounter': str(self.smart_stop_loss_counter),
                'stopLossExit': str(self.stop_loss_exit),
                'smartStopLossEnter': str(self.smart_stop_loss_enter),
                'previousStopLossPoint': self.get_safe_rounded_string(self.previous_stop_loss),
                'longTrailingPrice': self.get_safe_rounded_string(self.long_trailing_price),
                'shortTrailingPrice': self.get_safe_rounded_string(self.short_trailing_price),
                'buyLongPrice': self.get_safe_rounded_string(self.buy_long_price),
                'sellShortPrice': self.get_safe_rounded_string(self.sell_short_price),
                'safetyTimer': self.get_safe_rounded_string(self.safety_timer, symbol=' seconds', direction='right'),
                'scheduledTimerRemaining': self.get_remaining_safety_timer(),
            }

        if self.take_profit_type is not None:
            grouped_dict['takeProfit'] = {
                'takeProfitType': str(self.take_profit_type),
                'takeProfitPercentage': self.get_safe_rounded_percentage(self.take_profit_percentage_decimal),
                'trailingTakeProfitActivated': str(self.trailing_take_profit_activated),
                'takeProfitPoint': self.get_safe_rounded_string(self.take_profit_point),
                self.symbol: f'${self.current_price}',
            }

        if self.data_view.current_values:
            data_view = self.data_view
            grouped_dict['currentData'] = {
                'UTC Open Time': data_view.current_values['date_utc'].strftime('%Y-%m-%d %H:%M:%S'),
                'open': '$' + str(round(data_view.current_values['open'], self.precision)),
                'close': '$' + str(round(data_view.current_values['close'], self.precision)),
                'high': '$' + str(round(data_view.current_values['high'], self.precision)),
                'low': '$' + str(round(data_view.current_values['low'], self.precision)),
                'volume': str(round(data_view.current_values['volume'], self.precision)),
                'quoteAssetVolume': str(round(data_view.current_values['quote_asset_volume'], self.precision)),
                'numberOfTrades': str(round(data_view.current_values['number_of_trades'], self.precision)),
                'takerBuyBaseAsset': str(round(data_view.current_values['taker_buy_base_asset'], self.precision)),
                'takerBuyQuoteAsset': str(round(data_view.current_values['taker_buy_quote_asset'], self.precision)),
            }

        self.add_strategy_info_to_grouped_dict(grouped_dict)
        return grouped_dict

    def add_strategy_info_to_grouped_dict(self, grouped_dict: dict):
        """
        Adds strategy information to the dictionary provided.
        :param grouped_dict: Dictionary to add strategy information to.
        """
        for strategy_name, strategy in self.strategies.items():

            grouped_dict[strategy_name] = {
                'trend': str(strategy.trend),
                'enabled': 'True',
            }

            strategy.populate_grouped_dict(grouped_dict[strategy_name])

    def get_remaining_safety_timer(self) -> str:
        """
        Returns the number of seconds left before checking to see if a real stop loss has occurred.
        """
        if not self.scheduled_safety_timer:
            return 'None'
        else:
            remaining = int(self.scheduled_safety_timer - time.time())
            return f'{remaining} seconds'

    def add_trade(self, message: str, force: bool = False, orderID: str = None, stop_loss_exit: bool = False,
                  smart_enter: bool = False):
        """
        Adds a trade to list of trades
        :param smart_enter: Boolean that'll determine whether current position is entered from a smart enter or not.
        :param stop_loss_exit: Boolean for whether last position was exited because of a stop loss.
        :param orderID: Order ID returned from Binance API.
        :param force: Boolean that determines whether trade was conducted autonomously or by hand.
        :param message: Message used for conducting trade.
        """
        initial_net = self.previous_net
        final_net = self.get_net()
        profit = final_net - initial_net
        profit_percentage = self.get_profit_percentage(initial_net, final_net)
        method = "Manual" if force else "Automation"

        trade = {
            'date': datetime.utcnow(),
            'orderID': orderID,
            'action': message,
            'pair': self.symbol,
            'price': f'${round(self.current_price, self.precision)}',
            'method': method,
            'percentage': f'{round(profit_percentage, 2)}%',
            'profit': f'${round(profit, self.precision)}'
        }

        if self.add_trade_callback:
            try:
                self.add_trade_callback.emit(trade)
            except AttributeError:  # This means bot was closed with closeEvent()
                pass

        self.trades.append(trade)
        self.previous_net = final_net
        self.stop_loss_exit = stop_loss_exit
        self.smart_stop_loss_enter = smart_enter
        self.scheduled_safety_timer = None

        self.output_message(f'\nDatetime in UTC: {datetime.utcnow()}\n'
                            f'Order ID: {orderID}\n'
                            f'Action: {message}\n'
                            f'Pair: {self.symbol}\n'
                            f'Price: {round(self.current_price, self.precision)}\n'
                            f'Method: {method}\n'
                            f'Percentage: {round(profit_percentage, 2)}%\n'
                            f'Profit: ${round(profit, self.precision)}\n')

    def buy_long(self, msg: str, usd: float = None, force: bool = False, smart_enter: bool = False):
        """
        Buys coin at current market price with amount of USD specified. If not specified, assumes bot goes all in.
        Function also takes into account Binance's 0.1% transaction fee.
        :param smart_enter: Boolean that'll determine whether current position is entered from a smart enter or not.
        :param msg: Message to be used for displaying trade information.
        :param usd: Amount used to enter long.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.current_position == LONG:
                return

            if usd is None:
                usd = self.balance

            if usd <= 0:
                raise ValueError(f"You cannot buy with ${usd}.")

            if usd > self.balance:
                raise ValueError(f'You currently have ${self.balance}. You cannot invest ${usd}.')

            self.current_price = self.data_view.get_current_price()
            transaction_fee = usd * self.transaction_fee_percentage_decimal
            self.commission_paid += transaction_fee
            self.current_position = LONG
            self.buy_long_price = self.long_trailing_price = self.current_price
            self.coin += (usd - transaction_fee) / self.current_price
            self.balance -= usd
            self.add_trade(msg, force=force, smart_enter=smart_enter)

    def sell_long(self, msg: str, coin: float = None, force: bool = False, stop_loss_exit: bool = False):
        """
        Sells specified amount of coin at current market price. If not specified, assumes bot sells all coin.
        Function also takes into account Binance's 0.1% transaction fee.
        :param stop_loss_exit: Boolean for whether last position was exited because of a stop loss.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to exit long.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.current_position != LONG:
                return

            if coin is None:
                coin = self.coin

            if coin <= 0:
                raise ValueError(f"You cannot sell {coin} {self.coin_name}.")

            if coin > self.coin:
                raise ValueError(f'You have {self.coin} {self.coin_name}. You cannot sell {coin} {self.coin_name}.')

            self.current_price = self.data_view.get_current_price()
            self.commission_paid += coin * self.current_price * self.transaction_fee_percentage_decimal
            self.balance += coin * self.current_price * (1 - self.transaction_fee_percentage_decimal)
            self.current_position = None
            self.custom_stop_loss = None
            self.previous_position = LONG
            self.coin -= coin
            self.add_trade(msg, force=force, stop_loss_exit=stop_loss_exit)

            if self.coin == 0:
                self.buy_long_price = self.long_trailing_price = None

    def buy_short(self, msg: str, coin: float = None, force: bool = False, stop_loss_exit: bool = False):
        """
        Buys borrowed coin at current market price and returns to market.
        Function also takes into account Binance's 0.1% transaction fee.
        If coin amount is not specified, bot will assume to try to pay back everything in return.
        :param stop_loss_exit: Boolean for whether last position was exited because of a stop loss.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to buy back to exit short position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.current_position != SHORT:
                return

            if coin is None:
                coin = self.coin_owed

            if coin <= 0:
                raise ValueError(f"You cannot buy {coin} {self.coin_name}. Did you mean to sell short?")

            self.current_price = self.data_view.get_current_price()
            self.coin_owed -= coin
            self.custom_stop_loss = None
            self.current_position = None
            self.previous_position = SHORT
            self.commission_paid += self.current_price * coin * self.transaction_fee_percentage_decimal
            self.balance -= self.current_price * coin * (1 + self.transaction_fee_percentage_decimal)
            self.add_trade(msg, force=force, stop_loss_exit=stop_loss_exit)

            if self.coin_owed == 0:
                self.sell_short_price = self.short_trailing_price = None

    def sell_short(self, msg: str, coin: float = None, force: bool = False, smart_enter: bool = False):
        """
        Borrows coin and sells them at current market price.
        Function also takes into account Binance's 0.1% transaction fee.
        If no coin is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to enter short position.
        :param force: Boolean that determines whether bot executed action or human.
        :param smart_enter: Boolean that'll determine whether current position is entered from a smart enter or not.
        """
        with self.lock:
            if self.current_position == SHORT:
                return

            self.current_price = self.data_view.get_current_price()

            if coin is None:
                transaction_fee = self.balance * self.transaction_fee_percentage_decimal
                coin = (self.balance - transaction_fee) / self.current_price

            if coin <= 0:
                raise ValueError(f"You cannot borrow negative {abs(coin)} {self.coin_name}.")

            self.coin_owed += coin
            self.commission_paid += self.current_price * coin * self.transaction_fee_percentage_decimal
            self.balance += self.current_price * coin * (1 - self.transaction_fee_percentage_decimal)
            self.current_position = SHORT
            self.sell_short_price = self.short_trailing_price = self.current_price
            self.add_trade(msg, force=force, smart_enter=smart_enter)

    def get_trend(self, dataObject: Data = None, log_data: bool = False) -> Union[int, None]:
        """
        Returns trend based on the strategies provided.
        :param dataObject: Data object to use to retrieve trend.
        :param log_data: Boolean whether data should be logged or not.
        :return: Integer in the form of an enum.
        """
        if not dataObject:  # We usually only pass the dataObject for a lower interval.
            dataObject = self.data_view

        df = pd.DataFrame(dataObject.data + [dataObject.current_values])
        df['high/low'] = (df['high'] + df['low']) / 2
        df['open/close'] = (df['open'] + df['close']) / 2

        trends = [strategy.get_trend(df=df, data=dataObject, log_data=log_data)
                  if not isinstance(strategy, CustomStrategy) else strategy.get_trend(df=df)
                  for strategy in self.strategies.values()]
        return self.get_cumulative_trend(trends=trends)

    def short_position_logic(self, trend):
        """
        This function will handle all the logic when bot is in a short position.
        :param trend: Current trend the bot registers based on strategies provided.
        """
        if self.custom_stop_loss is not None and self.current_price >= self.custom_stop_loss:
            self.buy_short('Bought short because of custom stop loss.')
        elif self.get_stop_loss() is not None and self.current_price >= self.get_stop_loss():
            if not self.safety_timer:
                self.buy_short('Bought short because of stop loss.', stop_loss_exit=True)
            else:
                if not self.scheduled_safety_timer:
                    self.scheduled_safety_timer = time.time() + self.safety_timer
                else:
                    if time.time() > self.scheduled_safety_timer:
                        self.buy_short('Bought short because of stop loss and safety timer.', stop_loss_exit=True)
        elif self.get_take_profit() is not None and self.current_price <= self.get_take_profit():
            self.buy_short('Bought short because of take profit.')
        elif not self.in_human_control:
            if trend == BULLISH:
                self.buy_short('Bought short because a bullish trend was detected.')
                self.buy_long('Bought long because a bullish trend was detected.')
            elif trend == EXIT_SHORT:
                self.buy_short('Bought short because an exit-short trend was detected.')

    def long_position_logic(self, trend):
        """
        This function will handle all the logic when bot is in a long position.
        :param trend: Current trend the bot registers based on strategies provided.
        """
        if self.custom_stop_loss is not None and self.current_price <= self.custom_stop_loss:
            self.sell_long('Sold long because of custom stop loss.')
        elif self.get_stop_loss() is not None and self.current_price <= self.get_stop_loss():
            if not self.safety_timer:
                self.sell_long('Sold long because of stop loss.', stop_loss_exit=True)
            else:
                if not self.scheduled_safety_timer:
                    self.scheduled_safety_timer = time.time() + self.safety_timer
                else:
                    if time.time() > self.scheduled_safety_timer:
                        self.sell_long('Sold long because of stop loss and safety timer.', stop_loss_exit=True)
        elif self.get_take_profit() is not None and self.current_price >= self.get_take_profit():
            self.sell_long('Sold long because of take profit.')
        elif not self.in_human_control:
            if trend == BEARISH:
                self.sell_long('Sold long because a cross was detected.')
                self.sell_short('Sold short because a cross was detected.')
            elif trend == EXIT_LONG:
                self.sell_long("Sold long because an exit-long trend was detected.")

    def no_position_logic(self, trend):
        """
        This function will handle all the logic when bot is not in any position.
        :param trend: Current trend the bot registers based on strategies provided.
        """
        if self.stop_loss_exit and self.smart_stop_loss_counter > 0:
            if self.previous_position == LONG:
                if self.current_price > self.previous_stop_loss:
                    self.buy_long('Reentered long because of smart stop loss.', smart_enter=True)
                    self.smart_stop_loss_counter -= 1
                    return
            elif self.previous_position == SHORT:
                if self.current_price < self.previous_stop_loss:
                    self.sell_short('Reentered short because of smart stop loss.', smart_enter=True)
                    self.smart_stop_loss_counter -= 1
                    return

        if not self.in_human_control:
            if trend == BULLISH and self.previous_position != LONG:
                self.buy_long('Bought long because a bullish trend was detected.')
                self.reset_smart_stop_loss()
            elif trend == BEARISH and self.previous_position != SHORT:
                self.sell_short('Sold short because a bearish trend was detected.')
                self.reset_smart_stop_loss()
            elif trend == ENTER_LONG:
                self.buy_long("Bought long because an enter-long trend was detected.")
                self.reset_smart_stop_loss()
            elif trend == ENTER_SHORT:
                self.sell_short("Sold short because an enter-short trend was detected.")
                self.reset_smart_stop_loss()

    # noinspection PyTypeChecker
    def main_logic(self, log_data: bool = True):
        """
        Main bot logic will use to trade.
        If there is a trend and the previous position did not reflect the trend, the bot enters position.
        :param log_data: Boolean that will determine where data is logged or not.
        """
        self.trend = trend = self.get_trend(log_data=log_data)
        if self.current_position == SHORT:
            self.short_position_logic(trend)
        elif self.current_position == LONG:
            self.long_position_logic(trend)
        else:
            self.no_position_logic(trend)

    def reset_smart_stop_loss(self):
        """
        Resets smart stop loss counter.
        """
        self.smart_stop_loss_counter = self.smart_stop_loss_initial_counter

    def get_net(self) -> float:
        """
        Returns net balance with current price of coin being traded. It factors in the current balance, the amount
        shorted, and the amount owned.
        :return: Net balance.
        """
        if self.current_price is None:
            self.current_price = self.data_view.get_current_price()

        return self.starting_balance + self.get_profit()

    def get_profit(self) -> float:
        """
        Returns profit or loss.
        :return: A number representing profit if positive and loss if negative.
        """
        if self.current_price is None:
            self.current_price = self.data_view.get_current_price()

        balance = self.balance
        balance += self.current_price * self.coin
        balance -= self.current_price * self.coin_owed

        return balance - self.starting_balance

    def get_coin_name(self) -> str:
        """
        Returns target coin name.
        Function assumes trader is using a coin paired with USDT.
        """
        temp = self.data_view.symbol.upper().split('USDT')
        return temp[0]

    def output_no_position_information(self):
        """
        Outputs general information about status of bot when not in a position.
        """
        if self.current_position is None:
            if not self.in_human_control:
                self.output_message('\nCurrently not a in short or long position. Waiting for next cross.')
            else:
                self.output_message('\nCurrently not a in short or long position. Waiting for human intervention.')

    def output_short_information(self):
        """
        Outputs general information about status of trade when in a short position.
        """
        if self.current_position == SHORT and self.stop_loss is not None:
            self.output_message('\nCurrently in short position.')
            self.output_message(f'{self.get_stop_loss_strategy_string()}: ${round(self.stop_loss, self.precision)}')

    def output_long_information(self):
        """
        Outputs general information about status of trade when in a long position.
        """
        if self.current_position == LONG and self.stop_loss is not None:
            self.output_message('\nCurrently in long position.')
            self.output_message(f'{self.get_stop_loss_strategy_string()}: ${round(self.stop_loss, self.precision)}')

    def output_control_mode(self):
        """
        Outputs general information about status of bot.
        """
        if self.in_human_control:
            self.output_message('Currently in human control. Bot is waiting for human input to continue.')
        else:
            self.output_message('Currently in autonomous mode.')

    def output_profit_information(self):
        """
        Outputs general information about profit.
        """
        profit = round(self.get_profit(), self.precision)
        self.output_message(f'{self.get_profit_or_loss_string(profit)}: ${abs(profit)}')

    def output_basic_information(self):
        """
        Prints out basic information about trades.
        """
        self.output_message('---------------------------------------------------')
        self.output_message(f'Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_control_mode()

        if self.current_price is None:
            self.current_price = self.data_view.get_current_price()

        if self.current_price * self.coin > 5:  # If total worth of coin owned is more than $5, assume we're in long.
            self.output_message(f'{self.coin_name} owned: {self.coin}')
            self.output_message(f'Price bot bought {self.coin_name} long for: ${self.buy_long_price}')

        if self.current_price * self.coin_owed > 5:  # If worth of coin owed is more than $5, assume we're in short.
            self.output_message(f'{self.coin_name} owed: {self.coin_owed}')
            self.output_message(f'Price bot sold {self.coin_name} short for: ${self.sell_short_price}')

        if self.current_position == LONG:
            self.output_long_information()
        elif self.current_position == SHORT:
            self.output_short_information()
        elif self.current_position is None:
            self.output_no_position_information()

        self.output_message(f'\nCurrent {self.coin_name} price: ${self.current_price}')
        self.output_message(f'Balance: ${round(self.balance, self.precision)}')
        self.output_profit_information()
        if type(self) == SimulationTrader:  # pylint: disable=unidiomatic-typecheck
            self.output_message(f'\nTrades conducted this simulation: {len(self.trades)}\n')
        else:
            self.output_message(f'\nTrades conducted in live market: {len(self.trades)}\n')

    def get_run_result(self, is_simulation: bool = False):
        """
        Gets end result of simulation.
        :param is_simulation: Boolean that'll determine if coins are returned or not.
        """
        self.output_message('\n---------------------------------------------------\nBot run has ended.')
        self.ending_time = datetime.utcnow()
        if is_simulation and self.coin > 0:
            self.output_message(f"Selling all {self.coin_name}...")
            self.sell_long('Sold all owned coin as simulation ended.')

        if is_simulation and self.coin_owed > 0:
            self.output_message(f"Returning all borrowed {self.coin_name}...")
            self.buy_short('Returned all borrowed coin as simulation ended.')

        self.output_message("\nResults:")
        self.output_message(f'Starting time: {self.starting_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'End time: {self.ending_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'Elapsed time: {self.ending_time - self.starting_time}')
        self.output_message(f'Starting balance: ${self.starting_balance}')
        self.output_message(f'Ending balance: ${round(self.balance, self.precision)}')
        self.output_message(f'Trades conducted: {len(self.trades)}')
        self.output_profit_information()

    def log_trades_and_daily_net(self):
        """
        Logs trades.
        """
        self.output_message(f'\n\nTotal trade(s) in previous simulation: {len(self.trades)}')
        for counter, trade in enumerate(self.trades, 1):
            self.output_message(f'\n{counter}. Date in UTC: {trade["date"]}')
            self.output_message(f'\nAction taken: {trade["action"]}')

        self.output_message('\nDaily Nets:')
        for index, net in enumerate(self.daily_change_nets, start=1):
            self.output_message(f'Day {index}: {round(net, 2)}%')

        self.output_message("")

    def output_configuration(self):
        """
        Messages to output for configuration.
        """
        self.output_message('---------------------------------------------------')
        self.output_message('Bot Configuration:')
        self.output_message(f'\tStarting time: {self.starting_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'\tStarting balance: ${self.starting_balance}')
        self.output_message(f'\tSymbol: {self.symbol}')
        self.output_message(f'\tInterval: {convert_small_interval(self.data_view.interval)}')
        self.output_message(f'\tPrecision: {self.precision}')
        self.output_message(f'\tTransaction fee percentage: {self.transaction_fee_percentage_decimal}%')
        self.output_message(f'\tStarting coin: {self.coin}')
        self.output_message(f'\tStarting borrowed coin: {self.coin_owed}')
        self.output_message(f'\tStarting net: ${self.get_net()}')
        self.output_message(f'\tStop loss type: {self.get_stop_loss_strategy_string()}')
        self.output_message(f'\tLoss percentage: {self.loss_percentage_decimal * 100}%')
        self.output_message(f'\tSmart stop loss counter: {self.smart_stop_loss_initial_counter}')
        self.output_message(f'\tSafety timer: {self.safety_timer}')
        self.output_message(self.get_strategies_info_string())
        self.output_message('\nEnd of Configuration')
        self.output_message('---------------------------------------------------')

    def retrieve_margin_values(self):
        """
        This is used in the real trader to retrieve margin values from Binance.
        """
        pass

    def check_current_position(self):
        """
        This is used in the real trader to check its current position reflective of Binance.
        """
        pass
