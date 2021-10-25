"""
Simple strategy builder.
"""

import sys
from typing import Dict

from talib import abstract
import talib

from PyQt5.QtWidgets import QDialog, QComboBox, QApplication, QFormLayout, QLabel, QVBoxLayout


def get_normalized_indicator_map() -> Dict[str, str]:
    """
    Get a normalized indicator map where the raw value is the key and the normalized value is the value.
    :return: Dictionary of raw/normalized values.
    """
    raw_indicators = talib.get_functions()
    parsed_indicators = [abstract.Function(indicator).info['display_name'] for indicator in raw_indicators]

    # Zip then throw inside a dict and return.
    return dict(zip(raw_indicators, parsed_indicators))


class StrategyBuilder(QDialog):
    TALIB_FUNCTION_GROUPS = list(talib.get_function_groups().keys())
    ALL_FUNCTION_GROUPS = ["All"] + TALIB_FUNCTION_GROUPS
    RAW_TO_PARSED_INDICATORS = get_normalized_indicator_map()
    PARSED_TO_RAW_INDICATORS = {v: k for k, v in RAW_TO_PARSED_INDICATORS.items()}

    def __init__(self, parent=None):
        super(QDialog, self).__init__(parent)

        self.layout = QVBoxLayout()
        self.selection_layout = QFormLayout()
        self.info_layout = QFormLayout()

        self.layout.addLayout(self.selection_layout)
        self.layout.addLayout(self.info_layout)

        self.indicator_combo_box = QComboBox()
        self.indicator_group_combo_box = QComboBox()

        self.selection_layout.addRow(QLabel('Indicator Group'), self.indicator_group_combo_box)
        self.selection_layout.addRow(QLabel('Indicator'), self.indicator_combo_box)

        self.indicator_combo_box.currentTextChanged.connect(self.update_indicator)

        self.indicator_group_combo_box.currentTextChanged.connect(self.update_indicators)
        self.indicator_group_combo_box.addItems(self.ALL_FUNCTION_GROUPS)

        self.setLayout(self.layout)
        self.setWindowTitle('Strategy Builder')

    def update_indicator(self):
        """
        Update indicator being shown based on the indicator combobox.
        """
        indicator = self.indicator_combo_box.currentText()

        if not indicator:
            return  # Weird issue where it crashes about KeyError = ''? TODO: Figure out why.

        while self.info_layout.rowCount() > 0:
            self.info_layout.removeRow(0)

        # We need to un-parse because TALIB only recognizes unparsed indicators.
        raw_indicator = self.PARSED_TO_RAW_INDICATORS[indicator]
        indicator_info = abstract.Function(raw_indicator).info

        for key, value in indicator_info.items():
            value = str(value)
            if not isinstance(key, str):
                continue

            row = (QLabel(key), QLabel(value))
            self.info_layout.addRow(*row)

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


def except_hook(cls, exception, trace_back):
    """
    Exception hook.
    """
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    s = StrategyBuilder()
    s.show()
    sys.excepthook = except_hook
    sys.exit(app.exec_())
