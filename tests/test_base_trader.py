"""
Test base trader.
"""

import pytest

from algobot.enums import BEARISH, BULLISH, LONG, SHORT, STOP, TRAILING
from algobot.traders.trader import Trader


@pytest.fixture(scope='function', name='trader')
def get_trader_object() -> Trader:
    """
    Get a trader object.
    :return: Trader
    """
    return Trader(symbol="BTCUSDT", precision=2, starting_balance=1000)


def test_add_trade(trader: Trader):
    """
    Test trader add trade functionality.
    :param trader: Trader object.
    """
    trader.current_period = {'date_utc': 'test_date'}
    trader.current_price = 10

    trader.add_trade(message="test_trade", stop_loss_exit=True, smart_enter=True)
    assert trader.stop_loss_exit is True
    assert trader.smart_stop_loss_enter is True
    assert trader.trades[-1] == {
        'date': 'test_date',
        'action': 'test_trade',
        'net': trader.starting_balance
    }


def test_buy_long(trader: Trader):
    """
    Test trader buy long functionality.
    :param trader: Trader object.
    """
    trader.current_period = {'date_utc': 'test_date'}
    trader.current_price = 10

    transaction_fee = trader.starting_balance * trader.transaction_fee_percentage_decimal
    coin = (trader.starting_balance - transaction_fee) / trader.current_price

    trader.buy_long("test_buy", smart_enter=True)
    assert trader.smart_stop_loss_enter is True
    assert trader.stop_loss_exit is False
    assert trader.current_position == LONG
    assert trader.buy_long_price == trader.current_price
    assert trader.long_trailing_price == trader.current_price
    assert trader.balance == 0
    assert trader.coin == coin
    assert trader.commissions_paid == transaction_fee
    assert trader.trades[-1] == {
        'date': 'test_date',
        'action': 'test_buy',
        'net': round(trader.get_net(), trader.precision)
    }


def test_sell_long(trader: Trader):
    """
    Test trader sell long functionality.
    :param trader: Trader object.
    """
    trader.current_period = {'date_utc': 'test_date'}
    trader.current_price = 10

    transaction_fee = trader.starting_balance * trader.transaction_fee_percentage_decimal
    coin = (trader.starting_balance - transaction_fee) / trader.current_price

    trader.buy_long("test_buy")
    trader.current_price = 15

    previous_transaction_fee = transaction_fee
    transaction_fee = coin * trader.current_price * trader.transaction_fee_percentage_decimal
    balance = coin * trader.current_price - transaction_fee

    trader.sell_long("test_sell", stop_loss_exit=True)
    assert trader.smart_stop_loss_enter is False
    assert trader.stop_loss_exit is True
    assert trader.balance == balance
    assert trader.current_position is None
    assert trader.previous_position == LONG
    assert trader.buy_long_price is None
    assert trader.long_trailing_price is None
    assert trader.commissions_paid == transaction_fee + previous_transaction_fee
    assert trader.coin == 0
    assert trader.trades[-1] == {
        'date': 'test_date',
        'action': 'test_sell',
        'net': round(trader.get_net(), trader.precision)
    }


def test_sell_short(trader: Trader):
    """
    Test trader sell short functionality.
    :param trader: Trader object.
    """
    trader.current_period = {'date_utc': 'test_date'}
    trader.current_price = 10

    transaction_fee = trader.starting_balance * trader.transaction_fee_percentage_decimal
    coin_owed = trader.starting_balance / trader.current_price

    trader.sell_short("test_short")
    assert trader.smart_stop_loss_enter is False
    assert trader.stop_loss_exit is False
    assert trader.balance == trader.starting_balance * 2 - transaction_fee
    assert trader.current_position == SHORT
    assert trader.sell_short_price == trader.current_price
    assert trader.short_trailing_price == trader.current_price
    assert trader.coin == 0
    assert trader.coin_owed == coin_owed
    assert trader.commissions_paid == transaction_fee
    assert trader.trades[-1] == {
        'date': 'test_date',
        'action': 'test_short',
        'net': round(trader.get_net(), trader.precision)
    }


def test_buy_short(trader: Trader):
    """
    Test trader buy short functionality.
    :param trader: Trader object.
    """
    trader.current_period = {'date_utc': 'test_date'}
    trader.current_price = 10

    transaction_fee = trader.starting_balance * trader.transaction_fee_percentage_decimal
    coin_owed = trader.starting_balance / trader.current_price

    trader.sell_short("test_short", smart_enter=True)
    trader.current_price = 5

    previous_transaction_fee = transaction_fee
    transaction_fee = coin_owed * trader.current_price * trader.transaction_fee_percentage_decimal
    balance = trader.balance - coin_owed * trader.current_price - transaction_fee

    trader.buy_short("test_end_short", stop_loss_exit=True)
    assert trader.stop_loss_exit is True
    assert trader.smart_stop_loss_enter is False
    assert trader.current_position is None
    assert trader.previous_position == SHORT
    assert trader.sell_short_price is None
    assert trader.short_trailing_price is None
    assert trader.balance == balance
    assert trader.commissions_paid == previous_transaction_fee + transaction_fee
    assert trader.coin == 0
    assert trader.coin_owed == 0
    assert trader.trades[-1] == {
        'date': 'test_date',
        'action': 'test_end_short',
        'net': round(trader.get_net(), trader.precision)
    }


def test_set_and_reset_smart_stop_loss(trader: Trader):
    """
    Test trader set and reset smart stop loss functionality.
    :param trader: Trader object.
    """
    trader.set_smart_stop_loss_counter(5)
    trader.smart_stop_loss_counter = 0
    trader.reset_smart_stop_loss()
    assert trader.smart_stop_loss_counter == 5


def test_set_safety_timer(trader: Trader):
    """
    Test trader set safety timer functionality.
    :param trader: Trader object.
    """
    trader.set_safety_timer(0)
    assert trader.safety_timer is None

    trader.set_safety_timer(10)
    assert trader.safety_timer == 10


def test_apply_take_profit_settings(trader: Trader):
    """
    Test trader apply take profit settings functionality.
    :param trader: Trader object.
    """
    take_profit_settings = {
        'takeProfitPercentage': 25,
        'takeProfitType': STOP
    }
    trader.apply_take_profit_settings(take_profit_settings)

    assert trader.take_profit_percentage_decimal == 0.25
    assert trader.take_profit_type == STOP


def test_apply_loss_settings(trader: Trader):
    """
    Test trader apply loss settings functionality.
    :param trader: Trader object.
    """
    loss_settings = {
        'lossType': STOP,
        'lossPercentage': 5.5,
        'smartStopLossCounter': 15,
        'safetyTimer': 45
    }
    trader.apply_loss_settings(loss_settings)

    assert trader.loss_strategy == STOP
    assert trader.loss_percentage_decimal == 0.055
    assert trader.smart_stop_loss_initial_counter == 15
    assert trader.smart_stop_loss_counter == 15
    assert trader.safety_timer == 45


def test_get_stop_loss(trader: Trader):
    """
    Test trader get stop loss functionality.
    :param trader: Trader object.
    """
    trader.loss_strategy = STOP
    trader.loss_percentage_decimal = 0.1
    trader.current_price = 5

    trader.current_position = LONG
    trader.buy_long_price = 10
    assert trader.get_stop_loss() == 10 * (1 - trader.loss_percentage_decimal)

    trader.current_position = SHORT
    trader.sell_short_price = 10
    assert trader.get_stop_loss() == 10 * (1 + trader.loss_percentage_decimal)

    trader.current_position = None
    assert trader.get_stop_loss() is None

    # TODO implement trailing stop loss test


def test_get_stop_loss_strategy_string(trader: Trader):
    """
    Test trader sell long functionality.
    :param trader: Trader object.
    """
    trader.loss_strategy = STOP
    assert trader.get_stop_loss_strategy_string() == "Stop Loss"

    trader.loss_strategy = TRAILING
    assert trader.get_stop_loss_strategy_string() == "Trailing Loss"

    trader.loss_strategy = None
    assert trader.get_stop_loss_strategy_string() == "None"


@pytest.mark.parametrize(
    'trends, expected',
    [
        ([BEARISH, BULLISH, BEARISH, None], None),
        ([BEARISH, BEARISH, BEARISH], BEARISH),
        ([BULLISH, BULLISH, BULLISH, BULLISH, BULLISH], BULLISH)
     ]
)
def test_get_cumulative_trend(trader: Trader, trends, expected):
    """
    Test trader get cumulative trend.
    """
    assert trader.get_cumulative_trend(trends) == expected


@pytest.mark.parametrize(
    'initial_net, final_net, expected',
    [
        (100, 200, 100),
        (100, 0, -100),
        (100, 50, -50),
        (100, 130, 30)
    ]
)
def test_get_profit_percentage(trader: Trader, initial_net, final_net, expected):
    """
    Test trader get profit percentage.
    """
    assert trader.get_profit_percentage(initial_net, final_net) == expected


@pytest.mark.parametrize(
    'profit_or_loss, expected',
    [
        (0, 'Profit'),
        (5, 'Profit'),
        (-1, 'Loss')
    ]
)
def test_get_profit_or_loss_string(trader: Trader, profit_or_loss, expected):
    """
    Test trader get profit or loss string functionality.
    """
    assert trader.get_profit_or_loss_string(profit_or_loss) == expected


@pytest.mark.parametrize(
    'current_position, expected',
    [
        (LONG, 'Long'),
        (SHORT, 'Short'),
        (None, 'None')
    ]
)
def test_get_position_string(trader: Trader, current_position, expected):
    """
    Test trader get position string functionality.
    """
    trader.current_position = current_position
    assert trader.get_position_string() == expected


@pytest.mark.parametrize(
    'current_position',
    [LONG, SHORT, None]
)
def test_get_position(trader: Trader, current_position):
    """
    Test trader get position functionality.
    """
    trader.current_position = current_position
    assert trader.get_position() == current_position


@pytest.mark.parametrize(
    'percentage, expected',
    [
        (0.05123, '5.12%'),
        (0.01, '1.0%')
    ]
)
def test_get_safe_rounded_percentage(trader: Trader, percentage, expected):
    """
    Test trader get safe rounded percentage functionality.
    """
    assert trader.get_safe_rounded_percentage(percentage) == expected


def test_get_safe_rounded_string(trader: Trader):
    """
    Test trader get safe rounded string functionality.
    """
    trader.precision = 3
    assert trader.get_safe_rounded_string(value=5.1231) == '$5.123'
    assert trader.get_safe_rounded_string(value=5.12345, round_digits=5) == '$5.12345'
    assert trader.get_safe_rounded_string(value=5.12345, round_digits=0) == '$5.0'
    assert trader.get_safe_rounded_string(1.23, round_digits=2, symbol='*', direction='right', multiplier=5) == '6.15*'


def test_get_take_profit(trader: Trader):
    """
    Test trader get take profit functionality.
    """
    trader.take_profit_type = STOP
    trader.take_profit_percentage_decimal = 0.05

    trader.current_position = LONG
    trader.buy_long_price = 10
    assert trader.get_take_profit() == 10 * (1 + 0.05)

    trader.current_position = SHORT
    trader.sell_short_price = 10
    assert trader.get_take_profit() == 10 * (1 - 0.05)

    trader.take_profit_type = None
    assert trader.get_take_profit() is None

    trader.take_profit_type = 5
    with pytest.raises(ValueError, match="Invalid type of take profit type provided."):
        trader.get_take_profit()


def test_get_net(trader: Trader):
    """
    Test trader get net.
    """
    trader.current_period = {'date_utc': 'test_date'}
    trader.current_price = 100
    trader.buy_long("test")

    trader.current_price = 200
    assert trader.get_net() == trader.current_price * trader.coin

    trader.current_price = 50
    assert trader.get_net() == trader.current_price * trader.coin
    trader.sell_long("end_buy_net")

    trader.starting_balance = trader.balance = 1000
    trader.commissions_paid = 0
    trader.current_price = 20
    trader.sell_short("test_short")
    assert trader.get_net() == trader.starting_balance - trader.commissions_paid

    trader.current_price = 10
    trader.buy_short("test_end_short")
    assert round(trader.get_net(), 2) == 1498.50

    trader.starting_balance = trader.balance = 1000
    trader.commissions_paid = 0
    trader.current_price = 5
    trader.sell_short("test")
    trader.buy_short("test")
    assert trader.get_net() == 998
