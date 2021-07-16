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
    startDate, endDate = get_calendar_dates(config_obj=gui.configuration, caller=caller)
    precision = algo_dict['precision'].currentText()
    symbol = gui.configuration.optimizer_backtest_dict[caller]['dataType']

    d = {
        'startDate': startDate,
        'endDate': endDate,
        'symbol': symbol,
        'startingBalance': algo_dict['startingBalance'].value(),
        'data': gui.configuration.optimizer_backtest_dict[caller]['data'],
        'precision': parse_precision(precision, symbol),
        'marginEnabled': algo_dict['marginEnabled'].isChecked(),
        'strategyInterval': algo_dict['strategyInterval'].currentText(),
        'logger': gui.logger
    }

    if caller == OPTIMIZER:
        d.update({
            'drawdownPercentage': algo_dict['drawdownPercentage'].value(),
            'strategies': []
        })

    if caller == BACKTEST:
        d.update({
            'outputTrades': algo_dict['outputTrades'].isChecked(),
            'strategies': get_strategies(gui.configuration, BACKTEST),
        })

    return d
