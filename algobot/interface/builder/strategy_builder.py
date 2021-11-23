"""
Simple strategy builder.
"""

import json
import os
import sys
from typing import TYPE_CHECKING, Dict, Optional

from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QLabel,
                             QLineEdit, QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from algobot.enums import TRENDS
from algobot.helpers import STRATEGIES_DIR
from algobot.interface.builder.indicator_selector import IndicatorSelector
from algobot.interface.utils import create_popup

if TYPE_CHECKING:
    from algobot.__main__ import Interface


class StrategyBuilder(QDialog):
    """
    Strategy builder class.
    """
    def __init__(self, parent: Optional['Interface'] = None):
        """
        Strategy builder. Helps add indicators, comparison operator, and comparisons against.
        :param parent: Parent that initializes the strategy builder. (This should be the Algobot GUI).
        """
        super(StrategyBuilder, self).__init__(parent)
        self.setWindowTitle('Strategy Builder')
        self.parent = parent

        # Main indicator selector GUI.
        self.indicator_selector = IndicatorSelector(parent=self)

        # Store the current strategy builder state in this dictionary. We'll dump the state into a JSON file.
        self.state = self.get_empty_state()

        # Main layout itself. This contains the tab widget, input for strategy name, saving, and reset buttons.
        self.layout = QVBoxLayout()

        # Main tab widget that'll hold the tabs.
        self.main_tabs_widget = QTabWidget()
        self.tabs = {trend: (QWidget(), QFormLayout()) for trend in TRENDS}

        for trend, (tab, tab_layout) in self.tabs.items():
            add_indicator_button = QPushButton(f"Add {trend} Indicator")

            # We need to the store the func args here, or else it'll use the latest trend from the loop.
            add_indicator_button.clicked.connect(lambda _, strict_key=trend: self.open_indicator_selector(strict_key))
            tab.setLayout(tab_layout)

            # Add this tab to the main tabs widget.
            self.main_tabs_widget.addTab(tab, trend)

            # Add button to add indicators to inner tab.
            tab_layout.addRow(add_indicator_button)

        # Define a scroll and set the main tabs widget as its main widget. This is super important, as the view looks
        #  hideous when there are a lot of indicators selected (it can shrink and it's not good). That's why we must
        #  encapsulate the items in a scroll, so users can scroll up and down when appropriate.
        scroll = QScrollArea()
        scroll.setWidget(self.main_tabs_widget)
        scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)

        # Create input for strategy name.
        self.layout.addWidget(QLabel('Strategy Name'))
        self.strategy_name_input = QLineEdit()
        self.strategy_name_input.setPlaceholderText("Enter your strategy name here. This is a required field.")
        self.layout.addWidget(self.strategy_name_input)

        # Create input for strategy description.
        self.layout.addWidget(QLabel('Strategy Description'))
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Optional: Enter strategy description.")
        self.layout.addWidget(self.description_input)

        self.create_strategy_button = QPushButton("Create Strategy")
        self.create_strategy_button.clicked.connect(self.save_strategy)
        self.layout.addWidget(self.create_strategy_button)

        self.reset_button = QPushButton("Reset Builder")
        self.reset_button.clicked.connect(self.restore_builder)
        self.layout.addWidget(self.reset_button)

        self.setLayout(self.layout)

        # Set minimum size equal to the main tab widget size. This ensures the strategy builder doesn't start small.
        self.setMinimumSize(self.main_tabs_widget.size())

    @staticmethod
    def get_empty_state() -> Dict[str, dict]:
        """
        Get an empty state.
        :return: Dictionary containing empty state.
        """
        return {trend: {} for trend in TRENDS}

    def restore_builder(self):
        """
        Restore the builder to its initial state.

        Sample state item:
            {'Enter Long':
                {'33e14177-318b-426a-87ce-a6dde86955fe': {
                    'add_against_groupbox': <PyQt5.QtWidgets.QGroupBox object at 0x0000024873507CA0>,
                    'against': None,
                    'name': 'TRIX',
                    'operator': <PyQt5.QtWidgets.QComboBox object at 0x00000248735073A0>,
                    'groupbox': <PyQt5.QtWidgets.QGroupBox object at 0x0000024873507CB9>
                }
            }

        """
        for trend, trend_values in self.state.items():
            for uuid, uuid_values in trend_values.items():
                self.indicator_selector.delete_groupbox(
                    indicator=uuid_values['name'],
                    groupbox=uuid_values['groupbox'],
                    trend=trend,
                    uuid=uuid,
                    bypass_popup=True
                )

        self.state = self.get_empty_state()
        self.strategy_name_input.setText("")
        self.description_input.setText("")

    def save_strategy(self):
        """
        Save strategy into a JSON format.
        """
        strategy_name = self.strategy_name_input.text()
        if not strategy_name.strip():
            create_popup(self, "No strategy name found. Please provide a strategy name.")
            return

        if not any(self.state.values()):
            create_popup(self, "No trend indicators found. Please select at least one indicator.")
            return

        description = self.description_input.text()
        parsed_dict = {
            'name': strategy_name,
            'description': description if description.strip() else "No description provided."
        }

        parsed_dict = self.create_parsed_dict(self.state, parsed_dict)
        if not os.path.exists(STRATEGIES_DIR):
            os.mkdir(STRATEGIES_DIR)

        default_path = os.path.join(STRATEGIES_DIR, strategy_name)
        file_path, _ = QFileDialog.getSaveFileName(self, f'Save {strategy_name} strategy', default_path,
                                                   'JSON (*.json)')

        # User selected cancel.
        if not file_path:
            return

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_dict, f, indent=4)

        create_popup(self, f"Strategy {strategy_name} has been successfully created.")

        if self.parent is not None:
            self.parent.reload_custom_strategies()

    def create_parsed_dict(self, from_dict: dict, to_dict: dict) -> dict:
        """
        Create parsed dictionary to dump into a JSON. It should parse and read the QWidget values and store their
         actual held values.

        Note that this function can be recursive.

        :param from_dict: Dictionary to create a parsed dictionary from.
        :param to_dict: Dictionary to populate.
        :return: Parsed dictionary.
        """
        # We don't use these keys as they're not needed for strategies.
        useless_keys = {'add_against_groupbox', 'groupbox'}

        for key, value in from_dict.items():
            if isinstance(value, dict):
                to_dict[key] = self.create_parsed_dict(value, {})
            elif isinstance(value, QComboBox):
                to_dict[key] = value.currentText()
            elif isinstance(value, (QSpinBox, QDoubleSpinBox)):
                to_dict[key] = value.value()
            elif key in useless_keys:
                continue
            else:
                to_dict[key] = value

        return to_dict

    def open_indicator_selector(self, trend: str):
        """
        Open the indicator selector. Note that we set the trend of indicator selector here, then we delegate the logic
         over to the indicator selector. It'll then in turn update the state set within this strategy builder object
         itself.
        :param trend: Trend to save indicator as.
        """
        self.indicator_selector.trend = trend
        self.indicator_selector.open()


def except_hook(cls, exception, trace_back):
    """
    Exception hook.
    """
    sys.__excepthook__(cls, exception, trace_back)


def main():
    """
    Main function if run independently.
    """
    app = QApplication(sys.argv)

    strategy_builder = StrategyBuilder()
    strategy_builder.show()

    sys.excepthook = except_hook
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
