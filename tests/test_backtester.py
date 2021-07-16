"""
Test backtester object.
"""

import os
from datetime import datetime

import pytest

from algobot.enums import LONG, SHORT, STOP, TRAILING
from algobot.helpers import convert_all_dates_to_datetime, load_from_csv
from algobot.traders.backtester import Backtester

test_data = load_from_csv(path=f'{os.path.dirname(__file__)}/1INCHUSDT_data_1m.csv', descending=False)
convert_all_dates_to_datetime(test_data)


@pytest.fixture(scope='function', name='backtester')
def get_backtester():
    """
    Sets up a backtester object and returns it as a fixture.
    """
    backtester = Backtester(
            startingBalance=1000,
            data=test_data,
            strategies=[],
            strategyInterval='15m',
            symbol="1INCHUSDT",
            marginEnabled=True,
        )
    backtester.apply_take_profit_settings({'takeProfitType': TRAILING, 'takeProfitPercentage': 5})
    backtester.apply_loss_settings({'lossType': TRAILING, 'lossPercentage': 5})
    return backtester


def test_initialization(backtester: Backtester):
    """
    Test initialization of backtester object.
    """
    assert backtester.interval == "1 Minute"
    assert backtester.intervalMinutes == 1
    assert backtester.takeProfitPercentageDecimal == 0.05
    assert backtester.startDateIndex == 0
    assert backtester.endDateIndex == len(test_data) - 1
    assert backtester.strategyInterval == "15 Minutes"
    assert backtester.strategyIntervalMinutes == 15
    assert backtester.intervalGapMinutes == 14
    assert backtester.intervalGapMultiplier == 15
    assert backtester.data[0]['date_utc'] < backtester.data[1]['date_utc']


def test_get_gap_data(backtester: Backtester):
    """
    Test gap data return function.
    """
    gap_data = backtester.data[:15]
    max_price = max([data['high'] for data in gap_data])
    min_price = min([data['low'] for data in gap_data])
    volume = sum([data['volume'] for data in gap_data])
    result = backtester.get_gap_data(gap_data)

    assert gap_data[0]['date_utc'] == result['date_utc']
    assert gap_data[0]['open'] == result['open']
    assert gap_data[-1]['close'] == result['close']
    assert min_price == result['low']
    assert max_price == result['high']
    assert volume == result['volume']

    backtester.strategyInterval = '1 Hour'
    gap_data = backtester.data[10:70]
    max_price = max([data['high'] for data in gap_data])
    min_price = min([data['low'] for data in gap_data])
    volume = sum([data['volume'] for data in gap_data])
    result = backtester.get_gap_data(gap_data, check=False)

    assert gap_data[0]['date_utc'] == result['date_utc']
    assert gap_data[0]['open'] == result['open']
    assert gap_data[-1]['close'] == result['close']
    assert min_price == result['low']
    assert max_price == result['high']
    assert volume == result['volume']


def test_check_data(backtester: Backtester):
    """
    Tests check data function.
    """
    backtester.data.reverse()
    backtester.check_data()

    assert backtester.data[0]['date_utc'] < backtester.data[-1]['date_utc']


def test_find_date_index(backtester: Backtester):
    """
    Test find date index function.
    """
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

    assert len(backtester.data) == index


def test_get_start_date_index(backtester: Backtester):
    """
    Test get start date index function.
    """
    assert backtester.get_start_index(backtester.data[0]['date_utc']) == 0
    assert backtester.get_start_index(backtester.data[5]['date_utc']) == 0

    with pytest.raises(IndexError, match="Date not found"):
        backtester.get_start_index(datetime(1998, 1, 1, 1, 1))


def test_get_end_date_index(backtester: Backtester):
    """
    Test get end date index function.
    """
    assert backtester.get_end_index(backtester.data[-1]['date_utc']) == len(backtester.data) - 1
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


def test_buy_long(backtester: Backtester):
    """
    Tests backtester buy long function.
    """
    backtester.set_indexed_current_price_and_period(0)
    backtester.buy_long("Test purchase.")
    commission = backtester.transactionFeePercentageDecimal * backtester.startingBalance

    assert backtester.commissionsPaid == commission
    assert backtester.currentPosition == LONG
    assert backtester.coin == (backtester.startingBalance - commission) / backtester.currentPrice
    assert backtester.balance == 0
    assert backtester.buyLongPrice == backtester.currentPrice
    assert backtester.trades[0]['action'] == "Test purchase."
    assert backtester.trades[0]['date'] == backtester.currentPeriod['date_utc']


def test_sell_long(backtester: Backtester):
    """
    Test backtester sell long function.
    """
    backtester.set_indexed_current_price_and_period(0)
    commission = backtester.balance * backtester.transactionFeePercentageDecimal
    backtester.buy_long("Test purchase to test sell.")

    backtester.set_indexed_current_price_and_period(3)
    commission += backtester.coin * backtester.currentPrice * backtester.transactionFeePercentageDecimal
    backtester.sell_long("Test sell.")

    assert backtester.commissionsPaid == commission
    assert backtester.currentPosition is None
    assert backtester.coin == 0
    assert backtester.balance == backtester.get_net()
    assert backtester.trades[1]['action'] == "Test sell."
    assert backtester.trades[1]['date'] == backtester.currentPeriod['date_utc']


def test_sell_short(backtester: Backtester):
    """
    Tests backtester sell short function.
    """
    backtester.set_indexed_current_price_and_period(0)
    backtester.sell_short("Test short.")

    commission = backtester.transactionFeePercentageDecimal * backtester.startingBalance
    balance = backtester.startingBalance + backtester.currentPrice * backtester.coinOwed - commission

    assert backtester.commissionsPaid == commission
    assert backtester.currentPosition == SHORT
    assert backtester.coinOwed == backtester.startingBalance / backtester.currentPrice
    assert backtester.balance == balance
    assert backtester.sellShortPrice == backtester.currentPrice
    assert backtester.trades[0]['action'] == "Test short."
    assert backtester.trades[0]['date'] == backtester.currentPeriod['date_utc']


def test_buy_short(backtester: Backtester):
    """
    Tests backtester buy short function.
    """
    backtester.set_indexed_current_price_and_period(0)
    backtester.sell_short("Test sell short to buy short.")

    backtester.set_indexed_current_price_and_period(3)
    commission = backtester.startingBalance * backtester.transactionFeePercentageDecimal
    commission += backtester.coinOwed * backtester.currentPrice * backtester.transactionFeePercentageDecimal
    backtester.buy_short("Test buy short.")

    assert backtester.commissionsPaid == commission
    assert backtester.currentPosition is None
    assert backtester.coinOwed == 0
    assert backtester.balance == backtester.get_net()
    assert backtester.trades[1]['action'] == "Test buy short."
    assert backtester.trades[1]['date'] == backtester.currentPeriod['date_utc']


def test_add_trade_and_reset_trades(backtester: Backtester):
    """
    Tests backtester add trade functionality.
    """
    backtester.set_indexed_current_price_and_period(0)
    backtester.add_trade("Test add trade.")

    assert backtester.trades[0]['date'] == backtester.currentPeriod['date_utc']
    assert backtester.trades[0]['action'] == "Test add trade."
    assert backtester.trades[0]['net'] == round(backtester.get_net(), backtester.precision)

    backtester.reset_trades()
    assert backtester.trades == []


def test_smart_stop_loss(backtester: Backtester):
    """
    Tests backtester smart stop loss logic.
    """
    test_counter = 3  # Don't change this.
    backtester.set_smart_stop_loss_counter(test_counter)
    assert backtester.smartStopLossInitialCounter == test_counter

    backtester.set_priced_current_price_and_period(5)
    backtester.buy_long("Dummy purchase to test smart stop loss.")
    backtester.set_priced_current_price_and_period(4)
    backtester.main_logic()  # Stop loss triggered.
    backtester.set_priced_current_price_and_period(5)
    backtester.main_logic()  # Smart stop loss purchase.
    assert backtester.smartStopLossCounter == test_counter - 1

    backtester.set_priced_current_price_and_period(3)
    backtester.main_logic()  # Stop loss triggered.
    backtester.set_priced_current_price_and_period(6)
    backtester.main_logic()  # Smart stop loss purchase.
    assert backtester.smartStopLossCounter == test_counter - 2

    backtester.set_priced_current_price_and_period(2)
    backtester.main_logic()  # Stop loss triggered.
    backtester.set_priced_current_price_and_period(1.9)
    backtester.main_logic()  # No smart stop loss purchase.
    assert backtester.smartStopLossCounter == test_counter - 2

    backtester.set_priced_current_price_and_period(10)
    backtester.main_logic()  # Smart stop loss purchase.
    assert backtester.smartStopLossCounter == test_counter - 3

    backtester.set_priced_current_price_and_period(1)
    backtester.main_logic()  # Stop loss triggered.
    backtester.smartStopLossCounter = 0  # Set stop loss counter at 0, so bot can't reenter.
    backtester.set_priced_current_price_and_period(150)  # Set exorbitant price but don't let bot reenter.
    backtester.main_logic()  # Should not reenter as counter is 0.
    assert backtester.currentPosition is None
    assert backtester.smartStopLossCounter == 0

    backtester.reset_smart_stop_loss()  # Counter is reset.
    backtester.main_logic()  # Should reenter.
    assert backtester.currentPosition == LONG
    assert backtester.smartStopLossCounter == backtester.smartStopLossInitialCounter - 1


def test_long_stop_loss(backtester: Backtester):
    """
    Test backtester stop loss logic in a long position.
    """
    backtester.lossStrategy = STOP
    backtester.set_priced_current_price_and_period(5)
    backtester.buy_long("Test purchase.")
    assert backtester.get_stop_loss() == 5 * (1 - backtester.lossPercentageDecimal)

    backtester.set_priced_current_price_and_period(10)
    assert backtester.get_stop_loss() == 5 * (1 - backtester.lossPercentageDecimal)

    backtester.lossStrategy = TRAILING
    assert backtester.get_stop_loss() == 10 * (1 - backtester.lossPercentageDecimal)


def test_short_stop_loss(backtester: Backtester):
    """
    Test backtester stop loss logic in a short position.
    """
    backtester.lossStrategy = STOP
    backtester.set_priced_current_price_and_period(5)
    backtester.sell_short("Test short.")
    assert backtester.get_stop_loss() == 5 * (1 + backtester.lossPercentageDecimal)

    backtester.set_priced_current_price_and_period(3)
    assert backtester.get_stop_loss() == 5 * (1 + backtester.lossPercentageDecimal)

    backtester.lossStrategy = TRAILING
    assert backtester.get_stop_loss() == 3 * (1 + backtester.lossPercentageDecimal)


def test_stop_take_profit(backtester: Backtester):
    """
    Test backtester take profit logic.
    """
    backtester.takeProfitType = STOP
    backtester.set_priced_current_price_and_period(10)
    backtester.buy_long("Test purchase.")
    assert backtester.get_take_profit() == 10 * (1 + backtester.takeProfitPercentageDecimal)

    backtester.sell_long("Test sell long.")
    backtester.sell_short("Sell short.")
    assert backtester.get_take_profit() == 10 * (1 - backtester.takeProfitPercentageDecimal)


def test_trailing_take_profit(backtester: Backtester):
    """
    Test trailing take profit.
    """
    pass
