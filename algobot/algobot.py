import sys
import traceback

import assets

from data import Data
from telegramBot import TelegramBot
from realtrader import RealTrader
from simulationtrader import SimulatedTrader
from option import Option
from enums import *
from helpers import *

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QDialog, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSlot, QObject, pyqtSignal
from PyQt5.QtGui import QPalette, QColor, QIcon
from pyqtgraph import DateAxisItem, mkPen

app = QApplication(sys.argv)

mainUi = f'../UI{os.path.sep}algobot.ui'
configurationUi = f'../UI{os.path.sep}configuration.ui'
otherCommandsUi = f'../UI{os.path.sep}otherCommands.ui'
statisticsUi = f'../UI{os.path.sep}statistics.ui'
aboutUi = f'../UI{os.path.sep}about.ui'


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class Worker(QRunnable):
    """
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

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
            self.signals.error.emit(str(e))


class Interface(QMainWindow):
    def __init__(self, parent=None):
        super(Interface, self).__init__(parent)  # Initializing object
        uic.loadUi(mainUi, self)  # Loading the main UI
        self.configuration = Configuration()  # Loading configuration
        self.otherCommands = OtherCommands()  # Loading other commands
        self.about = About()  # Loading about information
        self.statistics = Statistics()  # Loading statistics
        self.threadPool = QThreadPool()  # Initiating threading pool
        self.graphs = (self.simulationGraph, self.backtestGraph, self.realGraph, self.avgGraph, self.simulationAvgGraph)
        self.setup_graphs()  # Setting up graphs
        self.initiate_slots()  # Initiating slots
        self.threadPool.start(Worker(self.load_tickers))  # Load tickers

        self.plots = []
        self.advancedLogging = True
        self.runningLive = False
        self.trader = None
        self.simulationTrader = None
        self.traderType = None
        self.lowerIntervalData = None
        self.telegramBot = None
        self.add_to_activity_monitor('Initialized interface.')

    def initiate_bot_thread(self, caller):
        worker = Worker(lambda: self.run_bot(caller))
        worker.signals.error.connect(self.end_bot_and_create_popup)
        worker.signals.result.connect(lambda: print("lol"))
        self.threadPool.start(worker)

    def end_bot_and_create_popup(self, msg):
        self.disable_interface(False, self.traderType)
        self.endBotButton.setEnabled(False)
        self.endSimulationButton.setEnabled(False)
        # self.timestamp_message('Ended bot because of an error.')
        self.create_popup(msg)

    def automate_trading(self):
        crossInform = False
        lowerCrossPosition = -5

        while self.runningLive:
            try:
                if not self.trader.dataView.data_is_updated():
                    self.timestamp_message("Updating data...")
                    self.trader.dataView.update_data()

                if self.trader.get_position() is not None:
                    crossInform = False

                if not crossInform and self.trader.get_position() is None and not self.trader.inHumanControl:
                    crossInform = True
                    self.timestamp_message("Waiting for a cross.")

                self.update_info()
                self.update_trades_to_list_view()

                if self.advancedLogging:
                    self.trader.output_basic_information()

                self.trader.currentPrice = self.trader.dataView.get_current_price()
                currentPrice = self.trader.currentPrice
                if self.trader.longTrailingPrice is not None and currentPrice > self.trader.longTrailingPrice:
                    self.trader.longTrailingPrice = self.trader.currentPrice
                if self.trader.shortTrailingPrice is not None and currentPrice < self.trader.shortTrailingPrice:
                    self.trader.shortTrailingPrice = self.trader.currentPrice

                if not self.trader.inHumanControl:
                    self.trader.main_logic()

                if lowerCrossPosition != self.trader.get_position():
                    if self.trader.check_cross_v2(dataObject=self.lowerIntervalData):
                        lowerCrossPosition = self.trader.get_position()
                        self.timestamp_message('Lower interval cross detected.')

                if self.trader.get_position() is None:
                    self.exitPositionButton.setEnabled(False)
                    self.waitOverrideButton.setEnabled(False)
                else:
                    self.exitPositionButton.setEnabled(True)
                    self.waitOverrideButton.setEnabled(True)

                if self.trader.get_position() == LONG:
                    self.forceLongButton.setEnabled(False)
                    self.forceShortButton.setEnabled(True)

                if self.trader.get_position() == SHORT:
                    self.forceLongButton.setEnabled(True)
                    self.forceShortButton.setEnabled(False)
            except Exception as e:
                raise e
                # self.trader.output_message(f'Error: {e}')

    def run_bot(self, caller):
        self.create_trader(caller)
        self.disable_interface(True, caller)
        self.set_parameters(caller)
        self.enable_override(caller)

        if self.configuration.enableTelegramTrading.isChecked():
            if self.telegramBot is None:
                self.telegramBot = TelegramBot(gui=self)
            self.telegramBot.start()
            self.add_to_activity_monitor('Starting Telegram bot.')

        self.plots = []
        self.setup_plots()
        self.automate_trading()

    def end_bot(self, caller):
        if caller == SIMULATION:
            self.simulationTrader.get_simulation_result()
            self.endSimulationButton.setEnabled(False)
            self.add_to_simulation_activity_monitor("Ended Simulation")
            self.runSimulationButton.setEnabled(True)
            tempTrader = self.simulationTrader
        else:
            self.endBotWithExitingTrade.setEnabled(False)
            self.telegramBot.stop()
            self.add_to_activity_monitor('Killed Telegram bot.')
            self.add_to_activity_monitor("Killed bot.>")
            self.runBotButton.setEnabled(True)
            tempTrader = self.trader
        tempTrader.log_trades()
        # self.disable_override()
        # self.update_trades_to_list_view()
        self.disable_interface(False, caller=caller)
        tempTrader.dataView.dump_to_table()
        # if self.lowerIntervalData is not None:
        #     self.lowerIntervalData.dump_to_table()
        #     self.lowerIntervalData = None
        self.destroy_trader(tempTrader)

    def destroy_trader(self, caller):
        if caller == SIMULATION:
            self.simulationTrader = None
        elif caller == LIVE:
            self.trader = None
        elif caller == BACKTEST:
            pass
        else:
            raise ValueError("invalid caller type specified.")

    def create_trader(self, caller):
        if caller == SIMULATION:
            symbol = self.configuration.simulationTickerComboBox.currentText()
            interval = convert_interval(self.configuration.simulationIntervalComboBox.currentText())
            startingBalance = self.configuration.simulationStartingBalanceSpinBox.value()
            self.add_to_simulation_activity_monitor(f"Retrieving data for interval {interval}...")
            self.simulationTrader = SimulatedTrader(startingBalance=startingBalance,
                                                    symbol=symbol,
                                                    interval=interval,
                                                    loadData=True)
        elif caller == LIVE:
            symbol = self.configuration.tickerComboBox.currentText()
            interval = convert_interval(self.configuration.intervalComboBox.currentText())
            apiSecret = self.configuration.binanceApiSecret.text()
            apiKey = self.configuration.binanceApiKey.text()
            if len(apiSecret) == 0:
                raise ValueError('Please specify an API secret key. No API secret key found.')
            elif len(apiKey) == 0:
                raise ValueError("Please specify an API key. No API key found.")
            self.add_to_activity_monitor(f"Retrieving data for interval {interval}...")
            self.trader = RealTrader(apiSecret=apiSecret, apiKey=apiKey, interval=interval, symbol=symbol)
        else:
            raise ValueError("Invalid caller.")

        if True:
            sortedIntervals = ('1m', '3m', '5m', '15m', '30m', '1h', '2h', '12h', '4h', '6h', '8h', '1d', '3d')
            if interval != '1m':
                lowerInterval = sortedIntervals[sortedIntervals.index(interval) - 1]
                self.add_to_activity_monitor(f'Retrieving data for lower interval {lowerInterval}...')
                self.lowerIntervalData = Data(lowerInterval)

        # self.trader.dataView.get_data_from_database()
        # if not self.trader.dataView.database_is_updated():
        #     self.timestamp_message("Updating data...")
        #     self.trader.dataView.update_database()
        # else:
        #     self.timestamp_message("Data is up-to-date.")

    def set_parameters(self, caller):
        if caller == LIVE:
            self.trader.lossStrategy, self.trader.lossPercentage = self.get_loss_settings(caller)
            self.trader.tradingOptions = self.get_trading_options(caller)
        elif caller == SIMULATION:
            self.simulationTrader.lossStrategy, self.simulationTrader.lossPercentage = self.get_loss_settings(caller)
            self.simulationTrader.tradingOptions = self.get_trading_options(caller)
        else:
            raise ValueError('Invalid caller.')

    def set_advanced_logging(self, boolean):
        if self.advancedLogging:
            self.add_to_activity_monitor(f'Logging method has been changed to advanced.')
        else:
            self.add_to_activity_monitor(f'Logging method has been changed to simple.')
        self.advancedLogging = boolean

    def disable_interface(self, boolean, caller):
        boolean = not boolean
        if caller == 'backtest':
            self.backtestConfigurationTabWidget.setEnabled(boolean)
            self.runBacktestButton.setEnabled(boolean)
            self.endBacktestButton.setEnabled(not boolean)
        elif caller == 'simulation':
            self.simulationConfigurationTabWidget.setEnabled(boolean)
            self.runSimulationButton.setEnabled(boolean)
            self.endSimulationButton.setEnabled(not boolean)
        elif caller == 'live':
            self.mainConfigurationTabWidget.setEnabled(boolean)
            self.runBotButton.setEnabled(boolean)
            self.endBotBUtton.setEnabled(not boolean)

    def update_trades_to_list_view(self):
        widgetCount = self.tradesListWidget.count()
        tradeCount = len(self.trader.trades)

        if widgetCount < tradeCount:
            remaining = tradeCount - widgetCount
            for trade in self.trader.trades[-remaining:]:
                self.add_trade_to_list_view(f'{trade["action"]}')
                self.timestamp_message(f'{trade["action"]}')

    def add_trade_to_list_view(self, msg):
        self.tradesListWidget.addItem(msg)

    def update_info(self):
        self.statistics.currentBalanceValue.setText(f'${round(self.trader.balance, 2)}')
        self.statistics.startingBalanceValue.setText(f'${round(self.trader.startingBalance, 2)}')
        self.statistics.autonomousValue.setText(str(not self.trader.inHumanControl))

        if self.trader.inHumanControl:
            self.autonomousStateLabel.setText('WARNING: IN HUMAN CONTROL')
        else:
            self.autonomousStateLabel.setText('INFO: IN AUTONOMOUS MODE')

        if self.trader.get_profit() < 0:
            self.statistics.profitLossLabel.setText("Loss")
            self.statistics.profitLossValue.setText(f'${-round(self.trader.get_profit(), 2)}')
        else:
            self.statistics.profitLossLabel.setText("Gain")
            self.statistics.profitLossValue.setText(f'${round(self.trader.get_profit(), 2)}')

        position = self.trader.get_position()

        if position == LONG:
            self.statistics.currentPositionValue.setText('Long')
        elif position == SHORT:
            self.statistics.currentPositionValue.setText('Short')
        else:
            self.statistics.currentPositionValue.setText('None')

        self.statistics.currentBtcLabel.setText(f'{self.trader.coinName} Owned')
        self.statistics.currentBtcValue.setText(f'{round(self.trader.coin, 6)}')
        self.statistics.btcOwedLabel.setText(f'{self.trader.coinName} Owed')
        self.statistics.btcOwedValue.setText(f'{round(self.trader.coinOwed, 6)}')
        self.statistics.tradesMadeValue.setText(str(len(self.trader.trades)))
        self.statistics.currentTickerLabel.setText(str(self.trader.dataView.symbol))
        self.statistics.currentTickerValue.setText(f'${self.trader.dataView.get_current_price()}')

        if self.trader.get_stop_loss() is not None:
            if self.trader.lossStrategy == STOP_LOSS:
                self.statistics.lossPointLabel.setText('Stop Loss')
            else:
                self.statistics.lossPointLabel.setText('Trailing Loss')
            self.statistics.lossPointValue.setText(f'${round(self.trader.get_stop_loss(), 2)}')
        else:
            self.statistics.lossPointValue.setText('None')

        currentUTC = datetime.utcnow().timestamp()

        if len(self.trader.tradingOptions) > 0:
            option = self.trader.tradingOptions[0]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.plots[0]['x'].append(currentUTC)
            self.plots[0]['y'].append(initialAverage)
            self.plots[0]['plot'].setData(self.plots[0]['x'], self.plots[0]['y'])

            self.plots[1]['x'].append(currentUTC)
            self.plots[1]['y'].append(finalAverage)
            self.plots[1]['plot'].setData(self.plots[1]['x'], self.plots[1]['y'])

            self.statistics.baseInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})'
                                                                  f' {option.parameter.capitalize()}')
            self.statistics.baseInitialMovingAverageValue.setText(f'${initialAverage}')
            self.statistics.baseFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})'
                                                                f' {option.parameter.capitalize()}')
            self.statistics.baseFinalMovingAverageValue.setText(f'${finalAverage}')

        if len(self.trader.tradingOptions) > 1:
            self.statistics.nextInitialMovingAverageLabel.show()
            self.statistics.nextInitialMovingAverageValue.show()
            self.statistics.nextFinalMovingAverageLabel.show()
            self.statistics.nextFinalMovingAverageValue.show()

            option = self.trader.tradingOptions[1]
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.plots[2]['x'].append(currentUTC)
            self.plots[2]['y'].append(initialAverage)
            self.plots[2]['plot'].setData(self.plots[2]['x'], self.plots[2]['y'])

            self.plots[3]['x'].append(currentUTC)
            self.plots[3]['y'].append(finalAverage)
            self.plots[3]['plot'].setData(self.plots[3]['x'], self.plots[3]['y'])

            self.statistics.nextInitialMovingAverageLabel.setText(f'{option.movingAverage}({option.initialBound})'
                                                                  f' - {option.parameter.capitalize()}')
            print("", end="")  # so PyCharm stops nagging us
            self.statistics.nextInitialMovingAverageValue.setText(f'${initialAverage}')
            self.statistics.nextFinalMovingAverageLabel.setText(f'{option.movingAverage}({option.finalBound})'
                                                                f' - {option.parameter.capitalize()}')
            self.statistics.nextFinalMovingAverageValue.setText(f'${finalAverage}')
        else:
            self.statistics.nextInitialMovingAverageLabel.hide()
            self.statistics.nextInitialMovingAverageValue.hide()
            self.statistics.nextFinalMovingAverageLabel.hide()
            self.statistics.nextFinalMovingAverageValue.hide()

    def enable_override(self, caller):
        if caller == SIMULATION:
            self.pauseBotSimulationButton.setEnabled(True)
            self.forceLongSimulationButton.setEnabled(True)
            self.forceShortSimulationButton.setEnabled(True)
        elif caller == LIVE:
            self.pauseBotButton.setEnabled(True)
            self.forceLongButton.setEnabled(True)
            self.forceShortButton.setEnabled(True)
        else:
            raise ValueError("Invalid caller specified.")

    # to fix
    def disable_override(self):
        self.overrideGroupBox.setEnabled(False)

    def exit_position(self, humanControl=True):
        self.trader.inHumanControl = humanControl
        if humanControl:
            self.pauseBotButton.setText('Resume Bot')
        else:
            self.pauseBotButton.setText('Pause Bot')

        if self.trader.get_position() == LONG:
            if humanControl:
                self.trader.sell_long('Force exiting long.', stopLoss=True)
            else:
                self.trader.sell_long('Exiting long because of override and resuming autonomous logic.',
                                      stopLoss=True)
        elif self.trader.get_position() == SHORT:
            if humanControl:
                self.trader.buy_short('Force exiting short.', stopLoss=True)
            else:
                self.trader.buy_short('Exiting short because of override and resuming autonomous logic..',
                                      stopLoss=True)

        self.forceShortButton.setEnabled(True)
        self.forceLongButton.setEnabled(True)
        self.exitPositionButton.setEnabled(False)
        self.waitOverrideButton.setEnabled(False)

    def force_long(self):
        self.trader.inHumanControl = True
        self.pauseBotButton.setText('Resume Bot')
        self.timestamp_message('Forcing long and stopping autonomous logic.')
        if self.trader.get_position() == SHORT:
            self.trader.buy_short('Exiting short because long was forced.')

        self.trader.buy_long('Force executed long.')
        self.forceShortButton.setEnabled(False)
        self.forceLongButton.setEnabled(False)
        self.exitPositionButton.setEnabled(True)
        self.waitOverrideButton.setEnabled(True)

    def force_short(self):
        self.trader.inHumanControl = True
        self.pauseBotButton.setText('Resume Bot')
        self.timestamp_message('Forcing short and stopping autonomous logic.')
        if self.trader.get_position() == LONG:
            self.trader.sell_long('Exiting long because short was forced.')

        self.trader.sell_short('Force executed short.')
        self.forceShortButton.setEnabled(False)
        self.forceLongButton.setEnabled(True)
        self.exitPositionButton.setEnabled(True)
        self.waitOverrideButton.setEnabled(True)

    def pause_or_resume_bot(self):
        if self.pauseBotButton.text() == 'Pause Bot':
            self.trader.inHumanControl = True
            self.pauseBotButton.setText('Resume Bot')
            self.timestamp_message('Pausing bot logic.')
        else:
            self.trader.inHumanControl = False
            self.pauseBotButton.setText('Pause Bot')
            self.timestamp_message('Resuming bot logic.')

    def get_trading_options(self, caller):
        if caller == BACKTEST:
            baseAverageType = self.configuration.backtestAverageTypeComboBox.currentText()
            baseParameter = self.configuration.backtestParameterComboBox.currentText().lower()
            baseInitialValue = self.configuration.backtestInitialValueSpinBox.value()
            baseFinalValue = self.configuration.backtestFinalValueSpinBox.value()
            options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]

            if self.configuration.backtestDoubleCrossCheckMark.isChecked():
                additionalAverageType = self.configuration.backtestDoubleAverageComboBox.currentText()
                additionalParameter = self.configuration.backtestDoubleParameterComboBox.currentText().lower()
                additionalInitialValue = self.configuration.backtestDoubleInitialValueSpinBox.value()
                additionalFinalValue = self.configuration.backtestDoubleFinalValueSpinBox.value()
                option = Option(additionalAverageType, additionalParameter, additionalInitialValue,
                                additionalFinalValue)
                options.append(option)

            return options
        elif caller == SIMULATION:
            baseAverageType = self.configuration.simulationAverageTypeComboBox.currentText()
            baseParameter = self.configuration.simulationParameterComboBox.currentText().lower()
            baseInitialValue = self.configuration.simulationInitialValueSpinBox.value()
            baseFinalValue = self.configuration.simulationFinalValueSpinBox.value()
            options = [Option(baseAverageType, baseParameter, baseInitialValue, baseFinalValue)]

            if self.configuration.simulationDoubleCrossCheckMark.isChecked():
                additionalAverageType = self.configuration.simulationDoubleAverageComboBox.currentText()
                additionalParameter = self.configuration.simulationDoubleParameterComboBox.currentText().lower()
                additionalInitialValue = self.configuration.simulationDoubleInitialValueSpinBox.value()
                additionalFinalValue = self.configuration.simulationDoubleFinalValueSpinBox.value()
                option = Option(additionalAverageType, additionalParameter, additionalInitialValue,
                                additionalFinalValue)
                options.append(option)

            return options
        elif caller == LIVE:
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
                option = Option(additionalAverageType, additionalParameter, additionalInitialValue,
                                additionalFinalValue)
                options.append(option)

            return options
        else:
            raise ValueError("Invalid caller specified.")

    def get_loss_settings(self, caller):
        if caller == BACKTEST:
            if self.configuration.backtestTrailingLossRadio.isChecked():
                return TRAILING_LOSS, self.configuration.backtestLossPercentageSpinBox.value()
            else:
                return STOP_LOSS, self.configuration.backtestLossPercentageSpinBox.value()
        elif caller == SIMULATION:
            if self.configuration.simulationTrailingLossRadio.isChecked():
                return TRAILING_LOSS, self.configuration.simulationLossPercentageSpinBox.value()
            else:
                return STOP_LOSS, self.configuration.simulationLossPercentageSpinBox.value()
        elif caller == LIVE:
            if self.configuration.trailingLossRadio.isChecked():
                return TRAILING_LOSS, self.configuration.lossPercentageSpinBox.value()
            else:
                return STOP_LOSS, self.configuration.lossPercentageSpinBox.value()

    def closeEvent(self, event):
        """
        Close event override. Makes user confirm they want to end program if something is running live.
        :param event: close event
        """
        if self.runningLive:
            qm = QMessageBox
            ret = qm.question(self, 'Close?', "Are you sure to end the program?",
                              qm.Yes | qm.No)

            if ret == qm.Yes:
                self.end_bot(self.traderType)
                event.accept()
            else:
                event.ignore()

    def setup_graphs(self):
        """
        Sets up all available graphs in application.
        """
        currentDate = datetime.utcnow().timestamp()
        nextDate = currentDate + 3600000

        for graph in self.graphs:
            graph.setAxisItems({'bottom': DateAxisItem()})
            graph.setBackground('w')
            graph.setLabel('left', 'Price')
            graph.setLabel('bottom', 'Datetime in UTC')
            graph.setLimits(xMin=currentDate, xMax=nextDate)
            graph.addLegend()

            if graph == self.backtestGraph:
                graph.setTitle("Backtest Price Change")
            elif graph == self.simulationGraph:
                graph.setTitle("Simulation Price Change")
            elif graph == self.realGraph:
                graph.setTitle("Live Price Change")
            elif graph == self.simulationAvgGraph:
                graph.setTitle("Simulation Moving Averages")
            elif graph == self.avgGraph:
                graph.setTitle("Live Moving Averages")

        # self.graphWidget.setLimits(xMin=currentDate, xMax=nextDate)
        # self.graphWidget.addLegend()
        # self.graphWidget.plotItem.setMouseEnabled(y=False)

    # to fix
    def setup_plots(self, graph, trader):
        colors = self.get_graph_colors()
        currentDate = datetime.utcnow().timestamp()
        for option in trader.tradingOptions:
            initialAverage = trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = trader.get_average(option.movingAverage, option.parameter, option.finalBound)
            initialName = f'{option.movingAverage}({option.initialBound}) {option.parameter.capitalize()}'
            finalName = f'{option.movingAverage}({option.finalBound}) {option.parameter.capitalize()}'
            initialDict = {
                'plot': self.plot_graph((currentDate,), (initialAverage,), color=colors.pop(), plotName=initialName),
                'x': [currentDate, ],
                'y': [initialAverage, ]
            }
            self.plots.append(initialDict)

            finalDict = {
                'plot': self.plot_graph((currentDate,), (finalAverage,), color=colors.pop(), plotName=finalName),
                'x': [currentDate, ],
                'y': [initialAverage, ]
            }
            self.plots.append(finalDict)

    def get_graph_colors(self):
        """
        Returns graph colors to be placed based on configuration.
        """
        config = self.configuration
        colorDict = {'blue': 'b',
                     'green': 'g',
                     'red': 'r',
                     'cyan': 'c',
                     'magenta': 'm',
                     'yellow': 'y',
                     'black': 'k',
                     'white': 'w'}
        colors = [config.balanceColor.currentText(), config.avg1Color.currentText(), config.avg2Color.currentText(),
                  config.avg3Color.currentText(), config.avg4Color.currentText()]
        return [colorDict[color.lower()] for color in colors]

    @staticmethod
    def plot_graph(graph, x, y, plotName, color):
        """
        Plots to graph provided.
        :param graph: Graph function will plot on.
        :param x: X values of graph.
        :param y: Y values of graph.
        :param plotName: Name of graph.
        :param color: Color graph will be drawn in.
        """
        pen = mkPen(color=color)
        return graph.plot(x, y, name=plotName, pen=pen)

    def test_table(self, table, trade):
        """
        Initial function made to test table functionalities in QT.
        :param table: Table to insert row at.
        :param trade: Trade information to add.
        """
        rowPosition = self.simulationTable.rowCount()
        columns = self.simulationTable.columnCount()

        self.simulationTable.insertRow(rowPosition)
        for column in range(columns):
            table.setItem(rowPosition, column, QTableWidgetItem(str(trade[column])))

    def add_to_simulation_activity_monitor(self, message: str):
        self.add_to_table(self.simulationActivityMonitor, [message])

    def add_to_activity_monitor(self, message: str):
        """
        Function that adds activity information to activity monitor.
        :param message: Message to add to activity log.
        """
        self.add_to_table(self.activityMonitor, [message])

    def show_main_settings(self):
        """
        Opens main settings in the configuration window.
        """
        self.configuration.show()
        self.configuration.configurationTabWidget.setCurrentIndex(0)
        self.configuration.mainConfigurationTabWidget.setCurrentIndex(0)

    def show_backtest_settings(self):
        """
        Opens backtest settings in the configuration window.
        """
        self.configuration.show()
        self.configuration.configurationTabWidget.setCurrentIndex(1)
        self.configuration.backtestConfigurationTabWidget.setCurrentIndex(0)

    def show_simulation_settings(self):
        """
        Opens simulation settings in the configuration window.
        """
        self.configuration.show()
        self.configuration.configurationTabWidget.setCurrentIndex(2)
        self.configuration.simulationConfigurationTabWidget.setCurrentIndex(0)

    @staticmethod
    def add_to_table(table, data):
        """
        Function that will add specified data to a provided table.
        :param table: Table we will add data to.
        :param data: Data we will add to table.
        """
        rowPosition = table.rowCount()
        columns = table.columnCount()

        data.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if len(data) != columns:
            raise ValueError('Data needs to have the same amount of columns as table.')

        table.insertRow(rowPosition)
        for column in range(0, columns):
            table.setItem(rowPosition, column, QTableWidgetItem(str(data[column])))

    def create_configuration_slots(self):
        """
        Creates configuration slots.
        """
        self.configuration.lightModeRadioButton.toggled.connect(lambda: self.set_light_mode())
        self.configuration.darkModeRadioButton.toggled.connect(lambda: self.set_dark_mode())
        self.configuration.bloombergModeRadioButton.toggled.connect(lambda: self.set_bloomberg_mode())
        self.configuration.simpleLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(False))
        self.configuration.advancedLoggingRadioButton.clicked.connect(lambda: self.set_advanced_logging(True))

    def create_action_slots(self):
        """
        Creates actions slots.
        """
        self.otherCommandsAction.triggered.connect(lambda: self.otherCommands.show())
        self.configurationAction.triggered.connect(lambda: self.configuration.show())
        self.statisticsAction.triggered.connect(lambda: self.statistics.show())
        self.aboutNigerianPrinceAction.triggered.connect(lambda: self.about.show())

    def create_bot_slots(self):
        """
        Creates bot slots.
        """
        self.runBotButton.clicked.connect(lambda: self.initiate_bot_thread(caller=LIVE))
        self.endBotButton.clicked.connect(lambda: self.end_bot(caller=LIVE))
        self.configureBotButton.clicked.connect(self.show_main_settings)
        self.forceLongButton.clicked.connect(self.force_long)
        self.forceShortButton.clicked.connect(self.force_short)
        self.pauseBotButton.clicked.connect(self.pause_or_resume_bot)
        self.exitPositionButton.clicked.connect(lambda: self.exit_position(True))
        self.waitOverrideButton.clicked.connect(lambda: self.exit_position(False))

    def create_simulation_slots(self):
        """
        Creates simulation slots.
        """
        self.runSimulationButton.clicked.connect(lambda: self.initiate_bot_thread(caller=SIMULATION))
        self.endSimulationButton.clicked.connect(lambda: self.end_bot(caller=LIVE))
        self.configureSimulationButton.clicked.connect(self.show_simulation_settings)
        self.forceLongSimulationButton.clicked.connect(lambda: print("lol"))
        self.forceShortSimulationButton.clicked.connect(lambda: print("lol"))
        self.pauseBotSimulationButton.clicked.connect(lambda: print("lol"))
        self.exitPositionSimulationButton.clicked.connect(lambda: print("lol"))
        self.waitOverrideSimulationButton.clicked.connect(lambda: print("lol"))

    def create_backtest_slots(self):
        """
        Creates backtest slots.
        """
        self.configureBacktestButton.clicked.connect(self.show_backtest_settings)
        self.runBacktestButton.clicked.connect(lambda: print("backtest pressed"))
        self.endBacktestButton.clicked.connect(lambda: print("end backtest"))

    def create_interface_slots(self):
        """
        Creates interface slots.
        """
        self.create_bot_slots()
        self.create_simulation_slots()
        self.create_backtest_slots()

    def initiate_slots(self):
        """
        Initiates all interface slots.
        """
        self.create_action_slots()
        self.create_configuration_slots()
        self.create_interface_slots()

    def load_tickers(self):
        """
        Loads all available tickers from Binance API and displays them on appropriate combo boxes in application.
        """
        tickers = [ticker['symbol'] for ticker in Data(loadData=False).binanceClient.get_all_tickers()
                   if 'USDT' in ticker['symbol']]
        tickers.sort()
        self.configuration.tickerComboBox.clear()
        self.configuration.backtestTickerComboBox.clear()
        self.configuration.simulationTickerComboBox.clear()

        self.configuration.tickerComboBox.addItems(tickers)
        self.configuration.backtestTickerComboBox.addItems(tickers)
        self.configuration.simulationTickerComboBox.addItems(tickers)

        self.otherCommands.csvGenerationTicker.clear()
        self.otherCommands.csvGenerationTicker.addItems(tickers)

    def create_popup(self, msg):
        """
        Creates a popup with message provided.
        :param msg: Message provided.
        """
        if '-1021' in msg:
            msg = msg + ' Please sync your system time.'
        QMessageBox.about(self, 'Warning', msg)

    def set_dark_mode(self):
        """
        Switches interface to a dark theme.
        """
        app.setPalette(get_dark_palette())
        for graph in self.graphs:
            graph.setBackground('k')

    def set_light_mode(self):
        """
        Switches interface to a light theme.
        """
        app.setPalette(get_light_palette())
        for graph in self.graphs:
            graph.setBackground('w')

    def set_bloomberg_mode(self):
        """
        Switches interface to bloomberg theme.
        """
        app.setPalette(get_bloomberg_palette())
        for graph in self.graphs:
            graph.setBackground('k')

    @staticmethod
    def timestamp_message(msg, output=None):
        """
        This is not used anymore, but it adds a message to a ListWidget object from QT.
        :param msg: Message to be added.
        :param output: ListWidget object.
        """
        output.append(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {msg}')

    def display_trade_options(self):
        """
        This is never used, but it displays trading options.
        """
        for option in self.trader.tradingOptions:
            initialAverage = self.trader.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.trader.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.timestamp_message(f'Parameter: {option.parameter}')
            self.timestamp_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
            self.timestamp_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')


class Configuration(QDialog):
    def __init__(self, parent=None):
        super(Configuration, self).__init__(parent)  # Initializing object
        uic.loadUi(configurationUi, self)  # Loading the main UI
        self.load_slots()

    def load_slots(self):
        """
        Loads all configuration interface slots.
        """
        self.doubleCrossCheckMark.toggled.connect(self.toggle_double_cross_groupbox)
        self.simulationDoubleCrossCheckMark.toggled.connect(self.toggle_simulation_double_cross_groupbox)
        self.backtestDoubleCrossCheckMark.toggled.connect(self.toggle_backtest_double_cross_groupbox)

        self.simulationCopySettingsButton.clicked.connect(self.copy_settings_to_simulation)

        self.backtestCopySettingsButton.clicked.connect(self.copy_settings_to_backtest)
        self.backtestImportDataButton.clicked.connect(self.import_data)
        self.backtestDownloadDataButton.clicked.connect(self.download_data)

        self.testTelegramButton.clicked.connect(self.test_telegram)

    # To fix
    def test_telegram(self):
        """
        Tests Telegram connection.
        """
        self.telegrationConnectionResult.setText('Testing connection...')
        print(self.telegramApiKey.text())

    def download_data(self):
        self.backtestInfoLabel.setText("Downloading data...")

    def import_data(self):
        self.backtestInfoLabel.setText("Importing data...")

    def copy_settings_to_simulation(self):
        self.simulationIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.simulationTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())

        self.simulationAverageTypeComboBox.setCurrentIndex(self.averageTypeComboBox.currentIndex())
        self.simulationParameterComboBox.setCurrentIndex(self.parameterComboBox.currentIndex())
        self.simulationInitialValueSpinBox.setValue(self.initialValueSpinBox.value())
        self.simulationFinalValueSpinBox.setValue(self.finalValueSpinBox.value())

        self.simulationDoubleCrossCheckMark.setChecked(self.doubleCrossCheckMark.isChecked())
        self.simulationDoubleAverageComboBox.setCurrentIndex(self.doubleAverageComboBox.currentIndex())
        self.simulationDoubleParameterComboBox.setCurrentIndex(self.doubleParameterComboBox.currentIndex())
        self.simulationDoubleInitialValueSpinBox.setValue(self.doubleInitialValueSpinBox.value())
        self.simulationDoubleFinalValueSpinBox.setValue(self.doubleFinalValueSpinBox.value())

        self.simulationLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.simulationPriceLimitSpinBox.setValue(self.priceLimitSpinBox.value())
        self.simulationStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.simulationTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())

    def copy_settings_to_backtest(self):
        self.backtestIntervalComboBox.setCurrentIndex(self.intervalComboBox.currentIndex())
        self.backtestTickerComboBox.setCurrentIndex(self.tickerComboBox.currentIndex())

        self.backtestAverageTypeComboBox.setCurrentIndex(self.averageTypeComboBox.currentIndex())
        self.backtestParameterComboBox.setCurrentIndex(self.parameterComboBox.currentIndex())
        self.backtestInitialValueSpinBox.setValue(self.initialValueSpinBox.value())
        self.backtestFinalValueSpinBox.setValue(self.finalValueSpinBox.value())

        self.backtestDoubleCrossCheckMark.setChecked(self.doubleCrossCheckMark.isChecked())
        self.backtestDoubleAverageComboBox.setCurrentIndex(self.doubleAverageComboBox.currentIndex())
        self.backtestDoubleParameterComboBox.setCurrentIndex(self.doubleParameterComboBox.currentIndex())
        self.backtestDoubleInitialValueSpinBox.setValue(self.doubleInitialValueSpinBox.value())
        self.backtestDoubleFinalValueSpinBox.setValue(self.doubleFinalValueSpinBox.value())

        self.backtestLossPercentageSpinBox.setValue(self.lossPercentageSpinBox.value())
        self.backtestStopLossRadio.setChecked(self.stopLossRadio.isChecked())
        self.backtestTrailingLossRadio.setChecked(self.trailingLossRadio.isChecked())

    def toggle_double_cross_groupbox(self):
        self.toggle_groupbox(self.doubleCrossCheckMark, self.doubleCrossGroupBox)

    def toggle_simulation_double_cross_groupbox(self):
        self.toggle_groupbox(self.simulationDoubleCrossCheckMark, self.simulationDoubleCrossGroupBox)

    def toggle_backtest_double_cross_groupbox(self):
        self.toggle_groupbox(self.backtestDoubleCrossCheckMark, self.backtestDoubleCrossGroupBox)

    @staticmethod
    def toggle_groupbox(checkMark, groupBox):
        if checkMark.isChecked():
            groupBox.setEnabled(True)
        else:
            groupBox.setEnabled(False)


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
        savedPath = Data(loadData=False, interval=interval, symbol=symbol).get_current_interval_csv_data()

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


class About(QDialog):
    def __init__(self, parent=None):
        super(About, self).__init__(parent)  # Initializing object
        uic.loadUi(aboutUi, self)  # Loading the main UI


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
    palette.setColor(QPalette.Highlight, QColor(255, 140, 0))
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
    app.setStyle('Fusion')
    initialize_logger()
    interface = Interface()
    interface.showMaximized()
    app.setWindowIcon(QIcon('../media/algobotwolf.png'))
    sys.excepthook = except_hook
    sys.exit(app.exec_())


def except_hook(cls, exception, trace_back):
    sys.__excepthook__(cls, exception, trace_back)


if __name__ == '__main__':
    main()
