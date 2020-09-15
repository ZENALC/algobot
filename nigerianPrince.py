import sys
import traceback
import assets

from trader import SimulatedTrader, Option, Data
from helpers import *

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QDialog
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSlot
from PyQt5.QtGui import QPalette, QColor, QPixmap, QIcon

app = QApplication(sys.argv)
app.setStyle('Fusion')

mainUi = 'nigerianPrince.ui'
configurationUi = 'configuration.ui'
otherCommandsUi = 'otherCommands.ui'
statisticsUi = 'statistics.ui'


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
        uic.loadUi(mainUi, self)  # Loading the main UI
        self.configuration = Configuration()
        self.otherCommands = OtherCommands()
        self.statistics = Statistics()
        self.threadPool = QThreadPool()

        self.advancedLogging = True

        self.configuration.simpleLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(False))
        self.configuration.advancedLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(True))

        self.otherCommandsAction.triggered.connect(lambda: self.otherCommands.show())
        self.configurationAction.triggered.connect(lambda: self.configuration.show())
        self.statisticsAction.triggered.connect(lambda: self.statistics.show())

        self.runSimulationButton.clicked.connect(self.initiate_simulation_thread)
        self.endSimulationButton.clicked.connect(self.end_simulation)
        self.forceLongButton.clicked.connect(self.force_long)
        self.forceShortButton.clicked.connect(self.force_short)
        self.pauseBotButton.clicked.connect(self.pause_bot)
        self.exitPositionButton.clicked.connect(self.exit_position)

        self.trader = None
        self.runningLive = False
        self.liveThread = None

        self.timestamp_message('Greetings.')

    def set_advanced_logging(self, boolean):
        if self.advancedLogging:
            self.timestamp_message(f'Logging method has been changed to advanced.')
        else:
            self.timestamp_message(f'Logging method has been changed to simple.')
        self.advancedLogging = boolean

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
        baseAverageType = self.configuration.averageTypeComboBox.currentText()
        baseParameter = self.configuration.parameterComboBox.currentText().lower()
        baseInitialValue = self.configuration.initialValueSpinBox.value()
        baseFinalValue = self.configuration.finalValueSpinBox.value()

        options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]
        if self.configuration.doubleCrossCheckMark.isChecked():
            additionalAverageType = self.configuration.doubleAverageComboBox.currentText()
            additionalParameter = self.configuration.doubleParameterComboBox.currentText().lower()
            additionalInitialValue = self.configuration.doubleInitialValueSpinBox.value()
            additionalFinalValue = self.configuration.doubleFinalValueSpinBox.value()
            option = Option(additionalAverageType, additionalParameter, additionalInitialValue, additionalFinalValue)
            options.append(option)

        return options

    def get_loss_strategy(self):
        if self.configuration.trailingLossRadio.isChecked():
            return 2
        else:
            return 1

    def create_simulation_trader(self):
        symbol = self.configuration.tickerComboBox.currentText()
        interval = convert_interval(self.configuration.intervalComboBox.currentText())
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
        self.trader.lossPercentage = self.configuration.lossPercentageSpinBox.value()
        self.trader.lossStrategy = self.get_loss_strategy()
        self.trader.safetyTimer = self.configuration.sleepTimerSpinBox.value()
        self.trader.safetyMargin = self.configuration.marginSpinBox.value()

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

            if self.advancedLogging:
                self.trader.output_basic_information()

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
        self.configuration.mainOptionsGroupBox.setEnabled(boolean)
        self.configuration.averageOptionsGroupBox.setEnabled(boolean)
        self.configuration.lossOptionsGroupBox.setEnabled(boolean)
        self.configuration.otherOptionsBox.setEnabled(boolean)
        self.runSimulationButton.setEnabled(boolean)

    def destroy_simulation_trader(self):
        self.trader = None

    def end_simulation(self):
        self.timestamp_message("Ending simulation...\n\n")
        self.disable_override()
        self.endSimulationButton.setEnabled(False)
        self.runningLive = False
        self.grey_out_main_options(False)

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

    def update_info(self):
        self.statistics.currentBalanceValue.setText(f'${round(self.trader.balance, 2)}')
        self.statistics.startingBalanceValue.setText(f'${self.trader.startingBalance}')

        if self.trader.get_profit() < 0:
            self.statistics.profitLossLabel.setText("Loss")
            self.statistics.profitLossValue.setText(f'${-round(self.trader.get_profit(), 2)}')
        else:
            self.statistics.profitLossLabel.setText("Gain")
            self.statistics.profitLossValue.setText(f'${round(self.trader.get_profit(), 2)}')
        self.statistics.currentPositionValue.setText(str(self.trader.get_position()))
        self.statistics.currentBtcValue.setText(str(self.trader.btc))
        self.statistics.btcOwedValue.setText(str(self.trader.btcOwed))
        self.statistics.tradesMadeValue.setText(str(len(self.trader.trades)))
        self.statistics.currentTickerLabel.setText(str(self.trader.dataView.symbol))
        self.statistics.currentTickerValue.setText(f'${self.trader.dataView.get_current_price()}')

        if self.trader.get_stop_loss() is not None:
            if self.trader.lossStrategy == 1:
                self.statistics.lossPointLabel.setText('Stop loss')
            else:
                self.statistics.lossPointLabel.setText('Trailing loss')
            self.statistics.lossPointValue.setText(f'${round(self.trader.get_stop_loss(), 2)}')
        else:
            self.statistics.lossPointValue.setText('None')

        if len(self.trader.tradingOptions) > 0:
            option = self.trader.tradingOptions[0]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.statistics.baseInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})')
            self.statistics.baseInitialMovingAverageValue.setText(f'${initialAverage}')
            self.statistics.baseFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})')
            self.statistics.baseFinalMovingAverageValue.setText(f'${finalAverage}')

        if len(self.trader.tradingOptions) > 1:
            self.statistics.nextInitialMovingAverageLabel.show()
            self.statistics.nextInitialMovingAverageValue.show()
            self.statistics.nextFinalMovingAverageLabel.show()
            self.statistics.nextFinalMovingAverageValue.show()
            option = self.trader.tradingOptions[1]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            print('', end='')  # This is so PyCharm stops nagging us about duplicate code.

            self.statistics.nextInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})')
            self.statistics.nextInitialMovingAverageValue.setText(f'${initialAverage}')
            self.statistics.nextFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})')
            self.statistics.nextFinalMovingAverageValue.setText(f'${finalAverage}')
        else:
            self.statistics.nextInitialMovingAverageLabel.hide()
            self.statistics.nextInitialMovingAverageValue.hide()
            self.statistics.nextFinalMovingAverageLabel.hide()
            self.statistics.nextFinalMovingAverageValue.hide()


class Configuration(QDialog):
    def __init__(self, parent=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI

        self.lightModeRadioButton.toggled.connect(lambda: app.setPalette(get_light_palette()))
        self.darkModeRadioButton.toggled.connect(lambda: app.setPalette(get_dark_palette()))
        self.bloombergModeRadioButton.toggled.connect(lambda: app.setPalette(get_bloomberg_palette()))

        self.doubleCrossCheckMark.toggled.connect(self.interact_double_cross)

    def interact_double_cross(self):
        if self.doubleCrossCheckMark.isChecked():
            self.doubleCrossGroupBox.setEnabled(True)
        else:
            self.doubleCrossGroupBox.setEnabled(False)


class OtherCommands(QDialog):
    def __init__(self, parent=None):
        super(OtherCommands, self).__init__(parent)  # Initializing object
        uic.loadUi(otherCommandsUi, self)  # Loading the main UI

        self.threadPool = QThreadPool()

        self.generateCSVButton.clicked.connect(self.initiate_csv_generation)
        self.movingAverageMiscellaneousParameter.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousType.currentTextChanged.connect(self.initiate_misc_get_moving_average)
        self.movingAverageMiscellaneousValue.valueChanged.connect(self.initiate_misc_get_moving_average)

    def initiate_misc_get_moving_average(self):
        thread = Worker(self.get_moving_average_miscellaneous)
        self.threadPool.start(thread)

    def get_moving_average_miscellaneous(self):
        self.movingAverageMiscellaneousResult.setText("haha what did you expect?")

    def initiate_csv_generation(self):
        thread = Worker(self.generate_csv)
        self.threadPool.start(thread)

    def generate_csv(self):
        self.generateCSVButton.setEnabled(False)

        symbol = self.csvGenerationTicker.currentText()
        interval = convert_interval(self.csvGenerationDataInterval.currentText())
        self.csvGenerationStatus.setText("Downloading data...")
        savedPath = Data(loadData=False, interval=interval, symbol=symbol).get_csv_data(interval)

        # messageBox = QMessageBox()
        # messageBox.setText(f"Successfully saved CSV data to {savedPath}.")
        # messageBox.setIcon(QMessageBox.Information)
        # messageBox.exec_()
        self.csvGenerationStatus.setText(f"Successfully saved CSV data to {savedPath}.")
        self.generateCSVButton.setEnabled(True)


class Statistics(QDialog):
    def __init__(self, parent=None):
        super(Statistics, self).__init__(parent)  # Initializing object
        uic.loadUi(statisticsUi, self)  # Loading the main UI


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


def get_bloomberg_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QColor(255, 140, 0))
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ToolTipText, QColor(255, 140, 0))
    palette.setColor(QPalette.Text, QColor(255, 140, 0))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QColor(255, 140, 0))
    palette.setColor(QPalette.BrightText, QColor(252, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    return palette


def get_dark_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    return palette


def get_light_palette():
    palette = QPalette()
    return palette


def main():
    initialize_logger()
    interface = Interface()
    interface.showMaximized()
    app.setWindowIcon(QIcon(':/logo/nigerianPrince.png'))
    app.exec_()


if __name__ == '__main__':
    main()
