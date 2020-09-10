import sqlite3
import os
import time
import logging
from datetime import datetime, timedelta, timezone
from contextlib import closing
from binance.client import Client


class Data:
    def __init__(self, interval='1h', symbol='BTCUSDT'):
        """
        Data object that will retrieve current and historical prices from the Binance API and calculate moving averages.
        :param interval: Interval for which the data object will track prices.
        :param symbol: Symbol for which the data object will track prices.
        """
        if not self.is_valid_interval(interval):
            output_message("Invalid interval. Using default interval of 1h.", level=4)
            interval = '1h'

        self.interval = interval
        self.intervalUnit, self.intervalMeasurement = self.get_interval_unit_and_measurement()

        if not self.is_valid_symbol(symbol):
            output_message('Invalid symbol. Using default symbol of BTCUSDT.', level=4)
            symbol = 'BTCUSDT'

        self.symbol = symbol
        self.data = []
        self.ema_data = {}
        self.binanceClient = Client(None, None)  # Initialize Binance client

        # Create, initialize, store, and get values from database.
        self.databaseFile = 'btc.db'
        self.databaseTable = f'data_{self.interval}'
        self.create_table()
        self.get_data_from_database()
        if not self.database_is_updated():
            output_message("Updating data...")
            self.update_database()
        else:
            output_message("Database is up-to-date.")

    def create_table(self):
        """
        Creates a new table with interval if it does not exist
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(f'''
                                CREATE TABLE IF NOT EXISTS {self.databaseTable}(
                                trade_date TEXT PRIMARY KEY,
                                open_price TEXT NOT NULL,
                                high_price TEXT NOT NULL,
                                low_price TEXT NOT NULL,
                                close_price TEXT NOT NULL
                                );''')
                connection.commit()

    def dump_to_table(self):
        """
        Dumps date and price information to database.
        :return: A boolean whether data entry was successful or not.
        """
        query = f'''INSERT INTO {self.databaseTable} (trade_date, open_price, high_price, low_price, close_price) 
                    VALUES (?, ?, ?, ?, ?);'''
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                for data in self.data:
                    try:
                        cursor.execute(query,
                                       (data['date'].strftime('%Y-%m-%d %H:%M:%S'),
                                        data['open'],
                                        data['high'],
                                        data['low'],
                                        data['close'],
                                        ))
                        connection.commit()
                    except sqlite3.IntegrityError:
                        pass  # This just means the data already exists in the database, so ignore.
                    except sqlite3.OperationalError:
                        output_message("Insertion to database failed. Will retry next run.", 4)
                        return False
        output_message("Successfully stored all new data to database.")
        return True

    def get_latest_database_row(self):
        """
        Returns the latest row from database table.
        :return: Row data or None depending on if value exists.
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(f'SELECT trade_date FROM {self.databaseTable} ORDER BY trade_date DESC LIMIT 1')
                return cursor.fetchone()
            
    def get_data_from_database(self):
        """
        Loads data from database and appends it to run-time data.
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                rows = cursor.execute(f'''
                        SELECT "trade_date", "open_price","high_price", "low_price", "close_price"
                        FROM {self.databaseTable} ORDER BY trade_date DESC
                        ''').fetchall()

        if len(rows) > 0:
            output_message("Retrieving data from database...")
        else:
            output_message("No data found in database.")
            return

        for row in rows:
            self.data.append({'date': datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc),
                              'open': float(row[1]),
                              'high': float(row[2]),
                              'low': float(row[3]),
                              'close': float(row[4]),
                              })

    def database_is_updated(self):
        """
        Checks if data is updated or not with database by interval provided in accordance to UTC time.
        :return: A boolean whether data is updated or not.
        """
        result = self.get_latest_database_row()
        if result is None:
            return False
        latestDate = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return self.is_latest_date(latestDate)

    def update_database(self):
        """
        Updates database by retrieving information from Binance API
        """
        result = self.get_latest_database_row()
        if result is None:  # Then get the earliest timestamp possible
            timestamp = self.binanceClient._get_earliest_valid_timestamp(self.symbol, self.interval)
            output_message(f'Downloading all available historical data for {self.interval} intervals.')
        else:
            latestDate = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            timestamp = int(latestDate.timestamp()) * 1000  # Converting timestamp to milliseconds
            dateWithIntervalAdded = latestDate + timedelta(minutes=self.get_interval_minutes())
            output_message(f"Previous data up to UTC {dateWithIntervalAdded} found.")

        if not self.database_is_updated():
            newData = self.get_new_data(timestamp)
            output_message("Successfully downloaded all new data.")
            output_message("Inserting data to live program...")
            self.insert_data(newData)
            output_message("Storing updated data to database...")
            self.dump_to_table()
        else:
            output_message("Database is up-to-date.")

    def get_new_data(self, timestamp, limit=1000):
        """
        Returns new data from Binance API from timestamp specified.
        :param timestamp: Initial timestamp.
        :param limit: Limit per pull.
        :return: A list of dictionaries.
        """
        newData = self.binanceClient.get_historical_klines(self.symbol, self.interval, timestamp + 1, limit=limit)
        return newData[:-1]  # Up to -1st index, because we don't want current period data.

    def is_latest_date(self, latestDate):
        """
        Checks whether the latest date available is the latest period available.
        :param latestDate: Datetime object.
        :return: True or false whether date is latest period or not.
        """
        minutes = self.get_interval_minutes()
        return latestDate + timedelta(minutes=minutes) >= datetime.now(timezone.utc) - timedelta(minutes=minutes)

    def data_is_updated(self):
        """
        Checks whether data is fully updated or not.
        :return: A boolean whether data is updated or not with Binance values.
        """
        latestDate = self.data[0]['date']
        return self.is_latest_date(latestDate)

    def insert_data(self, newData):
        """
        Inserts data from newData to run-time data.
        :param newData: List with new data values.
        """
        for data in newData:
            parsedDate = datetime.fromtimestamp(int(data[0]) / 1000, tz=timezone.utc)
            self.data.insert(0, {'date': parsedDate,
                                 'open': float(data[1]),
                                 'high': float(data[2]),
                                 'low': float(data[3]),
                                 'close': float(data[4]),
                                 })

    def update_data(self):
        """
        Updates run-time data with Binance API values.
        """
        latestDate = self.data[0]['date']
        timestamp = int(latestDate.timestamp()) * 1000
        dateWithIntervalAdded = latestDate + timedelta(minutes=self.get_interval_minutes())
        output_message(f"Previous data found up to UTC {dateWithIntervalAdded}.")
        if not self.data_is_updated():
            newData = self.get_new_data(timestamp)
            self.insert_data(newData)
            output_message("Data has been updated successfully.")
        else:
            output_message("Data is up-to-date.")

    def get_current_data(self):
        """
        Retrieves current market dictionary with open, high, low, close prices.
        :return: A dictionary with current open, high, low, and close prices.
        """
        try:
            if not self.data_is_updated():
                self.update_data()

            currentInterval = self.data[0]['date'] + timedelta(minutes=self.get_interval_minutes())
            currentTimestamp = int(currentInterval.timestamp() * 1000)

            nextInterval = currentInterval + timedelta(minutes=self.get_interval_minutes())
            nextTimestamp = int(nextInterval.timestamp() * 1000) - 1
            currentData = self.binanceClient.get_klines(symbol=self.symbol,
                                                        interval=self.interval,
                                                        startTime=currentTimestamp,
                                                        endTime=nextTimestamp,
                                                        )[0]
            currentDataDictionary = {'date': currentInterval,
                                     'open': float(currentData[1]),
                                     'high': float(currentData[2]),
                                     'low': float(currentData[3]),
                                     'close': float(currentData[4])}
            return currentDataDictionary
        except Exception as e:
            output_message(f"Error: {e}. Retrying in 2 seconds...", 4)
            time.sleep(2)
            self.get_current_data()

    def get_current_price(self):
        """
        Returns the current market BTC price.
        :return: BTC market price
        """
        try:
            return float(self.binanceClient.get_symbol_ticker(symbol=self.symbol)['price'])
        except Exception as e:
            output_message(f'Error: {e}. Retrying in 2 seconds...', 4)
            time.sleep(2)
            self.get_current_price()

    def get_interval_unit_and_measurement(self):
        """
        Returns interval unit and measurement.
        :return: A tuple with interval unit and measurement respectively.
        """
        unit = self.interval[-1]  # Gets the unit of the interval. eg 12h = h
        measurement = int(self.interval[:-1])  # Gets the measurement, eg 12h = 12
        return unit, measurement

    def get_interval_minutes(self):
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
            output_message("Invalid interval.", 4)
            return None

    def get_csv_data(self, interval):
        """
        Creates a new CSV file with interval specified.
        :param interval: Interval to get data for.
        """
        if not self.is_valid_interval(interval):
            return
        timestamp = self.binanceClient._get_earliest_valid_timestamp(self.symbol, interval)
        output_message("Downloading all available historical data. This may take a while...")
        newData = self.binanceClient.get_historical_klines(self.symbol, interval, timestamp, limit=1000)
        output_message("Downloaded all data successfully.")

        folderName = 'CSV'
        fileName = f'btc_data_{interval}.csv'
        currentPath = os.getcwd()

        try:
            os.mkdir(folderName)
        except OSError:
            pass
        finally:
            os.chdir(folderName)

        with open(fileName, 'w') as f:
            f.write("Date_UTC, Open, High, Low, Close\n")
            for data in newData:
                parsedDate = datetime.fromtimestamp(int(data[0]) / 1000, tz=timezone.utc).strftime("%m/%d/%Y %I:%M %p")
                f.write(f'{parsedDate}, {data[1]}, {data[2]}, {data[3]}, {data[4]}\n')

        path = os.path.join(os.getcwd(), fileName)
        output_message(f'Data saved to {path}.')
        os.chdir(currentPath)

    @staticmethod
    def is_valid_interval(interval):
        """
        Returns whether interval provided is valid or not.
        :param interval: Interval argument.
        :return: A boolean whether the interval is valid or not.
        """
        availableIntervals = ('12h', '15m', '1d', '1h',
                              '1m', '2h', '30m', '3d', '3m', '4h', '5m', '6h', '8h')
        if interval in availableIntervals:
            return True
        else:
            output_message(f'Invalid interval. Available intervals are: \n{availableIntervals}')
            return False

    def is_valid_symbol(self, symbol):
        """
        Checks whether the symbol provided is valid or not for Binance.
        :param symbol: Symbol to be checked.
        :return: A boolean whether the symbol is valid or not.
        """
        tickers = self.binanceClient.get_all_tickers()
        for ticker in tickers:
            if ticker['symbol'] == symbol:
                return True
        return False

    def is_valid_average_input(self, shift, prices, extraShift=0):
        """
        Checks whether shift, prices, and (optional) extraShift are valid.
        :param shift: Periods from current period.
        :param prices: Amount of prices to iterate over.
        :param extraShift: Extra shift for EMA.
        :return: A boolean whether shift, prices, and extraShift are logical or not.
        """
        if shift < 0:
            output_message("Shift cannot be less than 0.")
            return False
        elif prices <= 0:
            output_message("Prices cannot be 0 or less than 0.")
            return False
        elif shift + extraShift + prices > len(self.data) + 1:
            output_message("Shift + prices period cannot be more than data available.")
            return False
        return True

    def verify_integrity(self):
        """
        Verifies integrity of data by checking if there's any repeated data.
        :return: A boolean whether the data contains no repeated data or not.
        """
        if len(self.data) < 1:
            output_message("No data found.", 4)
            return False

        previousData = self.data[0]
        for data in self.data[1:]:
            if data['date'] == previousData['date']:
                output_message("Repeated data detected.", 4)
                output_message(f'Previous data: {previousData}', 4)
                output_message(f'Next data: {data}', 4)
                return False
            previousData = data

        output_message("Data has been verified to be correct.")
        return True

    def get_sma(self, prices, parameter, shift=0, round_value=True):
        """
        Returns the simple moving average with run-time data and prices provided.
        :param boolean round_value: Boolean that specifies whether return value should be rounded
        :param int prices: Number of values for average
        :param int shift: Prices shifted from current price
        :param str parameter: Parameter to get the average of (e.g. open, close, high or low values)
        :return: SMA
        """
        if not self.is_valid_average_input(shift, prices):
            return None

        data = [self.get_current_data()] + self.data  # Data is current data + all-time period data
        data = data[shift: prices + shift]  # Data now starts from shift and goes up to prices + shift

        sma = sum([period[parameter] for period in data]) / prices
        if round_value:
            return round(sma, 2)
        return sma

    def get_wma(self, prices, parameter, shift=0, round_value=True):
        """
        Returns the weighted moving average with run-time data and prices provided.
        :param shift: Prices shifted from current period.
        :param boolean round_value: Boolean that specifies whether return value should be rounded
        :param int prices: Number of prices to loop over for average
        :param parameter: Parameter to get the average of (e.g. open, close, high or low values)
        :return: WMA
        """
        if not self.is_valid_average_input(shift, prices):
            return None

        data = [self.get_current_data()] + self.data
        total = data[shift][parameter] * prices  # Current total is first data period multiplied by prices.
        data = data[shift + 1: prices + shift]  # Data now does not include the first shift period.

        index = 0
        for x in range(prices - 1, 0, -1):
            total += x * data[index][parameter]
            index += 1

        divisor = prices * (prices + 1) / 2
        wma = total / divisor
        if round_value:
            return round(wma, 2)
        return wma

    def get_ema(self, prices, parameter, shift=0, sma_prices=5, round_value=True):
        """
        Returns the exponential moving average with data provided.
        :param shift: Prices shifted from current period.
        :param round_value: Boolean that specifies whether return value should be rounded
        :param int sma_prices: SMA prices to get first EMA over
        :param int prices: Days to iterate EMA over (or the period)
        :param str parameter: Parameter to get the average of (e.g. open, close, high, or low values)
        :return: EMA
        """
        if not self.is_valid_average_input(shift, prices, sma_prices):
            return None
        elif sma_prices <= 0:
            output_message("Initial amount of SMA values for initial EMA must be greater than 0.")
            return None

        data = [self.get_current_data()] + self.data
        sma_shift = len(data) - sma_prices
        ema = self.get_sma(sma_prices, parameter, shift=sma_shift, round_value=False)
        values = [(round(ema, 2), str(data[sma_shift]['date']))]
        multiplier = 2 / (prices + 1)

        for day in range(len(data) - sma_prices - shift):
            current_index = len(data) - sma_prices - day - 1
            current_price = data[current_index][parameter]
            ema = current_price * multiplier + ema * (1 - multiplier)
            values.append((round(ema, 2), str(data[current_index]['date'])))

        self.ema_data[prices] = {parameter: values}

        if round_value:
            return round(ema, 2)
        return ema


class SimulatedTrader:
    def __init__(self, startingBalance=1000, interval='1h', symbol='BTCUSDT'):
        self.dataView = Data(interval=interval, symbol=symbol)  # Retrieve data-view object
        self.binanceClient = self.dataView.binanceClient  # Retrieve Binance client
        # self.twilioClient = rest.Client()  # Initialize Twilio client for WhatsApp integration

        try:  # Attempt to parse startingBalance
            startingBalance = float(startingBalance)
        except (ValueError, ArithmeticError, ZeroDivisionError):
            print("Invalid starting balance. Using default value of $1,000.")
            startingBalance = 1000

        # Initialize initial values
        self.balance = startingBalance  # USD Balance
        self.btc = 0  # Amount of BTC we own
        self.btcOwed = 0  # Amount of BTC we owe
        self.transactionFee = 0.001  # Binance transaction fee
        self.totalTrades = []  # Total amount of trades conducted
        self.trades = []  # Amount of trades in previous run

        self.movingAverage = None  # Moving average used for technical analysis
        self.parameter = None  # Parameter used for technical analysis
        self.initialBound = None  # Initial bound for moving average
        self.finalBound = None  # Final bound for moving average
        self.lossPercentage = None  # Loss percentage for stop loss

        self.startingTime = None
        self.endingTime = None
        self.buyLongPrice = None
        self.sellShortPrice = None
        self.lossPrice = None
        self.longTrailingPrice = None
        self.shortTrailingPrice = None
        self.startingBalance = None
        self.currentPrice = None

        self.safetyMargin = None
        self.safetyTimer = None

        self.inHumanControl = False
        self.waitForLong = False
        self.waitForShort = False
        self.inLongPosition = False
        self.inShortPosition = False
        self.trailingLoss = False
        self.skipLongCross = False
        self.skipShortCross = False

    def log_trades(self):
        logging.info(f'\n\nTotal trade(s) in previous simulation: {len(self.simulatedTrades)}')
        for counter, trade in enumerate(self.simulatedTrades, 1):
            logging.info(f'\n{counter}. Date in UTC: {trade["date"]}')
            logging.info(f'\nAction taken: {trade["action"]}')

    def add_trade(self, message):
        """
        Adds a trade to list of trades
        :param message: Message used for conducting trade.
        """
        self.totalTrades.append({
            'date': datetime.utcnow(),
            'action': message
        })

    def buy_long(self, msg, usd=None):
        """
        Buys BTC at current market price with amount of USD specified. If not specified, assumes bot goes all in.
        Function also takes into account Binance's 0.1% transaction fee.
        """
        if usd is None:
            usd = self.balance

        if usd <= 0:
            output_message("You cannot buy with $0 or less.")
            if self.balance <= 0:
                output_message("Looks like you have run out of money.", 4)
            return
        elif usd > self.balance:
            output_message(f'You currently have ${self.balance}. You cannot invest ${usd}.')
            return

        transactionFee = usd * self.transactionFee
        self.currentPrice = self.dataView.get_current_price()
        btcBought = (usd - transactionFee) / self.currentPrice
        self.buyLongPrice = self.currentPrice
        self.btc += btcBought
        self.balance -= usd
        self.add_trade(msg)
        output_message(msg)

    def sell_long(self, msg, btc=None):
        """
        Sells specified amount of BTC at current market price. If not specified, assumes bot sells all BTC.
        Function also takes into account Binance's 0.1% transaction fee.
        """
        if btc is None:
            btc = self.btc

        if btc <= 0:
            output_message("You cannot sell 0 or negative BTC.")
            if self.btc <= 0:
                output_message("Looks like you do not have any BTC.", 4)
            return
        elif btc > self.btc:
            output_message(f'You currently have {self.btc} BTC. You cannot sell {btc} BTC.')
            return

        self.currentPrice = self.dataView.get_current_price()
        earned = btc * self.currentPrice * (1 - self.transactionFee)
        self.btc -= btc
        self.balance += earned
        self.add_trade(msg)
        output_message(msg)

        if self.btc == 0:
            self.buyLongPrice = None

    def buy_short(self, msg, btc=None):
        """
        Buys borrowed BTC at current market price and returns to market.
        Function also takes into account Binance's 0.1% transaction fee.
        If BTC amount is not specified, bot will assume to buy all owed back
        BTC.
        """
        if btc is None:
            btc = self.btcOwed

        if btc <= 0:
            output_message("You cannot buy 0 or less BTC.")
            return

        self.currentPrice = self.dataView.get_current_price()
        lost = self.currentPrice * btc * (1 + self.transactionFee)
        self.btcOwed -= btc
        self.balance -= lost
        self.add_trade(msg)
        output_message(msg)

        if self.btcOwed == 0:
            self.sellShortPrice = None

    def sell_short(self, msg, btc=None):
        """
        Borrows BTC and sells them at current market price.
        Function also takes into account Binance's 0.1% transaction fee.
        If no BTC is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        """
        self.currentPrice = self.dataView.get_current_price()

        if btc is None:
            transactionFee = self.balance * self.transactionFee
            btc = (self.balance - transactionFee) / self.currentPrice

        if btc <= 0:
            output_message("You cannot borrow 0 or less BTC.")
            return

        earned = self.currentPrice * btc * (1 - self.transactionFee)
        self.btcOwed += btc
        self.balance += earned
        self.sellShortPrice = self.currentPrice
        self.add_trade(msg)
        output_message(msg)

    def get_profit(self):
        """
        Returns profit or loss.
        :return: A number representing profit if positive and loss if negative.
        """
        balance = self.balance
        self.currentPrice = self.dataView.get_current_price()
        balance += self.btc * self.currentPrice * (1 - self.transactionFee)
        balance -= self.btcOwed * self.currentPrice * (1 + self.transactionFee)
        return balance - self.simulationStartingBalance

    def validate_margin_trade(self, tradeType, initialBound, finalBound, parameter, safetyMargin=0):
        """
        Checks if bot should go ahead with trade by checking if the average is really greater than the final average.
        :param safetyMargin: Safety margin to check if cross has occurred.
        :param tradeType: Type of trade conducted.
        :param initialBound: Initial bound for trade algorithm.
        :param finalBound: Final bound for trade algorithm.
        :param parameter: Parameter to use for trade algorithm.
        :return: A boolean whether trade should be performed or not.
        """
        if tradeType == 'SMA':
            initialAverage = self.dataView.get_sma(initialBound, parameter)
            finalAverage = self.dataView.get_sma(finalBound, parameter)
        elif tradeType == 'WMA':
            initialAverage = self.dataView.get_wma(initialBound, parameter)
            finalAverage = self.dataView.get_wma(finalBound, parameter)
        elif tradeType == 'EMA':
            initialAverage = self.dataView.get_ema(initialBound, parameter)
            finalAverage = self.dataView.get_ema(finalBound, parameter)
        else:
            output_message(f'Unknown trading type {tradeType}.', 4)
            return False

        return initialAverage + initialAverage * safetyMargin > finalAverage

    def validate_cross(self, waitTime, tradeType, initialBound, finalBound, parameter, safetyMargin):
        if waitTime > 0:
            output_message(f'Cross detected. Waiting {waitTime} seconds to validate...')
            time.sleep(waitTime)
        if not self.validate_margin_trade(tradeType, initialBound, finalBound, parameter, safetyMargin):
            output_message("Irregular averages occurred. Not taking any action.")
            return False
        return True

    def simulate(self, movingAverage="WMA", parameter="high", initialBound=20, finalBound=24, lossPercentage=0.015):
        """
        Starts a live simulation with given parameters.
        :param parameter: Type of parameter to use for averages. e.g close, open, high, low.
        :param movingAverage: Type of trade. e.g. SMA, WMA, EMA.
        :param initialBound: Initial bound. e.g SMA(9) > SMA(11), initial bound would be 9.
        :param finalBound: Final bound. e.g SMA(9) > SMA(11), final bound would be 11.
        :param loss: Loss percentage at which we sell long or buy short.
        """
        self.parameter = parameter.lower()
        self.movingAverage = movingAverage.upper()
        self.initialBound = initialBound
        self.finalBound = finalBound
        self.lossPercentage = lossPercentage
        self.trades = []
        self.sellShortPrice = None
        self.buyLongPrice = None
        self.shortTrailingPrice = None
        self.longTrailingPrice = None
        self.balance = 1000
        self.startingBalance = self.balance
        self.startingTime = datetime.now()

        easter_egg()

        lossStrategy = None
        while lossStrategy not in ('1', '2'):
            lossStrategy = input('Enter 1 for stop loss or 2 for trailing loss strategy>>')

        self.safetyTimer = None
        while self.safetyTimer is None:
            try:
                self.safetyTimer = int(input("Type in your safety timer (or 0 for no timer)>>"))
            except ValueError:
                print("Please type in a valid number.")

        self.safetyMargin = None
        while self.safetyMargin is None:
            try:
                self.safetyMargin = float(input("Type in your safety margin (for 2% type 0.02 or 0 for no margin)>>"))
            except ValueError:
                print("Please type in a valid number.")

        print("Starting simulation...")
        if lossStrategy == '1':
            self.trailingLoss = False
        elif lossStrategy == '2':
            self.trailingLoss = True

        self.simulate_option_1()
        print("\nExiting simulation.")
        self.endingTime = datetime.now()
        self.get_simulation_result()
        self.log_trades()

    def simulate_option_1(self):
        self.lossPrice = None
        fail = False  # Boolean for whether there was an error that occurred.
        self.skipLongCross = False
        self.skipShortCross = False
        self.waitForShort = False  # Boolean for whether we should wait to exit out of short position.
        self.waitForLong = False  # Boolean for whether we should wait to exit out of long position.
        self.inHumanControl = False  # Boolean for whether the bot is in human control.
        waitTime = 0  # Integer that describes how much bot will sleep to recheck if there is a cross.
        safetySleep = self.safetyTimer  # Safety sleep time that bot will sleep and then recheck if a cross exists.
        safetyMargin = self.safetyMargin  # Safety margin percentage to check for if cross is within marginal bounds.
        self.longTrailingPrice = None  # Variable that will keep track of long trailing price.
        self.shortTrailingPrice = None  # Variable that will keep track of short trailing price.
        self.inLongPosition = False  # Boolean that keeps track of whether we are in a long position.
        self.inShortPosition = False  # Boolean that keeps track of whether we are in a short position.

        while True:
            if len(self.trades) > 0:
                waitTime = safetySleep  # Once the first trade is conducted, then only do we wait to validate crosses.
            try:
                self.print_basic_information(loss)

                if fail:
                    output_message("Successfully fixed error.")
                    fail = False

                if not self.dataView.data_is_updated():
                    self.dataView.update_data()

                self.print_trade_type(tradeType, initialBound, finalBound, parameter)

                self.currentPrice = self.dataView.get_current_price()
                if self.trailingLoss:
                    if self.longTrailingPrice is not None and self.currentPrice < self.longTrailingPrice:
                        self.longTrailingPrice = self.currentPrice
                    elif self.shortTrailingPrice is not None and self.currentPrice > self.shortTrailingPrice:
                        self.shortTrailingPrice = self.currentPrice

                self.handle_long(tradeType, initialBound, finalBound, parameter, loss, comparison, safetyMargin,
                                 waitTime)

                self.handle_short(tradeType, initialBound, finalBound, parameter, loss, comparison, safetyMargin,
                                  waitTime)

                print("Type CTRL-C to cancel or override the simulation at any time.")
                time.sleep(1)
            except KeyboardInterrupt:
                action = None
                print('\nDo you want to end simulation or override? If this was an accident, enter nothing.')
                while action not in ('o', 's', ''):
                    action = input("Type 'o' to override, 's' to stop, or nothing to continue>>").lower()
                if action.lower().startswith('o'):
                    self.override()
                elif action.lower().startswith('s'):
                    return
            except Exception as e:
                if not fail:
                    output_message(f'ERROR: {e}')
                    output_message("Something went wrong. Trying again in 5 seconds.")
                time.sleep(5)
                output_message("Attempting to fix error...")
                fail = True

    def print_basic_information(self, loss):
        """
        Prints out basic information about trades.
        """
        output_message('---------------------------------------------------')
        self.currentPrice = self.dataView.get_current_price()
        output_message(f'\nCurrent time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        if self.inHumanControl:
            output_message(f'Currently in human control. Bot is waiting for human input to continue.')
        else:
            output_message(f'Currently in autonomous mode.')

        if self.btc > 0:
            output_message(f'BTC: {self.btc}')
            output_message(f'Price bot bought BTC long for: ${self.buyLongPrice}')

        if self.btcOwed > 0:
            output_message(f'BTC owed: {self.btcOwed}')
            output_message(f'Price bot sold BTC short for: ${self.sellShortPrice}')

        if self.buyLongPrice is not None:
            output_message(f'\nCurrently in long position.')
            if self.longTrailingPrice is not None:
                output_message(f'Long trailing loss value: ${round(self.longTrailingPrice * (1 - loss), 2)}')
            else:
                output_message(f'Stop loss: {round(self.buyLongPrice * (1 - loss), 2)}')
        elif self.sellShortPrice is not None:
            output_message(f'\nCurrently in short position.')
            if self.shortTrailingPrice is not None:
                output_message(f'Short trailing loss value: ${round(self.shortTrailingPrice * (1 + loss), 2)}')
            else:
                output_message(f'Stop loss: {round(self.sellShortPrice * (1 + loss), 2)}')
        else:
            if not self.inHumanControl:
                output_message(f'\nCurrently not a in short or long position. Waiting for next cross.')
            else:
                output_message(f'\nCurrently not a in short or long position. Waiting for human intervention.')

        output_message(f'\nCurrent BTC price: ${self.currentPrice}')
        output_message(f'Balance: ${round(self.balance, 2)}')
        output_message(f'\nTrades conducted this simulation: {len(self.simulatedTrades)}')

        profit = round(self.get_profit(), 2)
        if profit > 0:
            output_message(f'Profit: ${profit}')
        elif profit < 0:
            output_message(f'Loss: ${-profit}')
        else:
            output_message(f'No profit or loss currently.')
        output_message('')

    def print_trade_type(self, tradeType, initialBound, finalBound, parameter):
        """
        Prints out general information about current trade.
        :param tradeType: Current trade type.
        :param initialBound: Initial bound for trade algorithm.
        :param finalBound: Final bound for trade algorithm.
        :param parameter: Type of parameter used.
        """
        output_message(f'Parameter: {parameter}')
        if tradeType == 'SMA':
            output_message(f'{tradeType}({initialBound}) = {self.dataView.get_sma(initialBound, parameter)}')
            output_message(f'{tradeType}({finalBound}) = {self.get_sma(finalBound, parameter)}')
        elif tradeType == 'WMA':
            output_message(f'{tradeType}({initialBound}) = {self.dataView.get_wma(initialBound, parameter)}')
            output_message(f'{tradeType}({finalBound}) = {self.dataView.get_wma(finalBound, parameter)}')
        elif tradeType == 'EMA':
            output_message(f'{tradeType}({initialBound}) = {self.dataView.get_ema(initialBound, parameter)}')
            output_message(f'{tradeType}({finalBound}) = {self.dataView.get_ema(finalBound, parameter)}')
        else:
            output_message(f'Unknown trade type {tradeType}.')

    def override(self):
        action = None
        if not self.inHumanControl:
            while action not in ('w', ''):
                action = input("Type 'w' to pause the bot or nothing to close and wait for next cross>>")
            if action == 'w':
                output_message("Pausing the bot.")
                self.inHumanControl = True
            if self.inShortPosition:
                self.buy_short('Bought short because of override.')
                self.inShortPosition = False
                if action == '':
                    self.waitForShort = True
            elif self.inLongPosition:
                self.sell_long('Sold long because of override.')
                self.inLongPosition = False
                if action == '':
                    self.waitForLong = True
            else:
                output_message("Was not in a long or short position. Resuming simulation.")
            time.sleep(2)
        else:
            while action not in ('long', 'short', ''):
                output_message("Type 'long' to go long, 'short' to go short, or nothing to resume bot.")
                action = input('>>').lower()
            if action == 'long':
                self.buy_long("Buying long because of override.")
                if self.trailingLoss:
                    self.longTrailingPrice = self.dataView.get_current_price()
                self.inLongPosition = True
                self.waitForLong = True
                self.skipLongCross = True
            elif action == 'short':
                self.sell_short(f'Sold short because of override.')
                if self.trailingLoss:
                    self.shortTrailingPrice = self.dataView.get_current_price()
                self.inShortPosition = True
                self.waitForShort = True
                self.skipShortCross = True
            self.inHumanControl = False

    def handle_long(self, tradeType, initialBound, finalBound, parameter, loss, comparison, safetyMargin, waitTime):
        if comparison == '>':
            reverseComparison = '<'
        else:
            reverseComparison = '>'
        if not self.inShortPosition and not self.inHumanControl:  # This is for long positions.
            if self.buyLongPrice is None and not self.inLongPosition:  # If we are not in a long position.
                if not self.waitForLong:  # Checking if we must wait to open long position.
                    if self.validate_margin_trade(tradeType, initialBound, finalBound, parameter, comparison,
                                                  safetyMargin):
                        if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                                   comparison, safetyMargin):
                            return
                        self.buy_long(f'Bought long: {tradeType}({initialBound}) > {tradeType}({finalBound}).')
                        if self.trailingLoss:
                            self.longTrailingPrice = self.currentPrice
                        self.inLongPosition = True
                else:  # Checks if there is a cross to sell short.
                    if self.validate_margin_trade(tradeType, initialBound, finalBound, parameter, reverseComparison,
                                                  safetyMargin):
                        output_message("Cross detected.")
                        self.waitForLong = False

            else:  # If we are in a long position.
                if self.trailingLoss:
                    self.lossPrice = self.longTrailingPrice * (1 - loss)
                else:
                    self.lossPrice = self.buyLongPrice * (1 - loss)

                if self.currentPrice < self.lossPrice:
                    output_message(f'Loss is greater than {loss * 100}%. Selling all BTC.')
                    self.sell_long(f'Sold long because loss was greater than {loss * 100}%. Waiting for cross.')
                    self.longTrailingPrice = None
                    self.inLongPosition = False
                    self.waitForLong = True
                elif self.skipLongCross:
                    return
                elif self.validate_margin_trade(tradeType, initialBound, finalBound, parameter, reverseComparison, safetyMargin):
                    if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                               reverseComparison, safetyMargin):
                        return
                    self.sell_long(f'Sold long because a cross was detected.')
                    self.longTrailingPrice = None
                    self.inLongPosition = False
                    self.waitForLong = False
                    self.skipShortCross = False

    def handle_short(self, tradeType, initialBound, finalBound, parameter, loss, comparison, safetyMargin, waitTime):
        if comparison == '>':
            reverseComparison = '<'
        else:
            reverseComparison = '>'
        if not self.inLongPosition and not self.inHumanControl:  # This is for short position.
            if self.sellShortPrice is None and not self.inShortPosition:  # This is if we are not in short position.
                if not self.waitForShort:  # This is to check if we must wait to enter short position.
                    if self.validate_margin_trade(tradeType, initialBound, finalBound, parameter, reverseComparison,
                                                  safetyMargin):
                        if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                                   reverseComparison, safetyMargin):
                            return
                        self.sell_short(
                            f'Sold short as {tradeType}({initialBound}) < {tradeType}({finalBound})')
                        if self.trailingLoss:
                            self.shortTrailingPrice = self.currentPrice
                        self.inShortPosition = True
                else:
                    if self.validate_margin_trade(tradeType, initialBound, finalBound, parameter, comparison,
                                                  safetyMargin):
                        output_message("Cross detected!")
                        self.waitForShort = False
            else:
                if self.trailingLoss:
                    self.lossPrice = self.shortTrailingPrice * (1 + loss)
                else:
                    self.lossPrice = self.sellShortPrice * (1 + loss)

                if self.currentPrice > self.lossPrice:
                    self.buy_short(
                        f'Bought short because loss is greater than {loss * 100}%. Waiting for cross')
                    self.shortTrailingPrice = None
                    self.inShortPosition = False
                    self.waitForShort = True

                elif not self.skipShortCross and self.validate_margin_trade(tradeType, initialBound, finalBound, parameter,
                                                                            comparison, safetyMargin):
                    if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                               comparison, safetyMargin):
                        return
                    self.buy_short(f'Bought short because a cross was detected.')
                    self.shortTrailingPrice = None
                    self.inShortPosition = False
                    self.waitForShort = False
                    self.skipLongCross = False

    def get_simulation_result(self):
        """
        Gets end result of simulation.
        """
        if self.btc > 0:
            output_message("Selling all BTC...")
            self.sell_long(f'Sold long as simulation ended.')
        if self.btcOwed > 0:
            output_message("Returning all borrowed BTC...")
            self.buy_short(f'Bought short as simulation ended.')
        output_message("\nResults:")
        output_message(f'Starting time: {self.startingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        output_message(f'End time: {self.endingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        output_message(f'Elapsed time: {self.endingTime - self.startingTime}')
        output_message(f'Starting balance: ${self.simulationStartingBalance}')
        output_message(f'Ending balance: ${round(self.balance, 2)}')
        output_message(f'Trades conducted: {len(self.simulatedTrades)}')
        if self.balance > self.simulationStartingBalance:
            profit = self.balance - self.simulationStartingBalance
            output_message(f"Profit: ${round(profit, 2)}")
        elif self.balance < self.simulationStartingBalance:
            loss = self.simulationStartingBalance - self.balance
            output_message(f'Loss: ${round(loss, 2)}')
        else:
            output_message("No profit or loss occurred.")

        if len(self.simulatedTrades) > 0:
            print("\nYou can view the trades from the simulation in more detail.")
            print("Please type in bot.view_simulated_trades() to view them.")

    def view_simulated_trades(self):
        """
        Prints simulation result in more detail with each trade conducted.
        """
        print(f'\nTotal trade(s) in previous simulation: {len(self.simulatedTrades)}')
        for counter, trade in enumerate(self.simulatedTrades, 1):
            print(f'\n{counter}. Date in UTC: {trade["date"]}')
            print(f'Action taken: {trade["action"]}')


class RealTrader(SimulatedTrader):
    def __init__(self, interval='1h', symbol='BTCUDST'):
        apiKey = os.environ.get('binance_api')  # Retrieving API key from environment variables
        apiSecret = os.environ.get('binance_secret')  # Retrieving API secret from environment variables
        super().__init__(interval=interval, symbol=symbol, apiKey=apiKey, apiSecret=apiSecret)
        if not self.verify_api_and_secret():
            return

    def verify_api_and_secret(self):
        """
        Checks and prints if both API key and API secret are None values.
        Returns a boolean whether the API key and secret are valid or not.
        """
        if self.apiKey is None:
            output_message("No API key found.", 4)
            return False
        else:
            output_message("API key found.")

        if self.apiSecret is None:
            output_message("No API secret found.", 4)
            return False
        else:
            output_message("API secret found.")

        return True


def easter_egg():
    import random
    number = random.randint(1, 16)
    sleepTime = 0.25

    if number == 1:
        print('The two most important days in your life are the day you are born and the day you find out why.')
    elif number == 2:
        print('Financial freedom by sacrificing relationships; is it ever worth it?')
    elif number == 3:
        print("A guy asks a woman to sleep with him for $100, and the woman starts thinking. Suddenly the guy says "
              "I'll give you $20 for a night, and the girl gets mad and yells what type of girl do you think I am? "
              "The guy then says that he thought they already established that, and that now they're negotiating.")
    elif number == 4:
        print("We all do dumb things, that's what makes us human.")
    elif number == 5:
        print("Friends are like coins. You rather have 4 quarters than a 100 pennies.")
    elif number == 6:
        print('Fuck Bill Gates')
    elif number == 7:
        print('What is privacy again?')
    elif number == 8:
        print("If the virus was real and super contagious, why didn't it spread during BLM protests?")
    elif number == 9:
        print('Insanity is doing the same shit over and over again. Expecting shit to change.')
    elif number == 10:
        print("Rush B P90 no stop.")
    elif number == 11:
        print('Wakanda forever.')
    elif number == 12:
        print('Read the manuals. Read the books.')
    elif number == 13:
        print('4 cases in New Zealand? Lock down everything again!')
    elif number == 14:
        print('Fake pandemic.')
    elif number == 15:
        print('You think money is a powerful tool? Fuck that, fear will always fuck you up.')
    else:
        print("Fucking shape shifting reptilians, bro. Fucking causing this virus and shit.")

    time.sleep(sleepTime)


def output_message(message, level=2):
    """Prints out and logs message"""
    print(message)
    if level == 2:
        logging.info(message)
    elif level == 3:
        logging.debug(message)
    elif level == 4:
        logging.warning(message)
    elif level == 5:
        logging.critical(message)


def initialize_logger():
    """Initializes logger"""
    if not os.path.exists('Logs'):
        os.mkdir('Logs')

    logFileName = f'{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'
    logging.basicConfig(filename=f'Logs/{logFileName}', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s: %(message)s')