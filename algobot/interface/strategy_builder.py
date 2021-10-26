"""
Simple strategy builder.
"""

import sys
from typing import Dict, OrderedDict

import talib
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
                             QPushButton, QSpinBox, QVBoxLayout)
from talib import abstract

from algobot.interface.configuration_helpers import get_default_widget, get_h_line
from algobot.interface.utils import get_v_spacer


def get_normalized_indicator_map() -> Dict[str, str]:
    """
    Get a normalized indicator map where the raw value is the key and the normalized value is the value.
    :return: Dictionary of raw/normalized values.
    """
    raw_indicators = talib.get_functions()
    parsed_indicators = [abstract.Function(indicator).info['display_name'] for indicator in raw_indicators]

    # Zip then throw inside a dict and return.
    return dict(zip(raw_indicators, parsed_indicators))


class IndicatorSelector(QDialog):
    TALIB_FUNCTION_GROUPS = list(talib.get_function_groups().keys())
    ALL_FUNCTION_GROUPS = ["All"] + TALIB_FUNCTION_GROUPS
    RAW_TO_PARSED_INDICATORS = get_normalized_indicator_map()
    PARSED_TO_RAW_INDICATORS = {v: k for k, v in RAW_TO_PARSED_INDICATORS.items()}

    # Turn this on if you want to see more information.
    ADVANCED = False
    state = {}

    def __init__(self, parent=None):
        super(QDialog, self).__init__(parent)

        self.layout = QVBoxLayout()
        self.selection_layout = QFormLayout()
        self.info_layout = QFormLayout()

        self.layout.addLayout(self.selection_layout)
        self.layout.addLayout(self.info_layout)

        self.submit_button = QPushButton("Add Indicator")
        self.submit_button.clicked.connect(self.add_indicator)
        self.layout.addWidget(self.submit_button)

        self.layout.addItem(get_v_spacer())

        self.indicator_combo_box = QComboBox()
        self.indicator_group_combo_box = QComboBox()

        self.selection_layout.addRow(QLabel('Indicator Group'), self.indicator_group_combo_box)
        self.selection_layout.addRow(QLabel('Indicator'), self.indicator_combo_box)
        self.selection_layout.addRow(get_h_line())

        self.indicator_combo_box.currentTextChanged.connect(self.update_indicator)

        self.indicator_group_combo_box.currentTextChanged.connect(self.update_indicators)
        self.indicator_group_combo_box.addItems(self.ALL_FUNCTION_GROUPS)

        self.setLayout(self.layout)
        self.setWindowTitle('Indicator Selector')

    def add_indicator(self):
        print(self.state)

    def update_indicator(self):
        """
        Update indicator being shown based on the indicator combobox.
        """
        # Clear state.
        self.state = {}
        indicator = self.indicator_combo_box.currentText()

        if not indicator:
            return  # Weird issue where it crashes about KeyError = ''? TODO: Figure out why.

        while self.info_layout.rowCount() > 0:
            self.info_layout.removeRow(0)

        # We need to un-parse because TALIB only recognizes unparsed indicators.
        raw_indicator = self.PARSED_TO_RAW_INDICATORS[indicator]
        indicator_info = abstract.Function(raw_indicator).info

        parameters = indicator_info.pop('parameters')

        for key, value in indicator_info.items():
            if self.ADVANCED:
                value = str(value)
            else:
                if isinstance(value, (list, OrderedDict)) or not value:
                    continue

            key = ' '.join(map(str.capitalize, key.split('_')))

            row = (QLabel(key), QLabel(value))
            self.info_layout.addRow(*row)

        for param_name, param in parameters.items():
            if isinstance(param, int):
                input_obj = get_default_widget(QSpinBox, param, None, None)
            elif isinstance(param, float):
                input_obj = get_default_widget(QDoubleSpinBox, param, None, None)
            elif isinstance(param, str):
                input_obj = QLineEdit()
            else:
                raise ValueError("Unknown type of data encountered.")

            input_obj.setEnabled(False)

            row = (QLabel(param_name.capitalize()), input_obj)
            self.info_layout.addRow(*row)
            self.state = {**indicator_info, param_name: input_obj}

        if len(parameters) == 0:
            self.info_layout.addRow(QLabel("No parameters found."), QLabel(""))

    def update_indicators(self, normalize: bool = True):
        """
        Update indicators available based on the groupbox.
        :param normalize: Whether to normalize the display name or not.
        """
        indicator_group = self.indicator_group_combo_box.currentText()

        if indicator_group == 'All':
            indicators = talib.get_functions()
        else:
            indicators = list(talib.get_function_groups()[indicator_group])

        if normalize:
            indicators = [abstract.Function(indicator).info['display_name'] for indicator in indicators]

        self.indicator_combo_box.clear()
        self.indicator_combo_box.addItems(sorted(indicators))


class StrategyBuilder(QDialog):
    def __init__(self, parent=None):
        super(QDialog, self).__init__(parent)
        self.setWindowTitle('Strategy Builder')

        self.layout = QVBoxLayout()

        self.main_layouts = {
            'Buy Long': QFormLayout(),
            'Sell Long': QFormLayout(),
            'Sell Short': QFormLayout(),
            'Buy Short': QFormLayout()
        }

        for key, layout in self.main_layouts.items():
            add_indicator_button = QPushButton(f"Add {key} Indicator")
            layout.addRow(QLabel(key))
            layout.addRow(add_indicator_button)
            self.layout.addLayout(layout)
            self.layout.addWidget(get_h_line())

        self.setLayout(self.layout)


def except_hook(cls, exception, trace_back):
    """
    Exception hook.
    """
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    strategy_builder = StrategyBuilder()
    strategy_builder.show()

    indicator_selector = IndicatorSelector()
    indicator_selector.show()

    sys.excepthook = except_hook
    sys.exit(app.exec_())
