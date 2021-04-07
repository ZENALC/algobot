from typing import Any, Dict

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from algobot.enums import OPTIMIZER
from algobot.traders.backtester import Backtester


class OptimizerSignals(QObject):
    activity = pyqtSignal(tuple)
    error = pyqtSignal(str)
    restore = pyqtSignal()
    started = pyqtSignal()


class OptimizerThread(QRunnable):
    def __init__(self, gui, logger, combos):
        super(OptimizerThread, self).__init__()
        self.signals = OptimizerSignals()
        self.combos = combos
        self.gui = gui
        self.logger = logger
        self.running = True
        self.caller = OPTIMIZER

    def get_configuration_details(self) -> Dict[str, Any]:
        """
        Returns configuration details from GUI in a dictionary to setup optimizer.
        :return: GUI configuration details in a dictionary.
        """
        config = self.gui.configuration
        startDate, endDate = config.get_calendar_dates(OPTIMIZER)

        return {
            'startingBalance': config.optimizerStartingBalanceSpinBox.value(),
            'data': config.optimizer_backtest_dict[OPTIMIZER]['data'],
            'startDate': startDate,
            'endDate': endDate,
            'dataType': config.optimizer_backtest_dict[OPTIMIZER]['dataType'],
            'precision': config.optimizerPrecisionSpinBox.value(),
            'outputTrades': config.optimizerOutputTradesCheckBox.isChecked(),
            'marginEnabled': config.optimizerMarginTradingCheckBox.isChecked(),
            'strategies': [],
            'strategyInterval': config.optimizerStrategyIntervalCombobox.currentText(),
        }

    def setup(self):
        configDetails = self.get_configuration_details()
        self.gui.optimizer = Backtester(startingBalance=configDetails['startingBalance'],
                                        data=configDetails['data'],
                                        symbol=configDetails['dataType'],
                                        marginEnabled=configDetails['marginEnabled'],
                                        startDate=configDetails['startDate'],
                                        endDate=configDetails['endDate'],
                                        precision=configDetails['precision'],
                                        outputTrades=configDetails['outputTrades'],
                                        strategies=configDetails['strategies'],
                                        strategyInterval=configDetails['strategyInterval'])

    def stop(self):
        self.running = False

    def run_optimizer(self):
        optimizer = self.gui.optimizer
        optimizer.optimize(combos=self.combos, thread=self)
        self.running = False

    @pyqtSlot()
    def run(self):
        try:
            self.setup()
            self.run_optimizer()
        except Exception as e:
            self.logger.exception(repr(e))
            self.signals.error.emit(str(e))
        finally:
            self.signals.restore.emit()
