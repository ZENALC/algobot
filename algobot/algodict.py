from enums import SIMULATION, BACKTEST, LIVE


# noinspection DuplicatedCode
def get_interface_dictionary(parent, caller: int = None):
    """
    Returns dictionary of objects from QT. Used for DRY principles.
    :param parent: Parent object from which to retrieve objects.
    :param caller: Caller that will determine which sub dictionary gets returned.
    :return: Dictionary of objects.
    """
    interfaceDictionary = {
        SIMULATION: {
            'mainInterface': {
                # Portfolio
                'profitLabel': parent.simulationProfitLabel,
                'profitValue': parent.simulationProfitValue,
                'percentageValue': parent.simulationPercentageValue,
                'netTotalValue': parent.simulationNetTotalValue,
                'tickerLabel': parent.simulationTickerLabel,
                'tickerValue': parent.simulationTickerValue,
                'customStopLossValue': parent.customSimulationStopLossValue,
                'positionValue': parent.simulationPositionValue,
                # Buttons
                'pauseBotButton': parent.pauseBotSimulationButton,
                'runBotButton': parent.runSimulationButton,
                'endBotButton': parent.endSimulationButton,
                'forceShortButton': parent.forceShortSimulationButton,
                'forceLongButton': parent.forceLongSimulationButton,
                'exitPositionButton': parent.exitPositionSimulationButton,
                'waitOverrideButton': parent.waitOverrideSimulationButton,
                'enableCustomStopLossButton': parent.enableSimulationCustomStopLossButton,
                'disableCustomStopLossButton': parent.disableSimulationCustomStopLossButton,
                # Groupboxes
                'overrideGroupBox': parent.simulationOverrideGroupBox,
                'customStopLossGroupBox': parent.customSimulationStopLossGroupBox,
                # Graphs
                'graph': parent.simulationGraph,
                'averageGraph': parent.simulationAvgGraph,
                # Table
                'historyTable': parent.simulationHistoryTable,
                'activityTable': parent.simulationActivityMonitor,
                'historyLabel': parent.simulationTradesHistoryLabel,
            },
            'configuration': {
                'mainTab': parent.configuration.simulationMainTab,
                'lossTab': parent.configuration.simulationLossTab,
                'trailingLossRadio': parent.configuration.simulationTrailingLossRadio,
                'lossPercentage': parent.configuration.simulationLossPercentageSpinBox,
                'mainConfigurationTabWidget': parent.configuration.simulationConfigurationTabWidget,
                'ticker': parent.configuration.simulationTickerComboBox,
                'interval': parent.configuration.simulationIntervalComboBox,
                'lowerIntervalCheck': parent.configuration.lowerIntervalSimulationCheck,
                'smartStopLossCounter': parent.configuration.simulationSmartStopLossSpinBox,
                'safetyTimer': parent.configuration.simulationSafetyTimerSpinBox,
                'precision': parent.configuration.simulationPrecisionSpinBox,
            }
        },
        LIVE: {
            'mainInterface': {
                # Portfolio
                'profitLabel': parent.profitLabel,
                'profitValue': parent.profitValue,
                'percentageValue': parent.percentageValue,
                'netTotalValue': parent.netTotalValue,
                'tickerLabel': parent.tickerLabel,
                'tickerValue': parent.tickerValue,
                'customStopLossValue': parent.customStopLossValue,
                'positionValue': parent.positionValue,
                # Buttons
                'pauseBotButton': parent.pauseBotButton,
                'runBotButton': parent.runBotButton,
                'endBotButton': parent.endBotButton,
                'forceShortButton': parent.forceShortButton,
                'forceLongButton': parent.forceLongButton,
                'exitPositionButton': parent.exitPositionButton,
                'waitOverrideButton': parent.waitOverrideButton,
                'enableCustomStopLossButton': parent.enableCustomStopLossButton,
                'disableCustomStopLossButton': parent.disableCustomStopLossButton,
                # Groupboxes
                'overrideGroupBox': parent.overrideGroupBox,
                'customStopLossGroupBox': parent.customStopLossGroupBox,
                # Graphs
                'graph': parent.liveGraph,
                'averageGraph': parent.avgGraph,
                # Table
                'historyTable': parent.historyTable,
                'activityTable': parent.activityMonitor,
                'historyLabel': parent.liveTradesHistoryLabel,
            },
            'configuration': {
                'mainTab': parent.configuration.mainMainTab,
                'lossTab': parent.configuration.mainLossTab,
                'trailingLossRadio': parent.configuration.trailingLossRadio,
                'lossPercentage': parent.configuration.lossPercentageSpinBox,
                'mainConfigurationTabWidget': parent.configuration.mainConfigurationTabWidget,
                'ticker': parent.configuration.tickerComboBox,
                'interval': parent.configuration.intervalComboBox,
                'lowerIntervalCheck': parent.configuration.lowerIntervalCheck,
                'smartStopLossCounter': parent.configuration.smartStopLossSpinBox,
                'safetyTimer': parent.configuration.safetyTimerSpinBox,
                'precision': parent.configuration.precisionSpinBox,
            }
        },
        BACKTEST: {
            'configuration': {
                'mainTab': parent.configuration.backtestMainTab,
                'lossTab': parent.configuration.backtestLossTab,
                'trailingLossRadio': parent.configuration.backtestTrailingLossRadio,
                'lossPercentage': parent.configuration.backtestLossPercentageSpinBox,
                'mainConfigurationTabWidget': parent.configuration.backtestConfigurationTabWidget,
                'smartStopLossCounter': parent.configuration.backtestSmartStopLossSpinBox,
                'precision': parent.configuration.backtestPrecisionSpinBox,
            },
            'mainInterface': {
                'runBotButton': parent.runBacktestButton,
                'endBotButton': parent.endBacktestButton,
                # Graphs
                'graph': parent.backtestGraph,
                # Table
                'historyTable': parent.backtestTable,
            }
        }
    }
    if caller is not None:
        return interfaceDictionary[caller]
    return interfaceDictionary
