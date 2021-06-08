from typing import Any, Dict

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from algobot.enums import OPTIMIZER
from algobot.interface.config_utils.calendar_utils import get_calendar_dates
from algobot.traders.backtester import Backtester


class OptimizerSignals(QObject):
    activity = pyqtSignal(tuple)
    error = pyqtSignal(str)
    restore = pyqtSignal()
    started = pyqtSignal()
    finished = pyqtSignal()


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
        startDate, endDate = get_calendar_dates(config_obj=config, caller=OPTIMIZER)

        return {
            'startingBalance': config.optimizerStartingBalanceSpinBox.value(),
            'data': config.optimizer_backtest_dict[OPTIMIZER]['data'],
            'startDate': startDate,
            'endDate': endDate,
            'symbol': config.optimizer_backtest_dict[OPTIMIZER]['dataType'],
            'precision': config.optimizerPrecisionSpinBox.value(),
            'marginEnabled': config.optimizerMarginTradingCheckBox.isChecked(),
            'strategies': [],
            'strategyInterval': config.optimizerStrategyIntervalCombobox.currentText(),
            'drawdownPercentage': config.drawdownPercentageSpinBox.value()
        }

    def setup(self):
        self.gui.optimizer = Backtester(**self.get_configuration_details())

    def stop(self):
        self.running = False

    def run_optimizer(self):
        optimizer = self.gui.optimizer
        optimizer.optimize(combos=self.combos, thread=self)
        self.running = False
        self.signals.finished.emit()

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
