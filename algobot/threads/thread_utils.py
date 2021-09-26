"""
Some helpers for threads.
"""
from typing import Any, Dict

from algobot.algodict import get_interface_dictionary
from algobot.enums import BACKTEST, OPTIMIZER
from algobot.helpers import parse_precision
from algobot.interface.config_utils.calendar_utils import get_calendar_dates
from algobot.interface.config_utils.strategy_utils import get_strategies


def get_config_helper(gui, caller) -> Dict[str, Any]:
    """
    Get configuration settings for backtests and optimizers. TODO: Cleanup.
    :param gui: GUI object that called this function.
    :param caller: Caller object (backtest or optimizer in this case).
    :return: Dictionary containing configuration settings.
    """
    algo_dict = get_interface_dictionary(gui, caller)['configuration']
    start_date, end_date = get_calendar_dates(config_obj=gui.configuration, caller=caller)
    precision = algo_dict['precision'].currentText()
    symbol = gui.configuration.optimizer_backtest_dict[caller]['dataType']

    temp_dict = {
        'start_date': start_date,
        'end_date': end_date,
        'symbol': symbol,
        'starting_balance': algo_dict['startingBalance'].value(),
        'data': gui.configuration.optimizer_backtest_dict[caller]['data'],
        'precision': parse_precision(precision, symbol),
        'margin_enabled': algo_dict['marginEnabled'].isChecked(),
        'strategy_interval': algo_dict['strategyInterval'].currentText(),
        'logger': gui.logger
    }

    if caller == OPTIMIZER:
        temp_dict.update({
            'drawdown_percentage': algo_dict['drawdownPercentage'].value(),
            'strategies': []
        })

    if caller == BACKTEST:
        temp_dict.update({
            'output_trades': algo_dict['outputTrades'].isChecked(),
            'strategies': get_strategies(gui.configuration, BACKTEST),
        })

    return temp_dict
