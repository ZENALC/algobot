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
            },
            'configuration': {
                'mainTab': parent.configuration.simulationMainTab,
                'averageTab': parent.configuration.simulationAverageTab,
                'lossTab': parent.configuration.simulationLossTab,
                'baseAverageType': parent.configuration.simulationAverageTypeComboBox,
                'baseParameter': parent.configuration.simulationParameterComboBox,
                'baseInitialValue': parent.configuration.simulationInitialValueSpinBox,
                'baseFinalValue': parent.configuration.simulationFinalValueSpinBox,
                'doubleCrossCheck': parent.configuration.simulationDoubleCrossCheckMark,
                'additionalAverageType': parent.configuration.simulationDoubleAverageComboBox,
                'additionalParameter': parent.configuration.simulationDoubleParameterComboBox,
                'additionalInitialValue': parent.configuration.simulationDoubleInitialValueSpinBox,
                'additionalFinalValue': parent.configuration.simulationDoubleFinalValueSpinBox,
                'trailingLossRadio': parent.configuration.simulationTrailingLossRadio,
                'lossPercentage': parent.configuration.simulationLossPercentageSpinBox,
                'mainConfigurationTabWidget': parent.configuration.simulationConfigurationTabWidget,
                'ticker': parent.configuration.simulationTickerComboBox,
                'interval': parent.configuration.simulationIntervalComboBox,
                'lowerIntervalCheck': parent.configuration.lowerIntervalSimulationCheck,
                'stoicCheck': parent.configuration.simulationStoicCheckMark,
                'stoicInput1': parent.configuration.simulationStoicSpinBox1,
                'stoicInput2': parent.configuration.simulationStoicSpinBox2,
                'stoicInput3': parent.configuration.simulationStoicSpinBox3,
                'smartStopLossCounter': parent.configuration.simulationSmartStopLossSpinBox,
                'shrekCheck': parent.configuration.simulationShrekCheckMark,
                'shrekInput1': parent.configuration.simulationShrekSpinBox1,
                'shrekInput2': parent.configuration.simulationShrekSpinBox2,
                'shrekInput3': parent.configuration.simulationShrekSpinBox3,
                'shrekInput4': parent.configuration.simulationShrekSpinBox4,
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
            },
            'configuration': {
                'mainTab': parent.configuration.mainMainTab,
                'averageTab': parent.configuration.mainAverageTab,
                'lossTab': parent.configuration.mainLossTab,
                'baseAverageType': parent.configuration.averageTypeComboBox,
                'baseParameter': parent.configuration.parameterComboBox,
                'baseInitialValue': parent.configuration.initialValueSpinBox,
                'baseFinalValue': parent.configuration.finalValueSpinBox,
                'doubleCrossCheck': parent.configuration.doubleCrossCheckMark,
                'additionalAverageType': parent.configuration.doubleAverageComboBox,
                'additionalParameter': parent.configuration.doubleParameterComboBox,
                'additionalInitialValue': parent.configuration.doubleInitialValueSpinBox,
                'additionalFinalValue': parent.configuration.doubleFinalValueSpinBox,
                'trailingLossRadio': parent.configuration.trailingLossRadio,
                'lossPercentage': parent.configuration.lossPercentageSpinBox,
                'mainConfigurationTabWidget': parent.configuration.mainConfigurationTabWidget,
                'ticker': parent.configuration.tickerComboBox,
                'interval': parent.configuration.intervalComboBox,
                'lowerIntervalCheck': parent.configuration.lowerIntervalCheck,
                'stoicCheck': parent.configuration.stoicCheckMark,
                'stoicInput1': parent.configuration.stoicSpinBox1,
                'stoicInput2': parent.configuration.stoicSpinBox2,
                'stoicInput3': parent.configuration.stoicSpinBox3,
                'smartStopLossCounter': parent.configuration.smartStopLossSpinBox,
                'shrekCheck': parent.configuration.shrekCheckMark,
                'shrekInput1': parent.configuration.shrekSpinBox1,
                'shrekInput2': parent.configuration.shrekSpinBox2,
                'shrekInput3': parent.configuration.shrekSpinBox3,
                'shrekInput4': parent.configuration.shrekSpinBox4,
                'safetyTimer': parent.configuration.safetyTimerSpinBox,
                'precision': parent.configuration.precisionSpinBox,
            }
        },
        BACKTEST: {
            'configuration': {
                'mainTab': parent.configuration.backtestMainTab,
                'averageTab': parent.configuration.backtestAverageTab,
                'lossTab': parent.configuration.backtestLossTab,
                'baseAverageType': parent.configuration.backtestAverageTypeComboBox,
                'baseParameter': parent.configuration.backtestParameterComboBox,
                'baseInitialValue': parent.configuration.backtestInitialValueSpinBox,
                'baseFinalValue': parent.configuration.backtestFinalValueSpinBox,
                'doubleCrossCheck': parent.configuration.backtestDoubleCrossCheckMark,
                'additionalAverageType': parent.configuration.backtestDoubleAverageComboBox,
                'additionalParameter': parent.configuration.backtestDoubleParameterComboBox,
                'additionalInitialValue': parent.configuration.backtestDoubleInitialValueSpinBox,
                'additionalFinalValue': parent.configuration.backtestDoubleFinalValueSpinBox,
                'trailingLossRadio': parent.configuration.backtestTrailingLossRadio,
                'lossPercentage': parent.configuration.backtestLossPercentageSpinBox,
                'mainConfigurationTabWidget': parent.configuration.backtestConfigurationTabWidget,
                'smartStopLossCounter': parent.configuration.backtestSmartStopLossSpinBox,
                'shrekInput1': parent.configuration.backtestShrekSpinBox1,
                'shrekInput2': parent.configuration.backtestShrekSpinBox2,
                'shrekInput3': parent.configuration.backtestShrekSpinBox3,
                'shrekInput4': parent.configuration.backtestShrekSpinBox4,
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
