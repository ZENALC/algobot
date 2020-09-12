import sys
from trader import SimulatedTrader, Option
from helpers import *

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import QThreadPool, QRunnable

app = QApplication(sys.argv)
uiFile = 'nigerianPrince.ui'


class Interface(QMainWindow):
    def __init__(self, parent=None):
        super(Interface, self).__init__(parent)  # Initializing object
        uic.loadUi(uiFile, self)  # Loading the UI

        self.doubleCrossCheckMark.toggled.connect(self.interact_double_cross)
        self.generateCSVButton.clicked.connect(self.generate_csv)
        self.runSimulationButton.clicked.connect(self.run_simulation)
        self.endSimulationButton.clicked.connect(self.end_simulation)

        self.trader = None

        self.timestamp_message('Greetings.')

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
        self.trader = SimulatedTrader(startingBalance=startingBalance,
                                      symbol=symbol,
                                      interval=interval)

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

    def output_trade_options(self):
        for option in self.trader.tradingOptions:
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.timestamp_message(f'Parameter: {option.parameter}')
            self.timestamp_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
            self.timestamp_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')

    def run_simulation(self):
        self.timestamp_message('Starting simulation.')
        self.grey_out(True)
        self.create_simulation_trader()
        self.reset_trader()
        self.set_parameters()
        self.trader.tradingOptions = self.get_trading_options()

        while True:
            if not self.trader.dataView.data_is_updated():
                self.timestamp_message("Updating data...")
                self.trader.dataView.update_data()

            self.output_trade_options()
            self.update_statistics()

            self.trader.currentPrice = self.trader.dataView.get_current_price()
            if self.trader.longTrailingPrice is not None and self.trader.currentPrice > self.trader.longTrailingPrice:
                self.trader.longTrailingPrice = self.trader.currentPrice
            if self.trader.shortTrailingPrice is not None and self.trader.currentPrice < self.trader.shortTrailingPrice:
                self.trader.shortTrailingPrice = self.trader.currentPrice

            if not self.trader.inHumanControl:
                self.trader.main_logic()

    def grey_out(self, boolean):
        boolean = not boolean
        self.mainOptionsGroupBox.setEnabled(boolean)
        self.averageOptionsGroupBox.setEnabled(boolean)
        self.lossOptionsGroupBox.setEnabled(boolean)
        self.otherOptionsBox.setEnabled(boolean)
        self.runSimulationButton.setEnabled(boolean)

    def destroy_simulation_trader(self):
        self.trader = None

    def end_simulation(self):
        self.destroy_simulation_trader()
        self.grey_out(False)

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

    def generate_csv(self):
        pass

    def timestamp_message(self, msg):
        self.botOutput.appendPlainText(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {msg}')

    def add_trade_to_list_view(self, msg):
        self.tradesListWidget.addItem(msg)

    def interact_double_cross(self):
        if self.doubleCrossCheckMark.isChecked():
            self.doubleCrossGroupBox.setEnabled(True)
        else:
            self.doubleCrossGroupBox.setEnabled(False)

    def update_statistics(self):
        self.currentBalanceValue.setText(str(self.trader.balance))
        self.startingBalanceValue.setText(str(self.trader.startingBalance))
        self.profitLossValue.setText(str(self.trader.get_profit()))
        self.currentPositionValue.setText(str(self.trader.get_position()))
        self.currentBtcValue.setText(str(self.trader.btc))
        self.btcOwedValue.setText(str(self.trader.btcOwed))
        self.tradesMadeValue.setText(str(len(self.trader.trades)))


def main():
    initialize_logger()
    interface = Interface()
    interface.show()
    app.exec_()


if __name__ == '__main__':
    main()
