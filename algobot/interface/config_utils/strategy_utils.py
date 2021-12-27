"""
Strategy helper functions for configuration.py can be found here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from PyQt5.QtWidgets import QComboBox

from algobot.helpers import get_interval_minutes, get_interval_strings

if TYPE_CHECKING:
    from algobot.interface.configuration import Configuration


def strategy_enabled(config_obj: Configuration, strategy_name: str, caller: str) -> bool:
    """
    Returns a boolean whether a strategy is enabled or not.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param strategy_name: Name of strategy to check if enabled.
    :param caller: Caller of the strategy.
    :return: Boolean whether strategy is enabled or not.
    """
    tab = config_obj.get_category_tab(caller)

    if strategy_name in config_obj.hidden_strategies:
        return False

    return config_obj.strategy_dict[tab, strategy_name, 'groupBox'].isChecked()


def get_strategies(config_obj: Configuration, caller: str) -> List[Dict[str, Any]]:
    """
    Returns strategy information from GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that asked for strategy information.
    :return: List of strategy information.
    """
    strategies = []
    for custom_strategy in config_obj.json_strategies.values():
        strategy_name = custom_strategy['name']
        if strategy_enabled(config_obj, strategy_name, caller):
            strategies.append(config_obj.strategy_dict[config_obj.get_category_tab(caller), strategy_name])

    return strategies


def reset_strategy_interval_combo_box(strategy_combobox: QComboBox, interval_combobox: QComboBox,
                                      start_index: int = 0, filter_intervals: bool = True, divisor: int = None):
    """
    This function will reset the strategy combobox based on what interval is picked in the interval combobox.
    :param strategy_combobox: Combobox to modify based on the interval combobox.
    :param interval_combobox: Interval combobox that will trigger this function.
    :param start_index: Optional start index to start from when getting interval strings.
    :param filter_intervals: Boolean on whether to filter tickers or not.
    :param divisor: Divisor to use for filtering intervals. If none is provided, it will use data interval minutes.
    """
    data_interval = interval_combobox.currentText()
    if not data_interval:
        return  # Means text is empty, so just return.

    data_interval_minutes = get_interval_minutes(data_interval)
    data_index = interval_combobox.currentIndex()

    strategy_interval = strategy_combobox.currentText()
    intervals = get_interval_strings(starting_index=start_index + data_index)

    if filter_intervals:
        divisor = divisor if divisor is not None else data_interval_minutes
        intervals = [interval for interval in intervals if get_interval_minutes(interval) % divisor == 0]

    strategy_combobox.clear()
    strategy_combobox.addItems(intervals)

    previous_strategy_interval_index = strategy_combobox.findText(strategy_interval)
    if previous_strategy_interval_index != -1:
        strategy_combobox.setCurrentIndex(previous_strategy_interval_index)
