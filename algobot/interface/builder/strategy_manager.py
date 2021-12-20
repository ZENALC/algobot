"""
Strategy manager.
"""
import os
from typing import TYPE_CHECKING, Dict

from PyQt5.QtWidgets import QComboBox, QDialog, QLabel, QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout

from algobot.interface.configuration_helpers import get_h_line
from algobot.interface.utils import confirm_message_box, get_bold_font

if TYPE_CHECKING:
    from algobot.interface.configuration import Interface


class StrategyManager(QDialog):
    """
    Strategy manager for strategy edits and deletions.
    """
    def __init__(self, parent: 'Interface'):
        super(StrategyManager, self).__init__(parent)
        self.setWindowTitle("Strategy Manager")
        self.parent = parent
        self.configuration = self.parent.configuration
        self.layout = QVBoxLayout()

        self.json_strategies = self.parse_strategies()
        self.strategies_found_label = QLabel(f"{len(self.json_strategies)} strategies available for management.")
        self.strategies_found_label.setFont(get_bold_font())
        self.layout.addWidget(self.strategies_found_label)

        self.refresh_button = QPushButton("Refresh strategies")
        self.refresh_button.clicked.connect(self.reset_gui)
        self.layout.addWidget(self.refresh_button)
        self.layout.addWidget(get_h_line())

        self.layout.addWidget(QLabel("Strategies"))
        self.strategies_combobox = QComboBox()
        self.strategies_combobox.addItems(self.json_strategies.keys())
        self.layout.addWidget(self.strategies_combobox)

        self.delete_button = QPushButton("Delete Strategy")
        self.delete_button.clicked.connect(self.delete_strategy)
        self.layout.addWidget(self.delete_button)

        self.control_state()
        self.layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self.setLayout(self.layout)

    def control_state(self):
        """
        Control state of widgets based on JSON strategies existent.
        """
        enable = len(self.json_strategies) > 0
        self.strategies_combobox.setEnabled(enable)
        self.delete_button.setEnabled(enable)

    def parse_strategies(self) -> Dict[str, dict]:
        """
        Parse strategies in a way that the strategy name is the key and the strategy along with the path is the value.
        :return: New parsed dictionary.
        """
        new_dict = {}
        for path, strategy in self.configuration.json_strategies_with_path:
            strategy_name = strategy['name']
            new_dict[strategy_name] = strategy
            new_dict[strategy_name]['path'] = path

        return new_dict

    def reset_gui(self):
        """
        Reset GUI by refreshing dictionary information.
        """
        self.configuration.reload_custom_strategies()
        self.json_strategies = self.parse_strategies()
        self.strategies_found_label.setText(f"{len(self.json_strategies)} strategies available for management.")
        self.strategies_combobox.clear()
        self.strategies_combobox.addItems(self.json_strategies.keys())
        self.control_state()

    def delete_strategy(self):
        """
        Delete a strategy.
        """
        selected_strategy = self.strategies_combobox.currentText()

        if not selected_strategy:
            return

        if confirm_message_box(f"Are you sure you want to delete the strategy: {selected_strategy}?", self):
            strategy = self.json_strategies[selected_strategy]
            os.remove(strategy['path'])
            self.configuration.reload_custom_strategies()
            self.reset_gui()
