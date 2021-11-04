"""
Simple strategy builder.
"""

import sys
from typing import Dict, OrderedDict, Optional

import talib
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
                             QPushButton, QSpinBox, QVBoxLayout, QGroupBox, QMessageBox, QRadioButton)
from talib import abstract
from talib import MA_Type

from algobot.interface.configuration_helpers import get_default_widget, get_h_line
from algobot.interface.utils import get_v_spacer, create_popup, get_bold_font


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
    """
    Indicator selector. This will be initialized by the strategy builder.
    """

    TALIB_FUNCTION_GROUPS = list(talib.get_function_groups().keys())
    ALL_FUNCTION_GROUPS = ["All"] + TALIB_FUNCTION_GROUPS
    RAW_TO_PARSED_INDICATORS = get_normalized_indicator_map()
    PARSED_TO_RAW_INDICATORS = {v: k for k, v in RAW_TO_PARSED_INDICATORS.items()}

    MOVING_AVERAGE_TYPES_BY_NUM = vars(MA_Type)['_lookup']
    MOVING_AVERAGE_TYPES_BY_NAME = {k: v for k, v in MOVING_AVERAGE_TYPES_BY_NUM.items()}

    # Turn this on if you want to see more information.
    ADVANCED = False
    state = {}

    def __init__(self, parent: Optional['StrategyBuilder'], helper: bool = False):
        super(QDialog, self).__init__(parent)

        self.layout = QVBoxLayout()
        self.selection_layout = QFormLayout()
        self.info_layout = QFormLayout()
        self.parent = parent
        self.trend = None

        # This should only be true when calling the indicator selector to select an against value.
        if helper is False:
            self.temp_indicator_selector = IndicatorSelector(None, helper=True)

        self.helper = helper

        self.current_add_against_groupbox: Optional[QGroupBox] = None

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
        """
        Add indicator to the strategy builder state.
        """
        # No need to do any logic for now. We are only using for this against values.
        if self.helper is True:
            return

        if self.trend is None:
            raise ValueError("Some trend needs to be set to add indicator.")

        self.parent.state.setdefault(self.trend, [])
        self.parent.state[self.trend].append(self.state)

        # Add the added indicator view to the strategy builder.
        indicator_name = str(self.state['name'])

        operands = ['>', '<', '>=', '<=', '==', '!=']
        operands_combobox = QComboBox()
        operands_combobox.addItems(operands)

        delete_button = QPushButton('Delete')

        info_label = QLabel(f"You are creating a strategy for: {indicator_name}.")
        info_label.setFont(get_bold_font())

        current_price_radio = QRadioButton('Current Price')
        static_value_radio = QRadioButton('Static Value')
        another_indicator_radio = QRadioButton('Another Indicator')

        vbox = QVBoxLayout()
        vbox.addWidget(get_h_line())
        vbox.addWidget(delete_button)
        vbox.addWidget(get_h_line())
        vbox.addWidget(info_label)
        vbox.addWidget(QLabel("Operand"))
        vbox.addWidget(operands_combobox)
        vbox.addWidget(QLabel("Against"))

        vbox.addWidget(current_price_radio)
        current_price_radio.toggled.connect(lambda: self.add_against_values(vbox))

        vbox.addWidget(static_value_radio)
        static_value_radio.toggled.connect(lambda: self.add_against_values(vbox, 'static'))

        vbox.addWidget(another_indicator_radio)
        another_indicator_radio.toggled.connect(lambda: self.add_against_values(vbox, 'indicator'))

        group_box = QGroupBox(indicator_name)
        group_box.setLayout(vbox)

        delete_button.clicked.connect(lambda: self.delete_groupbox(indicator_name, group_box))

        section_layout = self.parent.main_layouts[self.trend]
        section_layout.addRow(group_box)

    def add_against_values(self, vbox: QVBoxLayout, add_type=None):
        # Clear out the previous groupbox.
        if self.current_add_against_groupbox is not None:
            self.current_add_against_groupbox.setParent(None)

        local_vbox = QVBoxLayout()

        self.current_add_against_groupbox = groupbox = QGroupBox()
        groupbox.setLayout(local_vbox)

        if add_type == 'indicator':
            local_vbox.addWidget(QLabel("Enter indicator from selector below."))

            add_indicator_button = QPushButton('Add indicator')
            add_indicator_button.clicked.connect(lambda: self.temp_indicator_selector.open())

            local_vbox.addWidget(add_indicator_button)

        elif add_type == 'static':
            local_vbox.addWidget(QLabel("Enter static value below."))

            spinbox = QDoubleSpinBox()
            spinbox.setMaximum(99999999999)
            local_vbox.addWidget(spinbox)

        elif add_type is None:
            local_vbox.addWidget(QLabel("Bot will execute transactions based on the current price."))

        else:
            raise ValueError("Invalid type of add type provided. Only accepted ones are None, indicator, and static.")

        vbox.addWidget(groupbox)

    def delete_groupbox(self, indicator: str, groupbox: QGroupBox):
        message = f'Are you sure you want to delete this indicator ({indicator})?'
        msg_box = QMessageBox
        ret = msg_box.question(self, 'Warning', message, msg_box.Yes | msg_box.No)

        if ret == msg_box.Yes:
            groupbox.setParent(None)

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

        defaults_label = QLabel('Parameters and their defaults')
        defaults_label.setFont(get_bold_font())

        self.info_layout.addRow(defaults_label)

        for param_name, param in parameters.items():
            if isinstance(param, int):
                if param_name == 'matype':
                    input_obj = QLineEdit()
                    input_obj.setText(self.MOVING_AVERAGE_TYPES_BY_NUM[param])
                else:
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
            self.info_layout.addRow(QLabel("No parameters found."))

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
        """
        Strategy builder. Helps add indicators, comparison operator, and comparisons against.
        :param parent: Parent that initializes the strategy builder. (This should be the Algobot GUI).
        """
        super(QDialog, self).__init__(parent)
        self.indicator_selector = IndicatorSelector(parent=self)
        self.setWindowTitle('Strategy Builder')

        self.state = {}
        self.layout = QVBoxLayout()

        self.main_layouts = {
            'Buy Long': QFormLayout(),
            'Sell Long': QFormLayout(),
            'Sell Short': QFormLayout(),
            'Buy Short': QFormLayout()
        }

        for trend, layout in self.main_layouts.items():
            add_indicator_button = QPushButton(f"Add {trend} Indicator")
            add_indicator_button.clicked.connect(lambda _, strict_key=trend: self.open_indicator_selector(strict_key))

            layout.addRow(QLabel(trend))
            layout.addRow(add_indicator_button)

            self.layout.addLayout(layout)
            self.layout.addWidget(get_h_line())

        self.layout.addWidget(QLabel('Strategy Name'))

        self.strategy_name_input = QLineEdit()
        self.layout.addWidget(self.strategy_name_input)

        self.create_strategy_button = QPushButton("Create Strategy")
        self.create_strategy_button.clicked.connect(self.save_strategy)
        self.layout.addWidget(self.create_strategy_button)

        self.setLayout(self.layout)

    def save_strategy(self):
        """
        Save strategy into a JSON format.
        """
        strategy_name = self.strategy_name_input.text()

        if not strategy_name.strip():
            create_popup(self, "No strategy name found. Please provide a name.")
            return

        if len(self.state) == 1:
            create_popup(self, "No trend indicators found. Please at least select one indicator.")

        self.state['name'] = strategy_name

        import pprint
        pprint.pprint(self.state)

    def open_indicator_selector(self, trend: str):
        """
        Open the indicator selector.
        :param trend: Trend to save indicator as.
        """
        self.indicator_selector.open()
        self.indicator_selector.trend = trend


def except_hook(cls, exception, trace_back):
    """
    Exception hook.
    """
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    strategy_builder = StrategyBuilder()
    strategy_builder.show()

    sys.excepthook = except_hook
    sys.exit(app.exec_())
