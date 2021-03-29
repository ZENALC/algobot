import unittest

import pytest

from algobot.enums import BEARISH, BULLISH, LONG, SHORT, STOP, TRAILING
from algobot.traders.trader import Trader


class TestBaseTrader(unittest.TestCase):
    def setUp(self) -> None:
        """
        Sets up a backtester object.
        """
        self.trader = Trader(symbol="BTCUSDT", precision=2, startingBalance=1000)

    def test_add_trade(self):
        with pytest.raises(NotImplementedError, match='Please implement a function for adding trades.'):
            self.trader.add_trade()

    def test_buy_long(self):
        with pytest.raises(NotImplementedError, match='Please implement a function for buying long.'):
            self.trader.buy_long()

    def test_sell_long(self):
        with pytest.raises(NotImplementedError, match='Please implement a function for selling long.'):
            self.trader.sell_long()

    def test_sell_short(self):
        with pytest.raises(NotImplementedError, match='Please implement a function for selling short.'):
            self.trader.sell_short()

    def test_buy_short(self):
        with pytest.raises(NotImplementedError, match='Please implement a function for buying short.'):
            self.trader.buy_short()

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

    def test_setup_strategies(self):
        pass

    def test_get_stop_loss(self):
        pass

    def test_get_stop_loss_strategy_string(self):
        self.trader.lossStrategy = STOP
        self.assertEqual(self.trader.get_stop_loss_strategy_string(), "Stop Loss")

        self.trader.lossStrategy = TRAILING
        self.assertEqual(self.trader.get_stop_loss_strategy_string(), "Trailing Loss")

        self.trader.lossStrategy = None
        self.assertEqual(self.trader.get_stop_loss_strategy_string(), "None")

    def test_get_strategy_inputs(self):
        pass

    def test_get_strategies_info_string(self):
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


if __name__ == '__main__':
    unittest.main()
