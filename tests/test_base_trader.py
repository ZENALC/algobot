"""
Test base trader.
"""

import pytest

from algobot.enums import BEARISH, BULLISH, LONG, SHORT, STOP, TRAILING
from algobot.strategies.strategy import Strategy
from algobot.traders.trader import Trader


@pytest.fixture(scope='function', name='trader')
def get_trader_object() -> Trader:
    """
    Get a trader object.
    :return: Trader
    """
    return Trader(symbol="BTCUSDT", precision=2, startingBalance=1000)


def test_add_trade(trader: Trader):
    """
    Test trader add trade functionality.
    :param trader: Trader object.
    """
    trader.currentPeriod = {'date_utc': 'test_date'}
    trader.currentPrice = 10

    trader.add_trade(message="test_trade", stopLossExit=True, smartEnter=True)
    assert trader.stopLossExit is True
    assert trader.smartStopLossEnter is True
    assert trader.trades[-1] == {
        'date': 'test_date',
        'action': 'test_trade',
        'net': trader.startingBalance
    }


def test_buy_long(trader: Trader):
    """
    Test trader buy long functionality.
    :param trader: Trader object.
    """
    trader.currentPeriod = {'date_utc': 'test_date'}
    trader.currentPrice = 10

    transaction_fee = trader.startingBalance * trader.transactionFeePercentageDecimal
    coin = (trader.startingBalance - transaction_fee) / trader.currentPrice

    trader.buy_long("test_buy", smartEnter=True)
    assert trader.smartStopLossEnter is True
    assert trader.stopLossExit is False
    assert trader.currentPosition == LONG
    assert trader.buyLongPrice == trader.currentPrice
    assert trader.longTrailingPrice == trader.currentPrice
    assert trader.balance == 0
    assert trader.coin == coin
    assert trader.commissionsPaid == transaction_fee
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
    trader.currentPeriod = {'date_utc': 'test_date'}
    trader.currentPrice = 10

    transaction_fee = trader.startingBalance * trader.transactionFeePercentageDecimal
    coin = (trader.startingBalance - transaction_fee) / trader.currentPrice

    trader.buy_long("test_buy")
    trader.currentPrice = 15

    previous_transaction_fee = transaction_fee
    transaction_fee = coin * trader.currentPrice * trader.transactionFeePercentageDecimal
    balance = coin * trader.currentPrice - transaction_fee

    trader.sell_long("test_sell", stopLossExit=True)
    assert trader.smartStopLossEnter is False
    assert trader.stopLossExit is True
    assert trader.balance == balance
    assert trader.currentPosition is None
    assert trader.previousPosition == LONG
    assert trader.buyLongPrice is None
    assert trader.longTrailingPrice is None
    assert trader.commissionsPaid == transaction_fee + previous_transaction_fee
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
    trader.currentPeriod = {'date_utc': 'test_date'}
    trader.currentPrice = 10

    transaction_fee = trader.startingBalance * trader.transactionFeePercentageDecimal
    coin_owed = trader.startingBalance / trader.currentPrice

    trader.sell_short("test_short")
    assert trader.smartStopLossEnter is False
    assert trader.stopLossExit is False
    assert trader.balance == trader.startingBalance * 2 - transaction_fee
    assert trader.currentPosition == SHORT
    assert trader.sellShortPrice == trader.currentPrice
    assert trader.shortTrailingPrice == trader.currentPrice
    assert trader.coin == 0
    assert trader.coinOwed == coin_owed
    assert trader.commissionsPaid == transaction_fee
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
    trader.currentPeriod = {'date_utc': 'test_date'}
    trader.currentPrice = 10

    transaction_fee = trader.startingBalance * trader.transactionFeePercentageDecimal
    coin_owed = trader.startingBalance / trader.currentPrice

    trader.sell_short("test_short", smartEnter=True)
    trader.currentPrice = 5

    previous_transaction_fee = transaction_fee
    transaction_fee = coin_owed * trader.currentPrice * trader.transactionFeePercentageDecimal
    balance = trader.balance - coin_owed * trader.currentPrice - transaction_fee

    trader.buy_short("test_end_short", stopLossExit=True)
    assert trader.stopLossExit is True
    assert trader.smartStopLossEnter is False
    assert trader.currentPosition is None
    assert trader.previousPosition == SHORT
    assert trader.sellShortPrice is None
    assert trader.shortTrailingPrice is None
    assert trader.balance == balance
    assert trader.commissionsPaid == previous_transaction_fee + transaction_fee
    assert trader.coin == 0
    assert trader.coinOwed == 0
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
    trader.smartStopLossCounter = 0
    trader.reset_smart_stop_loss()
    assert trader.smartStopLossCounter == 5


def test_set_safety_timer(trader: Trader):
    """
    Test trader set safety timer functionality.
    :param trader: Trader object.
    """
    trader.set_safety_timer(0)
    assert trader.safetyTimer is None

    trader.set_safety_timer(10)
    assert trader.safetyTimer == 10


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

    assert trader.takeProfitPercentageDecimal == 0.25
    assert trader.takeProfitType == STOP


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

    assert trader.lossStrategy == STOP
    assert trader.lossPercentageDecimal == 0.055
    assert trader.smartStopLossInitialCounter == 15
    assert trader.smartStopLossCounter == 15
    assert trader.safetyTimer == 45


def test_get_stop_loss(trader: Trader):
    """
    Test trader get stop loss functionality.
    :param trader: Trader object.
    """
    trader.lossStrategy = STOP
    trader.lossPercentageDecimal = 0.1
    trader.currentPrice = 5

    trader.currentPosition = LONG
    trader.buyLongPrice = 10
    assert trader.get_stop_loss() == 10 * (1 - trader.lossPercentageDecimal)

    trader.currentPosition = SHORT
    trader.sellShortPrice = 10
    assert trader.get_stop_loss() == 10 * (1 + trader.lossPercentageDecimal)

    trader.currentPosition = None
    assert trader.get_stop_loss() is None

    # TODO implement trailing stop loss test


def test_get_stop_loss_strategy_string(trader: Trader):
    """
    Test trader sell long functionality.
    :param trader: Trader object.
    """
    trader.lossStrategy = STOP
    assert trader.get_stop_loss_strategy_string() == "Stop Loss"

    trader.lossStrategy = TRAILING
    assert trader.get_stop_loss_strategy_string() == "Trailing Loss"

    trader.lossStrategy = None
    assert trader.get_stop_loss_strategy_string() == "None"


def test_get_strategy_inputs(trader: Trader):
    """
    Test trader get strategy inputs functionality.
    :param trader: Trader object.
    """
    dummy_strategy = Strategy(name="dummy", parent=None)

    def temp():
        return 3, 4, 5

    dummy_strategy.get_params = temp
    assert dummy_strategy.get_params() == (3, 4, 5)

    trader.strategies = {'dummy': dummy_strategy}
    assert trader.get_strategy_inputs('dummy') == '3, 4, 5'


def test_get_strategies_info_string(trader: Trader):
    """
    Test trader get strategies info string functionality.
    :param trader: Trader object.
    """
    dummy_strategy = Strategy(name="dummy", parent=None)
    dummy_strategy2 = Strategy(name='dummy2', parent=None)

    def temp():
        return 3, 4, 5

    def temp2():
        return 5, 6, 7, 8, 9, 10

    dummy_strategy.get_params = temp
    dummy_strategy2.get_params = temp2
    expected_string = 'Strategies:\n\tDummy: 3, 4, 5\n\tDummy2: 5, 6, 7, 8, 9, 10'

    trader.strategies = {'dummy': dummy_strategy, 'dummy2': dummy_strategy2}
    assert trader.get_strategies_info_string() == expected_string


def test_get_trend(trader: Trader):
    """
    Test trader get trend functionality.
    :param trader: Trader object.
    """
    assert trader.get_trend() is None

    bullish_strategy1 = Strategy(name='b1', parent=None)
    bullish_strategy1.trend = BULLISH

    trader.strategies['b1'] = bullish_strategy1
    assert trader.get_trend() == BULLISH

    bullish_strategy2 = Strategy(name='b2', parent=None)
    bullish_strategy2.trend = BULLISH

    trader.strategies['b2'] = bullish_strategy2
    assert trader.get_trend() == BULLISH

    bearish_strategy = Strategy(name='b3', parent=None)
    bearish_strategy.trend = BEARISH

    trader.strategies['b3'] = bearish_strategy
    assert trader.get_trend() is None

    for strategy in trader.strategies.values():
        strategy.trend = BEARISH

    assert trader.get_trend() == BEARISH


def test_setup_strategies(trader: Trader):
    """
    Test trader setup strategies functionality.  # TODO: Implement actual test.
    :param trader: Trader object.
    """
    pass


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
    'stop_type, expected',
    [
        (STOP, 'Stop'),
        (TRAILING, 'Trailing'),
        (None, 'None')
    ]
)
def test_get_trailing_or_stop_loss_string(trader: Trader, stop_type, expected):
    """
    Test trader get trailing or stop loss string.
    """
    assert trader.get_trailing_or_stop_type_string(stop_type) == expected


@pytest.mark.parametrize(
    'trend, expected',
    [
        (None, 'None'),
        (BEARISH, "Bearish"),
        (BULLISH, "Bullish")
    ]
)
def test_get_trend_string(trader: Trader, trend, expected):
    """
    Test trader get trend string functionality.
    """
    assert trader.get_trend_string(trend) == expected


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
    trader.currentPosition = current_position
    assert trader.get_position_string() == expected


@pytest.mark.parametrize(
    'current_position',
    [LONG, SHORT, None]
)
def test_get_position(trader: Trader, current_position):
    """
    Test trader get position functionality.
    """
    trader.currentPosition = current_position
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
    assert trader.get_safe_rounded_string(value=5.12345, roundDigits=5) == '$5.12345'
    assert trader.get_safe_rounded_string(value=5.12345, roundDigits=0) == '$5.0'
    assert trader.get_safe_rounded_string(1.23, roundDigits=2, symbol='*', direction='right', multiplier=5) == '6.15*'


def test_get_take_profit(trader: Trader):
    """
    Test trader get take profit functionality.
    """
    trader.takeProfitType = STOP
    trader.takeProfitPercentageDecimal = 0.05

    trader.currentPosition = LONG
    trader.buyLongPrice = 10
    assert trader.get_take_profit() == 10 * (1 + 0.05)

    trader.currentPosition = SHORT
    trader.sellShortPrice = 10
    assert trader.get_take_profit() == 10 * (1 - 0.05)

    trader.takeProfitType = None
    assert trader.get_take_profit() is None

    trader.takeProfitType = 5
    with pytest.raises(ValueError, match="Invalid type of take profit type provided."):
        trader.get_take_profit()


def test_get_net(trader: Trader):
    """
    Test trader get net.
    """
    trader.currentPeriod = {'date_utc': 'test_date'}
    trader.currentPrice = 100
    trader.buy_long("test")

    trader.currentPrice = 200
    assert trader.get_net() == trader.currentPrice * trader.coin

    trader.currentPrice = 50
    assert trader.get_net() == trader.currentPrice * trader.coin
    trader.sell_long("end_buy_net")

    trader.startingBalance = trader.balance = 1000
    trader.commissionsPaid = 0
    trader.currentPrice = 20
    trader.sell_short("test_short")
    assert trader.get_net() == trader.startingBalance - trader.commissionsPaid

    trader.currentPrice = 10
    trader.buy_short("test_end_short")
    assert round(trader.get_net(), 2) == 1498.50

    trader.startingBalance = trader.balance = 1000
    trader.commissionsPaid = 0
    trader.currentPrice = 5
    trader.sell_short("test")
    trader.buy_short("test")
    assert trader.get_net() == 998
