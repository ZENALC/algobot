import time
from datetime import datetime
from threading import Lock
from typing import Union

from algobot.data import Data
from algobot.enums import BEARISH, BULLISH, LONG, SHORT
from algobot.helpers import convert_small_interval, get_logger
from algobot.traders.trader import Trader


class SimulationTrader(Trader):
    def __init__(self,
                 startingBalance: float = 1000,
                 interval: str = '1h',
                 symbol: str = 'BTCUSDT',
                 loadData: bool = True,
                 updateData: bool = True,
                 logFile: str = 'simulation',
                 precision: int = 2,
                 addTradeCallback=None):
        """
        SimulationTrader object that will mimic real live market trades.
        :param startingBalance: Balance to start simulation trader with.
        :param interval: Interval to start trading on.
        :param symbol: Symbol to start trading with.
        :param loadData: Boolean whether we load data from data object or not.
        :param updateData: Boolean for whether data will be updated if it is loaded.
        :param logFile: Filename that logger will log to.
        :param precision: Precision to round data to.
        :param addTradeCallback: Callback signal to emit to (if provided) to reflect a new transaction.
        """
        super().__init__(precision=precision, symbol=symbol, startingBalance=startingBalance)
        self.logger = get_logger(logFile=logFile, loggerName=logFile)  # Get logger.
        self.dataView: Data = Data(interval=interval, symbol=symbol, loadData=loadData,
                                   updateData=updateData, logObject=self.logger, precision=precision)
        self.binanceClient = self.dataView.binanceClient  # Retrieve Binance client.
        self.symbol = self.dataView.symbol  # Retrieve symbol from data-view object.
        self.coinName = self.get_coin_name()  # Retrieve primary coin to trade.
        self.commissionPaid = 0  # Total commission paid to broker.
        self.completedLoop = True  # Loop that'll keep track of bot. We wait for this to turn False before some action.
        self.inHumanControl = False  # Boolean that keeps track of whether human or bot controls transactions.
        self.lock = Lock()  # Lock to ensure a transaction doesn't occur when another one is taking place.
        self.addTradeCallback = addTradeCallback  # Callback for GUI to add trades.
        self.dailyChangeNets = []  # Daily change net list. Will contain list of all nets.
        self.optionDetails = []  # Current option values. Holds most recent option values.
        self.lowerOptionDetails = []  # Lower option values. Holds lower interval option values (if exist).

    def output_message(self, message: str, level: int = 2, printMessage: bool = False):
        """
        Prints out and logs message provided.
        :param message: Message to be logged and/or outputted.
        :param level: Level to be debugged at.
        :param printMessage: Boolean that determines whether messaged will be printed or not.
        """
        if printMessage:
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
        groupedDict = {
            'general': {
                'currentBalance': f'${round(self.balance, 2)}',
                'startingBalance': f'${round(self.startingBalance, 2)}',
                'tradesMade': str(len(self.trades)),
                'coinOwned': f'{round(self.coin, 6)}',
                'coinOwed': f'{round(self.coinOwed, 6)}',
                'ticker': self.symbol,
                'tickerPrice': f'${self.currentPrice}',
                'interval': f'{convert_small_interval(self.dataView.interval)}',
                'position': self.get_position_string(),
                'autonomous': str(not self.inHumanControl),
                'precision': str(self.precision),
                'trend': self.get_trend_string(self.trend)
            }
        }

        if self.lossStrategy is not None:
            groupedDict['stopLoss'] = {
                'stopLossType': self.get_stop_loss_strategy_string(),
                'stopLossPercentage': self.get_safe_rounded_percentage(self.lossPercentageDecimal),
                'stopLossPoint': self.get_safe_rounded_string(self.get_stop_loss()),
                self.symbol: f'${self.currentPrice}',
                'customStopPointValue': self.get_safe_rounded_string(self.customStopLoss),
                'initialSmartStopLossCounter': str(self.smartStopLossInitialCounter),
                'smartStopLossCounter': str(self.smartStopLossCounter),
                'stopLossExit': str(self.stopLossExit),
                'smartStopLossEnter': str(self.smartStopLossEnter),
                'previousStopLossPoint': self.get_safe_rounded_string(self.previousStopLoss),
                'longTrailingPrice': self.get_safe_rounded_string(self.longTrailingPrice),
                'shortTrailingPrice': self.get_safe_rounded_string(self.shortTrailingPrice),
                'buyLongPrice': self.get_safe_rounded_string(self.buyLongPrice),
                'sellShortPrice': self.get_safe_rounded_string(self.sellShortPrice),
                'safetyTimer': self.get_safe_rounded_string(self.safetyTimer, symbol=' seconds', direction='right'),
                'scheduledTimerRemaining': self.get_remaining_safety_timer(),
            }

        if self.takeProfitType is not None:
            groupedDict['takeProfit'] = {
                'takeProfitType': self.get_trailing_or_stop_type_string(self.takeProfitType),
                'takeProfitPercentage': self.get_safe_rounded_percentage(self.takeProfitPercentageDecimal),
                'trailingTakeProfitActivated': str(self.trailingTakeProfitActivated),
                'takeProfitPoint': self.get_safe_rounded_string(self.takeProfitPoint),
                self.symbol: f'${self.currentPrice}',
            }

        if self.dataView.current_values:
            groupedDict['currentData'] = {
                'UTC Open Time': self.dataView.current_values['date_utc'].strftime('%Y-%m-%d %H:%M:%S'),
                'open': '$' + str(round(self.dataView.current_values['open'], self.precision)),
                'close': '$' + str(round(self.dataView.current_values['close'], self.precision)),
                'high': '$' + str(round(self.dataView.current_values['high'], self.precision)),
                'low': '$' + str(round(self.dataView.current_values['low'], self.precision)),
                'volume': str(round(self.dataView.current_values['volume'], self.precision)),
                'quoteAssetVolume': str(round(self.dataView.current_values['quote_asset_volume'], self.precision)),
                'numberOfTrades': str(round(self.dataView.current_values['number_of_trades'], self.precision)),
                'takerBuyBaseAsset': str(round(self.dataView.current_values['taker_buy_base_asset'], self.precision)),
                'takerBuyQuoteAsset': str(round(self.dataView.current_values['taker_buy_quote_asset'], self.precision)),
            }

        self.add_strategy_info_to_grouped_dict(groupedDict)
        return groupedDict

    def add_strategy_info_to_grouped_dict(self, groupedDict: dict):
        """
        Adds strategy information to the dictionary provided.
        :param groupedDict: Dictionary to add strategy information to.
        """
        for strategyName, strategy in self.strategies.items():
            if strategyName == 'movingAverage':
                groupedDict['movingAverages'] = movingAverageDict = {
                    'trend': self.get_trend_string(strategy.trend),
                    'enabled': 'True',
                }
                for optionDetail in self.optionDetails:
                    initialAverage, finalAverage, initialAverageLabel, finalAverageLabel = optionDetail
                    movingAverageDict[initialAverageLabel] = f'${round(initialAverage, self.precision)}'
                    movingAverageDict[finalAverageLabel] = f'${round(finalAverage, self.precision)}'

                if self.lowerOptionDetails:
                    for optionDetail in self.lowerOptionDetails:
                        initialAverage, finalAverage, initialAverageLabel, finalAverageLabel = optionDetail
                        movingAverageDict[f'Lower {initialAverageLabel}'] = f'${round(initialAverage, self.precision)}'
                        movingAverageDict[f'Lower {finalAverageLabel}'] = f'${round(finalAverage, self.precision)}'
            else:
                groupedDict[strategyName] = {
                    'trend': self.get_trend_string(strategy.trend),
                    'enabled': 'True',
                    'inputs': strategy.get_params()
                }

                if 'values' in strategy.strategyDict:
                    for key in strategy.strategyDict['values']:
                        value = strategy.strategyDict['values'][key]
                        if type(value) == float:
                            value = round(value, self.precision)
                        groupedDict[strategyName][key] = value

                for x in strategy.get_params():
                    if x in self.dataView.rsi_data:
                        groupedDict[strategyName][f'RSI({x})'] = round(self.dataView.rsi_data[x], self.precision)

    def get_remaining_safety_timer(self) -> str:
        """
        Returns the number of seconds left before checking to see if a real stop loss has occurred.
        """
        if not self.scheduledSafetyTimer:
            return 'None'
        else:
            remaining = int(self.scheduledSafetyTimer - time.time())
            return f'{remaining} seconds'

    def add_trade(self, message: str, force: bool = False, orderID: str = None, stopLossExit: bool = False,
                  smartEnter: bool = False):
        """
        Adds a trade to list of trades
        :param smartEnter: Boolean that'll determine whether current position is entered from a smart enter or not.
        :param stopLossExit: Boolean for whether last position was exited because of a stop loss.
        :param orderID: Order ID returned from Binance API.
        :param force: Boolean that determines whether trade was conducted autonomously or by hand.
        :param message: Message used for conducting trade.
        """
        initialNet = self.previousNet
        finalNet = self.get_net()
        profit = finalNet - initialNet
        profitPercentage = self.get_profit_percentage(initialNet, finalNet)
        method = "Manual" if force else "Automation"

        trade = {
            'date': datetime.utcnow(),
            'orderID': orderID,
            'action': message,
            'pair': self.symbol,
            'price': f'${round(self.currentPrice, self.precision)}',
            'method': method,
            'percentage': f'{round(profitPercentage, 2)}%',
            'profit': f'${round(profit, self.precision)}'
        }

        if self.addTradeCallback:
            try:
                self.addTradeCallback.emit(trade)
            except AttributeError:  # This means bot was closed with closeEvent()
                pass

        self.trades.append(trade)
        self.previousNet = finalNet
        self.stopLossExit = stopLossExit
        self.smartStopLossEnter = smartEnter
        self.scheduledSafetyTimer = None

        self.output_message(f'\nDatetime in UTC: {datetime.utcnow()}\n'
                            f'Order ID: {orderID}\n'
                            f'Action: {message}\n'
                            f'Pair: {self.symbol}\n'
                            f'Price: {round(self.currentPrice, self.precision)}\n'
                            f'Method: {method}\n'
                            f'Percentage: {round(profitPercentage, 2)}%\n'
                            f'Profit: ${round(profit, self.precision)}\n')

    def buy_long(self, msg: str, usd: float = None, force: bool = False, smartEnter: bool = False):
        """
        Buys coin at current market price with amount of USD specified. If not specified, assumes bot goes all in.
        Function also takes into account Binance's 0.1% transaction fee.
        :param smartEnter: Boolean that'll determine whether current position is entered from a smart enter or not.
        :param msg: Message to be used for displaying trade information.
        :param usd: Amount used to enter long.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.currentPosition == LONG:
                return

            if usd is None:
                usd = self.balance

            if usd <= 0:
                raise ValueError(f"You cannot buy with ${usd}.")
            elif usd > self.balance:
                raise ValueError(f'You currently have ${self.balance}. You cannot invest ${usd}.')

            self.currentPrice = self.dataView.get_current_price()
            transactionFee = usd * self.transactionFeePercentageDecimal
            self.commissionPaid += transactionFee
            self.currentPosition = LONG
            self.buyLongPrice = self.longTrailingPrice = self.currentPrice
            self.coin += (usd - transactionFee) / self.currentPrice
            self.balance -= usd
            self.add_trade(msg, force=force, smartEnter=smartEnter)

    def sell_long(self, msg: str, coin: float = None, force: bool = False, stopLossExit: bool = False):
        """
        Sells specified amount of coin at current market price. If not specified, assumes bot sells all coin.
        Function also takes into account Binance's 0.1% transaction fee.
        :param stopLossExit: Boolean for whether last position was exited because of a stop loss.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to exit long.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.currentPosition != LONG:
                return

            if coin is None:
                coin = self.coin

            if coin <= 0:
                raise ValueError(f"You cannot sell {coin} {self.coinName}.")
            elif coin > self.coin:
                raise ValueError(f'You have {self.coin} {self.coinName}. You cannot sell {coin} {self.coinName}.')

            self.currentPrice = self.dataView.get_current_price()
            self.commissionPaid += coin * self.currentPrice * self.transactionFeePercentageDecimal
            self.balance += coin * self.currentPrice * (1 - self.transactionFeePercentageDecimal)
            self.currentPosition = None
            self.customStopLoss = None
            self.previousPosition = LONG
            self.coin -= coin
            self.add_trade(msg, force=force, stopLossExit=stopLossExit)

            if self.coin == 0:
                self.buyLongPrice = self.longTrailingPrice = None

    def buy_short(self, msg: str, coin: float = None, force: bool = False, stopLossExit: bool = False):
        """
        Buys borrowed coin at current market price and returns to market.
        Function also takes into account Binance's 0.1% transaction fee.
        If coin amount is not specified, bot will assume to try to pay back everything in return.
        :param stopLossExit: Boolean for whether last position was exited because of a stop loss.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to buy back to exit short position.
        :param force: Boolean that determines whether bot executed action or human.
        """
        with self.lock:
            if self.currentPosition != SHORT:
                return

            if coin is None:
                coin = self.coinOwed

            if coin <= 0:
                raise ValueError(f"You cannot buy {coin} {self.coinName}. Did you mean to sell short?")

            self.currentPrice = self.dataView.get_current_price()
            self.coinOwed -= coin
            self.customStopLoss = None
            self.currentPosition = None
            self.previousPosition = SHORT
            self.commissionPaid += self.currentPrice * coin * self.transactionFeePercentageDecimal
            self.balance -= self.currentPrice * coin * (1 + self.transactionFeePercentageDecimal)
            self.add_trade(msg, force=force, stopLossExit=stopLossExit)

            if self.coinOwed == 0:
                self.sellShortPrice = self.shortTrailingPrice = None

    def sell_short(self, msg: str, coin: float = None, force: bool = False, smartEnter: bool = False):
        """
        Borrows coin and sells them at current market price.
        Function also takes into account Binance's 0.1% transaction fee.
        If no coin is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        :param msg: Message to be used for displaying trade information.
        :param coin: Coin amount to sell to enter short position.
        :param force: Boolean that determines whether bot executed action or human.
        :param smartEnter: Boolean that'll determine whether current position is entered from a smart enter or not.
        """
        with self.lock:
            if self.currentPosition == SHORT:
                return

            self.currentPrice = self.dataView.get_current_price()

            if coin is None:
                transactionFee = self.balance * self.transactionFeePercentageDecimal
                coin = (self.balance - transactionFee) / self.currentPrice

            if coin <= 0:
                raise ValueError(f"You cannot borrow negative {abs(coin)} {self.coinName}.")

            self.coinOwed += coin
            self.commissionPaid += self.currentPrice * coin * self.transactionFeePercentageDecimal
            self.balance += self.currentPrice * coin * (1 - self.transactionFeePercentageDecimal)
            self.currentPosition = SHORT
            self.sellShortPrice = self.shortTrailingPrice = self.currentPrice
            self.add_trade(msg, force=force, smartEnter=smartEnter)

    def get_trend(self, dataObject: Data = None, log_data: bool = False) -> Union[int, None]:
        """
        Returns trend based on the strategies provided.
        :return: Integer in the form of an enum.
        """
        if not dataObject:
            dataObject = self.dataView

        trends = [strategy.get_trend(data=dataObject, log_data=log_data) for strategy in self.strategies.values()]
        return self.get_cumulative_trend(trends=trends)

    def short_position_logic(self, trend):
        """
        This function will handle all the logic when bot is in a short position.
        :param trend: Current trend the bot registers based on strategies provided.
        """
        if self.customStopLoss is not None and self.currentPrice >= self.customStopLoss:
            self.buy_short('Bought short because of custom stop loss.')
        elif self.get_stop_loss() is not None and self.currentPrice >= self.get_stop_loss():
            if not self.safetyTimer:
                self.buy_short('Bought short because of stop loss.', stopLossExit=True)
            else:
                if not self.scheduledSafetyTimer:
                    self.scheduledSafetyTimer = time.time() + self.safetyTimer
                else:
                    if time.time() > self.scheduledSafetyTimer:
                        self.buy_short('Bought short because of stop loss and safety timer.', stopLossExit=True)
        elif self.get_take_profit() is not None and self.currentPrice <= self.get_take_profit():
            self.buy_short('Bought short because of take profit.')
        elif not self.inHumanControl and trend == BULLISH:
            self.buy_short('Bought short because a bullish trend was detected.')
            self.buy_long('Bought long because a bullish trend was detected.')

    def long_position_logic(self, trend):
        """
        This function will handle all the logic when bot is in a long position.
        :param trend: Current trend the bot registers based on strategies provided.
        """
        if self.customStopLoss is not None and self.currentPrice <= self.customStopLoss:
            self.sell_long('Sold long because of custom stop loss.')
        elif self.get_stop_loss() is not None and self.currentPrice <= self.get_stop_loss():
            if not self.safetyTimer:
                self.sell_long('Sold long because of stop loss.', stopLossExit=True)
            else:
                if not self.scheduledSafetyTimer:
                    self.scheduledSafetyTimer = time.time() + self.safetyTimer
                else:
                    if time.time() > self.scheduledSafetyTimer:
                        self.sell_long('Sold long because of stop loss and safety timer.', stopLossExit=True)
        elif self.get_take_profit() is not None and self.currentPrice >= self.get_take_profit():
            self.sell_long('Sold long because of take profit.')
        elif not self.inHumanControl and trend == BEARISH:
            self.sell_long('Sold long because a cross was detected.')
            self.sell_short('Sold short because a cross was detected.')

    def no_position_logic(self, trend):
        """
        This function will handle all the logic when bot is not in any position.
        :param trend: Current trend the bot registers based on strategies provided.
        """
        if self.stopLossExit and self.smartStopLossCounter > 0:
            if self.previousPosition == LONG:
                if self.currentPrice > self.previousStopLoss:
                    self.buy_long('Reentered long because of smart stop loss.', smartEnter=True)
                    self.smartStopLossCounter -= 1
                    return
            elif self.previousPosition == SHORT:
                if self.currentPrice < self.previousStopLoss:
                    self.sell_short('Reentered short because of smart stop loss.', smartEnter=True)
                    self.smartStopLossCounter -= 1
                    return

        if not self.inHumanControl:
            if trend == BULLISH and self.previousPosition != LONG:
                self.buy_long('Bought long because a bullish trend was detected.')
                self.reset_smart_stop_loss()
            elif trend == BEARISH and self.previousPosition != SHORT:
                self.sell_short('Sold short because a bearish trend was detected.')
                self.reset_smart_stop_loss()

    # noinspection PyTypeChecker
    def main_logic(self, log_data: bool = True):
        """
        Main bot logic will use to trade.
        If there is a trend and the previous position did not reflect the trend, the bot enters position.
        :param log_data: Boolean that will determine where data is logged or not.
        """
        self.trend = trend = self.get_trend(log_data=log_data)
        if self.currentPosition == SHORT:
            self.short_position_logic(trend)
        elif self.currentPosition == LONG:
            self.long_position_logic(trend)
        else:
            self.no_position_logic(trend)

    def reset_smart_stop_loss(self):
        """
        Resets smart stop loss counter.
        """
        self.smartStopLossCounter = self.smartStopLossInitialCounter

    def get_net(self) -> float:
        """
        Returns net balance with current price of coin being traded. It factors in the current balance, the amount
        shorted, and the amount owned.
        :return: Net balance.
        """
        if self.currentPrice is None:
            self.currentPrice = self.dataView.get_current_price()

        return self.startingBalance + self.get_profit()

    def get_profit(self) -> float:
        """
        Returns profit or loss.
        :return: A number representing profit if positive and loss if negative.
        """
        if self.currentPrice is None:
            self.currentPrice = self.dataView.get_current_price()

        balance = self.balance
        balance += self.currentPrice * self.coin
        balance -= self.currentPrice * self.coinOwed

        return balance - self.startingBalance

    def get_coin_name(self) -> str:
        """
        Returns target coin name.
        Function assumes trader is using a coin paired with USDT.
        """
        temp = self.dataView.symbol.upper().split('USDT')
        return temp[0]

    def get_average(self, movingAverage: str, parameter: str, value: int, dataObject: Data = None,
                    update: bool = True, round_value: bool = False) -> float:
        """
        Returns the moving average with parameter and value provided
        :param round_value: Boolean for whether returned value should be rounded or not.
        :param update: Boolean for whether average will call the API to get latest values or not.
        :param dataObject: Data object to be used to get moving averages.
        :param movingAverage: Moving average to get the average from the data view.
        :param parameter: Parameter for the data view to use in the moving average.
        :param value: Value for the moving average to use in the moving average.
        :return: A float value representing the moving average.
        """
        if not dataObject:
            dataObject = self.dataView

        if movingAverage == 'SMA':
            return dataObject.get_sma(value, parameter, update=update, round_value=round_value)
        elif movingAverage == 'WMA':
            return dataObject.get_wma(value, parameter, update=update, round_value=round_value)
        elif movingAverage == 'EMA':
            return dataObject.get_ema(value, parameter, update=update, round_value=round_value)
        else:
            raise ValueError(f'Unknown moving average {movingAverage}.')

    def output_trade_options(self):
        """
        Outputs general information about current trade options.
        """
        if 'movingAverage' in self.strategies:
            for option in self.strategies['movingAverage'].get_params():
                initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
                finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

                self.output_message(f'Parameter: {option.parameter}')
                self.output_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
                self.output_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')

    def output_no_position_information(self):
        """
        Outputs general information about status of bot when not in a position.
        """
        if self.currentPosition is None:
            if not self.inHumanControl:
                self.output_message('\nCurrently not a in short or long position. Waiting for next cross.')
            else:
                self.output_message('\nCurrently not a in short or long position. Waiting for human intervention.')

    def output_short_information(self):
        """
        Outputs general information about status of trade when in a short position.
        """
        if self.currentPosition == SHORT and self.stopLoss is not None:
            self.output_message('\nCurrently in short position.')
            self.output_message(f'{self.get_stop_loss_strategy_string()}: ${round(self.stopLoss, self.precision)}')

    def output_long_information(self):
        """
        Outputs general information about status of trade when in a long position.
        """
        if self.currentPosition == LONG and self.stopLoss is not None:
            self.output_message('\nCurrently in long position.')
            self.output_message(f'{self.get_stop_loss_strategy_string()}: ${round(self.stopLoss, self.precision)}')

    def output_control_mode(self):
        """
        Outputs general information about status of bot.
        """
        if self.inHumanControl:
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

        if self.currentPrice is None:
            self.currentPrice = self.dataView.get_current_price()

        if self.currentPrice * self.coin > 5:  # If total worth of coin owned is more than $5, assume we're in long.
            self.output_message(f'{self.coinName} owned: {self.coin}')
            self.output_message(f'Price bot bought {self.coinName} long for: ${self.buyLongPrice}')

        if self.currentPrice * self.coinOwed > 5:  # If total worth of coin owed is more than $5, assume we're in short.
            self.output_message(f'{self.coinName} owed: {self.coinOwed}')
            self.output_message(f'Price bot sold {self.coinName} short for: ${self.sellShortPrice}')

        if self.currentPosition == LONG:
            self.output_long_information()
        elif self.currentPosition == SHORT:
            self.output_short_information()
        elif self.currentPosition is None:
            self.output_no_position_information()

        self.output_message(f'\nCurrent {self.coinName} price: ${self.currentPrice}')
        self.output_message(f'Balance: ${round(self.balance, self.precision)}')
        self.output_profit_information()
        if type(self) == SimulationTrader:
            self.output_message(f'\nTrades conducted this simulation: {len(self.trades)}\n')
        else:
            self.output_message(f'\nTrades conducted in live market: {len(self.trades)}\n')

    def get_run_result(self, isSimulation: bool = False):
        """
        Gets end result of simulation.
        :param isSimulation: Boolean that'll determine if coins are returned or not.
        """
        self.output_message('\n---------------------------------------------------\nBot run has ended.')
        self.endingTime = datetime.utcnow()
        if isSimulation and self.coin > 0:
            self.output_message(f"Selling all {self.coinName}...")
            self.sell_long('Sold all owned coin as simulation ended.')

        if isSimulation and self.coinOwed > 0:
            self.output_message(f"Returning all borrowed {self.coinName}...")
            self.buy_short('Returned all borrowed coin as simulation ended.')

        self.output_message("\nResults:")
        self.output_message(f'Starting time: {self.startingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'End time: {self.endingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'Elapsed time: {self.endingTime - self.startingTime}')
        self.output_message(f'Starting balance: ${self.startingBalance}')
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
        for index, net in enumerate(self.dailyChangeNets, start=1):
            self.output_message(f'Day {index}: {round(net, 2)}%')

        self.output_message("")

    def output_configuration(self):
        self.output_message('---------------------------------------------------')
        self.output_message('Bot Configuration:')
        self.output_message(f'\tStarting time: {self.startingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'\tStarting balance: ${self.startingBalance}')
        self.output_message(f'\tSymbol: {self.symbol}')
        self.output_message(f'\tInterval: {convert_small_interval(self.dataView.interval)}')
        self.output_message(f'\tPrecision: {self.precision}')
        self.output_message(f'\tTransaction fee percentage: {self.transactionFeePercentageDecimal}%')
        self.output_message(f'\tStarting coin: {self.coin}')
        self.output_message(f'\tStarting borrowed coin: {self.coinOwed}')
        self.output_message(f'\tStarting net: ${self.get_net()}')
        self.output_message(f'\tStop loss type: {self.get_stop_loss_strategy_string()}')
        self.output_message(f'\tLoss percentage: {self.lossPercentageDecimal * 100}%')
        self.output_message(f'\tSmart stop loss counter: {self.smartStopLossInitialCounter}')
        self.output_message(f'\tSafety timer: {self.safetyTimer}')
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
