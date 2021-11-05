"""
Simple strategy builder.
"""

import sys

from PyQt5.QtWidgets import QApplication, QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from algobot.interface.builder.indicator_selector import IndicatorSelector
from algobot.interface.configuration_helpers import get_h_line
from algobot.interface.utils import create_popup


class StrategyBuilder(QDialog):
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

            # We need to the store the func args here, or else it'll use the latest trend from the loop.
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
        TODO: Wrap up.
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
