import os
import unittest
from datetime import datetime

import pytest

from algobot.enums import LONG, SHORT, STOP, TRAILING
from algobot.helpers import convert_all_dates_to_datetime, load_from_csv
from algobot.traders.backtester import Backtester

test_data = load_from_csv(path=f'{os.path.dirname(__file__)}/1INCHUSDT_data_1m.csv', descending=False)
convert_all_dates_to_datetime(test_data)


class TestBacktester(unittest.TestCase):
    def setUp(self) -> None:
        """
        Sets up a backtester object.
        """
        self.backtester = Backtester(
            startingBalance=1000,
            data=test_data,
            strategies=[],
            strategyInterval='15m',
            symbol="1INCHUSDT",
            marginEnabled=True,
        )
        self.backtester.apply_take_profit_settings({'takeProfitType': TRAILING, 'takeProfitPercentage': 5})
        self.backtester.apply_loss_settings({'lossType': TRAILING, 'lossPercentage': 5})

    def test_initialization(self):
        """
        Test initialization of backtester object.
        """
        backtester = self.backtester
        self.assertEqual(backtester.interval, "1 Minute")
        self.assertEqual(backtester.intervalMinutes, 1)
        self.assertEqual(backtester.takeProfitPercentageDecimal, 0.05)
        self.assertEqual(backtester.startDateIndex, 0)
        self.assertEqual(backtester.endDateIndex, len(test_data) - 1)
        self.assertEqual(backtester.strategyInterval, "15 Minutes")
        self.assertEqual(backtester.strategyIntervalMinutes, 15)
        self.assertEqual(backtester.intervalGapMinutes, 14)
        self.assertEqual(backtester.intervalGapMultiplier, 15)
        self.assertTrue(backtester.data[0]['date_utc'] < backtester.data[1]['date_utc'])

    def test_get_gap_data(self):
        """
        Test gap data return function.
        """
        backtester = self.backtester

        gap_data = backtester.data[:15]
        max_price = max([data['high'] for data in gap_data])
        min_price = min([data['low'] for data in gap_data])
        result = backtester.get_gap_data(gap_data)

        self.assertEqual(gap_data[0]['date_utc'], result['date_utc'])
        self.assertEqual(gap_data[0]['open'], result['open'])
        self.assertEqual(gap_data[-1]['close'], result['close'])
        self.assertEqual(min_price, result['low'])
        self.assertEqual(max_price, result['high'])

        backtester.strategyInterval = '1 Hour'
        gap_data = backtester.data[10:70]
        max_price = max([data['high'] for data in gap_data])
        min_price = min([data['low'] for data in gap_data])
        result = backtester.get_gap_data(gap_data, check=False)

        self.assertEqual(gap_data[0]['date_utc'], result['date_utc'])
        self.assertEqual(gap_data[0]['open'], result['open'])
        self.assertEqual(gap_data[-1]['close'], result['close'])
        self.assertEqual(min_price, result['low'])
        self.assertEqual(max_price, result['high'])

    def test_check_data(self):
        """
        Tests check data function.
        """
        backtester = self.backtester
        backtester.data.reverse()
        backtester.check_data()

        self.assertTrue(backtester.data[0]['date_utc'] < backtester.data[-1]['date_utc'])

    def test_find_date_index(self):
        """
        Tests find date index function.
        """
        backtester = self.backtester
        data = {
            'date_utc': datetime(2025, 1, 1, 1, 1, 1),
            'open': 0,
            'close': 0,
            'high': 0,
            'low': 0
        }

        backtester.data.append(data)
        index = backtester.find_date_index(data['date_utc'])
        backtester.data.pop()

        self.assertEqual(len(backtester.data), index)

    def test_get_start_date_index(self):
        """
        Test get start date index function.
        """
        backtester = self.backtester
        self.assertEqual(backtester.get_start_index(backtester.data[0]['date_utc']), 0)
        self.assertEqual(backtester.get_start_index(backtester.data[5]['date_utc']), 0)

        with pytest.raises(IndexError, match="Date not found"):
            backtester.get_start_index(datetime(1998, 1, 1, 1, 1))

    def test_get_end_date_index(self):
        """
        Test get end date index function.
        """
        backtester = self.backtester
        self.assertEqual(backtester.get_end_index(backtester.data[-1]['date_utc']), len(backtester.data) - 1)

        with pytest.raises(IndexError, match="Date not found."):
            backtester.get_end_index(datetime(2000, 1, 1))

        test_date = backtester.data[0]['date_utc']
        index = backtester.find_date_index(test_date, starting=False)
        backtester.data = backtester.data[index:]
        with pytest.raises(IndexError, match="You need at least one data period."):
            backtester.get_end_index(test_date)

        test_date = backtester.data[3]['date_utc']
        backtester.startDateIndex = 3
        backtester.data = backtester.data[:4]
        with pytest.raises(IndexError, match="Ending date index cannot be less than or equal to start date index."):
            backtester.get_end_index(test_date)

    def test_buy_long(self):
        """
        Tests backtester buy long function.
        """
        backtester = self.backtester
        backtester.set_indexed_current_price_and_period(0)
        backtester.buy_long("Test purchase.")

        rem = 1 - backtester.transactionFeePercentage  # Percentage of transaction left over.

        self.assertEqual(backtester.commissionsPaid, backtester.transactionFeePercentage * backtester.startingBalance)
        self.assertEqual(backtester.currentPosition, LONG)
        self.assertEqual(backtester.coin, backtester.startingBalance / backtester.currentPrice * rem)
        self.assertEqual(backtester.balance, 0)
        self.assertEqual(backtester.buyLongPrice, backtester.currentPrice)
        self.assertEqual(backtester.trades[0]['action'], "Test purchase.")
        self.assertEqual(backtester.trades[0]['date'], backtester.currentPeriod['date_utc'])

    def test_sell_long(self):
        """
        Test backtester sell long function.
        """
        backtester = self.backtester
        backtester.set_indexed_current_price_and_period(0)
        commission = backtester.balance * backtester.transactionFeePercentage
        backtester.buy_long("Test purchase to test sell.")

        backtester.set_indexed_current_price_and_period(3)
        commission += backtester.coin * backtester.currentPrice * backtester.transactionFeePercentage
        backtester.sell_long("Test sell.")

        self.assertEqual(backtester.commissionsPaid, commission)
        self.assertEqual(backtester.currentPosition, None)
        self.assertEqual(backtester.coin, 0)
        self.assertEqual(backtester.balance, backtester.get_net())
        self.assertEqual(backtester.trades[1]['action'], "Test sell.")
        self.assertEqual(backtester.trades[1]['date'], backtester.currentPeriod['date_utc'])

    def test_sell_short(self):
        """
        Tests backtester sell short function.
        """
        backtester = self.backtester
        backtester.set_indexed_current_price_and_period(0)
        backtester.sell_short("Test short.")

        rem = 1 - backtester.transactionFeePercentage
        commission = backtester.transactionFeePercentage * backtester.startingBalance
        balance = backtester.startingBalance + backtester.currentPrice * backtester.coinOwed - commission

        self.assertEqual(backtester.commissionsPaid, commission)
        self.assertEqual(backtester.currentPosition, SHORT)
        self.assertEqual(backtester.coinOwed, backtester.startingBalance / backtester.currentPrice * rem)
        self.assertEqual(backtester.balance, balance)
        self.assertEqual(backtester.sellShortPrice, backtester.currentPrice)
        self.assertEqual(backtester.trades[0]['action'], "Test short.")
        self.assertEqual(backtester.trades[0]['date'], backtester.currentPeriod['date_utc'])

    def test_buy_short(self):
        """
        Tests backtester buy short function.
        """
        backtester = self.backtester
        backtester.set_indexed_current_price_and_period(0)
        backtester.sell_short("Test sell short to buy short.")

        backtester.set_indexed_current_price_and_period(3)
        commission = backtester.startingBalance * backtester.transactionFeePercentage
        commission += backtester.coinOwed * backtester.currentPrice * backtester.transactionFeePercentage
        backtester.buy_short("Test buy short.")

        self.assertEqual(backtester.commissionsPaid, commission)
        self.assertEqual(backtester.currentPosition, None)
        self.assertEqual(backtester.coinOwed, 0)
        self.assertEqual(backtester.balance, backtester.get_net())
        self.assertEqual(backtester.trades[1]['action'], "Test buy short.")
        self.assertEqual(backtester.trades[1]['date'], backtester.currentPeriod['date_utc'])

    def test_add_trade_and_reset_trades(self):
        """
        Tests backtester add trade functionality.
        """
        backtester = self.backtester
        backtester.set_indexed_current_price_and_period(0)
        backtester.add_trade("Test add trade.")

        self.assertEqual(backtester.trades[0]['date'], backtester.currentPeriod['date_utc'])
        self.assertEqual(backtester.trades[0]['action'], "Test add trade.")
        self.assertEqual(backtester.trades[0]['net'], round(backtester.get_net(), backtester.precision))

        backtester.reset_trades()
        self.assertEqual(backtester.trades, [])

    def test_smart_stop_loss(self):
        """
        Tests backtester smart stop loss logic.
        """
        backtester = self.backtester
        test_counter = 3  # Don't change this.
        backtester.set_smart_stop_loss_counter(test_counter)
        self.assertEqual(backtester.smartStopLossInitialCounter, test_counter)

        backtester.set_priced_current_price_and_period(5)
        backtester.buy_long("Dummy purchase to test smart stop loss.")
        backtester.set_priced_current_price_and_period(4)
        backtester.main_logic()  # Stop loss triggered.
        backtester.set_priced_current_price_and_period(5)
        backtester.main_logic()  # Smart stop loss purchase.
        self.assertEqual(backtester.smartStopLossCounter, test_counter - 1)

        backtester.set_priced_current_price_and_period(3)
        backtester.main_logic()  # Stop loss triggered.
        backtester.set_priced_current_price_and_period(6)
        backtester.main_logic()  # Smart stop loss purchase.
        self.assertEqual(backtester.smartStopLossCounter, test_counter - 2)

        backtester.set_priced_current_price_and_period(2)
        backtester.main_logic()  # Stop loss triggered.
        backtester.set_priced_current_price_and_period(1.9)
        backtester.main_logic()  # No smart stop loss purchase.
        self.assertEqual(backtester.smartStopLossCounter, test_counter - 2)

        backtester.set_priced_current_price_and_period(10)
        backtester.main_logic()  # Smart stop loss purchase.
        self.assertEqual(backtester.smartStopLossCounter, test_counter - 3)

        backtester.set_priced_current_price_and_period(1)
        backtester.main_logic()  # Stop loss triggered.
        backtester.smartStopLossCounter = 0  # Set stop loss counter at 0, so bot can't reenter.
        backtester.set_priced_current_price_and_period(150)  # Set exorbitant price but don't let bot reenter.
        backtester.main_logic()  # Should not reenter as counter is 0.
        self.assertEqual(backtester.currentPosition, None)
        self.assertEqual(backtester.smartStopLossCounter, 0)

        backtester.reset_smart_stop_loss()  # Counter is reset.
        backtester.main_logic()  # Should reenter.
        self.assertEqual(backtester.currentPosition, LONG)
        self.assertEqual(backtester.smartStopLossCounter, backtester.smartStopLossInitialCounter - 1)

    def test_long_stop_loss(self):
        """
        Test backtester stop loss logic in a long position.
        """
        backtester = self.backtester
        backtester.lossStrategy = STOP
        backtester.set_priced_current_price_and_period(5)
        backtester.buy_long("Test purchase.")
        self.assertEqual(backtester.get_stop_loss(), 5 * (1 - backtester.lossPercentageDecimal))

        backtester.set_priced_current_price_and_period(10)
        self.assertEqual(backtester.get_stop_loss(), 5 * (1 - backtester.lossPercentageDecimal))

        backtester.lossStrategy = TRAILING
        self.assertEqual(backtester.get_stop_loss(), 10 * (1 - backtester.lossPercentageDecimal))

    def test_short_stop_loss(self):
        """
        Test backtester stop loss logic in a short position.
        """
        backtester = self.backtester
        backtester.lossStrategy = STOP
        backtester.set_priced_current_price_and_period(5)
        backtester.sell_short("Test short.")
        self.assertEqual(backtester.get_stop_loss(), 5 * (1 + backtester.lossPercentageDecimal))

        backtester.set_priced_current_price_and_period(3)
        self.assertEqual(backtester.get_stop_loss(), 5 * (1 + backtester.lossPercentageDecimal))

        backtester.lossStrategy = TRAILING
        self.assertEqual(backtester.get_stop_loss(), 3 * (1 + backtester.lossPercentageDecimal))

    def test_stop_take_profit(self):
        """
        Test backtester take profit logic.
        """
        backtester = self.backtester
        backtester.takeProfitType = STOP
        backtester.set_priced_current_price_and_period(10)
        backtester.buy_long("Test purchase.")
        self.assertEqual(backtester.get_take_profit(), 10 * (1 + backtester.takeProfitPercentageDecimal))

        backtester.sell_long("Test sell long.")
        backtester.sell_short("Sell short.")
        self.assertEqual(backtester.get_take_profit(), 10 * (1 - backtester.takeProfitPercentageDecimal))

    def test_trailing_take_profit(self):
        pass


if __name__ == '__main__':
    unittest.main()
