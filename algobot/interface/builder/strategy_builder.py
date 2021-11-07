"""
Simple strategy builder.
"""
import json
import os
import sys

from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QLabel,
                             QLineEdit, QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from algobot.helpers import STRATEGIES_DIR
from algobot.interface.builder.indicator_selector import IndicatorSelector
from algobot.interface.utils import create_popup


class StrategyBuilder(QDialog):
    """
    Strategy builder class.
    """
    def __init__(self, parent=None):
        """
        Strategy builder. Helps add indicators, comparison operator, and comparisons against.
        :param parent: Parent that initializes the strategy builder. (This should be the Algobot GUI).
        """
        super(QDialog, self).__init__(parent)
        self.setWindowTitle('Strategy Builder')

        # Main indicator selector GUI.
        self.indicator_selector = IndicatorSelector(parent=self)

        # Store the current strategy builder state in this dictionary. We'll dump the state into a JSON file.
        self.state = {
            'Buy Long': {},
            'Sell Long': {},
            'Sell Short': {},
            'Buy Short': {}
        }
        self.layout = QVBoxLayout()

        self.main_tabs_widget = QTabWidget()
        self.tabs = {
            'Buy Long': QWidget(),
            'Sell Long': QWidget(),
            'Sell Short': QWidget(),
            'Buy Short': QWidget(),
        }

        self.main_layouts = {
            'Buy Long': QFormLayout(),
            'Sell Long': QFormLayout(),
            'Sell Short': QFormLayout(),
            'Buy Short': QFormLayout()
        }

        for trend, tab_layout in self.main_layouts.items():
            add_indicator_button = QPushButton(f"Add {trend} Indicator")

            # We need to the store the func args here, or else it'll use the latest trend from the loop.
            add_indicator_button.clicked.connect(lambda _, strict_key=trend: self.open_indicator_selector(strict_key))

            inner_tab = self.tabs[trend]
            inner_tab.setLayout(tab_layout)

            self.main_tabs_widget.addTab(inner_tab, trend)

            tab_layout.addRow(QLabel(trend))
            tab_layout.addRow(add_indicator_button)

        scroll = QScrollArea()
        scroll.setWidget(self.main_tabs_widget)
        scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)
        self.layout.addWidget(QLabel('Strategy Name'))

        self.strategy_name_input = QLineEdit()
        self.layout.addWidget(self.strategy_name_input)

        self.create_strategy_button = QPushButton("Create Strategy")
        self.create_strategy_button.clicked.connect(self.save_strategy)
        self.layout.addWidget(self.create_strategy_button)

        self.reset_button = QPushButton("Reset Builder")
        self.reset_button.clicked.connect(self.restore_builder)
        self.layout.addWidget(self.reset_button)

        self.setLayout(self.layout)
        self.setMinimumSize(self.main_tabs_widget.size())

    def restore_builder(self):
        """
        Restore the builder to initial state.
        """
        for trend, trend_values in self.state.items():
            for uuid, uuid_values in trend_values.items():
                indicator = uuid_values['name']
                self.indicator_selector.delete_groupbox(
                    indicator=indicator,
                    groupbox=uuid_values['groupbox'],
                    trend=trend,
                    uuid=uuid,
                    bypass_popup=True
                )

        self.state = {
            'Buy Long': {},
            'Sell Long': {},
            'Sell Short': {},
            'Buy Short': {}
        }

    def save_strategy(self):
        """
        Save strategy into a JSON format.
        """
        strategy_name = self.strategy_name_input.text()
        self.state['name'] = strategy_name

        if not strategy_name.strip():
            create_popup(self, "No strategy name found. Please provide a name.")
            return

        trend_keys = ('Sell Long', 'Buy Long', 'Sell Short', 'Buy Short')
        if not any(self.state[trend_key] for trend_key in trend_keys):
            create_popup(self, "No trend indicators found. Please at least select one indicator.")
            return

        parsed_dict = self.create_parsed_dict(self.state)

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

    def create_parsed_dict(self, from_dict: dict) -> dict:
        """
        Create parsed dictionary to dump into a JSON. It should parse and read the QWidget values.
        :param from_dict: Dictionary to create a parsed dictionary from.
        :return: Parsed dictionary.
        """
        useless_keys = {'add_against_groupbox', 'groupbox'}
        parsed_dict = {}
        for key, value in from_dict.items():
            if isinstance(value, dict):
                parsed_dict[key] = self.create_parsed_dict(value)
            elif isinstance(value, QComboBox):
                parsed_dict[key] = value.currentText()
            elif isinstance(value, (QSpinBox, QDoubleSpinBox)):
                parsed_dict[key] = value.value()
            elif key in useless_keys:
                continue
            else:
                parsed_dict[key] = value

        return parsed_dict

    def open_indicator_selector(self, trend: str):
        """
        Open the indicator selector. Note that we set the trend of indicator selector here, then we delegate the logic
         over to the indicator selector. It'll store the value set in its parent which is the strategy builder object
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


if __name__ == '__main__':
    app = QApplication(sys.argv)

    strategy_builder = StrategyBuilder()
    strategy_builder.show()

    sys.excepthook = except_hook
    sys.exit(app.exec_())
