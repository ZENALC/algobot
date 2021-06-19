"""
Slots helper functions for configuration.py can be found here.
"""
from PyQt5.QtWidgets import (QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                             QScrollArea, QSpinBox, QTabWidget, QVBoxLayout)

from algobot import helpers
from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION
from algobot.graph_helpers import get_and_set_line_color
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
    copy_config_helper, copy_settings_to_backtest, copy_settings_to_simulation,
    load_backtest_settings, load_config_helper, load_live_settings,
    load_optimizer_settings, load_simulation_settings, save_backtest_settings,
    save_config_helper, save_live_settings, save_optimizer_settings,
    save_simulation_settings)
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

    config_obj.intervalComboBox.addItems(intervals)
    config_obj.simulationIntervalComboBox.addItems(intervals)

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
    c = config_obj

    c.saveConfigurationButton.clicked.connect(lambda: save_config_helper(
        config_obj=c, caller=LIVE, result_label=c.configurationResult, func=save_live_settings))
    c.loadConfigurationButton.clicked.connect(lambda: load_config_helper(
        config_obj=c, caller=LIVE, result_label=c.configurationResult, func=load_live_settings))

    c.simulationCopySettingsButton.clicked.connect(lambda: copy_config_helper(
        config_obj=c, caller=SIMULATION, result_label=c.simulationCopyLabel, func=copy_settings_to_simulation))
    c.simulationSaveConfigurationButton.clicked.connect(lambda: save_config_helper(
        config_obj=c, caller=SIMULATION, result_label=c.simulationConfigurationResult, func=save_simulation_settings))
    c.simulationLoadConfigurationButton.clicked.connect(lambda: load_config_helper(
        config_obj=c, caller=SIMULATION, result_label=c.simulationConfigurationResult, func=load_simulation_settings))

    c.backtestImportDataButton.clicked.connect(lambda: import_data(c, BACKTEST))
    c.backtestDownloadDataButton.clicked.connect(lambda: download_data(c, BACKTEST))
    c.backtestStopDownloadButton.clicked.connect(lambda: stop_download(c, BACKTEST))
    c.backtestCopySettingsButton.clicked.connect(lambda: copy_config_helper(
        config_obj=c, caller=BACKTEST, result_label=c.backtestCopyLabel, func=copy_settings_to_backtest))
    c.backtestSaveConfigurationButton.clicked.connect(lambda: save_config_helper(
        config_obj=c, caller=BACKTEST, result_label=c.backtestConfigurationResult, func=save_backtest_settings))
    c.backtestLoadConfigurationButton.clicked.connect(lambda: load_config_helper(
        config_obj=c, caller=BACKTEST, result_label=c.backtestConfigurationResult, func=load_backtest_settings))

    c.optimizerImportDataButton.clicked.connect(lambda: import_data(c, OPTIMIZER))
    c.optimizerDownloadDataButton.clicked.connect(lambda: download_data(c, OPTIMIZER))
    c.optimizerStopDownloadButton.clicked.connect(lambda: stop_download(c, OPTIMIZER))
    c.optimizerSaveConfigurationButton.clicked.connect(lambda: save_config_helper(
        config_obj=c, caller=OPTIMIZER, result_label=c.optimizerConfigurationResult, func=save_optimizer_settings))
    c.optimizerLoadConfigurationButton.clicked.connect(lambda: load_config_helper(
        config_obj=c, caller=OPTIMIZER, result_label=c.optimizerConfigurationResult, func=load_optimizer_settings))

    c.setBalanceColorButton.clicked.connect(lambda: get_and_set_line_color(c, c.balanceColor))
    c.setMovingAverage1ColorButton.clicked.connect(lambda: get_and_set_line_color(c, c.movingAverage1Color))
    c.setMovingAverage2ColorButton.clicked.connect(lambda: get_and_set_line_color(c, c.movingAverage2Color))
    c.setMovingAverage3ColorButton.clicked.connect(lambda: get_and_set_line_color(c, c.movingAverage3Color))
    c.setMovingAverage4ColorButton.clicked.connect(lambda: get_and_set_line_color(c, c.movingAverage4Color))
    c.setHoverLineColorButton.clicked.connect(lambda: get_and_set_line_color(c, c.hoverLineColor))

    c.testCredentialsButton.clicked.connect(lambda: test_binance_credentials(c))
    c.saveCredentialsButton.clicked.connect(lambda: save_credentials(c))
    c.loadCredentialsButton.clicked.connect(lambda: load_credentials(config_obj=c, auto=False))

    c.testTelegramButton.clicked.connect(lambda: test_telegram(c))
    c.telegramApiKey.textChanged.connect(lambda: reset_telegram_state(c))
    c.telegramChatID.textChanged.connect(lambda: reset_telegram_state(c))
    c.graphPlotSpeedSpinBox.valueChanged.connect(c.update_graph_speed)
    c.enableHoverLine.stateChanged.connect(c.enable_disable_hover_line)

    load_interval_combo_boxes(c)  # Primarily used for backtester/optimizer interval changer logic.
    load_loss_slots(c)  # These slots are based on the ordering.
    load_take_profit_slots(c)
    load_strategy_slots(c)
