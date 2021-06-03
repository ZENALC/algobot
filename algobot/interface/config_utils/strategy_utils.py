"""
Strategy helper functions for configuration.py can be found here.
"""
from typing import Any, Dict, List, Tuple, Type, Union

from PyQt5.QtWidgets import (QComboBox, QDoubleSpinBox, QLabel, QLayout,
                             QLineEdit, QPushButton, QSpinBox, QTabWidget)

from algobot import helpers
from algobot.interface.configuration_helpers import (get_h_line,
                                                     get_input_widget_value,
                                                     set_value)
from algobot.strategies.strategy import Strategy


def strategy_enabled(config_obj, strategyName: str, caller: int) -> bool:
    """
    Returns a boolean whether a strategy is enabled or not.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param strategyName: Name of strategy to check if enabled.
    :param caller: Caller of the strategy.
    :return: Boolean whether strategy is enabled or not.
    """
    tab = config_obj.get_category_tab(caller)
    return config_obj.strategyDict[tab, strategyName, 'groupBox'].isChecked()


def get_strategies(config_obj, caller: int) -> List[tuple]:
    """
    Returns strategy information from GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that asked for strategy information.
    :return: List of strategy information.
    """
    strategies = []
    for strategyName, strategy in config_obj.strategies.items():
        if strategy_enabled(config_obj, strategyName, caller):
            values = get_strategy_values(config_obj, strategyName, caller, verbose=True)
            strategyTuple = (strategy, values, strategyName)
            strategies.append(strategyTuple)

    return strategies


def get_strategy_values(config_obj, strategyName: str, caller: int, verbose: bool = False) -> List[int]:
    """
    This will return values from the strategy provided.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param verbose: If verbose, return value of widget when possible.
    :param strategyName: Name of strategy to get values from.
    :param caller: Caller that'll determine which tab object is used to get the strategy values.
    :return: List of strategy values.
    """
    tab = config_obj.get_category_tab(caller)
    values = []
    for inputWidget in config_obj.strategyDict[tab, strategyName, 'values']:
        values.append(get_input_widget_value(inputWidget, verbose=verbose))

    return values


def set_strategy_values(config_obj, strategyName: str, caller: int, values):
    """
    Set GUI values for a strategy based on values passed.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param strategyName: Name of the strategy that'll have its values set.
    :param caller: Caller that'll determine which tab object gets returned.
    :param values: List of values to populate GUI with.
    :return: None
    """
    tab = config_obj.get_category_tab(caller)
    targetValues = config_obj.strategyDict[tab, strategyName, 'values']
    parameters = config_obj.strategyDict[tab, strategyName, 'parameters']
    layout = config_obj.strategyDict[tab, strategyName, 'layout']

    while len(values) < len(targetValues):
        delete_strategy_inputs(config_obj.strategyDict, parameters, strategyName, tab)
    while len(values) > len(targetValues):
        add_strategy_inputs(config_obj.strategyDict, parameters, strategyName, layout, tab)

    for index, widget in enumerate(targetValues):
        value = values[index]
        set_value(widget, value)


def add_strategy_inputs(strategyDict: dict, parameters: list, strategyName: str, groupBoxLayout, tab: QTabWidget):
    """
    Adds strategy parameters to the layout provided.
    :param strategyDict: Dictionary to modify.
    :param parameters: Parameters to add to the group box layout.
    :param strategyName: Name of strategy.
    :param groupBoxLayout: Layout to add parameters to.
    :param tab: Add which group box layout is in.
    :return: None
    """
    values, labels = create_strategy_inputs(parameters, strategyName, groupBoxLayout)
    strategyDict[tab, strategyName, 'labels'] += labels
    strategyDict[tab, strategyName, 'values'] += values
    strategyDict[tab, strategyName, 'status'].setText("Added additional slots.")


def delete_strategy_inputs(strategyDict: Dict[Any, Any], parameters: list, strategyName: str, tab: QTabWidget):
    """
    Dynamically deletes strategy inputs.
    :param strategyDict: Dictionary to modify.
    :param parameters: Parameters of the strategy.
    :param strategyName: Name of strategy to determine the dictionary.
    :param tab: Tab in which to delete strategy inputs.
    :return: None
    """
    values = strategyDict[tab, strategyName, 'values']
    labels = strategyDict[tab, strategyName, 'labels']
    if len(values) <= len(parameters):
        strategyDict[tab, strategyName, 'status'].setText("Can't delete additional slots.")
    else:
        for _ in range(len(parameters)):
            value = values.pop()
            value.setParent(None)

            label = labels.pop()
            label.setParent(None)

        labels.pop().setParent(None)  # Pop off the horizontal line from labels.
        strategyDict[tab, strategyName, 'status'].setText("Deleted additional slots.")


def create_strategy_inputs(parameters: List[Union[int, tuple]], strategyName: str,
                           groupBoxLayout: QLayout) -> Tuple[list, list]:
    """
    This function will create strategy slots and labels based on the parameters provided to the layout.
    :param parameters: Parameters to add to strategy GUI slots. These are fetched from get_param_types() in strategies.
    :param strategyName: Name of strategy.
    :param groupBoxLayout: Layout to add the slots to.
    :return: Tuple of labels and values lists.
    """
    labels = []
    values = []
    for paramIndex, parameter in enumerate(parameters):
        if type(parameter) == tuple:
            label = QLabel(parameter[0])
            parameter = parameter[1:]  # Set parameter to just the last element so we can use this later.
        elif parameter == int:
            label = QLabel(f'{strategyName} input {paramIndex + 1}')
            parameter = [parameter]
        else:
            raise TypeError("Please make sure your function get_param_types() only has ints or tuples.")

        if parameter[0] == int:
            value = QSpinBox()
            value.setRange(1, 500)
        elif parameter[0] == float:
            value = QDoubleSpinBox()
        elif parameter[0] == str:
            value = QLineEdit()
        elif parameter[0] == tuple:
            elements = parameter[1]
            value = QComboBox()
            value.addItems(elements)
        else:
            raise TypeError("Invalid type of parameter provided.")

        labels.append(label)
        values.append(value)
        groupBoxLayout.addRow(label, value)

    line = get_h_line()
    labels.append(line)
    groupBoxLayout.addWidget(line)

    return values, labels


def add_strategy_buttons(strategyDict: dict, parameters: list, strategyName: str, groupBoxLayout: QLayout,
                         tab: QTabWidget) -> Tuple[QPushButton, QPushButton]:
    """
    Creates add and delete buttons to strategy GUI.
    :param strategyDict: Strategy dictionary to modify.
    :param parameters: Parameters to pass to strategy inputs function.
    :param strategyName: Name of strategy.
    :param groupBoxLayout: Layout to add strategy buttons to.
    :param tab: Tab to modify GUI.
    :return: Tuple of add and delete buttons.
    """
    addButton = QPushButton("Add Extra")
    addButton.clicked.connect(lambda: add_strategy_inputs(strategyDict, parameters, strategyName, groupBoxLayout, tab))
    deleteButton = (QPushButton("Delete Extra"))
    deleteButton.clicked.connect(lambda: delete_strategy_inputs(strategyDict, parameters, strategyName, tab))

    return addButton, deleteButton


def get_strategies_dictionary(strategies: List[Type[Strategy]]) -> Dict[str, Type[Strategy]]:
    """
    Helper function to return a strategies dictionary with strategy name as the key and strategy itself as the value.
    :param strategies: List of strategies to process for dictionary.
    :return: Dictionary of strategies with strategy name as the key and strategy itself as the value.
    """
    ignoredStrategies = ['Sample']
    strategiesDict = {}
    for strategy in strategies:
        strategyName = strategy().name
        if strategyName not in ignoredStrategies:
            strategiesDict[strategyName] = strategy
    return strategiesDict


def reset_strategy_interval_comboBox(strategy_combobox: QComboBox, interval_combobox: QComboBox, start_index: int = 0):
    """
    This function will reset the strategy combobox based on what interval is picked in the interval combobox.
    :param strategy_combobox: Combobox to modify based on the interval combobox.
    :param interval_combobox: Interval combobox that will trigger this function.
    :param start_index: Optional start index to start from when getting interval strings.
    """
    strategyInterval = strategy_combobox.currentText()
    dataIndex = interval_combobox.currentIndex()
    intervals = helpers.get_interval_strings(startingIndex=start_index + dataIndex)

    strategy_combobox.clear()
    strategy_combobox.addItems(intervals)

    previousStrategyIntervalIndex = strategy_combobox.findText(strategyInterval)
    if previousStrategyIntervalIndex != -1:
        strategy_combobox.setCurrentIndex(previousStrategyIntervalIndex)
