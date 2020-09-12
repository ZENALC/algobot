import sqlite3
from datetime import timedelta, timezone
from contextlib import closing
from binance.client import Client
from helpers import *


class Data:
    def __init__(self, interval='1h', symbol='BTCUSDT', loadData=True):
        """
        Data object that will retrieve current and historical prices from the Binance API and calculate moving averages.
        :param interval: Interval for which the data object will track prices.
        :param symbol: Symbol for which the data object will track prices.
        """
        self.binanceClient = Client(None, None)  # Initialize Binance client
        if not self.is_valid_interval(interval):
            self.output_message("Invalid interval. Using default interval of 1h.", level=4)
            interval = '1h'

        self.interval = interval
        self.intervalUnit, self.intervalMeasurement = self.get_interval_unit_and_measurement()

        if not self.is_valid_symbol(symbol):
            self.output_message('Invalid symbol. Using default symbol of BTCUSDT.', level=4)
            symbol = 'BTCUSDT'

        self.symbol = symbol
        self.data = []
        self.ema_data = {}

        if loadData:
            # Create, initialize, store, and get values from database.
            self.databaseFile = 'btc.db'
            self.databaseTable = f'data_{self.interval}'
            self.create_table()
            self.get_data_from_database()
            if not self.database_is_updated():
                self.output_message("Updating data...")
                self.update_database()
            else:
                self.output_message("Database is up-to-date.")

    @staticmethod
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
                        self.output_message("Insertion to database failed. Will retry next run.", 4)
                        return False
        self.output_message("Successfully stored all new data to database.")
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
            self.output_message("Retrieving data from database...")
        else:
            self.output_message("No data found in database.")
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
            self.output_message(f'Downloading all available historical data for {self.interval} intervals.')
        else:
            latestDate = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            timestamp = int(latestDate.timestamp()) * 1000  # Converting timestamp to milliseconds
            dateWithIntervalAdded = latestDate + timedelta(minutes=self.get_interval_minutes())
            self.output_message(f"Previous data up to UTC {dateWithIntervalAdded} found.")

        if not self.database_is_updated():
            newData = self.get_new_data(timestamp)
            self.output_message("Successfully downloaded all new data.")
            self.output_message("Inserting data to live program...")
            self.insert_data(newData)
            self.output_message("Storing updated data to database...")
            self.dump_to_table()
        else:
            self.output_message("Database is up-to-date.")

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
        self.output_message(f"Previous data found up to UTC {dateWithIntervalAdded}.")
        if not self.data_is_updated():
            newData = self.get_new_data(timestamp)
            self.insert_data(newData)
            self.output_message("Data has been updated successfully.")
        else:
            self.output_message("Data is up-to-date.")

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
            self.output_message(f"Error: {e}. Retrying in 2 seconds...", 4)
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
            self.output_message(f'Error: {e}. Retrying in 2 seconds...', 4)
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
            self.output_message("Invalid interval.", 4)
            return None

    def get_current_interval_csv_data(self):
        pass

    def get_csv_data(self, interval):
        """
        Creates a new CSV file with interval specified.
        :param interval: Interval to get data for.
        """
        if not self.is_valid_interval(interval):
            return
        timestamp = self.binanceClient._get_earliest_valid_timestamp(self.symbol, interval)
        self.output_message("Downloading all available historical data. This may take a while...")
        newData = self.binanceClient.get_historical_klines(self.symbol, interval, timestamp, limit=1000)
        self.output_message("Downloaded all data successfully.")

        folderName = 'CSV'
        fileName = f'{self.symbol}_data_{interval}.csv'
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
        self.output_message(f'Data saved to {path}.')
        os.chdir(currentPath)

        return path

    def is_valid_interval(self, interval):
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
            self.output_message(f'Invalid interval. Available intervals are: \n{availableIntervals}')
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
            self.output_message("Shift cannot be less than 0.")
            return False
        elif prices <= 0:
            self.output_message("Prices cannot be 0 or less than 0.")
            return False
        elif shift + extraShift + prices > len(self.data) + 1:
            self.output_message("Shift + prices period cannot be more than data available.")
            return False
        return True

    def verify_integrity(self):
        """
        Verifies integrity of data by checking if there's any repeated data.
        :return: A boolean whether the data contains no repeated data or not.
        """
        if len(self.data) < 1:
            self.output_message("No data found.", 4)
            return False

        previousData = self.data[0]
        for data in self.data[1:]:
            if data['date'] == previousData['date']:
                self.output_message("Repeated data detected.", 4)
                self.output_message(f'Previous data: {previousData}', 4)
                self.output_message(f'Next data: {data}', 4)
                return False
            previousData = data

        self.output_message("Data has been verified to be correct.")
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
            self.output_message("Initial amount of SMA values for initial EMA must be greater than 0.")
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
    def __init__(self, startingBalance=1000, interval='1h', symbol='BTCUSDT', loadData=True):
        self.dataView = Data(interval=interval, symbol=symbol, loadData=loadData)  # Retrieve data-view object
        self.binanceClient = self.dataView.binanceClient  # Retrieve Binance client

        try:  # Attempt to parse startingBalance
            startingBalance = float(startingBalance)
        except (ValueError, ArithmeticError, ZeroDivisionError):
            print("Invalid starting balance. Using default value of $1,000.")
            startingBalance = 1000

        # Initialize initial values
        self.balance = startingBalance  # USD Balance
        self.btc = 0  # Amount of BTC we own
        self.btcOwed = 0  # Amount of BTC we owe
        self.transactionFeePercentage = 0.001  # Binance transaction fee
        self.totalTrades = []  # All trades conducted
        self.trades = []  # Amount of trades in previous run

        self.tradingOptions = []
        self.trend = None  # 1 is bullish, -1 is bearish
        self.lossPercentage = None  # Loss percentage for stop loss
        self.startingTime = None  # Starting time for previous bot run
        self.endingTime = None  # Ending time for previous bot run
        self.buyLongPrice = None  # Price we last bought BTC at in long position
        self.sellShortPrice = None  # Price we last sold BTC at in short position
        self.lossStrategy = None  # Type of loss type we are using: whether it's trailing loss or stop loss
        self.stopLoss = None  # Price at which bot will exit trade due to stop loss limits
        self.longTrailingPrice = None  # Price BTC has to be above for long position
        self.shortTrailingPrice = None  # Price BTC has to be below for short position
        self.startingBalance = self.balance  # Balance we started bot run with
        self.currentPrice = None  # Current price of BTC

        self.safetyMargin = None  # Margin percentage bot will check to validate cross
        self.safetyTimer = None  # Amount of seconds bot will wait to validate cross

        self.inHumanControl = False  # Boolean that keeps track of whether human or bot controls transactions
        self.waitToEnterLong = False  # Boolean that checks if bot should wait before entering long position
        self.waitToEnterShort = False  # Boolean that checks if bot should wait before entering short position
        self.inLongPosition = False  # Boolean that keeps track of whether bot is in a long position or not
        self.inShortPosition = False  # Boolean that keeps track of whether bot is in a short position or not

    @staticmethod
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

    def add_trade(self, message):
        """
        Adds a trade to list of trades
        :param message: Message used for conducting trade.
        """
        self.trades.append({
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
            self.output_message("You cannot buy with $0 or less.")
            if self.balance <= 0:
                self.output_message("Looks like you have run out of money.", 4)
            return
        elif usd > self.balance:
            self.output_message(f'You currently have ${self.balance}. You cannot invest ${usd}.')
            return

        transactionFee = usd * self.transactionFeePercentage
        self.inLongPosition = True
        self.currentPrice = self.dataView.get_current_price()
        self.buyLongPrice = self.currentPrice
        self.longTrailingPrice = self.currentPrice
        self.btc += (usd - transactionFee) / self.currentPrice
        self.balance -= usd
        self.add_trade(msg)
        self.output_message(msg)

    def sell_long(self, msg, btc=None):
        """
        Sells specified amount of BTC at current market price. If not specified, assumes bot sells all BTC.
        Function also takes into account Binance's 0.1% transaction fee.
        """
        if btc is None:
            btc = self.btc

        if btc <= 0:
            self.output_message("You cannot sell 0 or negative BTC.")
            if self.btc <= 0:
                self.output_message("Looks like you do not have any BTC.", 4)
            return
        elif btc > self.btc:
            self.output_message(f'You currently have {self.btc} BTC. You cannot sell {btc} BTC.')
            return

        self.currentPrice = self.dataView.get_current_price()
        earned = btc * self.currentPrice * (1 - self.transactionFeePercentage)
        self.inLongPosition = False
        self.btc -= btc
        self.balance += earned
        self.add_trade(msg)
        self.output_message(msg)

        if self.btc == 0:
            self.buyLongPrice = None
            self.longTrailingPrice = None

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
            self.output_message("You cannot buy 0 or less BTC.")
            return

        self.currentPrice = self.dataView.get_current_price()
        self.btcOwed -= btc
        self.inShortPosition = False
        loss = self.currentPrice * btc * (1 + self.transactionFeePercentage)
        self.balance -= loss
        self.add_trade(msg)
        self.output_message(msg)

        if self.btcOwed == 0:
            self.sellShortPrice = None
            self.shortTrailingPrice = None

    def sell_short(self, msg, btc=None):
        """
        Borrows BTC and sells them at current market price.
        Function also takes into account Binance's 0.1% transaction fee.
        If no BTC is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        """
        self.currentPrice = self.dataView.get_current_price()

        if btc is None:
            transactionFee = self.balance * self.transactionFeePercentage
            btc = (self.balance - transactionFee) / self.currentPrice

        if btc <= 0:
            self.output_message("You cannot borrow 0 or less BTC.")
            return

        self.btcOwed += btc
        self.balance += self.currentPrice * btc * (1 - self.transactionFeePercentage)
        self.inShortPosition = True
        self.sellShortPrice = self.currentPrice
        self.shortTrailingPrice = self.currentPrice
        self.add_trade(msg)
        self.output_message(msg)

    def get_profit(self):
        """
        Returns profit or loss.
        :return: A number representing profit if positive and loss if negative.
        """
        balance = self.balance
        self.currentPrice = self.dataView.get_current_price()
        balance += self.btc * self.currentPrice * (1 - self.transactionFeePercentage)
        balance -= self.btcOwed * self.currentPrice * (1 + self.transactionFeePercentage)
        return balance - self.startingBalance

    def get_position(self):
        if self.inLongPosition:
            return "Long"
        elif self.inShortPosition:
            return "Short"
        else:
            return None

    def get_average(self, movingAverage, parameter, value):
        """
        Returns the moving average with parameter and value provided
        :param movingAverage: Moving average to get the average from the data view.
        :param parameter: Parameter for the data view to use in the moving average.
        :param value: Value for the moving average to use in the moving average.
        :return: A float value representing the moving average.
        """
        if movingAverage == 'SMA':
            return self.dataView.get_sma(value, parameter)
        elif movingAverage == 'WMA':
            return self.dataView.get_wma(value, parameter)
        elif movingAverage == 'EMA':
            return self.dataView.get_ema(value, parameter)
        else:
            self.output_message(f'Unknown moving average {movingAverage}.', 4)
            return None

    def get_stop_loss(self):
        """
        Returns a stop loss for the position.
        :return: Stop loss value.
        """
        if self.inShortPosition:  # If we are in a short position
            if self.lossStrategy == 2:  # This means we use trailing loss.
                return self.shortTrailingPrice * (1 + self.lossPercentage)
            else:  # This means we use the basic stop loss.
                return self.sellShortPrice * (1 + self.lossPercentage)
        elif self.inLongPosition:  # If we in a long position
            if self.lossStrategy == 2:  # This means we use trailing loss.
                return self.longTrailingPrice * (1 - self.lossPercentage)
            else:  # This means we use the basic stop loss.
                return self.buyLongPrice * (1 - self.lossPercentage)

    def check_cross(self):
        """
        Checks if there is a cross
        :return: A boolean whether there is a cross or not.
        """
        if len(self.tradingOptions) == 0:  # Checking whether options exist.
            self.output_message("No trading options provided.")
            return

        cross = True

        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

            if option.previousFinalAverage is None or option.previousInitialAverage is None:
                option.previousInitialAverage = initialAverage
                option.previousFinalAverage = finalAverage
                cross = False
                continue

            if initialAverage > finalAverage:
                self.trend = 1  # This means we are bullish
            else:
                self.trend = -1  # This means we are bearish

            if option.previousInitialAverage >= option.previousFinalAverage:
                if initialAverage >= finalAverage:
                    cross = False

            if option.previousInitialAverage <= option.previousFinalAverage:
                if initialAverage <= finalAverage:
                    cross = False

            option.previousFinalAverage = finalAverage
            option.previousInitialAverage = initialAverage

        return cross

    def output_trade_options(self):
        """
        Outputs general information about current trade options.
        """
        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

            self.output_message(f'Parameter: {option.parameter}')
            self.output_message(f'{option.movingAverage}({option.initialBound}) = {initialAverage}')
            self.output_message(f'{option.movingAverage}({option.finalBound}) = {finalAverage}')

    def output_basic_information(self):
        """
        Prints out basic information about trades.
        """
        self.output_message('---------------------------------------------------')
        self.output_message(f'Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        if self.inHumanControl:
            self.output_message(f'Currently in human control. Bot is waiting for human input to continue.')
        else:
            self.output_message(f'Currently in autonomous mode.')

        if self.btc > 0:
            self.output_message(f'BTC: {self.btc}')
            self.output_message(f'Price bot bought BTC long for: ${self.buyLongPrice}')

        if self.btcOwed > 0:
            self.output_message(f'BTC owed: {self.btcOwed}')
            self.output_message(f'Price bot sold BTC short for: ${self.sellShortPrice}')

        if self.inLongPosition:
            self.output_message(f'\nCurrently in long position.')
            if self.lossStrategy == 2:
                longTrailingLossValue = round(self.longTrailingPrice * (1 - self.lossPercentage), 2)
                self.output_message(f'Long trailing loss: ${longTrailingLossValue}')
            else:
                self.output_message(f'Stop loss: {round(self.buyLongPrice * (1 - self.lossPercentage), 2)}')
        elif self.inShortPosition:
            self.output_message(f'\nCurrently in short position.')
            if self.lossStrategy == 2:
                shortTrailingLossValue = round(self.shortTrailingPrice * (1 + self.lossPercentage), 2)
                self.output_message(f'Short trailing loss: ${shortTrailingLossValue}')
            else:
                self.output_message(f'Stop loss: {round(self.sellShortPrice * (1 + self.lossPercentage), 2)}')
        else:
            if not self.inHumanControl:
                self.output_message(f'\nCurrently not a in short or long position. Waiting for next cross.')
            else:
                self.output_message(f'\nCurrently not a in short or long position. Waiting for human intervention.')

        self.output_message(f'\nCurrent BTC price: ${self.dataView.get_current_price()}')
        self.output_message(f'Balance: ${round(self.balance, 2)}')
        self.output_message(f'\nTrades conducted this simulation: {len(self.trades)}')

        profit = round(self.get_profit(), 2)
        if profit > 0:
            self.output_message(f'Profit: ${profit}')
        elif profit < 0:
            self.output_message(f'Loss: ${-profit}')
        else:
            self.output_message(f'No profit or loss currently.')
        self.output_message('')

    def get_simulation_result(self):
        """
        Gets end result of simulation.
        """
        if self.btc > 0:
            self.output_message("Selling all BTC...")
            self.sell_long(f'Sold long as simulation ended.')

        if self.btcOwed > 0:
            self.output_message("Returning all borrowed BTC...")
            self.buy_short(f'Bought short as simulation ended.')

        self.output_message("\nResults:")
        self.output_message(f'Starting time: {self.startingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'End time: {self.endingTime.strftime("%Y-%m-%d %H:%M:%S")}')
        self.output_message(f'Elapsed time: {self.endingTime - self.startingTime}')
        self.output_message(f'Starting balance: ${self.startingBalance}')
        self.output_message(f'Ending balance: ${round(self.balance, 2)}')
        self.output_message(f'Trades conducted: {len(self.trades)}')
        if self.balance > self.startingBalance:
            profit = self.balance - self.startingBalance
            self.output_message(f"Profit: ${round(profit, 2)}")
        elif self.balance < self.startingBalance:
            loss = self.startingBalance - self.balance
            self.output_message(f'Loss: ${round(loss, 2)}')
        else:
            self.output_message("No profit or loss occurred.")

    def log_trades(self):
        """
        Logs trades.
        """
        logging.info(f'\n\nTotal trade(s) in previous simulation: {len(self.trades)}')
        for counter, trade in enumerate(self.trades, 1):
            logging.info(f'\n{counter}. Date in UTC: {trade["date"]}')
            logging.info(f'\nAction taken: {trade["action"]}')

    def simulate(self, movingAverage="WMA", parameter="high", initialBound=20, finalBound=24, lossPercentage=0.015,
                 lossStrategy=None, safetyTimer=None, safetyMargin=None, options=None):
        """
        Starts a live simulation with given parameters.
        :param options: Argument for all trading options.
        :param safetyMargin: Margin percentage to validate cross
        :param safetyTimer: Amount of seconds to sleep to validate cross
        :param lossStrategy: Type of loss strategy to use
        :param parameter: Type of parameter to use for averages. e.g close, open, high, low.
        :param movingAverage: Type of trade. e.g. SMA, WMA, EMA.
        :param initialBound: Initial bound. e.g SMA(9) > SMA(11), initial bound would be 9.
        :param finalBound: Final bound. e.g SMA(9) > SMA(11), final bound would be 11.
        :param lossPercentage: Loss percentage at which we sell long or buy short.
        """
        if options is not None:
            self.tradingOptions = options
        else:
            tradingOption = Option(movingAverage, parameter, initialBound, finalBound)
            self.tradingOptions = [tradingOption]

        self.lossPercentage = lossPercentage
        self.lossStrategy = lossStrategy
        self.safetyTimer = safetyTimer
        self.safetyMargin = safetyMargin
        self.trades = []
        self.sellShortPrice = None
        self.buyLongPrice = None
        self.shortTrailingPrice = None
        self.longTrailingPrice = None
        self.balance = 1000
        self.startingBalance = self.balance
        self.startingTime = datetime.now()

        easter_egg()

        while self.lossStrategy not in (1, 2):
            try:
                self.lossStrategy = int(input('Enter 1 for stop loss or 2 for trailing loss strategy>>'))
            except ValueError:
                print("Please type in a valid number.")

        while self.safetyTimer is None:
            try:
                self.safetyTimer = int(input("Type in your safety timer (or 0 for no timer)>>"))
            except ValueError:
                print("Please type in a valid number.")

        while self.safetyMargin is None:
            try:
                self.safetyMargin = float(input("Type in your safety margin (for 2% type 0.02 or 0 for no margin)>>"))
            except ValueError:
                print("Please type in a valid number.")

        self.output_message("Starting simulation...")

        self.simulate_option_1()
        self.output_message("\nExiting simulation.")
        self.endingTime = datetime.now()
        self.get_simulation_result()
        self.log_trades()

    def simulate_option_1(self):
        fail = False  # Boolean for whether there was an error that occurred.
        waitTime = self.safetyTimer  # Integer that describes how much bot will sleep to recheck if there is a cross.
        self.safetyTimer = 0  # Initially the safetyTimer will be 0 until a first trade is made.
        self.waitToEnterShort = False  # Boolean for whether we should wait to exit out of short position.
        self.waitToEnterLong = False  # Boolean for whether we should wait to exit out of long position.
        self.inHumanControl = False  # Boolean for whether the bot is in human control.
        self.stopLoss = None  # Stop loss value at which bot will exit position
        self.longTrailingPrice = None  # Variable that will keep track of long trailing price.
        self.shortTrailingPrice = None  # Variable that will keep track of short trailing price.
        self.inLongPosition = False  # Boolean that keeps track of whether we are in a long position.
        self.inShortPosition = False  # Boolean that keeps track of whether we are in a short position.

        while True:
            if len(self.trades) > 0:
                self.safetyTimer = waitTime  # Once the first trade is conducted, then only we wait to validate crosses.
            try:
                self.output_basic_information()

                if fail:
                    self.output_message("Successfully fixed error.")
                    fail = False

                if not self.dataView.data_is_updated():
                    self.dataView.update_data()

                self.output_trade_options()

                self.currentPrice = self.dataView.get_current_price()
                if self.longTrailingPrice is not None and self.currentPrice > self.longTrailingPrice:
                    self.longTrailingPrice = self.currentPrice
                elif self.shortTrailingPrice is not None and self.currentPrice < self.shortTrailingPrice:
                    self.shortTrailingPrice = self.currentPrice

                if not self.inHumanControl:
                    self.main_logic()

                # print("Type CTRL-C to cancel or override the simulation at any time.")
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
                    self.output_message(f'ERROR: {e}')
                    self.output_message("Something went wrong. Trying again in 5 seconds.")
                time.sleep(5)
                self.output_message("Attempting to fix error...")
                fail = True

    def main_logic(self):
        if self.inShortPosition:  # This means we are in short position
            if self.currentPrice > self.get_stop_loss():  # If current price is greater, then exit trade.
                self.buy_short(f'Bought short because of stop loss.')
                self.waitToEnterShort = True

            if self.check_cross():
                self.buy_short(f'Bought short because a cross was detected.')
                self.buy_long(f'Bought long because a cross was detected.')

        elif self.inLongPosition:  # This means we are in long position
            if self.currentPrice < self.get_stop_loss():  # If current price is lower, then exit trade.
                self.sell_long(f'Sold long because of stop loss.')
                self.waitToEnterLong = True

            if self.check_cross():
                self.sell_long(f'Sold long because a cross was detected.')
                self.sell_short('Sold short because a cross was detected.')

        else:  # This means we are in neither position
            if self.check_cross():
                if self.trend == 1:
                    self.buy_long("Bought long because a cross was detected.")
                else:
                    self.sell_short("Sold short because a cross was detected.")

    def validate_trade(self):
        """
        Checks if bot should go ahead with trade by comparing initial and final averages.
        :return: A boolean whether trade should be performed or not.
        """
        for option in self.tradingOptions:
            initialAverage = self.get_average(option.movingAverage, option.parameter, option.initialBound)
            finalAverage = self.get_average(option.movingAverage, option.parameter, option.finalBound)

            if initialAverage is None or finalAverage is None:
                return False  # This means something went wrong with the moving average calculation.

            initialAverageWithMargin = initialAverage + initialAverage * self.safetyMargin

            if self.inLongPosition:
                if not initialAverageWithMargin > finalAverage:
                    return False
            elif self.inShortPosition:
                if not initialAverageWithMargin < finalAverage:
                    return False
            else:
                if initialAverageWithMargin > finalAverage:
                    self.inLongPosition = True
                elif initialAverageWithMargin < finalAverage:
                    self.inShortPosition = True

        return True

    def validate_cross(self):
        """
        Validates if cross is true by waiting then rechecking cross values.
        :return: Boolean whether cross is real or fake.
        """
        if self.safetyTimer > 0:
            self.output_message(f'Cross detected. Waiting {self.safetyTimer} seconds to validate...')
            time.sleep(self.safetyTimer)
        if not self.validate_trade():
            self.output_message("Irregular averages occurred. Not taking any action.")
            return False
        return True

    def override(self):
        action = None
        if not self.inHumanControl:
            while action not in ('w', ''):
                action = input("Type 'w' to pause the bot or nothing to close and wait for next cross>>")
            if action == 'w':
                self.output_message("Pausing the bot.")
                self.inHumanControl = True
            if self.inShortPosition:
                self.buy_short('Bought short because of override.')
                if action == '':
                    self.waitToEnterShort = True
            elif self.inLongPosition:
                self.sell_long('Sold long because of override.')
                if action == '':
                    self.waitToEnterLong = True
            else:
                self.output_message("Was not in a long or short position. Resuming simulation.")
        else:
            while action not in ('long', 'short', ''):
                self.output_message("Type 'long' to go long, 'short' to go short, or nothing to resume bot.")
                action = input('>>').lower()
            if action == 'long':
                self.buy_long("Buying long because of override.")
                self.waitToEnterLong = True
            elif action == 'short':
                self.sell_short(f'Sold short because of override.')
                self.waitToEnterShort = True
            self.inHumanControl = False


class RealTrader(SimulatedTrader):
    def __init__(self, interval='1h', symbol='BTCUDST'):
        self.apiKey = os.environ.get('binance_api')  # Retrieving API key from environment variables
        self.apiSecret = os.environ.get('binance_secret')  # Retrieving API secret from environment variables
        super().__init__(interval=interval, symbol=symbol)
        # self.twilioClient = rest.Client()  # Initialize Twilio client for WhatsApp integration
        self.binanceClient = Client(self.apiKey, self.apiSecret)
        if not self.verify_api_and_secret():
            return

    def verify_api_and_secret(self):
        """
        Checks and prints if both API key and API secret are None values.
        Returns a boolean whether the API key and secret are valid or not.
        """
        if self.apiKey is None:
            self.output_message("No API key found.", 4)
            return False
        else:
            self.output_message("API key found.")

        if self.apiSecret is None:
            self.output_message("No API secret found.", 4)
            return False
        else:
            self.output_message("API secret found.")

        return True


class Option:
    """
    Helper class object for trading objects
    """

    def __init__(self, movingAverage, parameter, initialBound, finalBound):
        self.movingAverage = movingAverage
        self.parameter = parameter
        self.initialBound = initialBound
        self.finalBound = finalBound
        self.previousInitialAverage = None
        self.previousFinalAverage = None

    def set_previous_initial_average(self, previousInitialAverage):
        self.previousInitialAverage = previousInitialAverage

    def set_previous_final_average(self, previousFinalAverage):
        self.previousFinalAverage = previousFinalAverage

    def set_moving_average(self, movingAverage):
        self.movingAverage = movingAverage

    def set_parameter(self, parameter):
        self.parameter = parameter

    def set_initial_bound(self, initialBound):
        self.initialBound = initialBound

    def set_final_bound(self, initialBound):
        self.initialBound = initialBound

    def get_moving_average(self):
        return self.movingAverage

    def get_parameter(self):
        return self.parameter

    def get_initial_bound(self):
        return self.initialBound

    def get_final_bound(self):
        return self.finalBound

    def __repr__(self):
        return f'Option({self.movingAverage}, {self.parameter}, {self.initialBound}, {self.finalBound})'


def main():
    pass


if __name__ == 'main':
    main()
