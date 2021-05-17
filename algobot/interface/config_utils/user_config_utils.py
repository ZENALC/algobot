"""
Saving, loading, and copying settings helper functions for configuration.py can be found here.
"""

import os

from PyQt5.QtWidgets import QFileDialog, QMessageBox

from algobot import helpers
from algobot.enums import BACKTEST, LIVE, SIMULATION
from algobot.interface.config_utils.strategy_utils import (get_strategy_values,
                                                           set_strategy_values)


def save_backtest_settings(config_obj):
    """
    Saves backtest settings to JSON file.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config = {
        'type': BACKTEST,
        'ticker': config_obj.backtestTickerLineEdit.text(),
        'interval': config_obj.backtestIntervalComboBox.currentIndex(),
        'startingBalance': config_obj.backtestStartingBalanceSpinBox.value(),
        'precision': config_obj.backtestPrecisionSpinBox.value(),
        'marginTrading': config_obj.backtestMarginTradingCheckBox.isChecked(),
    }

    config_obj.helper_save(BACKTEST, config)
    filePath = config_obj.helper_get_save_file_path("Backtest")

    if filePath:
        helpers.write_json_file(filePath, **config)
        file = os.path.basename(filePath)
        config_obj.backtestConfigurationResult.setText(f"Saved backtest configuration successfully to {file}.")
    else:
        config_obj.backtestConfigurationResult.setText("Could not save backtest configuration.")


def save_live_settings(config_obj):
    """
    Saves live settings to JSON file.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config = {
        'type': LIVE,
        'ticker': config_obj.tickerLineEdit.text(),
        'interval': config_obj.intervalComboBox.currentIndex(),
        'precision': config_obj.precisionSpinBox.value(),
        'usRegion': config_obj.usRegionRadio.isChecked(),
        'otherRegion': config_obj.otherRegionRadio.isChecked(),
        'isolatedMargin': config_obj.isolatedMarginAccountRadio.isChecked(),
        'crossMargin': config_obj.crossMarginAccountRadio.isChecked(),
        'lowerInterval': config_obj.lowerIntervalCheck.isChecked(),
    }

    config_obj.helper_save(LIVE, config)
    filePath = config_obj.helper_get_save_file_path("Live")

    if filePath:
        helpers.write_json_file(filePath, **config)
        file = os.path.basename(filePath)
        config_obj.configurationResult.setText(f"Saved live configuration successfully to {file}.")
    else:
        config_obj.configurationResult.setText("Could not save live configuration.")


def save_simulation_settings(config_obj):
    """
    Saves simulation settings to JSON file.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config = {
        'type': SIMULATION,
        'ticker': config_obj.simulationTickerLineEdit.text(),
        'interval': config_obj.simulationIntervalComboBox.currentIndex(),
        'startingBalance': config_obj.simulationStartingBalanceSpinBox.value(),
        'precision': config_obj.simulationPrecisionSpinBox.value(),
        'lowerInterval': config_obj.lowerIntervalSimulationCheck.isChecked(),
    }

    config_obj.helper_save(SIMULATION, config)
    filePath = config_obj.helper_get_save_file_path("Simulation")

    if filePath:
        helpers.write_json_file(filePath, **config)
        file = os.path.basename(filePath)
        config_obj.simulationConfigurationResult.setText(f"Saved simulation configuration successfully to {file}.")
    else:
        config_obj.simulationConfigurationResult.setText("Could not save simulation configuration.")


def load_live_settings(config_obj):
    """
    Loads live settings from JSON file and sets it to live settings.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    targetPath = config_obj.create_appropriate_config_folders('Live')
    filePath, _ = QFileDialog.getOpenFileName(config_obj, 'Load Credentials', targetPath, "JSON (*.json)")
    try:
        config = helpers.load_json_file(filePath)
        file = os.path.basename(filePath)
        if config['type'] != LIVE:
            QMessageBox.about(config_obj, 'Warning', 'Incorrect type of non-live configuration provided.')
        else:
            config_obj.tickerLineEdit.setText(str(config['ticker']))
            config_obj.intervalComboBox.setCurrentIndex(config['interval'])
            config_obj.precisionSpinBox.setValue(config['precision'])
            config_obj.usRegionRadio.setChecked(config['usRegion'])
            config_obj.otherRegionRadio.setChecked(config['otherRegion'])
            config_obj.isolatedMarginAccountRadio.setChecked(config['isolatedMargin'])
            config_obj.crossMarginAccountRadio.setChecked(config['crossMargin'])
            config_obj.lowerIntervalCheck.setChecked(config['lowerInterval'])
            config_obj.helper_load(LIVE, config)
            config_obj.configurationResult.setText(f"Loaded live configuration successfully from {file}.")
    except Exception as e:
        config_obj.logger.exception(str(e))
        config_obj.configurationResult.setText("Could not load live configuration.")


def load_simulation_settings(config_obj):
    """
    Loads simulation settings from JSON file and sets it to simulation settings.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    targetPath = config_obj.create_appropriate_config_folders('Simulation')
    filePath, _ = QFileDialog.getOpenFileName(config_obj, 'Load Credentials', targetPath, "JSON (*.json)")
    try:
        config = helpers.load_json_file(filePath)
        file = os.path.basename(filePath)
        if config['type'] != SIMULATION:
            QMessageBox.about(config_obj, 'Warning', 'Incorrect type of non-simulation configuration provided.')
        else:
            config_obj.simulationTickerLineEdit.setText(str(config['ticker']))
            config_obj.simulationIntervalComboBox.setCurrentIndex(config['interval'])
            config_obj.simulationStartingBalanceSpinBox.setValue(config['startingBalance'])
            config_obj.simulationPrecisionSpinBox.setValue(config['precision'])
            config_obj.lowerIntervalSimulationCheck.setChecked(config['lowerInterval'])
            config_obj.helper_load(SIMULATION, config)
            config_obj.simulationConfigurationResult.setText(f"Loaded sim configuration successfully from {file}.")
    except Exception as e:
        config_obj.logger.exception(str(e))
        config_obj.simulationConfigurationResult.setText("Could not load simulation configuration.")


def load_backtest_settings(config_obj):
    """
    Loads backtest settings from JSON file and sets them to backtest settings.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    targetPath = config_obj.create_appropriate_config_folders('Backtest')
    filePath, _ = QFileDialog.getOpenFileName(config_obj, 'Load Credentials', targetPath, "JSON (*.json)")
    try:
        config = helpers.load_json_file(filePath)
        file = os.path.basename(filePath)
        if config['type'] != BACKTEST:
            QMessageBox.about(config_obj, 'Warning', 'Incorrect type of non-backtest configuration provided.')
        else:
            config_obj.backtestTickerLineEdit.setText(str(config['ticker']))
            config_obj.backtestIntervalComboBox.setCurrentIndex(config['interval'])
            config_obj.backtestStartingBalanceSpinBox.setValue(config['startingBalance'])
            config_obj.backtestPrecisionSpinBox.setValue(config['precision'])
            config_obj.backtestMarginTradingCheckBox.setChecked(config['marginTrading'])
            config_obj.helper_load(BACKTEST, config)
            config_obj.backtestConfigurationResult.setText(f"Loaded backtest configuration successfully from {file}.")
    except Exception as e:
        config_obj.logger.exception(str(e))
        config_obj.backtestConfigurationResult.setText("Could not load backtest configuration.")


def copy_settings_to_simulation(config_obj):
    """
    Copies parameters from main configuration to simulation configuration.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :return: None
    """
    config_obj.simulationIntervalComboBox.setCurrentIndex(config_obj.intervalComboBox.currentIndex())
    config_obj.simulationTickerLineEdit.setText(config_obj.tickerLineEdit.text())
    config_obj.simulationPrecisionSpinBox.setValue(config_obj.precisionSpinBox.value())
    copy_loss_settings(config_obj, LIVE, SIMULATION)

    for strategyName in config_obj.strategies.keys():
        copy_strategy_settings(config_obj, LIVE, SIMULATION, strategyName)

    config_obj.simulationCopyLabel.setText("Copied all viable settings from main to simulation settings successfully.")


def copy_settings_to_backtest(config_obj):
    """
    Copies parameters from main configuration to backtest configuration.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :return: None
    """
    config_obj.backtestIntervalComboBox.setCurrentIndex(config_obj.intervalComboBox.currentIndex())
    config_obj.backtestTickerLineEdit.setText(config_obj.tickerLineEdit.text())
    config_obj.backtestPrecisionSpinBox.setValue(config_obj.precisionSpinBox.value())
    copy_loss_settings(config_obj, LIVE, BACKTEST)

    for strategyName in config_obj.strategies.keys():
        copy_strategy_settings(config_obj, LIVE, BACKTEST, strategyName)

    config_obj.backtestCopyLabel.setText("Copied all viable settings from main to backtest settings successfully.")


def copy_strategy_settings(config_obj, fromCaller: int, toCaller: int, strategyName: str):
    """
    Copies strategy settings from caller provided and sets it to caller provided based on strategy name.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param fromCaller: Function will copy settings from this caller.
    :param toCaller: Function will copy settings to this caller.
    :param strategyName: This strategy's settings will be copied.
    :return: None
    """
    fromCallerTab = config_obj.get_category_tab(fromCaller)
    toCallerTab = config_obj.get_category_tab(toCaller)

    fromCallerGroupBox = config_obj.strategyDict[fromCallerTab, strategyName, 'groupBox']
    config_obj.strategyDict[toCallerTab, strategyName, 'groupBox'].setChecked(fromCallerGroupBox.isChecked())
    set_strategy_values(config_obj, strategyName, toCaller, get_strategy_values(config_obj, strategyName, fromCaller))


def copy_loss_settings(config_obj, fromCaller: int, toCaller: int):
    """
    Copies loss settings from one caller to another.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param fromCaller: Loss settings will be copied from this trader.
    :param toCaller: Loss settings will be copied to this trader.
    :return: None
    """
    fromTab = config_obj.get_category_tab(fromCaller)
    toTab = config_obj.get_category_tab(toCaller)

    config_obj.lossDict[toTab, "lossType"].setCurrentIndex(config_obj.lossDict[fromTab, "lossType"].currentIndex())
    config_obj.lossDict[toTab, "lossPercentage"].setValue(config_obj.lossDict[fromTab, "lossPercentage"].value())
    config_obj.lossDict[toTab, "smartStopLossCounter"].setValue(config_obj.lossDict[fromTab,
                                                                "smartStopLossCounter"].value())

    if toTab != config_obj.backtestConfigurationTabWidget:
        config_obj.lossDict[toTab, "safetyTimer"].setValue(config_obj.lossDict[fromTab, "safetyTimer"].value())
