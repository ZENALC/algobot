"""
Indicator selector.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, OrderedDict
from uuid import uuid4

import talib
from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QRadioButton, QSpinBox, QVBoxLayout)
from talib import abstract

from algobot.interface.configuration_helpers import get_default_widget, get_h_line
from algobot.interface.utils import get_bold_font, get_v_spacer

if TYPE_CHECKING:
    # pylint: disable=ungrouped-imports
    from algobot.interface.builder.strategy_builder import StrategyBuilder


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

    # Get all the TALIB function groups. Note that we add all as an option as well. If all is selected, we simply
    #  display all possible indicators.
    TALIB_FUNCTION_GROUPS_DICT = talib.get_function_groups()
    TALIB_FUNCTION_GROUPS = list(TALIB_FUNCTION_GROUPS_DICT.keys())
    ALL_FUNCTION_GROUPS = ["All"] + TALIB_FUNCTION_GROUPS

    # Mapping between raw and parsed indicators. We display parsed on the frontend, but we'll store in raw format.
    RAW_TO_PARSED_INDICATORS = get_normalized_indicator_map()
    PARSED_TO_RAW_INDICATORS = {v: k for k, v in RAW_TO_PARSED_INDICATORS.items()}

    # TALIB sets moving averages by numbers. This is not very appealing in the frontend, so we'll map it to its
    #  appropriate moving average.
    MOVING_AVERAGE_TYPES_BY_NUM = vars(talib.MA_Type)['_lookup']
    MOVING_AVERAGE_TYPES_BY_NAME = MOVING_AVERAGE_TYPES_BY_NUM.items()

    def __init__(self, parent: Optional['StrategyBuilder'], helper: bool = False, advanced: bool = False):
        super(IndicatorSelector, self).__init__(parent)

        # Main overall layout.
        self.layout = QVBoxLayout()

        # Top selection layout. This is the only user-modifiable layout.
        self.selection_layout = QFormLayout()
        self.layout.addLayout(self.selection_layout)

        # Layout containing information pertaining to the indicator selected.
        self.info_layout = QFormLayout()
        self.layout.addLayout(self.info_layout)

        # Parent of the indicator selector. If this is None, it means we are calling this object to select an
        #  indicator against. If this is not None, then it'll be the strategy builder itself.
        self.parent = parent

        # Reset the trend to None to ensure no data discrepancy occurs.
        self.trend = None

        # Store current state of the indicator selector. It'll pick up what indicator is selected and its parameters.
        self.state = {}

        # Initialize with this at true if you want to see more information during indicator selection.
        self.advanced_mode = advanced

        # This should only be true when calling the indicator selector to select an against value. If this is not set
        #  to true, it'll start creating layouts in the strategy builder which is not something we want. Actually,
        #  it would not even work as the parent would be None, so it would crash! Please make sure the parent is also
        #  set to None in the strategy builder when calling this for an against value.

        # Callback for adding against indicator. This works okay because only one window is allowed regardless
        #  of how many indicators are created.
        self.callback = None
        self.helper = helper
        if helper is False:
            self.temp_indicator_selector = IndicatorSelector(None, helper=True)

        # Just adding the add indicator button here.
        self.submit_button = QPushButton("Select Indicator")
        self.submit_button.clicked.connect(self.add_indicator)
        self.layout.addWidget(self.submit_button)

        # Just adding a vertical line as a separator here.
        self.layout.addItem(get_v_spacer())

        # Creating the indicator group and indicator comboboxes. Note that the order in which these are defined
        #  matters. If you rearrange these, this will create funky behavior because of the trigger mutations.
        self.indicator_group_combo_box = QComboBox()
        self.indicator_combo_box = QComboBox()

        self.selection_layout.addRow(QLabel('Indicator Group'), self.indicator_group_combo_box)
        self.selection_layout.addRow(QLabel('Indicator'), self.indicator_combo_box)
        self.selection_layout.addRow(get_h_line())

        self.indicator_group_combo_box.currentTextChanged.connect(self.update_indicators)
        self.indicator_combo_box.currentTextChanged.connect(self.update_indicator)

        # This should always go AFTER the triggers have been created.
        self.indicator_group_combo_box.addItems(self.ALL_FUNCTION_GROUPS)

        self.setLayout(self.layout)
        self.setWindowTitle('Indicator Selector')

    def update_indicator(self):
        """
        Update indicator being shown based on the indicator combobox. This will update the info layout with the
         strategy information and its default parameters. Note that the indicators will only be able to be modified
         in the actual Algobot interface, not here. This is to have support for dynamic strategies; that is, we don't
         want to be constrained to the values defined in the strategy builder.
        """
        # Clear the state.
        self.state = {}

        indicator = self.indicator_combo_box.currentText()
        if not indicator:
            return  # Weird issue where it crashes about KeyError = ''? TODO: Figure out why.

        # Clear out the widgets in the info layout as we're updating the indicator.
        while self.info_layout.rowCount() > 0:
            self.info_layout.removeRow(0)

        # We need to un-parse because TALIB only recognizes unparsed indicators.
        raw_indicator = self.PARSED_TO_RAW_INDICATORS[indicator]

        # Now, let's populate the info items.
        indicator_info = abstract.Function(raw_indicator).info
        self.add_info_items(indicator_info)

        # Creating a title showing that this is just the parameters and their defaults.
        defaults_label = QLabel('Parameters and their defaults')
        defaults_label.setFont(get_bold_font())
        self.info_layout.addRow(defaults_label)

        # For each param, show the appropriate default value in its appropriate input field.
        self.add_param_items(indicator_info)

    def add_info_items(self, indicator_info: Dict[str, Any]):
        """
        Add info items to the info layout.
        :param indicator_info: Dictionary containing indicator information.
        """
        for key, value in indicator_info.items():
            if self.advanced_mode:
                value = str(value)
            else:
                if isinstance(value, (list, OrderedDict)) or not value:
                    continue

            key = ' '.join(map(str.capitalize, key.split('_')))

            row = (QLabel(key), QLabel(value))
            self.info_layout.addRow(*row)

    def add_against_radio_buttons(self, vbox, unique_identifier: str):
        """
        Add against radio buttons.
        :param vbox: Layout to add radio buttons to.
        :param unique_identifier: Unique identifier to distinguish in states.
        """
        current_price_radio = QRadioButton('Current Price')
        static_value_radio = QRadioButton('Static Value')
        another_indicator_radio = QRadioButton('Another Indicator')

        vbox.addWidget(current_price_radio)
        current_price_radio.toggled.connect(lambda: self.add_against_values(vbox, unique_identifier))

        vbox.addWidget(static_value_radio)
        static_value_radio.toggled.connect(lambda: self.add_against_values(vbox, unique_identifier, 'static'))

        vbox.addWidget(another_indicator_radio)
        another_indicator_radio.toggled.connect(lambda: self.add_against_values(vbox, unique_identifier, 'indicator'))

        # Default to current price radio selected.
        current_price_radio.setChecked(True)

    def add_param_items(self, indicator_info: Dict[str, Any]):
        """
        Add parameter items to the info layout.

        Parameters look like this:

            Without any parameters: OrderedDict()

            With parameters: OrderedDict([('timeperiod', 30)])

        Indicators look like this (they contain the params):

            { (without params)
                'name': 'CDLBELTHOLD',
                'group': 'Pattern Recognition',
                'display_name': 'Belt-hold',
                'function_flags': ['Output is a candlestick'],
                'input_names': OrderedDict([('prices', ['open', 'high', 'low', 'close'])]),
                'parameters': OrderedDict(),
                'output_flags': OrderedDict([('integer', ['Line'])]), 'output_names': ['integer']
            }

            { (with params)
                'name': 'BBANDS',
                'group': 'Overlap Studies',
                'display_name': 'Bollinger Bands',
                'function_flags': ['Output scale same as input'],
                'input_names': OrderedDict([('price', 'close')]),
                'parameters': OrderedDict([
                    ('timeperiod', 5),
                    ('nbdevup', 2),
                    ('nbdevdn', 2),
                    ('matype', 0)
                ]),
                'output_flags': OrderedDict([
                    ('upperband', ['Values represent an upper limit']),
                    ('middleband', ['Line']),
                    ('lowerband', ['Values represent a lower limit'])
                ]),
                'output_names': ['upperband', 'middleband', 'lowerband']}



        :param indicator_info: Dictionary containing indicator information.
        """
        self.submit_button.setEnabled(True)

        self.state = {
            'name': indicator_info['name']
        }

        parameters = indicator_info['parameters']
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

        if len(parameters) == 0:
            self.info_layout.addRow(QLabel("No parameters found. Cannot submit this indicator right now."))
            self.submit_button.setEnabled(False)

    def add_indicator(self):
        """
        Add indicator to the strategy builder state.
        """
        # Add the added indicator view to the strategy builder.
        indicator_name = str(self.state['name'])

        # No need to do any logic for now. We are only using for this against values.
        # TODO: Return indicator name once selected.
        if self.helper is True:
            self.callback(indicator_name)
            self.update_indicator()
            self.hide()
            return

        if self.trend is None:
            raise ValueError("Some trend needs to be set to add an indicator.")

        # Add trend key and add indicator to its list value.
        unique_identifier = str(uuid4())
        self.parent.state.setdefault(self.trend, {})
        self.parent.state[self.trend][unique_identifier] = self.state

        vbox = QVBoxLayout()
        vbox.addWidget(get_h_line())

        delete_button = QPushButton('Delete')
        delete_button.clicked.connect(lambda _, trend=self.trend: self.delete_groupbox(
            indicator_name, group_box, unique_identifier, trend))

        vbox.addWidget(delete_button)
        vbox.addWidget(get_h_line())

        info_label = QLabel(f"You are creating a strategy for: {indicator_name}.")
        info_label.setFont(get_bold_font())
        vbox.addWidget(info_label)

        self.add_operand(vbox, unique_identifier)
        self.add_against_radio_buttons(vbox, unique_identifier)

        group_box = QGroupBox(indicator_name)
        group_box.setLayout(vbox)

        self.parent.state[self.trend][unique_identifier]['groupbox'] = group_box

        section_layout = self.parent.main_layouts[self.trend]
        section_layout.addRow(group_box)

        # Reset state by re-updating indicator and hide the window. This is beyond imperative.
        # TODO: Consider refactoring this logic.
        self.update_indicator()
        self.hide()

    def add_operand(self, vbox: QVBoxLayout, unique_identifier: str):
        """
        Add operand values.
        :param vbox: Vertical layout to add operand values to.
        :param unique_identifier: Unique identifier to distinguish in states.
        """
        operands = ['>', '<', '>=', '<=', '==', '!=']
        self.parent.state[self.trend][unique_identifier]['operand'] = operands_combobox = QComboBox()
        operands_combobox.addItems(operands)

        vbox.addWidget(QLabel("Operand"))
        vbox.addWidget(operands_combobox)
        vbox.addWidget(QLabel("Against"))

    def add_against_values(self, vbox: QVBoxLayout, unique_identifier: str, add_type: Optional[str] = None):
        """
        Add against values.
        :param vbox: Vertical layout to add against values to.
        :param unique_identifier: Unique identifier to distinguish in states.
        :param add_type: Type of value to add.
        """
        unique_dict = self.parent.state[self.trend][unique_identifier]

        add_against_groupbox = 'add_against_groupbox'
        against = 'against'

        # Clear out the previous groupbox.
        if add_against_groupbox in unique_dict:
            unique_dict[add_against_groupbox].setParent(None)

        unique_dict[add_against_groupbox] = groupbox = QGroupBox()

        local_vbox = QVBoxLayout()
        groupbox.setLayout(local_vbox)

        if add_type == 'indicator':
            local_vbox.addWidget(QLabel("Enter indicator from selector below."))

            indicator_against_selected = QLabel('No indicator against selected.')

            def bind(selected_indicator: str):
                indicator_against_selected.setText(f'{selected_indicator} selected.')
                unique_dict[against] = selected_indicator

            def view_indicator_selector():
                self.temp_indicator_selector.callback = bind
                self.temp_indicator_selector.open()

            add_indicator_button = QPushButton('Select indicator')
            add_indicator_button.clicked.connect(view_indicator_selector)

            local_vbox.addWidget(add_indicator_button)
            local_vbox.addWidget(indicator_against_selected)
            unique_dict[against] = None

        elif add_type == 'static':
            local_vbox.addWidget(QLabel("Enter static value below."))

            spinbox = QDoubleSpinBox()
            spinbox.setMaximum(99999999999)
            local_vbox.addWidget(spinbox)
            unique_dict[against] = spinbox

        elif add_type is None:
            local_vbox.addWidget(QLabel("Bot will execute transactions based on the current price."))
            unique_dict[against] = 'current_price'

        else:
            raise ValueError("Invalid type of add type provided. Only accepted ones are None, indicator, and static.")

        vbox.addWidget(groupbox)

    def delete_groupbox(self, indicator: str, groupbox: QGroupBox, uuid: str, trend: str, bypass_popup: bool = False):
        """
        Delete groupbox based on the indicator and groupbox provided.

        Sample from state:
            {'Buy Long':
                {'33e14177-318b-426a-87ce-a6dde86955fe': {
                    'add_against_groupbox': <PyQt5.QtWidgets.QGroupBox object at 0x0000024873507CA0>,
                    'against': None,
                    'name': 'TRIX',
                    'operand': <PyQt5.QtWidgets.QComboBox object at 0x00000248735073A0>
                }
            }

        :param indicator: Indicator to remove. Only used for populating the messagebox.
        :param groupbox: Groupbox to remove.
        :param uuid: State UUID to remove from dictionary.
        :param trend: Trend associated with this groupbox.
        :param bypass_popup: Bypass popup. Used with restore_builder.
        """
        if not bypass_popup:
            message = f'Are you sure you want to delete this indicator ({indicator})?'
            msg_box = QMessageBox
            ret = msg_box.question(self, 'Warning', message, msg_box.Yes | msg_box.No)

        # If confirmed, delete the groupbox and remove from parent state.
        if bypass_popup or ret == msg_box.Yes:  # noqa

            # This is because the state will be reset anyway and we don't want the dictionary to change size during
            #  iteration. TODO: Cleanup.
            if not bypass_popup:
                del self.parent.state[trend][uuid]

            groupbox.setParent(None)

            # Resize the parent to shrink once groupbox has been deleted.
            if self.parent is not None:
                self.parent.adjustSize()

    def update_indicators(self, normalize: bool = True):
        """
        Update indicators available based on the groupbox.
        :param normalize: Whether to normalize the display name or not.
        """
        indicator_group = self.indicator_group_combo_box.currentText()

        if indicator_group == 'All':
            indicators = talib.get_functions()
        else:
            indicators = list(self.TALIB_FUNCTION_GROUPS_DICT[indicator_group])

        if normalize:
            indicators = [abstract.Function(indicator).info['display_name'] for indicator in indicators]

        self.indicator_combo_box.clear()
        self.indicator_combo_box.addItems(sorted(indicators))
