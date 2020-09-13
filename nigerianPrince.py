import sys
import traceback

from trader import SimulatedTrader, Option, Data
from helpers import *

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSlot

app = QApplication(sys.argv)
uiFile = 'nigerianPrince.ui'


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """

        # Retrieve args/kwargs here; and fire processing using them
        try:
            self.fn(*self.args, **self.kwargs)
        except Exception as e:
            print(f'Error: {e}')
            traceback.print_exc()


class Interface(QMainWindow):
    def __init__(self, parent=None):
        super(Interface, self).__init__(parent)  # Initializing object
        uic.loadUi(uiFile, self)  # Loading the UI
        self.threadPool = QThreadPool()

        self.doubleCrossCheckMark.toggled.connect(self.interact_double_cross)
        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)
        self.runSimulationButton.clicked.connect(self.initiate_simulation_thread)
        self.endSimulationButton.clicked.connect(self.end_simulation)
        self.forceLongButton.clicked.connect(self.force_long)
        self.forceShortButton.clicked.connect(self.force_short)
        self.pauseBotButton.clicked.connect(self.pause_bot)
        self.exitPositionButton.clicked.connect(self.exit_position)

        self.movingAverageMiscellaneousParameter.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousType.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousValue.valueChanged.connect(self.initiate_misc_get_moving_average)

        self.trader = None
        self.runningLive = False
        self.liveThread = None

        self.timestamp_message('Greetings.')

    def initiate_misc_get_moving_average(self):
        thread = Worker(self.get_moving_average_miscellaneous)
        self.threadPool.start(thread)

    def get_moving_average_miscellaneous(self):
        self.movingAverageMiscellaneousResult.setText("haha what did you expect?")

    def enable_override(self):
        self.overrideGroupBox.setEnabled(True)
        self.forceLongButton.setEnabled(True)
        self.forceShortButton.setEnabled(True)

    def disable_override(self):
        self.overrideGroupBox.setEnabled(False)

    def exit_position(self):
        if self.trader.get_position() == 'Long':
            self.timestamp_message('Force exiting long.')
            self.trader.sell_long('Force exiting long.')
        elif self.trader.get_position() == 'Short':
            self.timestamp_message('Force exiting short.')
            self.trader.buy_short('Force exiting short.')

        self.forceShortButton.setEnabled(True)
        self.forceLongButton.setEnabled(True)
        self.exitPositionButton.setEnabled(False)

    def force_long(self):
        self.timestamp_message('Forcing long.')
        if self.trader.get_position() == "Short":
            self.trader.buy_short('Exiting short because long was forced.')

        self.trader.buy_long('Forcing long.')
        self.forceShortButton.setEnabled(False)
        self.forceLongButton.setEnabled(False)
        self.exitPositionButton.setEnabled(True)

    def force_short(self):
        self.timestamp_message('Forcing short.')
        if self.trader.get_position() == "Long":
            self.trader.sell_long('Exiting long because short was forced.')

        self.trader.sell_short('Forcing short.')
        self.forceShortButton.setEnabled(False)
        self.forceLongButton.setEnabled(True)
        self.exitPositionButton.setEnabled(True)

    def pause_bot(self):
        pass

    def get_trading_options(self):
        baseAverageType = self.averageTypeComboBox.currentText()
        baseParameter = self.parameterComboBox.currentText().lower()
        baseInitialValue = self.initialValueSpinBox.value()
        baseFinalValue = self.finalValueSpinBox.value()

        options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]
        if self.doubleCrossCheckMark.isChecked():
            additionalAverageType = self.doubleAverageComboBox.currentText()
            additionalParameter = self.doubleParameterComboBox.currentText().lower()
            additionalInitialValue = self.doubleInitialValueSpinBox.value()
            additionalFinalValue = self.doubleFinalValueSpinBox.value()
            option = Option(additionalAverageType, additionalParameter, additionalInitialValue, additionalFinalValue)
            options.append(option)

        return options

    def get_loss_strategy(self):
        if self.trailingLossRadio.isChecked():
            return 2
        else:
            return 1

    def create_simulation_trader(self):
        symbol = self.tickerComboBox.currentText()
        interval = self.convert_interval(self.intervalComboBox.currentText())
        startingBalance = self.simulationStartingBalanceSpinBox.value()
        self.timestamp_message("Retrieving data...")
        self.trader = SimulatedTrader(startingBalance=startingBalance,
                                      symbol=symbol,
                                      interval=interval, loadData=True)

        # self.trader.dataView.get_data_from_database()
        # if not self.trader.dataView.database_is_updated():
        #     self.timestamp_message("Updating data...")
        #     self.trader.dataView.update_database()
        # else:
        #     self.timestamp_message("Data is up-to-date.")

    def reset_trader(self):
        self.trader.trades = []
        self.trader.sellShortPrice = None
        self.trader.buyLongPrice = None
        self.trader.shortTrailingPrice = None
        self.trader.longTrailingPrice = None
        self.trader.startingBalance = self.trader.balance
        self.trader.startingTime = datetime.now()

    def set_parameters(self):
        self.trader.lossPercentage = self.lossPercentageSpinBox.value()
        self.trader.lossStrategy = self.get_loss_strategy()
        self.trader.safetyTimer = self.sleepTimerSpinBox.value()
        self.trader.safetyMargin = self.marginSpinBox.value()

    def display_trade_options(self):
        for option in self.trader.tradingOptions:
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.timestamp_message(f'Parameter: {option.parameter}')
            self.timestamp_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
            self.timestamp_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')

    def initiate_simulation_thread(self):
        self.liveThread = Worker(self.run_simulation)
        self.threadPool.start(self.liveThread)

    def run_simulation(self):
        self.timestamp_message('Starting simulation...')
        self.endSimulationButton.setEnabled(True)
        self.grey_out_main_options(True)
        self.create_simulation_trader()
        self.reset_trader()
        self.set_parameters()
        self.trader.tradingOptions = self.get_trading_options()
        self.runningLive = True
        self.enable_override()
        self.tradesListWidget.clear()
        crossInform = False

        while self.runningLive:
            if not self.trader.dataView.data_is_updated():
                self.timestamp_message("Updating data...")
                self.trader.dataView.update_data()

            if self.trader.get_position() is not None:
                crossInform = False

            if not crossInform and self.trader.get_position() is None:
                crossInform = True
                self.timestamp_message("Waiting for a cross.")

            self.update_info()
            self.update_trades_to_list_view()

            self.trader.currentPrice = self.trader.dataView.get_current_price()
            if self.trader.longTrailingPrice is not None and self.trader.currentPrice > self.trader.longTrailingPrice:
                self.trader.longTrailingPrice = self.trader.currentPrice
            if self.trader.shortTrailingPrice is not None and self.trader.currentPrice < self.trader.shortTrailingPrice:
                self.trader.shortTrailingPrice = self.trader.currentPrice

            if not self.trader.inHumanControl:
                self.trader.main_logic()

            if self.trader.get_position() is None:
                self.exitPositionButton.setEnabled(False)

            if self.trader.get_position() == 'Long':
                self.forceLongButton.setEnabled(False)
                self.forceShortButton.setEnabled(True)

            if self.trader.get_position() == "Short":
                self.forceLongButton.setEnabled(True)
                self.forceShortButton.setEnabled(False)

    def grey_out_main_options(self, boolean):
        boolean = not boolean
        self.mainOptionsGroupBox.setEnabled(boolean)
        self.averageOptionsGroupBox.setEnabled(boolean)
        self.lossOptionsGroupBox.setEnabled(boolean)
        self.otherOptionsBox.setEnabled(boolean)
        self.runSimulationButton.setEnabled(boolean)

    def destroy_simulation_trader(self):
        self.trader = None

    def end_simulation(self):
        self.timestamp_message("Ending simulation...\n\n")
        self.disable_override()
        self.endSimulationButton.setEnabled(False)
        self.runningLive = False
        self.grey_out_main_options(False)

    @staticmethod
    def convert_interval(interval):
        intervals = {
            '12 Hours': '12h',
            '15 Minutes': '15m',
            '1 Day': '1d',
            '1 Hour': '1h',
            '1 Minute': '1m',
            '2 Hours': '2h',
            '30 Minutes': '30m',
            '3 Days': '3d',
            '3 Minutes': '3m',
            '4 Hours': '4h',
            '5 Minutes': '5m',
            '6 Hours': '6h',
            '8 Hours': '8h'
        }
        return intervals[interval]

    def initiate_csv_generation(self):
        thread = Worker(self.generate_csv)
        self.threadPool.start(thread)

    def generate_csv(self):
        self.generateCSVButton.setEnabled(False)

        symbol = self.csvGenerationTicker.currentText()
        interval = self.convert_interval(self.csvGenerationDataInterval.currentText())
        self.csvGenerationStatus.setText("Downloading data...")
        savedPath = Data(loadData=False, interval=interval, symbol=symbol).get_csv_data(interval)

        # messageBox = QMessageBox()
        # messageBox.setText(f"Successfully saved CSV data to {savedPath}.")
        # messageBox.setIcon(QMessageBox.Information)
        # messageBox.exec_()
        self.csvGenerationStatus.setText(f"Successfully saved CSV data to {savedPath}.")
        self.generateCSVButton.setEnabled(True)

    def timestamp_message(self, msg):
        self.botOutput.appendPlainText(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {msg}')

    def update_trades_to_list_view(self):
        widgetCount = self.tradesListWidget.count()
        tradeCount = len(self.trader.trades)

        if widgetCount < tradeCount:
            remaining = tradeCount - widgetCount
            for trade in self.trader.trades[-remaining:]:
                self.add_trade_to_list_view(f'{trade["date"]}: {trade["action"]}')

    def add_trade_to_list_view(self, msg):
        self.tradesListWidget.addItem(msg)

    def interact_double_cross(self):
        if self.doubleCrossCheckMark.isChecked():
            self.doubleCrossGroupBox.setEnabled(True)
        else:
            self.doubleCrossGroupBox.setEnabled(False)

    def update_info(self):
        self.currentBalanceValue.setText(f'${round(self.trader.balance, 2)}')
        self.startingBalanceValue.setText(f'${self.trader.startingBalance}')

        if self.trader.get_profit() < 0:
            self.profitLossLabel.setText("Loss")
            self.profitLossValue.setText(f'${-round(self.trader.get_profit(), 2)}')
        else:
            self.profitLossLabel.setText("Gain")
            self.profitLossValue.setText(f'${round(self.trader.get_profit(), 2)}')
        self.currentPositionValue.setText(str(self.trader.get_position()))
        self.currentBtcValue.setText(str(self.trader.btc))
        self.btcOwedValue.setText(str(self.trader.btcOwed))
        self.tradesMadeValue.setText(str(len(self.trader.trades)))
        self.currentTickerLabel.setText(str(self.trader.dataView.symbol))
        self.currentTickerValue.setText(f'${self.trader.dataView.get_current_price()}')

        if self.trader.get_stop_loss() is not None:
            if self.trader.lossStrategy == 1:
                self.lossPointLabel.setText('Stop loss')
            else:
                self.lossPointLabel.setText('Trailing loss')
            self.lossPointValue.setText(f'${round(self.trader.get_stop_loss(), 2)}')
        else:
            self.lossPointValue.setText('None')

        if len(self.trader.tradingOptions) > 0:
            option = self.trader.tradingOptions[0]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.baseInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})')
            self.baseInitialMovingAverageValue.setText(f'${initialAverage}')
            self.baseFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})')
            self.baseFinalMovingAverageValue.setText(f'${finalAverage}')

        if len(self.trader.tradingOptions) > 1:
            option = self.trader.tradingOptions[1]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            print('', end='')  # This is so PyCharm stops nagging us about duplicate code.

            self.nextInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})')
            self.nextInitialMovingAverageValue.setText(f'${initialAverage}')
            self.nextFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})')
            self.nextFinalMovingAverageValue.setText(f'${finalAverage}')


def main():
    initialize_logger()
    interface = Interface()
    interface.show()
    app.exec_()


if __name__ == '__main__':
    main()
