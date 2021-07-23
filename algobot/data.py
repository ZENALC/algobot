"""
Data object.
"""

import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Dict, List, Tuple, Union

import binance

from algobot.helpers import ROOT_DIR, SHORT_INTERVAL_MAP, get_logging_object, get_normalized_data, get_ups_and_downs
from algobot.typing_hints import DATA_TYPE


class Data:
    """
    Data object that will retrieve current and historical prices from the Binance API.
    """
    def __init__(self,
                 interval: str = '1h',
                 symbol: str = 'BTCUSDT',
                 load_data: bool = True,
                 update: bool = True,
                 log: bool = False,
                 log_file: str = 'data',
                 log_object: Logger = None,
                 precision: int = 2,
                 callback=None,
                 caller=None):
        """
        :param interval: Interval for which the data object will track prices.
        :param symbol: Symbol for which the data object will track prices.
        :param load_data: Boolean for whether data will be loaded or not.
        :param update: Boolean for whether data will be updated if it is loaded.
        :param log: Boolean for whether to log or not.
        :param log_file: Name of the logger file.
        :param log_object: Log object to use to log if provided.
        :param precision: Precision to round data to.
        :param callback: Signal for GUI to emit back to (if passed).
        :param caller: Caller of callback (if passed).
        """
        self.callback = callback  # Used to emit signals to GUI if provided.
        self.caller = caller  # Used to specify which caller emitted signals for GUI.
        self.binanceClient = binance.client.Client()  # Initialize Binance client to retrieve data.
        self.logger = get_logging_object(enable_logging=log, logFile=log_file, loggerObject=log_object)
        self.validate_interval(interval)  # Validate the interval provided.
        self.interval = interval  # Interval to trade in.
        self.intervalUnit, self.intervalMeasurement = self.get_interval_unit_and_measurement()
        self.precision = precision  # Decimal precision with which to show data.
        self.dataLimit = 2000  # Max amount of data to contain.
        self.downloadCompleted = False  # Boolean to determine whether data download is completed or not.
        self.downloadLoop = True  # Boolean to determine whether data is being downloaded or not.
        self.tickers = self.binanceClient.get_all_tickers()  # A list of all the tickers on Binance.
        self.symbol = symbol.upper()  # Symbol of data being used.
        self.validate_symbol(self.symbol)  # Validate symbol.
        self.data = []  # Total bot data.
        self.ema_dict = {}  # Cached past EMA data for memoization.
        self.rsi_data = {}  # Cached past RSI data for memoization.
        self.current_values = {  # This dictionary will hold current data values.
            'date_utc': datetime.now(tz=timezone.utc),
            'open': 0,
            'high': 0,
            'low': 0,
            'close': 0,
            'volume': 0,
            'quote_asset_volume': 0,
            'number_of_trades': 0,
            'taker_buy_base_asset': 0,
            'taker_buy_quote_asset': 0
        }

        self.databaseTable = f'data_{self.interval}'
        self.databaseFile = self.get_database_file()
        self.create_table()

        if load_data:
            # Create, initialize, store, and get values from database.
            self.load_data(update=update)

    @staticmethod
    def validate_interval(interval: str):
        """
        Validates interval. If incorrect interval, raises ValueError.
        :param interval: Interval to be checked in short form -> e.g. 12h for 12 hours
        """
        available_intervals = SHORT_INTERVAL_MAP.keys()
        if interval not in available_intervals:
            raise ValueError(f'Invalid interval {interval} given. Available intervals are: \n{available_intervals}')

    def validate_symbol(self, symbol: str):
        """
        Validates symbol for data to be retrieved. Raises ValueError if symbol type is incorrect.
        :param symbol: Symbol to be checked.
        """
        if symbol.strip() == '':
            raise ValueError("No symbol/ticker found.")
        if not self.is_valid_symbol(symbol):
            raise ValueError(f'Invalid symbol/ticker {symbol} provided.')

    def output_message(self, message: str, level: int = 2, printMessage: bool = False):
        """
        This function will log and optionally print the message provided.
        :param message: Messaged to be logged and potentially printed.
        :param level: Level message will be logged at.
        :param printMessage: Boolean that decides whether message will also be printed or not.
        """
        if printMessage:
            print(message)

        if self.logger:
            if level == 2:
                self.logger.info(message)
            elif level == 3:
                self.logger.debug(message)
            elif level == 4:
                self.logger.warning(message)
            elif level == 5:
                self.logger.critical(message)

    def get_database_file(self) -> str:
        """
        Retrieves database file path.
        :return: Database file path.
        """
        database_folder = os.path.join(ROOT_DIR, 'Databases')
        if not os.path.exists(database_folder):
            os.mkdir(database_folder)

        return os.path.join(database_folder, f'{self.symbol}.db')

    def create_table(self):
        """
        Creates a new table with interval if it does not exist.
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(f'''
                                CREATE TABLE IF NOT EXISTS {self.databaseTable}(
                                date_utc TEXT PRIMARY KEY,
                                open_price TEXT NOT NULL,
                                high_price TEXT NOT NULL,
                                low_price TEXT NOT NULL,
                                close_price TEXT NOT NULL,
                                volume TEXT NOT NULL,
                                quote_asset_volume TEXT NOT NULL,
                                number_of_trades TEXT NOT NULL,
                                taker_buy_base_asset TEXT NOT NULL,
                                taker_buy_quote_asset TEXT NOT NULL
                                );''')
                connection.commit()

    def dump_to_table(self, total_data: List[dict] = None) -> bool:
        """
        Dumps date and price information to database.
        :return: A boolean whether data entry was successful or not.
        """
        if total_data is None:
            total_data = self.data

        query = f'''INSERT INTO {self.databaseTable} (date_utc, open_price, high_price, low_price, close_price,
                    volume, quote_asset_volume, number_of_trades, taker_buy_base_asset, taker_buy_quote_asset)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);'''
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                for data in total_data:
                    try:
                        cursor.execute(query,
                                       (data['date_utc'].strftime('%Y-%m-%d %H:%M:%S'),
                                        data['open'],
                                        data['high'],
                                        data['low'],
                                        data['close'],
                                        data['volume'],
                                        data['quote_asset_volume'],
                                        data['number_of_trades'],
                                        data['taker_buy_base_asset'],
                                        data['taker_buy_quote_asset'],
                                        ))
                    except sqlite3.IntegrityError:
                        pass  # This just means the data already exists in the database, so ignore.
                    except sqlite3.OperationalError:
                        connection.commit()
                        self.output_message("Insertion to database failed. Will retry next run.", 4)
                        return False
            connection.commit()
        self.output_message("Successfully stored all new data to database.")
        return True

    def get_latest_database_row(self) -> list:
        """
        Returns the latest row from database table.
        :return: Row data or None depending on if value exists.
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(f'SELECT date_utc FROM {self.databaseTable} ORDER BY date_utc DESC LIMIT 1')
                return cursor.fetchone()

    def get_data_from_database(self):
        """
        Loads data from database and appends it to run-time data.
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                rows = cursor.execute(f'''
                        SELECT 
                        "date_utc", 
                        "open_price", 
                        "high_price", 
                        "low_price", 
                        "close_price", 
                        "volume",
                        "quote_asset_volume", 
                        "number_of_trades", 
                        "taker_buy_base_asset", 
                        "taker_buy_quote_asset"
                        FROM {self.databaseTable} ORDER BY date_utc
                        ''').fetchall()

        if len(rows) > 0:
            self.output_message("Retrieving data from database...")
        else:
            self.output_message("No data found in database.")

        for row in rows:
            date_utc = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            normalized_data = get_normalized_data(data=row, date_in_utc=date_utc)
            self.data.append(normalized_data)

    def database_is_updated(self) -> bool:
        """
        Checks if data is updated or not with database by interval provided in accordance to UTC time.
        :return: A boolean whether data is updated or not.
        """
        result = self.get_latest_database_row()
        if result is None:
            return False
        latest_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return self.is_latest_date(latest_date)

    # noinspection PyProtectedMember
    def get_latest_timestamp(self) -> int:
        """
        Returns latest timestamp available based on database.
        :return: Latest timestamp.
        """
        result = self.get_latest_database_row()
        if result is None:
            # pylint: disable=protected-access
            return self.binanceClient._get_earliest_valid_timestamp(self.symbol, self.interval)
        else:
            latest_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            return int(latest_date.timestamp()) * 1000 + 1  # Converting timestamp to milliseconds

    def load_data(self, update: bool = True):
        """
        Loads data to Data object.
        :param update: Boolean that determines whether data is updated or not.
        """
        self.get_data_from_database()
        if update:
            if not self.database_is_updated():
                self.output_message("Updating data...")
                self.update_database_and_data()
            else:
                self.output_message("Database is up-to-date.")

    # noinspection PyProtectedMember
    def update_database_and_data(self):
        """
        Updates database by retrieving information from Binance API
        """
        result = self.get_latest_database_row()
        if result is None:  # Then get the earliest timestamp possible.
            # pylint: disable = protected-access
            timestamp = self.binanceClient._get_earliest_valid_timestamp(self.symbol, self.interval)
            self.output_message(f'Downloading all available historical data for {self.interval} intervals.')
        else:
            latest_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            timestamp = int(latest_date.timestamp()) * 1000  # Converting timestamp to milliseconds
            date_with_interval_added = latest_date + timedelta(minutes=self.get_interval_minutes())
            self.output_message(f"Previous data up to UTC {date_with_interval_added} found.")

        if not self.database_is_updated():
            new_data = self.get_new_data(timestamp)
            self.output_message("Successfully downloaded all new data.")
            self.output_message("Inserting data to live program...")
            self.insert_data(new_data)
            self.output_message("Storing updated data to database...")
            self.dump_to_table(self.data[-len(new_data):])
        else:
            self.output_message("Database is up-to-date.")

    # noinspection PyProtectedMember
    def custom_get_new_data(self, limit: int = 500, progress_callback=None, locked=None, removeFirst: bool = False,
                            caller=-1) -> List[dict]:
        """
        Returns new data from Binance API from timestamp specified, however this one is custom-made.
        :param caller: Caller that called this function. Only used for botThread.
        :param removeFirst: Boolean whether newest data is removed or not.
        :param locked: Signal to emit back to GUI when storing data. Cannot be canceled once here. Used for databases.
        :param progress_callback: Signal to emit back to GUI to show progress.
        :param limit: Limit per pull.
        :return: A list of dictionaries.
        """
        # This code below is taken from binance client and slightly refactored to make usage of completion percentages.
        self.downloadLoop = True
        output_data = []  # Initialize our list
        timeframe = binance.client.interval_to_milliseconds(self.interval)
        start_ts = total_beginning_timestamp = self.get_latest_timestamp()
        end_progress = time.time() * 1000 - total_beginning_timestamp
        idx = 0

        while self.downloadLoop:
            temp_data = self.binanceClient.get_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=limit,
                startTime=start_ts,
                endTime=None
            )

            if len(temp_data) == 0:
                break

            output_data += temp_data
            start_ts = temp_data[-1][0]
            if progress_callback:
                progress = (start_ts - total_beginning_timestamp) / end_progress * 94
                progress_callback.emit(int(progress), "Downloading data...", caller)

            idx += 1
            # check if we received less than the required limit and exit the loop
            if len(temp_data) < limit:
                # exit the while loop
                break

            # increment next call by our timeframe
            start_ts += timeframe

            # sleep after every 5th call to be kind to the API
            if idx % 5 == 0:
                time.sleep(1)

        if not self.downloadLoop:
            progress_callback.emit(-1, "Download canceled.", caller)
            return []

        if locked:  # If we have a callback for emitting lock signals.
            locked.emit()

        if removeFirst:
            output_data.pop()

        progress_callback.emit(95, "Saving data...", caller)
        self.insert_data(output_data)
        progress_callback.emit(97, "This may take a while. Dumping data to database...", caller)

        start_index_for_dump = -len(output_data)

        if removeFirst:  # We don't want current data as it's not the latest data.
            self.dump_to_table(self.data[start_index_for_dump:])
        else:  # Strip off last element because it contains current info which we don't want to store.
            self.dump_to_table(self.data[start_index_for_dump:-1])

        progress_callback.emit(100, "Downloaded all new data successfully.", caller)
        self.downloadLoop = False
        self.downloadCompleted = True
        return self.data

    def get_new_data(self, timestamp: int, limit: int = 1000, get_current: bool = False) -> list:
        """
        Returns new data from Binance API from timestamp specified.
        :param timestamp: Initial timestamp.
        :param limit: Limit per pull.
        :param get_current: Boolean for whether to include current period's data.
        :return: A list of dictionaries.
        """
        new_data = self.binanceClient.get_historical_klines(self.symbol, self.interval, timestamp + 1, limit=limit)
        self.downloadCompleted = True
        if len(new_data[:-1]) == 0:
            raise RuntimeError("No data was fetched from Binance. Please check Binance server.")

        if get_current:
            return new_data
        else:
            return new_data[:-1]  # Up to -1st index, because we don't want current period data.

    def is_latest_date(self, latest_date: datetime) -> bool:
        """
        Checks whether the latest date available is the latest period available.
        :param latest_date: Datetime object.
        :return: True or false whether date is latest period or not.
        """
        minutes = self.get_interval_minutes()
        current_date = latest_date + timedelta(minutes=minutes) + timedelta(seconds=5)  # 5s leeway for server update
        return current_date >= datetime.now(timezone.utc) - timedelta(minutes=minutes)

    def data_is_updated(self) -> bool:
        """
        Checks whether data is fully updated or not.
        :return: A boolean whether data is updated or not with Binance values.
        """
        latest_date = self.data[-1]['date_utc']
        return self.is_latest_date(latest_date)

    def insert_data(self, new_data: List[List[str]]):
        """
        Inserts data from newData to run-time data.
        :param new_data: List with new data values.
        """
        for data in new_data:
            parsed_date = datetime.fromtimestamp(int(data[0]) / 1000, tz=timezone.utc)
            current_dict = get_normalized_data(data=data, date_in_utc=parsed_date)
            self.data.append(current_dict)

    def update_data(self, verbose: bool = False):
        """
        Updates run-time data with Binance API values.
        """
        latest_date = self.data[-1]['date_utc']
        timestamp = int(latest_date.timestamp()) * 1000
        date_with_interval_added = latest_date + timedelta(minutes=self.get_interval_minutes())
        if verbose:
            self.output_message(f"Previous data found up to UTC {date_with_interval_added}.")
        if not self.data_is_updated():
            # self.try_callback("Found new data. Attempting to update...")
            new_data = []
            while len(new_data) == 0:
                time.sleep(0.5)  # Sleep half a second for server to refresh new values.
                new_data = self.get_new_data(timestamp)
            self.insert_data(new_data)
            if verbose:
                self.output_message("Data has been updated successfully.\n")
            # self.try_callback("Updated data successfully.")
        else:
            self.output_message("Data is up-to-date.\n")

    def remove_past_data_if_needed(self):
        """
        Remove past data when over data limit.
        """
        if len(self.data) > self.dataLimit:  # Remove past data.
            self.dump_to_table()
            self.data = self.data[self.dataLimit // 2:]

    def get_current_data(self, counter: int = 0) -> Dict[str, Union[str, float]]:
        """
        Retrieves current market dictionary with open, high, low, close prices.
        :param counter: Counter to check how many times bot is trying to retrieve current data.
        :return: A dictionary with current open, high, low, and close prices.
        """
        try:
            self.remove_past_data_if_needed()
            if not self.data_is_updated():
                self.update_data()

            current_interval = self.data[-1]['date_utc'] + timedelta(minutes=self.get_interval_minutes())
            current_timestamp = int(current_interval.timestamp() * 1000)

            next_interval = current_interval + timedelta(minutes=self.get_interval_minutes())
            next_timestamp = int(next_interval.timestamp() * 1000) - 1
            current_data = self.binanceClient.get_klines(symbol=self.symbol,
                                                         interval=self.interval,
                                                         startTime=current_timestamp,
                                                         endTime=next_timestamp,
                                                         )[0]
            self.current_values = get_normalized_data(data=current_data, date_in_utc=current_interval)

            if counter > 0:
                self.try_callback("Successfully reconnected.")

            return self.current_values
        except Exception as e:
            sleep_time = 5 + counter * 2
            error_message = f"Error: {e}. Retrying in {sleep_time} seconds..."
            self.output_message(error_message, 4)
            self.try_callback(f"Internet connectivity issue detected. Trying again in {sleep_time} seconds.")
            self.ema_dict = {}  # Reset EMA cache as it could be corrupted.
            time.sleep(sleep_time)
            return self.get_current_data(counter=counter + 1)

    def try_callback(self, message: str):
        """
        Attempts to emit a signal to the GUI that called this data object (if it was called by a GUI).
        :param message: Message to send back.
        """
        if self.callback and self.caller is not None:
            self.callback.emit(self.caller, message)

    def get_current_price(self) -> float:
        """
        Returns the current market ticker price.
        :return: Ticker market price
        """
        try:
            return float(self.binanceClient.get_symbol_ticker(symbol=self.symbol)['price'])
        except Exception as e:
            error_message = f'Error: {e}. Retrying in 15 seconds...'
            self.output_message(error_message, 4)
            self.try_callback(message=error_message)
            time.sleep(15)
            return self.get_current_price()

    def get_interval_unit_and_measurement(self) -> Tuple[str, int]:
        """
        Returns interval unit and measurement.
        :return: A tuple with interval unit and measurement respectively.
        """
        unit = self.interval[-1]  # Gets the unit of the interval. eg 12h = h
        measurement = int(self.interval[:-1])  # Gets the measurement, eg 12h = 12
        return unit, measurement

    def get_interval_minutes(self) -> int:
        """
        Returns interval minutes.
        :return: An integer representing the minutes for an interval.
        """
        if self.intervalUnit == 'h':
            return self.intervalMeasurement * 60
        elif self.intervalUnit == 'm':
            return self.intervalMeasurement
        elif self.intervalUnit == 'd':
            return self.intervalMeasurement * 24 * 60
        else:
            raise ValueError("Invalid interval.", 4)

    def write_csv_data(self, total_data: list, file_name: str, army_time: bool = True) -> str:
        """
        Writes CSV data to CSV folder in root directory of application.
        :param army_time: Boolean if date will be in army type. If false, data will be in standard type.
        :param total_data: Data to write to CSV file.
        :param file_name: Filename to name CSV in.
        :return: Absolute path to CSV file.
        """
        dir_path = os.path.join(ROOT_DIR, "CSV", self.symbol)
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, file_name)
        with open(file_path, 'w') as f:
            f.write("Date_UTC, Open, High, Low, Close, Volume, Quote_Asset_Volume, Number_of_Trades, "
                    "Taker_Buy_Base_Asset, Taker_Buy_Quote_Asset\n")
            for data in total_data:
                if army_time:
                    parsed_date = data['date_utc'].strftime("%m/%d/%Y %H:%M")
                else:
                    parsed_date = data['date_utc'].strftime("%m/%d/%Y %I:%M %p")
                f.write(f'{parsed_date}, {data["open"]}, {data["high"]}, {data["low"]}, {data["close"]}, '
                        f'{data["volume"]}, {data["quote_asset_volume"]}, {data["number_of_trades"]}, '
                        f'{data["taker_buy_base_asset"]}, {data["taker_buy_quote_asset"]}\n')

        return file_path

    def create_csv_file(self, descending: bool = True, army_time: bool = True, start_date: datetime = None) -> str:
        """
        Creates a new CSV file with current interval and returns the absolute path to file.
        :param start_date: Date to have CSV data from.
        :param descending: Boolean that decides whether values in CSV are in descending format or not.
        :param army_time: Boolean that dictates whether dates will be written in army-time format or not.
        """
        file_name = f'{self.symbol}_data_{self.interval}.csv'

        data = self.data
        if start_date is not None:  # Getting data to start from.
            for index, period in enumerate(data):
                if period['date_utc'].date() <= start_date:
                    data = self.data[index:]
                    break

        if descending:
            path = self.write_csv_data(data[::-1], file_name=file_name, army_time=army_time)
        else:
            path = self.write_csv_data(data, file_name=file_name, army_time=army_time)

        self.output_message(f'Data saved to {path}.')
        return path

    def is_valid_symbol(self, symbol: str) -> bool:
        """
        Checks whether the symbol provided is valid or not for Binance.
        :param symbol: Symbol to be checked.
        :return: A boolean whether the symbol is valid or not.
        """
        for ticker in self.tickers:
            if ticker['symbol'] == symbol:
                return True
        return False

    def is_valid_average_input(self, shift: int, prices: int, extra_shift: int = 0) -> bool:
        """
        Checks whether shift, prices, and (optional) extraShift are valid.
        :param shift: Periods from current period.
        :param prices: Amount of prices to iterate over.
        :param extra_shift: Extra shift for EMA.
        :return: A boolean whether shift, prices, and extraShift are logical or not.
        TODO: Deprecate along with helper get EMA and RSI.
        """
        if shift < 0:
            self.output_message("Shift cannot be less than 0.")
            return False
        elif prices <= 0:
            self.output_message("Prices cannot be 0 or less than 0.")
            return False
        elif shift + extra_shift + prices > len(self.data) + 1:
            self.output_message("Shift + prices period cannot be more than data available.")
            return False
        return True

    def verify_integrity(self) -> DATA_TYPE:
        """
        Verifies integrity of data by checking if there's any repeated data.
        :return: List of duplicate data found.
        """
        if len(self.data) < 1:
            return []

        errored_data = []
        previous_data = self.data[0]
        for data in self.data[1:]:
            if data['date_utc'] != previous_data['date_utc']:
                errored_data.append(data)

            previous_data = data

        return errored_data

    def get_total_non_updated_data(self) -> DATA_TYPE:
        """
        Get total non-updated data. TODO: Deprecate this function.
        :return: Total non-updated data.
        """
        return self.data + [self.current_values]

    @staticmethod
    def helper_get_ema(up_data: list, down_data: list, periods: int) -> tuple:
        """
        Helper function to get the EMA for relative strength index.
        :param down_data: Other data to get EMA of.
        :param up_data: Data to get EMA of.
        :param periods: Number of periods to iterate through.
        :return: EMA
        """
        ema_up = up_data[0]
        ema_down = down_data[0]
        alpha = 1 / periods

        for index in range(1, len(up_data)):
            ema_up = up_data[index] * alpha + ema_up * (1 - alpha)
            ema_down = down_data[index] * alpha + ema_down * (1 - alpha)

        return ema_up, ema_down

    def get_rsi(self, prices: int = 14, parameter: str = 'close', shift: int = 0, round_value: bool = True,
                update: bool = True) -> float:
        """
        Returns relative strength index.
        :param update: Boolean for whether function should call API and get latest data or not.
        :param prices: Amount of prices to iterate through.
        :param parameter: Parameter to use for iterations. By default, it's close.
        :param shift: Amount of prices to shift prices by.
        :param round_value: Boolean that determines whether final value is rounded or not.
        :return: Final relative strength index.
        """
        if not self.is_valid_average_input(shift, prices):
            raise ValueError('Invalid input specified.')

        if shift > 0:
            update_dict = False
            data = self.data
            shift -= 1
        else:
            update_dict = True
            data = self.data + [self.get_current_data()] if update else self.get_total_non_updated_data()

        start = len(data) - 500 - prices - shift if len(data) > 500 + prices + shift else 0
        ups, downs = get_ups_and_downs(data=data[start:len(data) - shift], parameter=parameter)
        average_up, average_down = self.helper_get_ema(ups, downs, prices)
        rs = average_up / average_down
        rsi = 100 - 100 / (1 + rs)

        if shift == 0 and update_dict:
            self.rsi_data[prices] = rsi

        if round_value:
            return round(rsi, self.precision)
        return rsi
