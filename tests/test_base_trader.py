import unittest

import pytest

from algobot.enums import BEARISH, BULLISH, LONG, SHORT, STOP, TRAILING
from algobot.strategies.strategy import Strategy
from algobot.traders.trader import Trader


class TestBaseTrader(unittest.TestCase):
    def setUp(self) -> None:
        """
        Sets up a backtester object.
        """
        self.trader = Trader(symbol="BTCUSDT", precision=2, startingBalance=1000)

    def test_add_trade(self):
        self.trader.currentPeriod = {'date_utc': 'test_date'}
        self.trader.currentPrice = 10

        self.trader.add_trade(message="test_trade", stopLossExit=True, smartEnter=True)
        self.assertEqual(self.trader.stopLossExit, True)
        self.assertEqual(self.trader.smartStopLossEnter, True)
        self.assertEqual(self.trader.trades[-1], {
            'date': 'test_date',
            'action': 'test_trade',
            'net': self.trader.startingBalance
        })

    def test_buy_long(self):
        self.trader.currentPeriod = {'date_utc': 'test_date'}
        self.trader.currentPrice = 10

        transaction_fee = self.trader.startingBalance * self.trader.transactionFeePercentageDecimal
        coin = (self.trader.startingBalance - transaction_fee) / self.trader.currentPrice

        self.trader.buy_long("test_buy", smartEnter=True)
        self.assertEqual(self.trader.smartStopLossEnter, True)
        self.assertEqual(self.trader.stopLossExit, False)
        self.assertEqual(self.trader.currentPosition, LONG)
        self.assertEqual(self.trader.buyLongPrice, self.trader.currentPrice)
        self.assertEqual(self.trader.longTrailingPrice, self.trader.currentPrice)
        self.assertEqual(self.trader.balance, 0)
        self.assertEqual(self.trader.coin, coin)
        self.assertEqual(self.trader.commissionsPaid, transaction_fee)
        self.assertEqual(self.trader.trades[-1], {
            'date': 'test_date',
            'action': 'test_buy',
            'net': round(self.trader.get_net(), self.trader.precision)
        })

    def test_sell_long(self):
        self.trader.currentPeriod = {'date_utc': 'test_date'}
        self.trader.currentPrice = 10

        transaction_fee = self.trader.startingBalance * self.trader.transactionFeePercentageDecimal
        coin = (self.trader.startingBalance - transaction_fee) / self.trader.currentPrice

        self.trader.buy_long("test_buy")
        self.trader.currentPrice = 15

        previous_transaction_fee = transaction_fee
        transaction_fee = coin * self.trader.currentPrice * self.trader.transactionFeePercentageDecimal
        balance = coin * self.trader.currentPrice - transaction_fee

        self.trader.sell_long("test_sell", stopLossExit=True)
        self.assertEqual(self.trader.smartStopLossEnter, False)
        self.assertEqual(self.trader.stopLossExit, True)
        self.assertEqual(self.trader.balance, balance)
        self.assertEqual(self.trader.currentPosition, None)
        self.assertEqual(self.trader.previousPosition, LONG)
        self.assertEqual(self.trader.buyLongPrice, None)
        self.assertEqual(self.trader.longTrailingPrice, None)
        self.assertEqual(self.trader.commissionsPaid, transaction_fee + previous_transaction_fee)
        self.assertEqual(self.trader.coin, 0)
        self.assertEqual(self.trader.trades[-1], {
            'date': 'test_date',
            'action': 'test_sell',
            'net': round(self.trader.get_net(), self.trader.precision)
        })

    def test_sell_short(self):
        self.trader.currentPeriod = {'date_utc': 'test_date'}
        self.trader.currentPrice = 10

        transaction_fee = self.trader.startingBalance * self.trader.transactionFeePercentageDecimal
        coin_owed = self.trader.startingBalance / self.trader.currentPrice

        self.trader.sell_short("test_short")
        self.assertEqual(self.trader.smartStopLossEnter, False)
        self.assertEqual(self.trader.stopLossExit, False)
        self.assertEqual(self.trader.balance, self.trader.startingBalance * 2 - transaction_fee)
        self.assertEqual(self.trader.currentPosition, SHORT)
        self.assertEqual(self.trader.sellShortPrice, self.trader.currentPrice)
        self.assertEqual(self.trader.shortTrailingPrice, self.trader.currentPrice)
        self.assertEqual(self.trader.coin, 0)
        self.assertEqual(self.trader.coinOwed, coin_owed)
        self.assertEqual(self.trader.commissionsPaid, transaction_fee)
        self.assertEqual(self.trader.trades[-1], {
            'date': 'test_date',
            'action': 'test_short',
            'net': round(self.trader.get_net(), self.trader.precision)
        })

    def test_buy_short(self):
        self.trader.currentPeriod = {'date_utc': 'test_date'}
        self.trader.currentPrice = 10

        transaction_fee = self.trader.startingBalance * self.trader.transactionFeePercentageDecimal
        coin_owed = self.trader.startingBalance / self.trader.currentPrice

        self.trader.sell_short("test_short", smartEnter=True)
        self.trader.currentPrice = 5

        previous_transaction_fee = transaction_fee
        transaction_fee = coin_owed * self.trader.currentPrice * self.trader.transactionFeePercentageDecimal
        balance = self.trader.balance - coin_owed * self.trader.currentPrice - transaction_fee

        self.trader.buy_short("test_end_short", stopLossExit=True)
        self.assertEqual(self.trader.stopLossExit, True)
        self.assertEqual(self.trader.smartStopLossEnter, False)
        self.assertEqual(self.trader.currentPosition, None)
        self.assertEqual(self.trader.previousPosition, SHORT)
        self.assertEqual(self.trader.sellShortPrice, None)
        self.assertEqual(self.trader.shortTrailingPrice, None)
        self.assertEqual(self.trader.balance, balance)
        self.assertEqual(self.trader.commissionsPaid, previous_transaction_fee + transaction_fee)
        self.assertEqual(self.trader.coin, 0)
        self.assertEqual(self.trader.coinOwed, 0)
        self.assertEqual(self.trader.trades[-1], {
            'date': 'test_date',
            'action': 'test_end_short',
            'net': round(self.trader.get_net(), self.trader.precision)
        })

    def test_set_and_reset_smart_stop_loss(self):
        self.trader.set_smart_stop_loss_counter(5)
        self.trader.smartStopLossCounter = 0
        self.trader.reset_smart_stop_loss()
        self.assertEqual(self.trader.smartStopLossCounter, 5)

    def test_set_safety_timer(self):
        self.trader.set_safety_timer(0)
        self.assertEqual(self.trader.safetyTimer, None)

        self.trader.set_safety_timer(10)
        self.assertEqual(self.trader.safetyTimer, 10)

    def test_apply_take_profit_settings(self):
        take_profit_settings = {
            'takeProfitPercentage': 25,
            'takeProfitType': STOP
        }
        self.trader.apply_take_profit_settings(take_profit_settings)

        self.assertEqual(self.trader.takeProfitPercentageDecimal, 0.25)
        self.assertEqual(self.trader.takeProfitType, STOP)

    def test_apply_loss_settings(self):
        loss_settings = {
            'lossType': STOP,
            'lossPercentage': 5.5,
            'smartStopLossCounter': 15,
            'safetyTimer': 45
        }
        self.trader.apply_loss_settings(loss_settings)

        self.assertEqual(self.trader.lossStrategy, STOP)
        self.assertEqual(self.trader.lossPercentageDecimal, 0.055)
        self.assertEqual(self.trader.smartStopLossInitialCounter, 15)
        self.assertEqual(self.trader.smartStopLossCounter, 15)
        self.assertEqual(self.trader.safetyTimer, 45)

    def test_get_stop_loss(self):
        self.trader.lossStrategy = STOP
        self.trader.lossPercentageDecimal = 0.1
        self.trader.currentPrice = 5

        self.trader.currentPosition = LONG
        self.trader.buyLongPrice = 10
        self.assertEqual(self.trader.get_stop_loss(), 10 * (1 - self.trader.lossPercentageDecimal))

        self.trader.currentPosition = SHORT
        self.trader.sellShortPrice = 10
        self.assertEqual(self.trader.get_stop_loss(), 10 * (1 + self.trader.lossPercentageDecimal))

        self.trader.currentPosition = None
        self.assertEqual(self.trader.get_stop_loss(), None)

        # TODO implement trailing stop loss test

    def test_get_stop_loss_strategy_string(self):
        self.trader.lossStrategy = STOP
        self.assertEqual(self.trader.get_stop_loss_strategy_string(), "Stop Loss")

        self.trader.lossStrategy = TRAILING
        self.assertEqual(self.trader.get_stop_loss_strategy_string(), "Trailing Loss")

        self.trader.lossStrategy = None
        self.assertEqual(self.trader.get_stop_loss_strategy_string(), "None")

    def test_get_strategy_inputs(self):
        dummy_strategy = Strategy(name="dummy", parent=None)

        def temp():
            return 3, 4, 5

        dummy_strategy.get_params = temp
        self.assertEqual(dummy_strategy.get_params(), (3, 4, 5))

        self.trader.strategies = {'dummy': dummy_strategy}
        self.assertEqual(self.trader.get_strategy_inputs('dummy'), '3, 4, 5')

    def test_get_strategies_info_string(self):
        dummy_strategy = Strategy(name="dummy", parent=None)
        dummy_strategy2 = Strategy(name='dummy2', parent=None)

        def temp():
            return 3, 4, 5

        def temp2():
            return 5, 6, 7, 8, 9, 10

        dummy_strategy.get_params = temp
        dummy_strategy2.get_params = temp2
        expected_string = '\nStrategies:\n\tDummy: 3, 4, 5\n\tDummy2: 5, 6, 7, 8, 9, 10'

        self.trader.strategies = {'dummy': dummy_strategy, 'dummy2': dummy_strategy2}
        self.assertEqual(self.trader.get_strategies_info_string(), expected_string)

    def test_get_trend(self):
        self.assertEqual(self.trader.get_trend(), None)

        bullish_strategy1 = Strategy(name='b1', parent=None)
        bullish_strategy1.trend = BULLISH

        self.trader.strategies['b1'] = bullish_strategy1
        self.assertEqual(self.trader.get_trend(), BULLISH)

        bullish_strategy2 = Strategy(name='b2', parent=None)
        bullish_strategy2.trend = BULLISH

        self.trader.strategies['b2'] = bullish_strategy2
        self.assertEqual(self.trader.get_trend(), BULLISH)

        bearish_strategy = Strategy(name='b3', parent=None)
        bearish_strategy.trend = BEARISH

        self.trader.strategies['b3'] = bearish_strategy
        self.assertEqual(self.trader.get_trend(), None)

        for strategy in self.trader.strategies:
            self.trader.strategies[strategy].trend = BEARISH

        self.assertEqual(self.trader.get_trend(), BEARISH)

    def test_setup_strategies(self):
        pass

    def test_get_cumulative_trend(self):
        trends = [BEARISH, BULLISH, BEARISH, None]
        self.assertEqual(self.trader.get_cumulative_trend(trends), None)

        trends = [BEARISH, BEARISH, BEARISH]
        self.assertEqual(self.trader.get_cumulative_trend(trends), BEARISH)

        trends = [BULLISH, BULLISH, BULLISH, BULLISH, BULLISH]
        self.assertEqual(self.trader.get_cumulative_trend(trends), BULLISH)

    def test_get_profit_percentage(self):
        self.assertEqual(self.trader.get_profit_percentage(100, 200), 100)
        self.assertEqual(self.trader.get_profit_percentage(100, 0), -100)
        self.assertEqual(self.trader.get_profit_percentage(100, 50), -50)
        self.assertEqual(self.trader.get_profit_percentage(100, 130), 30)

    def test_get_trailing_or_stop_loss_string(self):
        self.assertEqual(self.trader.get_trailing_or_stop_type_string(STOP), 'Stop')
        self.assertEqual(self.trader.get_trailing_or_stop_type_string(TRAILING), 'Trailing')
        self.assertEqual(self.trader.get_trailing_or_stop_type_string(None), 'None')

    def test_get_trend_string(self):
        self.assertEqual(self.trader.get_trend_string(None), str(None))
        self.assertEqual(self.trader.get_trend_string(BEARISH), "Bearish")
        self.assertEqual(self.trader.get_trend_string(BULLISH), "Bullish")

    def test_get_profit_or_loss_string(self):
        self.assertEqual(self.trader.get_profit_or_loss_string(0), 'Profit')
        self.assertEqual(self.trader.get_profit_or_loss_string(5), 'Profit')
        self.assertEqual(self.trader.get_profit_or_loss_string(-1), 'Loss')

    def test_get_position_string(self):
        self.trader.currentPosition = LONG
        self.assertEqual(self.trader.get_position_string(), "Long")

        self.trader.currentPosition = SHORT
        self.assertEqual(self.trader.get_position_string(), "Short")

        self.trader.currentPosition = None
        self.assertEqual(self.trader.get_position_string(), "None")

    def test_get_position(self):
        self.trader.currentPosition = LONG
        self.assertEqual(self.trader.get_position(), LONG)

        self.trader.currentPosition = SHORT
        self.assertEqual(self.trader.get_position(), SHORT)

        self.trader.currentPosition = None
        self.assertEqual(self.trader.get_position(), None)

    def test_get_safe_rounded_percentage(self):
        self.assertEqual(self.trader.get_safe_rounded_percentage(0.05123), '5.12%')
        self.assertEqual(self.trader.get_safe_rounded_percentage(0.01), '1.0%')

    def test_get_safe_rounded_string(self):
        self.trader.precision = 3
        self.assertEqual(self.trader.get_safe_rounded_string(value=5.1231), '$5.123')
        self.assertEqual(self.trader.get_safe_rounded_string(value=5.12345, roundDigits=5), '$5.12345')
        self.assertEqual(self.trader.get_safe_rounded_string(value=5.12345, roundDigits=0), '$5.0')
        self.assertEqual(self.trader.get_safe_rounded_string(value=1.23, roundDigits=2, symbol='*', direction='right',
                                                             multiplier=5), '6.15*')

    def test_get_take_profit(self):
        self.trader.takeProfitType = STOP
        self.trader.takeProfitPercentageDecimal = 0.05

        self.trader.currentPosition = LONG
        self.trader.buyLongPrice = 10
        self.assertEqual(self.trader.get_take_profit(), 10 * (1 + 0.05))

        self.trader.currentPosition = SHORT
        self.trader.sellShortPrice = 10
        self.assertEqual(self.trader.get_take_profit(), 10 * (1 - 0.05))

        self.trader.takeProfitType = None
        self.assertEqual(self.trader.get_take_profit(), None)

        self.trader.takeProfitType = 5
        with pytest.raises(ValueError, match="Invalid type of take profit type provided."):
            self.trader.get_take_profit()

    def test_get_net(self):
        self.trader.currentPeriod = {'date_utc': 'test_date'}
        self.trader.currentPrice = 100
        self.trader.buy_long("test")

        self.trader.currentPrice = 200
        self.assertEqual(self.trader.get_net(), self.trader.currentPrice * self.trader.coin)

        self.trader.currentPrice = 50
        self.assertEqual(self.trader.get_net(), self.trader.currentPrice * self.trader.coin)
        self.trader.sell_long("end_buy_net")

        self.trader.startingBalance = self.trader.balance = 1000
        self.trader.commissionsPaid = 0
        self.trader.currentPrice = 20
        self.trader.sell_short("test_short")
        self.assertEqual(self.trader.get_net(), self.trader.startingBalance - self.trader.commissionsPaid)

        self.trader.currentPrice = 10
        self.trader.buy_short("test_end_short")
        self.assertEqual(round(self.trader.get_net(), 2), 1498.50)

        self.trader.startingBalance = self.trader.balance = 1000
        self.trader.commissionsPaid = 0
        self.trader.currentPrice = 5
        self.trader.sell_short("test")
        self.trader.buy_short("test")
        self.assertEqual(self.trader.get_net(), 998)


if __name__ == '__main__':
    unittest.main()
