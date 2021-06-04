"""
Slots helper functions for configuration.py can be found here.
"""
from PyQt5.QtWidgets import (QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                             QScrollArea, QSpinBox, QTabWidget, QVBoxLayout)

from algobot import helpers
from algobot.enums import BACKTEST, OPTIMIZER
from algobot.interface.config_utils.credential_utils import (
    load_credentials, save_credentials, test_binance_credentials)
from algobot.interface.config_utils.data_utils import (download_data,
                                                       import_data,
                                                       stop_download)
from algobot.interface.config_utils.strategy_utils import (
    add_strategy_buttons, create_strategy_inputs,
    reset_strategy_interval_comboBox)
from algobot.interface.config_utils.telegram_utils import (
    reset_telegram_state, test_telegram)
from algobot.interface.config_utils.user_config_utils import (
    copy_settings_to_backtest, copy_settings_to_simulation,
    load_backtest_settings, load_live_settings, load_simulation_settings,
    save_backtest_settings, save_live_settings, save_simulation_settings)
from algobot.interface.configuration_helpers import (
    add_start_end_step_to_layout, create_inner_tab, get_default_widget,
    get_regular_groupbox_and_layout)


def load_loss_slots(config_obj):
    """
    Loads slots for loss settings in GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    create_inner_tab(
        categoryTabs=config_obj.categoryTabs,
        description="Configure your stop loss settings here.",
        tabName="Stop Loss",
        input_creator=config_obj.create_loss_inputs,
        dictionary=config_obj.lossDict,
        signalFunction=config_obj.update_loss_settings,
        parent=config_obj
    )


def load_take_profit_slots(config_obj):
    """
    Loads slots for take profit settings in GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    create_inner_tab(
        categoryTabs=config_obj.categoryTabs,
        description="Configure your take profit settings here.",
        tabName="Take Profit",
        input_creator=config_obj.create_take_profit_inputs,
        dictionary=config_obj.takeProfitDict,
        signalFunction=config_obj.update_take_profit_settings,
        parent=config_obj
    )


def load_strategy_slots(config_obj):
    """
    This will initialize all the necessary strategy slots and add them to the configuration GUI. All the strategies
    are loaded from the self.strategies dictionary.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :return: None
    """
    for strategy in config_obj.strategies.values():
        temp = strategy()
        strategyName = temp.name
        parameters = temp.get_param_types()
        for tab in config_obj.categoryTabs:
            config_obj.strategyDict[tab, strategyName] = tabWidget = QTabWidget()
            descriptionLabel = QLabel(f'Strategy description: {temp.description}')
            descriptionLabel.setWordWrap(True)

            layout = QVBoxLayout()
            layout.addWidget(descriptionLabel)

            scroll = QScrollArea()  # Added a scroll area so user can scroll when additional slots are added.
            scroll.setWidgetResizable(True)

            if config_obj.get_caller_based_on_tab(tab) == OPTIMIZER:
                groupBox, groupBoxLayout = get_regular_groupbox_and_layout(f'Enable {strategyName} optimization?')
                config_obj.strategyDict[tab, strategyName] = groupBox
                for index, parameter in enumerate(parameters, start=1):
                    # TODO: Refactor this logic.
                    if type(parameter) != tuple or type(parameter) == tuple and parameter[1] in [int, float]:
                        if type(parameter) == tuple:
                            widget = QSpinBox if parameter[1] == int else QDoubleSpinBox
                            step_val = 1 if widget == QSpinBox else 0.1
                        else:
                            widget = QSpinBox if parameter == int else QDoubleSpinBox
                            step_val = 1 if widget == QSpinBox else 0.1
                        config_obj.strategyDict[strategyName, index, 'start'] = start = get_default_widget(widget, 1)
                        config_obj.strategyDict[strategyName, index, 'end'] = end = get_default_widget(widget, 1)
                        config_obj.strategyDict[strategyName, index, 'step'] = step = get_default_widget(widget,
                                                                                                         step_val)
                        if type(parameter) == tuple:
                            message = parameter[0]
                        else:
                            message = f"{strategyName} {index}"
                        add_start_end_step_to_layout(groupBoxLayout, message, start, end, step)
                    elif type(parameter) == tuple and parameter[1] == tuple:
                        groupBoxLayout.addRow(QLabel(parameter[0]))
                        for option in parameter[2]:
                            config_obj.strategyDict[strategyName, option] = checkBox = QCheckBox(option)
                            groupBoxLayout.addRow(checkBox)
                    else:
                        raise ValueError("Invalid type of parameter type provided.")
            else:
                groupBox, groupBoxLayout = get_regular_groupbox_and_layout(f"Enable {strategyName}?")
                config_obj.strategyDict[tab, strategyName, 'groupBox'] = groupBox

                status = QLabel()
                if temp.dynamic:
                    addButton, deleteButton = add_strategy_buttons(config_obj.strategyDict, parameters, strategyName,
                                                                   groupBoxLayout, tab)
                    horizontalLayout = QHBoxLayout()
                    horizontalLayout.addWidget(addButton)
                    horizontalLayout.addWidget(deleteButton)
                    horizontalLayout.addWidget(status)
                    horizontalLayout.addStretch()
                    layout.addLayout(horizontalLayout)

                values, labels = create_strategy_inputs(parameters, strategyName, groupBoxLayout)
                config_obj.strategyDict[tab, strategyName, 'values'] = values
                config_obj.strategyDict[tab, strategyName, 'labels'] = labels
                config_obj.strategyDict[tab, strategyName, 'parameters'] = parameters
                config_obj.strategyDict[tab, strategyName, 'layout'] = groupBoxLayout
                config_obj.strategyDict[tab, strategyName, 'status'] = status

            layout.addWidget(scroll)
            scroll.setWidget(groupBox)
            tabWidget.setLayout(layout)
            tab.addTab(tabWidget, strategyName)


def load_interval_combo_boxes(config_obj):
    """
    This function currently only handles combo boxes for backtester/optimizer interval logic. It'll update the
    strategy interval combo-box depending on what the data interval combo-box has as its current value.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    intervals = helpers.get_interval_strings(startingIndex=0)
    config_obj.backtestStrategyIntervalCombobox.addItems(intervals)
    config_obj.backtestIntervalComboBox.addItems(intervals)
    config_obj.backtestIntervalComboBox.currentTextChanged.connect(lambda: reset_strategy_interval_comboBox(
        strategy_combobox=config_obj.backtestStrategyIntervalCombobox,
        interval_combobox=config_obj.backtestIntervalComboBox
    ))

    config_obj.optimizerStrategyIntervalCombobox.addItems(intervals)
    config_obj.optimizerIntervalComboBox.addItems(intervals)
    config_obj.optimizerStrategyIntervalEndCombobox.addItems(intervals)

    config_obj.optimizerIntervalComboBox.currentTextChanged.connect(lambda: reset_strategy_interval_comboBox(
        strategy_combobox=config_obj.optimizerStrategyIntervalCombobox,
        interval_combobox=config_obj.optimizerIntervalComboBox
    ))

    config_obj.optimizerStrategyIntervalCombobox.currentTextChanged.connect(lambda: reset_strategy_interval_comboBox(
        strategy_combobox=config_obj.optimizerStrategyIntervalEndCombobox,
        interval_combobox=config_obj.optimizerStrategyIntervalCombobox,
        start_index=config_obj.optimizerIntervalComboBox.currentIndex(),
        divisor=helpers.get_interval_minutes(config_obj.optimizerIntervalComboBox.currentText())
    ))


def load_slots(config_obj):
    """
    Loads all configuration interface slots.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :return: None
    """
    config_obj.simulationCopySettingsButton.clicked.connect(lambda: copy_settings_to_simulation(config_obj))
    config_obj.simulationSaveConfigurationButton.clicked.connect(lambda: save_simulation_settings(config_obj))
    config_obj.simulationLoadConfigurationButton.clicked.connect(lambda: load_simulation_settings(config_obj))

    config_obj.backtestCopySettingsButton.clicked.connect(lambda: copy_settings_to_backtest(config_obj))
    config_obj.backtestSaveConfigurationButton.clicked.connect(lambda: save_backtest_settings(config_obj))
    config_obj.backtestLoadConfigurationButton.clicked.connect(lambda: load_backtest_settings(config_obj))
    config_obj.backtestImportDataButton.clicked.connect(lambda: import_data(config_obj, BACKTEST))
    config_obj.backtestDownloadDataButton.clicked.connect(lambda: download_data(config_obj, BACKTEST))
    config_obj.backtestStopDownloadButton.clicked.connect(lambda: stop_download(config_obj, BACKTEST))

    config_obj.optimizerImportDataButton.clicked.connect(lambda: import_data(config_obj, OPTIMIZER))
    config_obj.optimizerDownloadDataButton.clicked.connect(lambda: download_data(config_obj, OPTIMIZER))
    config_obj.optimizerStopDownloadButton.clicked.connect(lambda: stop_download(config_obj, OPTIMIZER))

    config_obj.testCredentialsButton.clicked.connect(lambda: test_binance_credentials(config_obj))
    config_obj.saveCredentialsButton.clicked.connect(lambda: save_credentials(config_obj))
    config_obj.loadCredentialsButton.clicked.connect(lambda: load_credentials(config_obj=config_obj, auto=False))

    config_obj.testTelegramButton.clicked.connect(lambda: test_telegram(config_obj))
    config_obj.telegramApiKey.textChanged.connect(lambda: reset_telegram_state(config_obj))
    config_obj.telegramChatID.textChanged.connect(lambda: reset_telegram_state(config_obj))

    config_obj.saveConfigurationButton.clicked.connect(lambda: save_live_settings(config_obj))
    config_obj.loadConfigurationButton.clicked.connect(lambda: load_live_settings(config_obj))
    config_obj.graphPlotSpeedSpinBox.valueChanged.connect(config_obj.update_graph_speed)
    config_obj.enableHoverLine.stateChanged.connect(config_obj.enable_disable_hover_line)

    load_interval_combo_boxes(config_obj)  # Primarily used for backtester/optimizer interval changer logic.
    load_loss_slots(config_obj)  # These slots are based on the ordering.
    load_take_profit_slots(config_obj)
    load_strategy_slots(config_obj)
