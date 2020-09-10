import sys
import trader
import logging
from datetime import datetime

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication

app = QApplication(sys.argv)
uiFile = 'nigerianPrince.ui'


class TradingBot(QMainWindow):
    def __init__(self, parent=None):
        super(TradingBot, self).__init__(parent)  # Initializing object
        uic.loadUi(uiFile, self)  # Loading the UI
        self.doubleCrossCheckMark.toggled.connect(self.interact_double_cross)
        self.generateCSVButton.clicked.connect(self.generate_csv)

        self.timestamp_message('Greetings.')

    def generate_csv(self):
        interval = self.dataIntervalComboBox.currentText()
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
        interval = intervals[interval]
        # self.dummyTrader.get_csv_data()

    def timestamp_message(self, msg):
        self.botOutput.appendPlainText(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {msg}')

    def add_trade_to_list_view(self, msg):
        self.tradesListWidget.addItem(msg)

    def interact_double_cross(self):
        if self.doubleCrossCheckMark.isChecked():
            self.doubleCrossGroupBox.setEnabled(True)
        else:
            self.doubleCrossGroupBox.setEnabled(False)


def main():
    tradingBot = TradingBot()

    class CustomTrader(trader.Trader, tradingBot):
        def output_message(self, message, level=2):
            print(message)
            if level == 2:
                logging.info(message)
            elif level == 3:
                logging.debug(message)
            elif level == 4:
                logging.warning(message)
            elif level == 5:
                logging.critical(message)

    tradingBot.show()
    app.exec_()


if __name__ == 'main':
    main()

