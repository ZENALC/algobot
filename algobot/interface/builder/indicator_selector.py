"""
Indicator selector.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, OrderedDict
from uuid import uuid4

import talib
from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QPushButton,
                             QRadioButton, QSizePolicy, QSpacerItem, QVBoxLayout)
from talib import abstract

from algobot.interface.configuration_helpers import get_h_line
from algobot.interface.utils import (OPERATORS, PARAMETER_MAP, confirm_message_box, get_bold_font, get_param_obj,
                                     get_v_spacer, get_widget_with_layout)

if TYPE_CHECKING:
    # Strategy builder calls indicator selector, so we can't just simply import strategy builder for hinting here.
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

    def __init__(
            self,
            parent: Optional['StrategyBuilder'],
            helper: bool = False,
            advanced: bool = False
    ):
        """
        Initialization of the indicator selector.

        This indicator selector is used for both adding indicators themselves and for adding against values. We use
         callbacks for indicator against values. This works fine regardless of how many indicators have been selected,
         because only one indicator selector window is allowed. That is, it'll always open the same one, so whatever
         button was clicked, it'll callback for that indicator and update only its against value.

        :param parent: Parent of this indicator selector. It should be the strategy builder under normal circumstances
         when adding an indicator and None when used for an against indicator.
        :param helper: Whether it's being used for an against indicator.
        :param advanced: Advanced mode to see more parameters in the info view.
        """
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

        self.helper = helper
        if helper is False:
            self.temp_indicator_selector = IndicatorSelector(self.parent, helper=True)

        # Callback for adding against indicator. This works okay because only one window is allowed regardless
        #  of how many indicators are created.
        self.callback = None

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

        # For each parameter, show the appropriate default value in its appropriate input field.
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

    def add_against_radio_buttons(self, vbox: QVBoxLayout, unique_identifier: str):
        """
        Add against radio buttons. Once toggled, they should trigger the add against values function and have it create
         appropriate UI elements.

        Note that we use the unique identifier to tell the radio buttons apart for all indicators. We also default
        checking to current price.

        :param vbox: Layout to add radio buttons to.
        :param unique_identifier: Unique identifier to distinguish in states.
        """
        current_price_radio = QRadioButton('Current Price')
        static_value_radio = QRadioButton('Static Value')
        another_indicator_radio = QRadioButton('Another Indicator')

        vbox.addWidget(current_price_radio)
        current_price_radio.toggled.connect(lambda *_args, trend=self.trend: self.add_against_values(
            vbox, unique_identifier, trend=trend
        ))

        vbox.addWidget(static_value_radio)
        static_value_radio.toggled.connect(lambda *_args, trend=self.trend: self.add_against_values(
            vbox, unique_identifier, trend=trend, add_type='static'
        ))

        vbox.addWidget(another_indicator_radio)
        another_indicator_radio.toggled.connect(lambda *_args, trend=self.trend: self.add_against_values(
            vbox, unique_identifier, trend=trend, add_type='indicator'
        ))

        # Default to current price radio selected.
        current_price_radio.setChecked(True)

    def add_param_items(self, indicator_info: Dict[str, Any]):
        """
        Add parameter items to the info layout.

        DISCLAIMER: Note these are not really needed. It's just for the user to see the parameters. None of these is
         actually modifiable.

        Parameters look like this:

            Without any parameters: OrderedDict()

            With parameters: OrderedDict([('timeperiod', 30)])

        Indicators look like this (they contain the parameters):

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

        # By default, we allow indicators to be selected. However, for indicators without parameters, we disallow
        #  submissions. Note if len(parameters) == 0, we disable this submission button.
        self.submit_button.setEnabled(True)

        # Initialize state with just the name. We don't need anything else. Operator and against will be populated once
        #  the user fills them in. Note that Algobot will automatically populate the strategy UI elements from just the
        #  strategy name.
        self.state = {
            'name': indicator_info['name']
        }

        parameters = indicator_info['parameters']
        for param_name, default_value in parameters.items():
            input_obj = get_param_obj(default_value=default_value, param_name=param_name)
            input_obj.setEnabled(False)

            row = (QLabel(PARAMETER_MAP.get(param_name, param_name)), input_obj)
            self.info_layout.addRow(*row)

        # TODO: Add support for indicators that return candlesticks.
        if len(parameters) == 0:
            self.info_layout.addRow(QLabel("No parameters found. Cannot submit this indicator right now."))
            self.submit_button.setEnabled(False)

    def reset_and_hide(self):
        """

        Reset state by re-updating indicator and hide the window. This is beyond imperative to hide() the window. If
         we don't update the indicator, and we don't change the indicator, we'll use duplicate groupboxes and other UI
         elements.

        TODO: Consider refactoring this logic.
        TODO: Fix bug where indicator selector makes strategy builder hide.

        """
        self.update_indicator()
        # self.hide()

    def add_indicator(self):
        """
        Add indicator to the strategy builder state. Note this class is the indicator selector class. This will
         populate the parent's state (strategy builder's state) based on the current trend set in the indicator
         selector.
        """
        # Add the added indicator view to the strategy builder.
        indicator_name = str(self.state['name'])

        # No need to do any logic for now. We are only using for this against values.
        if self.helper is True:
            self.callback(indicator_name)
            self.reset_and_hide()
            return

        if self.trend is None:
            raise ValueError("Some trend needs to be set to add an indicator.")

        parent_indicators_tab = self.parent.inner_tab_widgets[self.trend]
        self.state['tab_index'] = parent_indicators_tab.count()  # The count would be the current index here.

        # Add trend key and add indicator to its list value.
        unique_identifier = str(uuid4())
        self.parent.state.setdefault(self.trend, {})
        self.parent.state[self.trend][unique_identifier] = self.state

        # Initialize a vertical layout; we'll add all UI elements to this layout.
        indicator_tab = get_widget_with_layout(QVBoxLayout())

        # Tightly bind each delete button of each groupbox to its indicator name, groupbox element, unique identifier,
        #  and trend.
        delete_button = QPushButton('Delete')
        delete_button.clicked.connect(
            lambda _, trend=self.trend: self.delete_indicator(
                unique_identifier, trend
            )
        )

        indicator_tab.layout().addWidget(delete_button)

        self.add_operator(indicator_tab.layout(), unique_identifier)
        self.add_against_radio_buttons(indicator_tab.layout(), unique_identifier)

        indicator_tab.layout().addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        )

        parent_indicators_tab.addTab(indicator_tab, indicator_name)
        self.reset_and_hide()

    def add_operator(self, vbox: QVBoxLayout, unique_identifier: str):
        """
        Add operator values; there are the >, <, >=, etc values. When storing state, we'll just fetch the combobox's
         selected value.
        :param vbox: Vertical layout to add operator values to.
        :param unique_identifier: Unique identifier to distinguish in states.
        """
        self.parent.state[self.trend][unique_identifier]['operator'] = operators_combobox = QComboBox()
        operators_combobox.addItems(OPERATORS)

        vbox.addWidget(QLabel("Operator"))
        vbox.addWidget(operators_combobox)
        vbox.addWidget(QLabel("Against"))

    def add_against_values(self, vbox: QVBoxLayout, unique_identifier: str, trend: str, add_type: Optional[str] = None):
        """
        Add against UI element values.
        :param vbox: Vertical layout to add against values to. This vbox lives in the parent (strategy builder).
        :param unique_identifier: Unique identifier to distinguish in states.
        :param trend: Trend to add against values for.
        :param add_type: Type of value to add.
        """
        unique_dict = self.parent.state[trend][unique_identifier]

        add_against_groupbox = 'add_against_groupbox'
        against = 'against'

        # Clear out the previous add-against groupbox if it exists. Note this is the modifying the parent state. Also
        #  note that we still want to keep this unique dictionary; we only want to modify its add_against_groupbox key.
        if add_against_groupbox in unique_dict:
            unique_dict[add_against_groupbox].setParent(None)

        # Create new groupbox to replace the one nuked above.
        unique_dict[add_against_groupbox] = groupbox = QGroupBox()

        # Local vertical layout to add against UI elements to.
        local_vbox = QVBoxLayout()
        groupbox.setLayout(local_vbox)

        if add_type == 'indicator':
            local_vbox.addWidget(QLabel("Enter indicator from selector below."))
            indicator_against_selected = QLabel('No indicator against selected.')

            def bind(selected_indicator: str):
                """
                Callback function for the temp indicator to execute once user selects an indicator.
                :param selected_indicator: The indicator the user selected.
                """
                indicator_against_selected.setText(f'{selected_indicator} selected.')
                unique_dict[against] = selected_indicator

            def view_indicator_selector():
                """
                Call this function when adding against using another indicator. It'll update the temporary indicator
                 selector's callback function with bind() defined above.
                """
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

        # Add this groupbox to the appropriate vertical layout in the strategy builder.
        vbox.addWidget(groupbox)

    def delete_indicator(self, uuid: str, trend: str, bypass_popup: bool = False):
        """
        Delete indicator based on the trend and UUID provided.

        Sample from state:
            {'Enter Long':
                {'33e14177-318b-426a-87ce-a6dde86955fe': {
                    'add_against_groupbox': <PyQt5.QtWidgets.QGroupBox object at 0x0000024873507CA0>,
                    'against': None,
                    'name': 'TRIX',
                    'operator': <PyQt5.QtWidgets.QComboBox object at 0x00000248735073A0>,
                }
            }

        :param uuid: State UUID to remove from dictionary.
        :param trend: Trend associated with this groupbox.
        :param bypass_popup: Bypass popup. Used with restore_builder.
        """
        indicator = self.parent.state[trend][uuid]['name']
        if not bypass_popup:
            confirm = confirm_message_box(
                message=f'Are you sure you want to delete this indicator ({indicator})?',
                parent=self
            )

        # If confirmed or bypassing popup, delete the groupbox and remove from parent state.
        if bypass_popup or confirm:  # noqa

            tab_index = self.parent.state[trend][uuid]['tab_index']
            for loop_uuid, indicator in self.parent.state[trend].items():
                # We have to shift all existing indicators one step to the left post-deletion.
                if loop_uuid == uuid:
                    continue

                if indicator['tab_index'] > tab_index:
                    indicator['tab_index'] -= 1

            self.parent.inner_tab_widgets[trend].removeTab(tab_index)

            # This is because the state will be reset anyway and we don't want the dictionary to change size during
            #  iteration. TODO: Cleanup.
            if not bypass_popup:
                del self.parent.state[trend][uuid]

            # TODO: Resize only if window becomes smaller to make bigger?
            # Resize the parent to shrink once groupbox has been deleted.
            # if self.parent is not None:
            #     self.parent.adjustSize()

    def update_indicators(self, normalize: bool = True):
        """
        Update indicators available based on the indicator group combobox.
        :param normalize: Whether to normalize the display name or not.
        """
        indicator_group = self.indicator_group_combo_box.currentText()

        if indicator_group == 'All':
            indicators = talib.get_functions()
        else:
            indicators = list(self.TALIB_FUNCTION_GROUPS_DICT[indicator_group])

        if normalize:
            indicators = [abstract.Function(indicator).info['display_name'] for indicator in indicators]

        # Clear out current indicator selected after update above.
        self.indicator_combo_box.clear()

        # Display items in a sorted fashion.
        self.indicator_combo_box.addItems(sorted(indicators))
