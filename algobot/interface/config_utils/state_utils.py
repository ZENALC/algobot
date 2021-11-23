"""
Various utility functions for Algobot state.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from algobot import helpers
from algobot.graph_helpers import set_color_to_label
from algobot.interface.config_utils.slot_utils import (delete_strategy_slots, load_custom_strategy_slots,
                                                       load_strategy_slots)

if TYPE_CHECKING:
    from algobot.interface.configuration import Configuration


def load_state(config_obj: Configuration):
    """
    This function will attempt to load previous basic configuration settings from config_obj.state_file_path.
    :param config_obj: Configuration object.
    """
    if os.path.exists(config_obj.state_file_path):
        try:
            config = helpers.load_json_file(config_obj.state_file_path)

            config_obj.lightModeRadioButton.setChecked(config['lightTheme'])
            config_obj.darkModeRadioButton.setChecked(config['darkTheme'])
            config_obj.bloombergModeRadioButton.setChecked(config['bloombergTheme'])
            config_obj.bullModeRadioButton.setChecked(config['bullTheme'])
            config_obj.bearModeRadioButton.setChecked(config['bearTheme'])

            set_color_to_label(config_obj.balanceColor, config['balanceColor'])
            set_color_to_label(config_obj.hoverLineColor, (config['lineColor']))

            config_obj.graphIndicatorsCheckBox.setChecked(config['averagePlot'])
            config_obj.enableHoverLine.setChecked(config['hoverLine'])
            config_obj.failureLimitSpinBox.setValue(int(config['failureLimit']))
            config_obj.failureSleepSpinBox.setValue(int(config['failureSleep']))
            config_obj.token_pass = config['tokenPass']
            config_obj.chat_pass = config['chatPass']
            config_obj.telegrationConnectionResult.setText(config['telegramResult'])

            # Load saved tickers.
            config_obj.tickerLineEdit.setText(config['mainTicker'])
            config_obj.simulationTickerLineEdit.setText(config['simTicker'])
            config_obj.optimizerTickerLineEdit.setText(config['optimizerTicker'])
            config_obj.backtestTickerLineEdit.setText(config['backtestTicker'])

            # Load intervals.
            config_obj.intervalComboBox.setCurrentIndex(config['mainInterval'])
            config_obj.simulationIntervalComboBox.setCurrentIndex(config['simInterval'])
            config_obj.optimizerIntervalComboBox.setCurrentIndex(config['optimizerInterval'])
            config_obj.optimizerStrategyIntervalCombobox.setCurrentIndex(config['optimizerStrategyInterval'])
            config_obj.optimizerStrategyIntervalEndCombobox.setCurrentIndex(config['optimizerStrategyEndInterval'])
            config_obj.backtestIntervalComboBox.setCurrentIndex(config['backtestInterval'])
            config_obj.backtestStrategyIntervalCombobox.setCurrentIndex(config['backtestStrategyInterval'])

            config_obj.hidden_strategies = set(config['hiddenStrategies'])
            delete_strategy_slots(config_obj)
            load_strategy_slots(config_obj)
            load_custom_strategy_slots(config_obj)

            if config_obj.parent:
                config_obj.parent.add_to_live_activity_monitor('Loaded previous state successfully.')
        except Exception as e:
            config_obj.logger.exception(str(e))

            if config_obj.parent:
                config_obj.parent.add_to_live_activity_monitor('Failed to fully load previous state because of a '
                                                               'potential new update/install. Try restarting Algobot.')


def save_state(config_obj: Configuration):
    """
    Saves bot configuration to a JSON file for next application run.
    """
    # TODO: Dynamically populate this over time and get rid of this.
    config = {
        'lightTheme': config_obj.lightModeRadioButton.isChecked(),
        'darkTheme': config_obj.darkModeRadioButton.isChecked(),
        'bloombergTheme': config_obj.bloombergModeRadioButton.isChecked(),
        'bullTheme': config_obj.bullModeRadioButton.isChecked(),
        'bearTheme': config_obj.bearModeRadioButton.isChecked(),
        'balanceColor': config_obj.balanceColor.text(),
        'lineColor': config_obj.hoverLineColor.text(),
        'hoverLine': config_obj.enableHoverLine.isChecked(),
        'averagePlot': config_obj.graphIndicatorsCheckBox.isChecked(),
        'failureLimit': config_obj.failureLimitSpinBox.value(),
        'failureSleep': config_obj.failureSleepSpinBox.value(),
        'chatPass': config_obj.chat_pass,
        'tokenPass': config_obj.token_pass,
        'telegramResult': config_obj.telegrationConnectionResult.text(),
        'hiddenStrategies': list(config_obj.hidden_strategies),

        # Tickers
        'mainTicker': config_obj.tickerLineEdit.text(),
        'simTicker': config_obj.simulationTickerLineEdit.text(),
        'backtestTicker': config_obj.backtestTickerLineEdit.text(),
        'optimizerTicker': config_obj.optimizerTickerLineEdit.text(),

        # Intervals
        'mainInterval': int(config_obj.intervalComboBox.currentIndex()),
        'simInterval': int(config_obj.simulationIntervalComboBox.currentIndex()),
        'optimizerInterval': int(config_obj.optimizerIntervalComboBox.currentIndex()),
        'optimizerStrategyInterval': int(config_obj.optimizerStrategyIntervalCombobox.currentIndex()),
        'optimizerStrategyEndInterval': int(config_obj.optimizerStrategyIntervalEndCombobox.currentIndex()),
        'backtestInterval': int(config_obj.backtestIntervalComboBox.currentIndex()),
        'backtestStrategyInterval': int(config_obj.backtestStrategyIntervalCombobox.currentIndex())
    }

    helpers.write_json_file(config_obj.state_file_path, **config)
