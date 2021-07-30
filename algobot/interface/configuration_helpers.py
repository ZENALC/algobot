"""
Helpers for the configuration object.
"""

from typing import Any, Callable, Dict, List, Tuple, Union

from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QLabel, QLayout,
                             QLineEdit, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from algobot import helpers
from algobot.enums import OPTIMIZER


def add_start_end_step_to_layout(layout: QLayout, msg: str, start: QWidget, end: QWidget, step: QWidget):
    """
    Adds start, end, and step rows to the layout provided.
    """
    layout.addRow(QLabel(f"{helpers.get_label_string(msg)} Optimization"))
    layout.addRow("Start", start)
    layout.addRow("End", end)
    layout.addRow("Step", step)

    start.valueChanged.connect(lambda: (end.setValue(start.value()), end.setMinimum(start.value())))


def get_regular_groupbox_and_layout(name: str) -> Tuple[QGroupBox, QFormLayout]:
    """
    Returns a groupbox and a layout with the groupbox on the layout.
    :param name: Title to put for the groupbox.
    """
    layout = QFormLayout()
    group_box = QGroupBox(name)
    group_box.setCheckable(True)
    group_box.setChecked(False)
    group_box.setLayout(layout)

    return group_box, layout


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
        description_label = QLabel(description)
        description_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(description_label)

        if parent and parent.get_caller_based_on_tab(tab) == OPTIMIZER:
            group_box, group_box_layout = get_regular_groupbox_and_layout(f"Enable {tabName.lower()} optimization?")
            input_creator(tab, group_box_layout, isOptimizer=True)
        else:
            group_box, group_box_layout = get_regular_groupbox_and_layout(f"Enable {tabName.lower()}?")
            group_box.toggled.connect(lambda _, current_tab=tab: signalFunction(tab=current_tab))
            input_creator(tab, group_box_layout)

        dictionary[tab, 'groupBox'] = group_box

        scroll = QScrollArea()
        scroll.setWidget(group_box)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        tab_widget = QTabWidget()
        tab_widget.setLayout(layout)
        tab.addTab(tab_widget, tabName)


def set_value(widget: QWidget, value: Union[str, int, float]):
    """
    Sets appropriate value to a widget depending on what it is.
    :param widget: Widget to alter.
    :param value: Value to modify widget with.
    :return: None
    """
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
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
    if isinstance(inputWidget, (QSpinBox, QDoubleSpinBox)):
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
        minimum = -1

    default_widget.setMinimum(minimum)
    default_widget.setMaximum(maximum)
    return default_widget
