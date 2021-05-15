from typing import Any, Callable, Dict, List, Tuple, Type, Union

from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                             QFrame, QGroupBox, QLabel, QLayout, QLineEdit,
                             QPushButton, QScrollArea, QSpinBox, QTabWidget,
                             QVBoxLayout, QWidget)

from algobot.enums import OPTIMIZER
from algobot.strategies.strategy import Strategy


def get_regular_groupbox_and_layout(name: str) -> Tuple[QGroupBox, QFormLayout]:
    """
    Returns a groupbox and a layout with the groupbox on the layout.
    :param name: Title to put for the groupbox.
    """
    layout = QFormLayout()
    groupBox = QGroupBox(name)
    groupBox.setCheckable(True)
    groupBox.setChecked(False)
    groupBox.setLayout(layout)

    return groupBox, layout


def get_strategies_dictionary(strategies: List[Type[Strategy]]) -> Dict[str, Type[Strategy]]:
    """
    Helper function to return a strategies dictionary with strategy name as the key and strategy itself as the value.
    :param strategies: List of strategies to process for dictionary.
    :return: Dictionary of strategies with strategy name as the key and strategy itself as the value.
    """
    strategiesDict = {}
    for strategy in strategies:
        strategiesDict[strategy().name] = strategy
    return strategiesDict


def create_inner_tab(categoryTabs: List[QTabWidget], description: str, tabName: str, input_creator: Callable,
                     dictionary: Dict[Any, QGroupBox], signalFunction: Callable, parent: QDialog = None):
    """
    Creates inner tab for each category tab in list of category tabs provided.
    :param categoryTabs: Tabs to create inner tab and append to.
    :param description: Description to insert for inner tab.
    :param tabName: Name of tab to display.
    :param input_creator: Function to call for input creation.
    :param signalFunction: Function to call for input slots.
    :param dictionary: Dictionary to add items to for reference.
    :param parent: Parent configuration object.
    :return: None
    """
    for tab in categoryTabs:
        descriptionLabel = QLabel(description)
        descriptionLabel.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(descriptionLabel)

        if parent and parent.get_caller_based_on_tab(tab) == OPTIMIZER:
            groupBox, groupBoxLayout = get_regular_groupbox_and_layout(f"Enable {tabName.lower()} optimization?")
            input_creator(tab, groupBoxLayout, isOptimizer=True)
        else:
            groupBox, groupBoxLayout = get_regular_groupbox_and_layout(f"Enable {tabName.lower()}?")
            groupBox.toggled.connect(lambda _, current_tab=tab: signalFunction(tab=current_tab))
            input_creator(tab, groupBoxLayout)

        dictionary[tab, 'groupBox'] = groupBox

        scroll = QScrollArea()
        scroll.setWidget(groupBox)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        tabWidget = QTabWidget()
        tabWidget.setLayout(layout)
        tab.addTab(tabWidget, tabName)


def set_value(widget: QWidget, value: Union[str, int, float]):
    """
    Sets appropriate value to a widget depending on what it is.
    :param widget: Widget to alter.
    :param value: Value to modify widget with.
    :return: None
    """
    if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
        widget.setValue(value)
    elif isinstance(widget, QLineEdit):
        widget.setText(value)
    elif isinstance(widget, QComboBox):
        widget.setCurrentIndex(value)
    else:
        raise TypeError("Unknown type of instance provided. Please check load_strategy_slots() function.")


def get_input_widget_value(inputWidget: QWidget, verbose: bool = False):
    """
    This function will attempt to get the value of the inputWidget and return it.
    :param verbose: If verbose, return value of widget when possible.
    :param inputWidget: Input widget to try to get the value of.
    :return: Value of inputWidget object.
    """
    if isinstance(inputWidget, QSpinBox) or isinstance(inputWidget, QDoubleSpinBox):
        return inputWidget.value()
    elif isinstance(inputWidget, QLineEdit):
        return inputWidget.text()
    elif isinstance(inputWidget, QComboBox):
        if verbose:
            return inputWidget.currentText()
        else:
            return inputWidget.currentIndex()
    else:
        raise TypeError("Unknown type of instance provided. Please check load_strategy_slots() function.")


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


def add_strategy_buttons(sDict: dict, parameters: list, strategyName: str, groupBoxLayout: QLayout,
                         tab: QTabWidget) -> Tuple[QPushButton, QPushButton]:
    """
    Adds add and delete buttons to strategy GUI.
    :param sDict: Strategy dictionary to modify.
    :param parameters: Parameters to pass to strategy inputs function.
    :param strategyName: Name of strategy.
    :param groupBoxLayout: Layout to add strategy buttons to.
    :param tab: Tab to modify GUI.
    :return: Tuple of add and delete buttons.
    """
    addButton = QPushButton("Add Extra")
    addButton.clicked.connect(lambda: add_strategy_inputs(sDict, parameters, strategyName, groupBoxLayout, tab))
    deleteButton = (QPushButton("Delete Extra"))
    deleteButton.clicked.connect(lambda: delete_strategy_inputs(sDict, parameters, strategyName, tab))

    return addButton, deleteButton


def get_h_line() -> QFrame:
    """
    Returns a horizontal line object made using a QFrame object.
    :return: Horizontal line using a QFrame.
    """
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


def get_default_widget(widget: [QSpinBox, QDoubleSpinBox], default: Union[int, float], minimum: int = 1,
                       maximum: int = 99) -> Union[QSpinBox, QDoubleSpinBox]:
    """
    Returns a default QSpinbox or QDoubleSpinbox widget with default, minimum, and maximum values provided.
    """
    default_widget = widget()
    default_widget.setValue(default)

    # TODO: Hotfix for floats, but use a better method.
    if widget is QDoubleSpinBox:
        minimum = 0

    default_widget.setMinimum(minimum)
    default_widget.setMaximum(maximum)
    return default_widget
