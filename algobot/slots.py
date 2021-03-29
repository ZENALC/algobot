import webbrowser

from algobot.enums import BACKTEST, LIVE, SIMULATION
from algobot.helpers import clear_table, open_folder
from algobot.themes import (set_bear_mode, set_bloomberg_mode, set_bull_mode,
                            set_dark_mode, set_light_mode)


def initiate_slots(app, gui):
    """
    Initiates all interface slots.
    """
    create_action_slots(gui)
    create_configuration_slots(app=app, gui=gui)
    create_interface_slots(gui)


def create_interface_slots(gui):
    """
    Creates interface slots.
    """
    create_bot_slots(gui)
    create_simulation_slots(gui)
    create_backtest_slots(gui)

    # Other buttons in interface.
    gui.refreshNewsButton.clicked.connect(gui.news_thread)


def create_configuration_slots(app, gui):
    """
    Creates configuration slots.
    """
    gui.configuration.lightModeRadioButton.toggled.connect(lambda: set_light_mode(app, gui))
    gui.configuration.darkModeRadioButton.toggled.connect(lambda: set_dark_mode(app, gui))
    gui.configuration.bloombergModeRadioButton.toggled.connect(lambda: set_bloomberg_mode(app, gui))
    gui.configuration.bullModeRadioButton.toggled.connect(lambda: set_bull_mode(app, gui))
    gui.configuration.bearModeRadioButton.toggled.connect(lambda: set_bear_mode(app, gui))
    gui.configuration.simpleLoggingRadioButton.clicked.connect(lambda: gui.set_advanced_logging(False))
    gui.configuration.advancedLoggingRadioButton.clicked.connect(lambda: gui.set_advanced_logging(True))

    gui.configuration.updateBinanceValues.clicked.connect(gui.update_binance_values)
    gui.configuration.updateTickers.clicked.connect(gui.tickers_thread)


def create_action_slots(gui):
    """
    Creates actions slots.
    """
    gui.otherCommandsAction.triggered.connect(lambda: gui.otherCommands.show())
    gui.configurationAction.triggered.connect(lambda: gui.configuration.show())
    gui.aboutAlgobotAction.triggered.connect(lambda: gui.about.show())
    gui.liveStatisticsAction.triggered.connect(lambda: gui.show_statistics(0))
    gui.simulationStatisticsAction.triggered.connect(lambda: gui.show_statistics(1))
    gui.openBacktestResultsFolderAction.triggered.connect(lambda: open_folder("Backtest Results"))
    gui.openLogFolderAction.triggered.connect(lambda: open_folder("Logs"))
    gui.openCsvFolderAction.triggered.connect(lambda: open_folder('CSV'))
    gui.openDatabasesFolderAction.triggered.connect(lambda: open_folder('Databases'))
    gui.openCredentialsFolderAction.triggered.connect(lambda: open_folder('Credentials'))
    gui.openConfigurationsFolderAction.triggered.connect(lambda: open_folder('Configuration'))
    gui.sourceCodeAction.triggered.connect(lambda: webbrowser.open("https://github.com/ZENALC/algobot"))
    gui.tradingViewLiveAction.triggered.connect(lambda: gui.open_trading_view(LIVE))
    gui.tradingViewSimulationAction.triggered.connect(lambda: gui.open_trading_view(SIMULATION))
    gui.tradingViewBacktestAction.triggered.connect(lambda: gui.open_trading_view(BACKTEST))
    gui.tradingViewHomepageAction.triggered.connect(lambda: gui.open_trading_view(None))
    gui.binanceHomepageAction.triggered.connect(lambda: gui.open_binance(None))
    gui.binanceLiveAction.triggered.connect(lambda: gui.open_binance(LIVE))
    gui.binanceSimulationAction.triggered.connect(lambda: gui.open_binance(SIMULATION))
    gui.binanceBacktestAction.triggered.connect(lambda: gui.open_binance(BACKTEST))


# noinspection DuplicatedCode
def create_simulation_slots(gui):
    """
    Creates simulation slots.
    """
    gui.runSimulationButton.clicked.connect(lambda: gui.initiate_bot_thread(caller=SIMULATION))
    gui.endSimulationButton.clicked.connect(lambda: gui.end_bot_thread(caller=SIMULATION))
    gui.configureSimulationButton.clicked.connect(gui.show_simulation_settings)
    gui.forceLongSimulationButton.clicked.connect(lambda: gui.force_long(SIMULATION))
    gui.forceShortSimulationButton.clicked.connect(lambda: gui.force_short(SIMULATION))
    gui.pauseBotSimulationButton.clicked.connect(lambda: gui.pause_or_resume_bot(SIMULATION))
    gui.exitPositionSimulationButton.clicked.connect(lambda: gui.exit_position(SIMULATION, True))
    gui.waitOverrideSimulationButton.clicked.connect(lambda: gui.exit_position(SIMULATION, False))
    gui.enableSimulationCustomStopLossButton.clicked.connect(lambda: gui.set_custom_stop_loss(SIMULATION, True))
    gui.disableSimulationCustomStopLossButton.clicked.connect(lambda: gui.set_custom_stop_loss(SIMULATION, False))
    gui.clearSimulationTableButton.clicked.connect(lambda: clear_table(gui.simulationActivityMonitor))
    gui.clearSimulationTradesButton.clicked.connect(lambda: clear_table(gui.simulationHistoryTable))
    gui.exportSimulationTradesButton.clicked.connect(lambda: gui.export_trades(caller=SIMULATION))
    gui.importSimulationTradesButton.clicked.connect(lambda: gui.import_trades(caller=SIMULATION))


# noinspection DuplicatedCode
def create_bot_slots(gui):
    """
    Creates bot slots.
    """
    gui.runBotButton.clicked.connect(lambda: gui.initiate_bot_thread(caller=LIVE))
    gui.endBotButton.clicked.connect(lambda: gui.end_bot_thread(caller=LIVE))
    gui.configureBotButton.clicked.connect(gui.show_main_settings)
    gui.forceLongButton.clicked.connect(lambda: gui.force_long(LIVE))
    gui.forceShortButton.clicked.connect(lambda: gui.force_short(LIVE))
    gui.pauseBotButton.clicked.connect(lambda: gui.pause_or_resume_bot(LIVE))
    gui.exitPositionButton.clicked.connect(lambda: gui.exit_position(LIVE, True))
    gui.waitOverrideButton.clicked.connect(lambda: gui.exit_position(LIVE, False))
    gui.enableCustomStopLossButton.clicked.connect(lambda: gui.set_custom_stop_loss(LIVE, True))
    gui.disableCustomStopLossButton.clicked.connect(lambda: gui.set_custom_stop_loss(LIVE, False))
    gui.clearTableButton.clicked.connect(lambda: clear_table(gui.activityMonitor))
    gui.clearLiveTradesButton.clicked.connect(lambda: clear_table(gui.historyTable))
    gui.exportLiveTradesButton.clicked.connect(lambda: gui.export_trades(caller=LIVE))
    gui.importLiveTradesButton.clicked.connect(lambda: gui.import_trades(caller=LIVE))


def create_backtest_slots(gui):
    """
    Creates backtest slots.
    """
    gui.configureBacktestButton.clicked.connect(gui.show_backtest_settings)
    gui.runBacktestButton.clicked.connect(gui.initiate_backtest)
    gui.endBacktestButton.clicked.connect(gui.end_backtest_thread)
    gui.clearBacktestTableButton.clicked.connect(lambda: clear_table(gui.backtestTable))
    gui.viewBacktestsButton.clicked.connect(lambda: open_folder("Backtest Results"))
    gui.backtestResetCursorButton.clicked.connect(gui.reset_backtest_cursor)
