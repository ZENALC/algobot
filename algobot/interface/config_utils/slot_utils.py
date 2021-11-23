"""
Slots helper functions for configuration.py can be found here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QScrollArea,
                             QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from algobot import helpers
from algobot.enums import BACKTEST, LIVE, OPTIMIZER, SIMULATION, TRENDS
from algobot.graph_helpers import get_and_set_line_color
from algobot.interface.config_utils.credential_utils import load_credentials, save_credentials, test_binance_credentials
from algobot.interface.config_utils.data_utils import download_data, import_data, stop_download
from algobot.interface.config_utils.strategy_utils import (add_strategy_buttons, create_strategy_inputs,
                                                           reset_strategy_interval_combo_box)
from algobot.interface.config_utils.telegram_utils import reset_telegram_state, test_telegram
from algobot.interface.config_utils.user_config_utils import (copy_config_helper, copy_settings_to_backtest,
                                                              copy_settings_to_simulation, load_backtest_settings,
                                                              load_config_helper, load_live_settings,
                                                              load_optimizer_settings, load_simulation_settings,
                                                              save_backtest_settings, save_config_helper,
                                                              save_live_settings, save_optimizer_settings,
                                                              save_simulation_settings)
from algobot.interface.configuration_helpers import (add_start_end_step_to_layout, create_inner_tab, get_default_widget,
                                                     get_regular_groupbox_and_layout)
from algobot.interface.utils import OPERATORS, PARAMETER_MAP, get_param_obj

if TYPE_CHECKING:
    from algobot.interface.configuration import Configuration


def load_loss_slots(config_obj: Configuration):
    """
    Loads slots for loss settings in GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    create_inner_tab(
        category_tabs=config_obj.category_tabs,
        description="Configure your stop loss settings here.",
        tab_name="Stop Loss",
        input_creator=config_obj.create_loss_inputs,
        dictionary=config_obj.loss_dict,
        signal_function=config_obj.update_loss_settings,
        parent=config_obj
    )


def load_take_profit_slots(config_obj: Configuration):
    """
    Loads slots for take profit settings in GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    create_inner_tab(
        category_tabs=config_obj.category_tabs,
        description="Configure your take profit settings here.",
        tab_name="Take Profit",
        input_creator=config_obj.create_take_profit_inputs,
        dictionary=config_obj.take_profit_dict,
        signal_function=config_obj.update_take_profit_settings,
        parent=config_obj
    )


def load_hide_show_strategies(config_obj: Configuration):
    """
    Load slots for hiding/showing strategies.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    def hide_strategies(box: QCheckBox, name: str):
        if box.isChecked():
            config_obj.hidden_strategies.remove(name)
        else:
            config_obj.hidden_strategies.add(name)

        delete_strategy_slots(config_obj)
        load_strategy_slots(config_obj)
        load_custom_strategy_slots(config_obj)

    c_boxes = []
    for strategy_name in [*config_obj.strategies.keys(), *config_obj.custom_strategies]:
        c_boxes.append(QCheckBox())

        # When restoring slots, if the strategy is not hidden, tick it.
        if strategy_name not in config_obj.hidden_strategies:
            c_boxes[-1].setChecked(True)

        # Lambdas don't retain values, so we must cache variable args to the lambda func.
        # pylint: disable=cell-var-from-loop
        c_boxes[-1].toggled.connect(lambda *_, a=c_boxes[-1], s=strategy_name: hide_strategies(a, s))
        config_obj.hideStrategiesFormLayout.addRow(strategy_name, c_boxes[-1])


def delete_strategy_slots(config_obj: Configuration):
    """
    Delete strategy slots.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config_obj.strategy_dict = {}  # Reset the dictionary.

    for index, tab in enumerate(config_obj.category_tabs):
        nuke_index = 3 if index < 2 else 4  # TODO: Refactor this. This is hard coded based on category tabs.
        for _ in range(tab.count() - nuke_index):
            tab.removeTab(nuke_index)


def populate_parameters(values: dict, indicator: dict, inner_tab_layout: QFormLayout):
    """
    Populate parameters.
    :param values: Values dictionary to populate.
    :param indicator: Indicator to populate parameters from.
    :param inner_tab_layout: Layout to add parameters to.
    """
    # We are just calling this to get a combo box for price types (high, low, etc), so default can just be ''.
    values['price'] = price_widget = get_param_obj(default_value='', param_name='price')
    inner_tab_layout.addRow(QLabel('Price Type'), price_widget)

    for parameter, default_value in indicator['parameters'].items():
        label = QLabel(PARAMETER_MAP.get(parameter, parameter))
        values[parameter] = widget = get_param_obj(default_value=default_value, param_name=parameter)
        inner_tab_layout.addRow(label, widget)

    values['output'] = output_combobox = QComboBox()
    output_combobox.addItems(indicator['output_names'])
    inner_tab_layout.addRow("Output Type", output_combobox)


def populate_custom_indicator(indicator: dict, inner_tab_layout: QFormLayout, values: dict):
    """
    Populate custom indicator fields.
    :param indicator: Indicator to populate values from.
    :param inner_tab_layout: Layout to add widgets to.
    :param values: Values to reference when executing bot. We'll populate this dictionary.
    """
    values['indicator'] = indicator['name']
    populate_parameters(values, indicator, inner_tab_layout)

    values['operator'] = operators_combobox = QComboBox()
    operators_combobox.addItems(OPERATORS)
    operators_combobox.setCurrentIndex(OPERATORS.index(indicator['operator']))
    inner_tab_layout.addRow('Operator', operators_combobox)

    against = indicator['against']
    if isinstance(against, (float, int)):
        inner_tab_layout.addWidget(QLabel('Against static value defined below:'))
        values['against'] = against_widget = get_default_widget(QDoubleSpinBox, against, -99999, 99999)
        inner_tab_layout.addWidget(against_widget)

    elif against == 'current_price':
        inner_tab_layout.addWidget(QLabel("Bot will execute against current price."))
        values['against'] = 'current_price'

    else:
        # It must be against another indicator then.
        inner_tab_layout.addWidget(QLabel(f"Bot will execute against: {against['name']}."))
        values['against'] = {'indicator': against['name']}
        populate_parameters(values['against'], indicator=against, inner_tab_layout=inner_tab_layout)


def load_custom_strategy_slots(config_obj: Configuration):
    """
    This will load all the necessary slots for custom strategy slots.
    :param config_obj: Configuration object to populate slots on.
    :return: None
    """
    # pylint: disable=too-many-locals
    for strategy in config_obj.json_strategies:

        strategy_description = strategy.get('description', "Custom Strategy")
        strategy_name = strategy['name']

        if strategy_name in config_obj.hidden_strategies:  # Don't re-render hidden strategies.
            continue

        for tab in config_obj.category_tabs:
            tab_widget = QTabWidget()
            description_label = QLabel(f'Strategy description: {strategy_description}')
            description_label.setWordWrap(True)

            # This is the outer tab widget.
            main_tabs_widget = QTabWidget()

            group_box, group_box_layout = get_regular_groupbox_and_layout(f"Enable {strategy_name}?")
            group_box_layout.addRow(main_tabs_widget)

            config_obj.strategy_dict[tab, strategy_name, 'groupBox'] = group_box
            config_obj.strategy_dict[tab, strategy_name] = {'name': strategy_name}

            scroll = QScrollArea()  # Added a scroll area so user can scroll when additional slots are added.
            scroll.setWidgetResizable(True)
            scroll.setWidget(group_box)

            layout = QVBoxLayout()
            layout.addWidget(description_label)
            layout.addWidget(scroll)

            for trend, trend_items in strategy.items():
                # The key (trend) can be another key such as description or name. So we first ensure it's a valid trend
                #  by checking against the tab.
                if trend not in TRENDS:
                    continue

                # For each trend, we must now set the appropriate dictionary containing the widgets.
                config_obj.strategy_dict[tab, strategy_name][trend] = {}

                trend_tab, trend_tab_layout = QWidget(), QFormLayout()
                trend_tab.setLayout(trend_tab_layout)
                main_tabs_widget.addTab(trend_tab, trend)

                if len(trend_items) == 0:
                    trend_tab_layout.addRow(QLabel("No indicators found."))
                    continue

                # For each indicator inside a trend, we must place it inside a new tab.
                trend_tab_widget = QTabWidget()
                trend_tab_layout.addWidget(trend_tab_widget)

                for uuid, indicator in trend_items.items():

                    indicator_tab, indicator_tab_layout = QWidget(), QFormLayout()
                    indicator_tab.setLayout(indicator_tab_layout)
                    trend_tab_widget.addTab(indicator_tab, indicator['name'])

                    values = {}
                    populate_custom_indicator(
                        indicator=indicator,
                        inner_tab_layout=indicator_tab_layout,
                        values=values
                    )

                    config_obj.strategy_dict[tab, strategy_name][trend][uuid] = values

            tab_widget.setLayout(layout)
            tab.addTab(tab_widget, strategy_name)

            # For now, disable optimizers. TODO: add support.
            if tab is config_obj.category_tabs[-1]:
                group_box.setEnabled(False)
                layout.addWidget(QLabel("Warning: Optimizers are currently not supported for custom strategies."))


def load_strategy_slots(config_obj: Configuration):
    """
    This will initialize all the necessary strategy slots and add them to the configuration GUI. All the strategies
    are loaded from the config_obj.strategies dictionary.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :return: None
    """
    # TODO: Refactor to remove pylint disable below.
    # pylint: disable=too-many-locals, too-many-statements, too-many-nested-blocks
    for strategy_key_name, strategy in config_obj.strategies.items():
        if strategy_key_name in config_obj.hidden_strategies:  # Don't re-render hidden strategies.
            continue

        temp = strategy()
        strategy_name = temp.name
        parameters = temp.get_param_types()
        for tab in config_obj.category_tabs:
            config_obj.strategy_dict[tab, strategy_name] = tab_widget = QTabWidget()
            description_label = QLabel(f'Strategy description: {temp.description}')
            description_label.setWordWrap(True)

            layout = QVBoxLayout()
            layout.addWidget(description_label)

            scroll = QScrollArea()  # Added a scroll area so user can scroll when additional slots are added.
            scroll.setWidgetResizable(True)

            if config_obj.get_caller_based_on_tab(tab) == OPTIMIZER:
                group_box, group_box_layout = get_regular_groupbox_and_layout(f'Enable {strategy_name} optimization?')
                config_obj.strategy_dict[tab, strategy_name] = group_box
                for index, parameter in enumerate(parameters, start=1):
                    # TODO: Refactor this logic.
                    if not isinstance(parameter, tuple) or \
                            isinstance(parameter, tuple) and parameter[1] in [int, float]:
                        if isinstance(parameter, tuple):
                            widget = QSpinBox if parameter[1] == int else QDoubleSpinBox
                            step_val = 1 if widget == QSpinBox else 0.1
                        else:
                            widget = QSpinBox if parameter == int else QDoubleSpinBox
                            step_val = 1 if widget == QSpinBox else 0.1
                        config_obj.strategy_dict[strategy_name, index, 'start'] = start = get_default_widget(widget, 1)
                        config_obj.strategy_dict[strategy_name, index, 'end'] = end = get_default_widget(widget, 1)
                        config_obj.strategy_dict[strategy_name, index, 'step'] = step = get_default_widget(widget,
                                                                                                           step_val)
                        if isinstance(parameter, tuple):
                            message = parameter[0]
                        else:
                            message = f"{strategy_name} {index}"
                        add_start_end_step_to_layout(group_box_layout, message, start, end, step)
                    elif isinstance(parameter, tuple) and parameter[1] == tuple:
                        group_box_layout.addRow(QLabel(parameter[0]))
                        for option in parameter[2]:
                            config_obj.strategy_dict[strategy_name, option] = check_box = QCheckBox(option)
                            group_box_layout.addRow(check_box)
                    else:
                        raise ValueError("Invalid type of parameter type provided.")
            else:
                group_box, group_box_layout = get_regular_groupbox_and_layout(f"Enable {strategy_name}?")
                config_obj.strategy_dict[tab, strategy_name, 'groupBox'] = group_box

                status = QLabel()
                if temp.dynamic:
                    add_button, delete_button = add_strategy_buttons(config_obj.strategy_dict, parameters,
                                                                     strategy_name, group_box_layout, tab)
                    horizontal_layout = QHBoxLayout()
                    horizontal_layout.addWidget(add_button)
                    horizontal_layout.addWidget(delete_button)
                    horizontal_layout.addWidget(status)
                    horizontal_layout.addStretch()
                    layout.addLayout(horizontal_layout)

                values, labels = create_strategy_inputs(parameters, strategy_name, group_box_layout)
                config_obj.strategy_dict[tab, strategy_name, 'values'] = values
                config_obj.strategy_dict[tab, strategy_name, 'labels'] = labels
                config_obj.strategy_dict[tab, strategy_name, 'parameters'] = parameters
                config_obj.strategy_dict[tab, strategy_name, 'layout'] = group_box_layout
                config_obj.strategy_dict[tab, strategy_name, 'status'] = status

            layout.addWidget(scroll)
            scroll.setWidget(group_box)
            tab_widget.setLayout(layout)
            tab.addTab(tab_widget, strategy_name)


def load_precision_combo_boxes(config_obj: Configuration):
    """
    Load precision combo boxes on the config object provided.
    :param config_obj: Configuration object to load precision combo boxes on.
    """
    combo_boxes = [config_obj.precisionComboBox, config_obj.simulationPrecisionComboBox,
                   config_obj.backtestPrecisionComboBox, config_obj.optimizerPrecisionComboBox]
    precisions = ["Auto"] + [str(x) for x in range(2, 16)]
    for combo_box in combo_boxes:
        combo_box.addItems(precisions)


def load_interval_combo_boxes(config_obj: Configuration):
    """
    This function currently only handles combo boxes for backtester/optimizer interval logic. It'll update the
    strategy interval combo-box depending on what the data interval combo-box has as its current value.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    intervals = helpers.get_interval_strings(starting_index=0)

    config_obj.intervalComboBox.addItems(intervals)
    config_obj.simulationIntervalComboBox.addItems(intervals)

    config_obj.backtestStrategyIntervalCombobox.addItems(intervals)
    config_obj.backtestIntervalComboBox.addItems(intervals)
    config_obj.backtestIntervalComboBox.currentTextChanged.connect(lambda: reset_strategy_interval_combo_box(
        strategy_combobox=config_obj.backtestStrategyIntervalCombobox,
        interval_combobox=config_obj.backtestIntervalComboBox
    ))

    config_obj.optimizerStrategyIntervalCombobox.addItems(intervals)
    config_obj.optimizerIntervalComboBox.addItems(intervals)
    config_obj.optimizerStrategyIntervalEndCombobox.addItems(intervals)

    config_obj.optimizerIntervalComboBox.currentTextChanged.connect(lambda: reset_strategy_interval_combo_box(
        strategy_combobox=config_obj.optimizerStrategyIntervalCombobox,
        interval_combobox=config_obj.optimizerIntervalComboBox
    ))

    config_obj.optimizerStrategyIntervalCombobox.currentTextChanged.connect(lambda: reset_strategy_interval_combo_box(
        strategy_combobox=config_obj.optimizerStrategyIntervalEndCombobox,
        interval_combobox=config_obj.optimizerStrategyIntervalCombobox,
        start_index=config_obj.optimizerIntervalComboBox.currentIndex(),
        divisor=helpers.get_interval_minutes(config_obj.optimizerIntervalComboBox.currentText())
    ))


def load_slots(config_obj: Configuration):
    """
    Loads all configuration interface slots.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :return: None
    """
    c = config_obj  # pylint: disable=invalid-name

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
    c.setHoverLineColorButton.clicked.connect(lambda: get_and_set_line_color(c, c.hoverLineColor))

    c.testCredentialsButton.clicked.connect(lambda: test_binance_credentials(c))
    c.saveCredentialsButton.clicked.connect(lambda: save_credentials(c))
    c.loadCredentialsButton.clicked.connect(lambda: load_credentials(config_obj=c, auto=False))

    c.testTelegramButton.clicked.connect(lambda: test_telegram(c))
    c.telegramApiKey.textChanged.connect(lambda: reset_telegram_state(c))
    c.telegramChatID.textChanged.connect(lambda: reset_telegram_state(c))
    c.graphPlotSpeedSpinBox.valueChanged.connect(c.update_graph_speed)
    c.enableHoverLine.stateChanged.connect(c.enable_disable_hover_line)

    load_precision_combo_boxes(c)
    load_interval_combo_boxes(c)  # Primarily used for backtester/optimizer interval changer logic.
    load_loss_slots(c)  # These slots are based on the ordering.
    load_take_profit_slots(c)
    load_strategy_slots(c)
    load_custom_strategy_slots(c)
