"""
Helpers for the configuration object.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QLabel, QLayout,
                             QLineEdit, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget, QCheckBox)

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


def create_inner_tab(category_tabs: List[QTabWidget],
                     description: str,
                     tab_name: str,
                     input_creator: Callable,
                     dictionary: Dict[Any, QGroupBox],
                     signal_function: Callable,
                     parent: QDialog = None):
    """
    Creates inner tab for each category tab in list of category tabs provided.
    :param category_tabs: Tabs to create inner tab and append to.
    :param description: Description to insert for inner tab.
    :param tab_name: Name of tab to display.
    :param input_creator: Function to call for input creation.
    :param signal_function: Function to call for input slots.
    :param dictionary: Dictionary to add items to for reference.
    :param parent: Parent configuration object.
    :return: None
    """
    for tab in category_tabs:
        description_label = QLabel(description)
        description_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(description_label)

        if parent and parent.get_caller_based_on_tab(tab) == OPTIMIZER:
            group_box, group_box_layout = get_regular_groupbox_and_layout(f"Enable {tab_name.lower()} optimization?")
            input_creator(tab, group_box_layout, is_optimizer=True)
        else:
            group_box, group_box_layout = get_regular_groupbox_and_layout(f"Enable {tab_name.lower()}?")
            group_box.toggled.connect(lambda _, current_tab=tab: signal_function(tab=current_tab))
            input_creator(tab, group_box_layout)

        dictionary[tab, 'groupBox'] = group_box

        scroll = QScrollArea()
        scroll.setWidget(group_box)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        tab_widget = QTabWidget()
        tab_widget.setLayout(layout)
        tab.addTab(tab_widget, tab_name)


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


def get_input_widget_value(input_widget: QWidget, verbose: bool = False):
    """
    This function will attempt to get the value of the inputWidget and return it.
    :param verbose: If verbose, return value of widget when possible.
    :param input_widget: Input widget to try to get the value of.
    :return: Value of inputWidget object.
    """
    if isinstance(input_widget, QDoubleSpinBox):
        return float(input_widget.value())
    elif isinstance(input_widget, QSpinBox):
        return input_widget.value()
    elif isinstance(input_widget, QLineEdit):
        return input_widget.text()
    elif isinstance(input_widget, QCheckBox):
        return input_widget.text()
    elif isinstance(input_widget, QComboBox):
        if verbose:
            return input_widget.currentText()
        else:
            return input_widget.currentIndex()
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


def get_default_widget(widget: [QSpinBox, QDoubleSpinBox], default: Union[int, float], minimum: Optional[int] = 0,
                       maximum: Optional[int] = 999) -> Union[QSpinBox, QDoubleSpinBox]:
    """
    Returns a default QSpinbox or QDoubleSpinbox widget with default, minimum, and maximum values provided.
    """
    default_widget = widget()
    default_widget.setValue(default)

    # TODO: Hotfix for floats, but use a better method.
    if widget is QDoubleSpinBox and minimum > -1:
        minimum = -1

    if minimum is not None:
        default_widget.setMinimum(minimum)

    if maximum is not None:
        default_widget.setMaximum(maximum)

    return default_widget
