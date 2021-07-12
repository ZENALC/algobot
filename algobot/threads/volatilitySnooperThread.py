# TODO: Standardize thread operations to fewer files by leveraging kwargs.
import datetime

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

import algobot
from algobot.algorithms import (get_basic_volatility, get_gk_volatility,
                                get_parkinson_volatility, get_rs_volatility,
                                get_zh_volatility)
from algobot.helpers import (convert_long_interval, get_interval_minutes,
                             get_normalized_data)


class VolatilitySnooperSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    # pylint: disable=too-few-public-methods
    progress = pyqtSignal(int)
    activity = pyqtSignal(str)
    error = pyqtSignal(str)
    restore = pyqtSignal()
    started = pyqtSignal()
    finished = pyqtSignal(dict)


class VolatilitySnooperThread(QRunnable):
    def __init__(self, periods, interval, volatility, tickers, filter_word=None):
        super(VolatilitySnooperThread, self).__init__()
        self.periods = periods
        self.long_interval = interval
        self.short_interval = convert_long_interval(interval)
        self.volatility = volatility
        self.volatility_func = self.get_volatility_func()
        self.filter_word = filter_word
        self.tickers = self.get_filtered_tickers(tickers=tickers, filter_word=filter_word)
        self.binanceClient = algobot.BINANCE_CLIENT
        self.running = True
        self.signals = VolatilitySnooperSignals()

    @staticmethod
    def get_filtered_tickers(tickers, filter_word):
        if filter_word == '':
            filter_word = None

        if filter_word is not None:
            tickers = [ticker for ticker in tickers if filter_word.upper() in ticker]

        return tickers

    def get_volatility_func(self):
        volatility_map = {
            'basic': get_basic_volatility,
            'yang zhang': get_zh_volatility,
            'rogers satchell': get_rs_volatility,
            'garman-klass': get_gk_volatility,
            'parkinson': get_parkinson_volatility
        }
        return volatility_map[self.volatility.lower()]

    @staticmethod
    def get_current_timestamp():
        dt = datetime.datetime.now(datetime.timezone.utc)
        utc_time = dt.replace(tzinfo=datetime.timezone.utc)
        utc_timestamp = utc_time.timestamp()

        return utc_timestamp

    def get_starting_timestamp(self, multiplier: int = 1) -> int:
        current_timestamp = self.get_current_timestamp() * 1000
        period_minutes = get_interval_minutes(self.long_interval)
        period_microseconds = period_minutes * 60 * 1000 * (self.periods + 1)  # Using +1 for safety.

        return int(current_timestamp - period_microseconds * multiplier)

    def validate(self):
        if len(self.tickers) < 1:
            raise RuntimeError(f"No tickers found with the filter: {self.filter_word}.")

    def snoop(self):
        self.validate()
        self.signals.activity.emit('Starting the volatility snooper...')
        volatility_dict = {}
        for index, ticker in enumerate(self.tickers):
            if not self.running:
                break

            self.signals.activity.emit(f"Gathering volatility for {ticker}...")
            self.signals.progress.emit(int(index / len(self.tickers) * 100))

            data = self.binanceClient.get_historical_klines(ticker, self.short_interval, self.get_starting_timestamp())
            data_length = len(data)

            multiplier = 2
            impossible = False

            while len(data) < self.periods + 1:
                starting_timestamp = self.get_starting_timestamp(multiplier=multiplier)
                data = self.binanceClient.get_historical_klines(ticker, self.short_interval, starting_timestamp)
                multiplier += 1

                if len(data) == data_length:
                    impossible = True
                    break
                else:
                    data_length = len(data)

            if impossible:
                volatility_dict[ticker] = "Not enough data. Maybe the ticker is too new."
            else:
                data = [get_normalized_data(d) for d in data]
                volatility_dict[ticker] = self.volatility_func(periods=self.periods, data=data)

        return volatility_dict

    def stop(self):
        self.running = False

    @pyqtSlot()
    def run(self):
        try:
            self.signals.started.emit()
            volatility_dict = self.snoop()
            self.signals.finished.emit(volatility_dict)
        except Exception as e:
            algobot.MAIN_LOGGER.exception(repr(e))
            self.signals.error.emit(str(e))
        finally:
            self.running = False
            self.signals.restore.emit()
