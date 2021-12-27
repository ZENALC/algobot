"""
Saving, loading, and copying settings helper functions for configuration.py can be found here.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable, Union

from PyQt5.QtWidgets import QFileDialog, QLabel, QMessageBox

from algobot import helpers
from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION
from algobot.helpers import get_caller_string

if TYPE_CHECKING:
    from algobot.interface.configuration import Configuration


def create_appropriate_config_folders(config_obj: Configuration, folder: str) -> str:
    """
    Creates appropriate configuration folders. If a configuration folder doesn't exist, it'll create that. Next,
    it'll try to check if a type of configuration folder exists (e.g. Live, Simulation, Backtest). If it exists,
    it'll just return the path to it. If not, it'll create the folder then return the path to it.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param folder: Folder to create inside configuration folder.
    :return: Absolute path to new folder.
    """
    base_path = os.path.join(helpers.ROOT_DIR, config_obj.config_folder)
    helpers.create_folder_if_needed(base_path)

    target_path = os.path.join(base_path, folder)
    helpers.create_folder_if_needed(target_path, base_path=base_path)

    return target_path


def helper_load(config_obj: Configuration, caller: str, config: dict):
    """
    Helper function to load caller configuration to GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller to load configuration to.
    :param config: Configuration dictionary to get info from.
    :return: None
    """
    config_obj.set_loss_settings(caller, config)
    config_obj.set_take_profit_settings(caller, config)


def helper_save(config_obj: Configuration, caller: str, config: dict):
    """
    Helper function to save caller configuration from GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller to save configuration of.
    :param config: Configuration dictionary to dump info to.
    :return: None
    """
    config.update(config_obj.get_loss_settings(caller))
    config.update(config_obj.get_take_profit_settings(caller))


def helper_get_save_file_path(config_obj: Configuration, name: str) -> Union[str]:
    """
    Does necessary folder creations and returns save file path based on name provided.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param name: Name to use for file name and folder creation.
    :return: Absolute path to file.
    """
    name = name.capitalize()
    target_path = create_appropriate_config_folders(config_obj, name)
    default_path = os.path.join(target_path, f'{name.lower()}_configuration.json')
    file_path, _ = QFileDialog.getSaveFileName(config_obj, f'Save {name} Configuration', default_path, 'JSON (*.json)')
    return file_path


def save_config_helper(config_obj: Configuration, caller, result_label: QLabel, func: Callable):
    """
    Helper function to save configurations.
    :param config_obj: Configuration object (configuration.py)
    :param caller: Caller that'll determine which settings get saved.
    :param result_label: QLabel to modify post-action completion.
    :param func: Callback function to call for basic caller settings.
    """
    caller_str = get_caller_string(caller)
    config = func(config_obj)

    # TODO High priority: Save the optimizer settings. The function below is broken for optimizers.
    if caller != OPTIMIZER:
        helper_save(config_obj, caller, config)

    file_path = helper_get_save_file_path(config_obj, caller_str.capitalize())
    if file_path:
        helpers.write_json_file(file_path, **config)
        file = os.path.basename(file_path)
        result_label.setText(f"Saved {caller_str} configuration successfully to {file}.")
    else:
        result_label.setText(f"Could not save {caller_str} configuration.")


def save_backtest_settings(config_obj: Configuration):
    """
    Returns basic backtest settings as a dictionary.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    return {
        'type': BACKTEST,
        'ticker': config_obj.backtestTickerLineEdit.text(),
        'interval': config_obj.backtestIntervalComboBox.currentIndex(),
        'startingBalance': config_obj.backtestStartingBalanceSpinBox.value(),
        'precision': config_obj.backtestPrecisionComboBox.currentIndex(),
        'marginTrading': config_obj.backtestMarginTradingCheckBox.isChecked(),
    }


def save_optimizer_settings(config_obj: Configuration):
    """
    Returns basic optimizer settings as a dictionary.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    return {
        'type': OPTIMIZER,
        'ticker': config_obj.optimizerTickerLineEdit.text(),
        'interval': config_obj.optimizerIntervalComboBox.currentIndex(),
        'strategyIntervalStart': config_obj.optimizerStrategyIntervalCombobox.currentIndex(),
        'strategyIntervalEnd': config_obj.optimizerStrategyIntervalEndCombobox.currentIndex(),
        'startingBalance': config_obj.optimizerStartingBalanceSpinBox.value(),
        'precision': config_obj.optimizerPrecisionComboBox.currentIndex(),
        'drawdownPercentage': config_obj.drawdownPercentageSpinBox.value(),
        'marginTrading': config_obj.optimizerMarginTradingCheckBox.isChecked()
    }


def save_live_settings(config_obj: Configuration):
    """
    Returns basic live bot settings as a dictionary.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    return {
        'type': LIVE,
        'ticker': config_obj.tickerLineEdit.text(),
        'interval': config_obj.intervalComboBox.currentIndex(),
        'precision': config_obj.precisionComboBox.currentIndex(),
        'usRegion': config_obj.usRegionRadio.isChecked(),
        'otherRegion': config_obj.otherRegionRadio.isChecked(),
        'isolatedMargin': config_obj.isolatedMarginAccountRadio.isChecked(),
        'crossMargin': config_obj.crossMarginAccountRadio.isChecked(),
        'lowerInterval': config_obj.lowerIntervalCheck.isChecked(),
    }


def save_simulation_settings(config_obj: Configuration):
    """
    Returns basic simulation settings as a dictionary.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    return {
        'type': SIMULATION,
        'ticker': config_obj.simulationTickerLineEdit.text(),
        'interval': config_obj.simulationIntervalComboBox.currentIndex(),
        'startingBalance': config_obj.simulationStartingBalanceSpinBox.value(),
        'precision': config_obj.simulationPrecisionComboBox.currentIndex(),
        'lowerInterval': config_obj.lowerIntervalSimulationCheck.isChecked(),
    }


def load_config_helper(config_obj: Configuration, caller, result_label: QLabel, func: Callable):
    """
    Helper function to load configurations.
    :param config_obj: Configuration object (configuration.py).
    :param caller: Caller that called this function (optimizer, simulation, backtest, live).
    :param result_label: QLabel object to modify upon an action.
    :param func: Function to call for remaining configuration loading.
    """
    caller_str = get_caller_string(caller)
    target_path = create_appropriate_config_folders(config_obj, caller_str.capitalize())
    file_path, _ = QFileDialog.getOpenFileName(config_obj, f'Load {caller_str} config', target_path, "JSON (*.json)")

    try:
        config = helpers.load_json_file(file_path)
        file = os.path.basename(file_path)

        if config['type'] != caller:
            QMessageBox.about(config_obj, 'Warning', f'Incorrect type of non-{caller_str} configuration provided.')
        else:
            func(config_obj, config)

            # TODO: Fix optimizer saving/loading.
            if caller != OPTIMIZER:
                helper_load(config_obj, caller, config)

            result_label.setText(f"Loaded {caller_str} configuration successfully from {file}.")
    except Exception as e:
        config_obj.logger.exception(str(e))
        result_label.setText(f"Could not load {caller_str} configuration.")


def load_live_settings(config_obj: Configuration, config):
    """
    Loads live settings from JSON file and sets it to live settings.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param config: Dictionary containing the configuration.
    """
    config_obj.tickerLineEdit.setText(str(config['ticker']))
    config_obj.intervalComboBox.setCurrentIndex(config['interval'])
    config_obj.precisionComboBox.setCurrentIndex(config['precision'])
    config_obj.usRegionRadio.setChecked(config['usRegion'])
    config_obj.otherRegionRadio.setChecked(config['otherRegion'])
    config_obj.isolatedMarginAccountRadio.setChecked(config['isolatedMargin'])
    config_obj.crossMarginAccountRadio.setChecked(config['crossMargin'])
    config_obj.lowerIntervalCheck.setChecked(config['lowerInterval'])


def load_simulation_settings(config_obj: Configuration, config):
    """
    Loads simulation settings from JSON file and sets it to simulation settings.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param config: Dictionary containing the configuration.
    """
    config_obj.simulationTickerLineEdit.setText(str(config['ticker']))
    config_obj.simulationIntervalComboBox.setCurrentIndex(config['interval'])
    config_obj.simulationStartingBalanceSpinBox.setValue(config['startingBalance'])
    config_obj.simulationPrecisionComboBox.setCurrentIndex(config['precision'])
    config_obj.lowerIntervalSimulationCheck.setChecked(config['lowerInterval'])


def load_backtest_settings(config_obj: Configuration, config):
    """
    Loads backtest settings from JSON file and sets them to backtest settings.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param config: Dictionary containing the configuration.
    """
    config_obj.backtestTickerLineEdit.setText(str(config['ticker']))
    config_obj.backtestIntervalComboBox.setCurrentIndex(config['interval'])
    config_obj.backtestStartingBalanceSpinBox.setValue(config['startingBalance'])
    config_obj.backtestPrecisionComboBox.setCurrentIndex(config['precision'])
    config_obj.backtestMarginTradingCheckBox.setChecked(config['marginTrading'])


def load_optimizer_settings(config_obj: Configuration, config):
    """
    Loads optimizer settings from JSON file and sets them to optimizer settings.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param config: Dictionary containing the configuration.
    """
    config_obj.optimizerTickerLineEdit.setText(str(config['ticker']))
    config_obj.optimizerIntervalComboBox.setCurrentIndex(config['interval'])
    config_obj.optimizerStrategyIntervalCombobox.setCurrentIndex(config['strategyIntervalStart'])
    config_obj.optimizerStrategyIntervalEndCombobox.setCurrentIndex(config['strategyIntervalEnd'])
    config_obj.optimizerStartingBalanceSpinBox.setValue(config['startingBalance'])
    config_obj.optimizerPrecisionComboBox.setCurrentIndex(config['precision'])
    config_obj.drawdownPercentageSpinBox.setValue(config['drawdownPercentage'])


def copy_config_helper(config_obj: Configuration, caller, result_label, func: Callable):
    """
    Helper function to copy configurations from live bot to caller provided.
    :param config_obj: Configuration object.
    :param caller: Caller to copy settings to from live bot.
    :param result_label: Result label to modify after successful copy.
    :param func: Callback function that will copy base settings specific to the caller.
    """
    # TODO: Create copy function for optimizer.
    func(config_obj)
    copy_loss_settings(config_obj, LIVE, caller)
    result_label.setText(f"Copied all viable settings from main to {get_caller_string(caller)} settings successfully.")


def copy_settings_to_simulation(config_obj: Configuration):
    """
    Copies parameters from main configuration to simulation configuration.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config_obj.simulationIntervalComboBox.setCurrentIndex(config_obj.intervalComboBox.currentIndex())
    config_obj.simulationTickerLineEdit.setText(config_obj.tickerLineEdit.text())
    config_obj.simulationPrecisionComboBox.setCurrentIndex(config_obj.precisionComboBox.currentIndex())


def copy_settings_to_backtest(config_obj: Configuration):
    """
    Copies parameters from main configuration to backtest configuration.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config_obj.backtestIntervalComboBox.setCurrentIndex(config_obj.intervalComboBox.currentIndex())
    config_obj.backtestTickerLineEdit.setText(config_obj.tickerLineEdit.text())
    config_obj.backtestPrecisionComboBox.setCurrentIndex(config_obj.precisionComboBox.currentIndex())


def copy_strategy_settings(config_obj: Configuration, from_caller: str, to_caller: str, strategy_name: str):
    """
    Copies strategy settings from caller provided and sets it to caller provided based on strategy name.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param from_caller: Function will copy settings from this caller.
    :param to_caller: Function will copy settings to this caller.
    :param strategy_name: This strategy's settings will be copied.
    """
    from_caller_tab = config_obj.get_category_tab(from_caller)
    to_caller_tab = config_obj.get_category_tab(to_caller)

    from_caller_group_box = config_obj.strategy_dict[from_caller_tab, strategy_name, 'groupBox']
    config_obj.strategy_dict[to_caller_tab, strategy_name, 'groupBox'].setChecked(from_caller_group_box.isChecked())


def copy_loss_settings(config_obj: Configuration, from_caller: str, to_caller: str):
    """
    Copies loss settings from one caller to another.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param from_caller: Loss settings will be copied from this trader.
    :param to_caller: Loss settings will be copied to this trader.
    """
    from_tab = config_obj.get_category_tab(from_caller)
    to_tab = config_obj.get_category_tab(to_caller)

    config_obj.loss_dict[to_tab, "lossType"].setCurrentIndex(config_obj.loss_dict[from_tab, "lossType"].currentIndex())
    config_obj.loss_dict[to_tab, "lossPercentage"].setValue(config_obj.loss_dict[from_tab, "lossPercentage"].value())
    config_obj.loss_dict[to_tab, "smartStopLossCounter"].setValue(config_obj.loss_dict[from_tab,
                                                                                       "smartStopLossCounter"].value())

    if to_tab != config_obj.backtestConfigurationTabWidget:
        config_obj.loss_dict[to_tab, "safetyTimer"].setValue(config_obj.loss_dict[from_tab, "safetyTimer"].value())
