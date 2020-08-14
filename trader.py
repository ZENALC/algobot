import sqlite3
import os
import csv
import time
from datetime import datetime, timedelta, timezone
from contextlib import closing
# from twilio import rest
from binance.client import Client
from binance.websockets import BinanceSocketManager


class Trader:
    def __init__(self, startingBalance=1000, interval='1h', symbol='BTCUSDT'):
        if not self.is_valid_interval(interval):
            print("Invalid interval. Using default interval of 1h.")
            interval = '1h'

        self.interval = interval
        self.intervalMeasurement = int(self.interval[0:len(self.interval) - 1])
        self.intervalUnit = self.interval[-1]

        self.apiKey = os.environ.get('binance_api')
        self.apiSecret = os.environ.get('binance_secret')
        self.binanceClient = Client(self.apiKey, self.apiSecret)
        # self.twilioClient = rest.Client()

        if not self.is_valid_symbol(symbol):
            print('Invalid symbol. Using default symbol of BTCUSDT.')
            symbol = 'BTCUSDT'

        self.symbol = symbol

        self.data = []
        self.ema_data = {}
        self.startingBalance = startingBalance
        self.balance = self.startingBalance
        self.btc = 0
        self.btcOwed = 0
        self.btcOwedPrice = None
        self.transactionFee = 0.001
        self.startingTime = None
        self.endingTime = None
        self.buyLongPrice = None
        self.sellShortPrice = None
        self.simulatedTrades = []
        self.simulationStartingBalance = None
        self.longTrailingPrice = None
        self.shortTrailingPrice = None
        # self.btc_price = {'error': False, 'current': None, 'open': None, 'high': None, 'low': None, 'date': None}

        # Create, initialize, store, and get values from database.
        self.databaseFile = 'btc.db'
        self.databaseTable = f'data_{self.interval}'
        # self.databaseConnection, self.databaseCursor = self.get_database_connectors()
        self.create_table()
        self.get_data_from_database()
        if not self.database_is_updated():
            print("Updating data...")
            self.update_database()
        else:
            print("Database is up-to-date.")

        self.logFile = None
        self.log = None

        # Initialize and start the WebSocket
        # print("Initializing web socket...")
        # self.bsm = BinanceSocketManager(self.binanceClient)
        # # bsm.start_symbol_ticker_socket(self.exchange, self.btc_trade_history)
        # self.bsm.start_kline_socket(self.exchange, self.process_socket_message, self.interval)
        # self.bsm.start()
        # print("Initialized web socket.")

    def get_database_connectors(self):
        """
        Returns database connection and cursor.
        :return: A tuple with connection and cursor.
        """
        connection = sqlite3.connect(self.databaseFile)
        cursor = connection.cursor()
        return connection, cursor

    def get_data_from_database(self):
        """
        Loads data from database and appends it to run-time data.
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                rows = cursor.execute(f'''
                        SELECT "trade_date", "open_price",
                        "high_price", "low_price", "close_price"
                        FROM {self.databaseTable} ORDER BY trade_date DESC
                        ''').fetchall()

        if len(rows) > 0:
            print("Retrieving data from database...")
        else:
            print("No data found in database.")

        for row in rows:
            self.data.append({'date': datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc),
                              'open': float(row[1]),
                              'high': float(row[2]),
                              'low': float(row[3]),
                              'close': float(row[4]),
                              })

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
        success = True
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
                        pass
                    except sqlite3.OperationalError:
                        print("Data insertion was unsuccessful.")
                        success = False
                        break
        return success

    def get_latest_database_row(self):
        """
        Returns the latest row from database table.
        :return: Row data or None depending on if value exists.
        """
        with closing(sqlite3.connect(self.databaseFile)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(f'SELECT trade_date FROM {self.databaseTable} ORDER BY trade_date DESC LIMIT 1')
                return cursor.fetchone()

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
        if result is None:
            timestamp = self.binanceClient._get_earliest_valid_timestamp(self.symbol, self.interval)
            print(f'Downloading all available historical data for {self.interval} intervals. This may take a while...')
        else:
            latestDate = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            timestamp = int(latestDate.timestamp()) * 1000
            print(f"Previous data up to UTC {latestDate + timedelta(minutes=self.get_interval_minutes())} found.")

        if not self.database_is_updated():
            newData = self.binanceClient.get_historical_klines(self.symbol, self.interval, timestamp + 1, limit=1000)
            del newData[-1]  # This is because we don't want current period data
            print("Successfully downloaded all new data.")
            print("Inserting data to live program...")
            self.insert_data(newData)
            print("Storing updated data to database...")
            if self.dump_to_table():
                print("Successfully stored all new data to database.")
            else:
                print("Insertion to database failed. Will retry next run.")
        else:
            print("Database is up-to-date.")

    def get_data_from_csv(self, file):
        """
        Retrieves information from CSV, parses it, and adds it to run-time data.
        :return: List of dictionaries
        """
        with open(file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            next(csv_reader)  # skip over the header row
            for row in csv_reader:
                self.data.append({'date': datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S'),
                                  'open': float(row[1]),
                                  'high': float(row[2]),
                                  'low': float(row[3]),
                                  'close': float(row[4]),
                                  })

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
            dataList = [parsedDate] + data[1:]
            self.data.insert(0, {'date': dataList[0],
                                 'open': float(dataList[1]),
                                 'high': float(dataList[2]),
                                 'low': float(dataList[3]),
                                 'close': float(dataList[4]),
                                 })

    def update_data(self):
        """
        Updates run-time data with Binance API values.
        """
        latestDate = self.data[0]['date']
        timestamp = int(latestDate.timestamp()) * 1000
        print(f"Previous data found up to UTC {latestDate + timedelta(minutes=self.get_interval_minutes())}.")
        if not self.data_is_updated():
            newData = self.binanceClient.get_historical_klines(self.symbol, self.interval, timestamp, limit=1000)
            del newData[-1]  # removing current period data
            self.insert_data(newData)
            print("Data has been updated successfully.")
        else:
            print("Data is up-to-date.")

    def get_interval_minutes(self):
        if self.intervalUnit == 'h':
            return self.intervalMeasurement * 60
        elif self.intervalUnit == 'm':
            return self.intervalMeasurement
        elif self.intervalUnit == 'd':
            return self.intervalMeasurement * 24 * 60
        else:
            print("Invalid interval.")
            return None

    def is_valid_symbol(self, symbol):
        tickers = self.binanceClient.get_all_tickers()
        for ticker in tickers:
            if ticker['symbol'] == symbol:
                return True
        return False

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
            print(f'Invalid interval. Available intervals are: \n{availableIntervals}')
            return False

    def get_csv_data(self, interval):
        """
        Creates a new CSV file with interval specified.
        :param interval: Interval to get data for.
        """
        if not self.is_valid_interval(interval):
            return
        timestamp = self.binanceClient._get_earliest_valid_timestamp(self.symbol, interval)
        print("Downloading all available historical data. This may take a while...")
        newData = self.binanceClient.get_historical_klines(self.symbol, interval, timestamp, limit=1000)
        print("Downloaded all data successfully.")
        fileName = f'btc_data_{interval}.csv'
        with open(fileName, 'w') as f:
            f.write("Date, Open, High, Low, Close\n")
            for data in newData:
                parsedDate = datetime.fromtimestamp(int(data[0]) / 1000, tz=timezone.utc)
                f.write(f'{parsedDate}, {data[1]}, {data[2]}, {data[3]}, {data[4]}\n')
        path = os.path.join(os.getcwd(), fileName)
        print(f'Data saved to {path}.')

    def valid_average_input(self, shift, prices, extraShift=0):
        if shift < 0:
            print("Shift cannot be less than 0.")
            return False
        elif prices <= 0:
            print("Prices cannot be 0 or less than 0.")
            return False
        elif shift + extraShift + prices > len(self.data) + 1:
            print("Shift + prices period cannot be more than data available.")
            return False
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
        if not self.valid_average_input(shift, prices):
            return None

        data = [self.get_current_data()] + self.data
        data = data[shift: prices + shift]

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
        if not self.valid_average_input(shift, prices):
            return None

        data = [self.get_current_data()] + self.data
        total = data[shift][parameter] * prices
        data = data[shift + 1: prices + shift]

        index = 0
        divisor = prices * (prices + 1) / 2
        for x in range(prices - 1, 0, -1):
            total += x * data[index][parameter]
            index += 1

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
        if not self.valid_average_input(shift, prices, sma_prices):
            return None
        elif sma_prices <= 0:
            print("Initial amount of SMA values for initial EMA must be greater than 0.")
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

    def process_socket_message(self, msg):
        """
        Defines how to process incoming WebSocket messages
        """
        if msg['e'] != 'error':
            self.btc_price['current'] = float(msg['k']['c'])
            self.btc_price['open'] = float(msg['k']['o'])
            self.btc_price['high'] = float(msg['k']['h'])
            self.btc_price['low'] = float(msg['k']['l'])
            self.btc_price['date'] = datetime.now(tz=timezone.utc)
            if self.btc_price['error']:
                print("Successfully reconnected.")
                self.btc_price['error'] = False
        else:
            self.btc_price['error'] = True
            print("Something went wrong. Attempting to restart...")
            # self.bsm.stop_socket(self.conn)
            self.bsm.close()
            self.bsm.start_kline_socket(self.symbol, self.process_socket_message, self.interval)
            # self.bsm.start()

    def get_current_data(self):
        """
        Retrieves current market dictionary with open, high, low, close prices.
        :return: A dictionary with current open, high, low, and close prices.
        """
        try:
            current = datetime.now(tz=timezone.utc)
            if self.intervalUnit == 'h':
                currentIntervalDate = datetime(current.year, current.month, current.day, current.hour,
                                               tzinfo=timezone.utc)
            elif self.intervalUnit == 'm':
                currentIntervalDate = datetime(current.year, current.month, current.day, current.hour, current.minute,
                                               tzinfo=timezone.utc)
                remainder = currentIntervalDate.minute % self.intervalMeasurement
                currentIntervalDate = currentIntervalDate - timedelta(minutes=remainder)
            elif self.intervalUnit == 'd':
                currentIntervalDate = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)
            else:
                print("Unknown interval unit.")
                return None

            nextIntervalDate = currentIntervalDate + timedelta(minutes=self.get_interval_minutes())
            currentHourTimestamp = int(currentIntervalDate.timestamp() * 1000)
            nextHourTimestamp = int(nextIntervalDate.timestamp() * 1000) - 1
            currentData = self.binanceClient.get_klines(symbol=self.symbol,
                                                        interval=self.interval,
                                                        startTime=currentHourTimestamp,
                                                        endTime=nextHourTimestamp,
                                                        )[0]
            currentDataDictionary = {'date': currentIntervalDate,
                                     'open': float(currentData[1]),
                                     'high': float(currentData[2]),
                                     'low': float(currentData[3]),
                                     'close': float(currentData[4])}
            return currentDataDictionary
        except Exception as e:
            print(e)
            print("Attempting to fix...")
            time.sleep(2)
            self.get_current_data()
        # return self.btc_price

    def get_current_price(self):
        """
        Returns the current market BTC price.
        :return: BTC market price
        """
        try:
            return float(self.binanceClient.get_symbol_ticker(symbol=self.symbol)['price'])
        except Exception as e:
            print(e)
            time.sleep(2)
            self.get_current_price()
        # return self.btc_price['current']

    def process_transaction(self):
        pass

    def buy_long(self, usd=None):
        """
        Buys BTC at current market price with amount of USD specified. If not specified, assumes bot goes all in.
        Function also takes into account Binance's 0.1% transaction fee.
        """
        if usd is None:
            usd = self.balance

        if usd <= 0:
            print("You cannot buy with $0 or less.")
            if self.balance <= 0:
                print("Looks like you have run out of money.")
            return
        elif usd > self.balance:
            print(f'You currently have ${self.balance}. You cannot invest ${usd}.')
            return

        transactionFee = usd * self.transactionFee
        currentPrice = self.get_current_price()
        btcBought = (usd - transactionFee) / currentPrice
        self.buyLongPrice = currentPrice
        self.btc += btcBought
        self.balance -= usd

    def sell_long(self, btc=None):
        """
        Sells specified amount of BTC at current market price. If not specified, assumes bot sells all BTC.
        Function also takes into account Binance's 0.1% transaction fee.
        """
        if btc is None:
            btc = self.btc

        if btc <= 0:
            print("You cannot sell 0 or negative BTC.")
            if self.btc <= 0:
                print("Looks like you do not have any BTC.")
            return
        elif btc > self.btc:
            print(f'You currently have {self.btc} BTC. You cannot sell {btc} BTC.')
            return

        currentPrice = self.get_current_price()
        earned = btc * currentPrice * (1 - self.transactionFee)
        self.btc -= btc
        self.balance += earned

        if self.btc == 0:
            self.buyLongPrice = None

    def buy_short(self, btc=None):
        """
        Buys borrowed BTC at current market price and returns to market.
        Function also takes into account Binance's 0.1% transaction fee.
        If BTC amount is not specified, bot will assume to buy all owed back
        BTC.
        """
        if btc is None:
            btc = self.btcOwed

        if btc <= 0:
            print("You cannot buy 0 or less BTC.")
            return

        currentPrice = self.get_current_price()
        lost = currentPrice * btc * (1 + self.transactionFee)
        self.btcOwed -= btc
        self.balance -= lost

        if self.btcOwed == 0:
            self.sellShortPrice = None

    def sell_short(self, btc=None):
        """
        Borrows BTC and sells them at current market price.
        Function also takes into account Binance's 0.1% transaction fee.
        If no BTC is provided in function, bot will assume we borrow as much as
        bot can buy with current balance and market value.
        """
        currentPrice = self.get_current_price()

        if btc is None:
            transactionFee = self.balance * self.transactionFee
            btc = (self.balance - transactionFee) / currentPrice

        if btc <= 0:
            print("You cannot borrow 0 or less BTC.")
            return

        earned = currentPrice * btc * (1 - self.transactionFee)
        self.btcOwed += btc
        self.btcOwedPrice = currentPrice
        self.balance += earned
        self.sellShortPrice = currentPrice

    def add_trade(self, action):
        self.simulatedTrades.append({
            'date': datetime.utcnow(),
            'action': action
        })

    def generate_log_file(self):
        currentDirectory = os.getcwd()
        folderName = 'Logs'

        try:
            os.mkdir(folderName)
        except OSError:
            pass

        os.chdir(folderName)
        with open(self.logFile, 'w') as f:
            f.write(self.log)

        print(f'Successfully generated log at {os.path.join(os.getcwd(), self.logFile)}')

        os.chdir(currentDirectory)

    def past_data_simulate(self):
        self.balance = self.balance
        while True:
            tradingType1 = None
            tradingType2 = None
            tradingTypes = ('WMA', 'EMA', 'SMA')
            while tradingType1 not in tradingTypes:
                tradingType1 = input(f'Type in your first trading type (e.g. {tradingTypes})>> ').upper()
            while tradingType2 not in tradingTypes:
                tradingType2 = input(f'Type in your second trading type (e.g. {tradingTypes})>> ').upper()

            parameters = ('open', 'high', 'low', 'close')
            parameter1 = None
            parameter2 = None
            while parameter1 not in parameters:
                parameter1 = input(f"Type in your first parameter (e.g. {parameters})>> ").lower()
            while parameter2 not in parameters:
                parameter2 = input(f"Type in your second parameter (e.g. {parameters})>> ").lower()

            print(f'Is this correct? Initial: {tradingType1} - {parameter1} | Final: {tradingType2} - {parameter2}')
            success = input('Type in "y" or "n">> ').lower()
            if success.startswith('y'):
                break

        print("Running simulation...")

    def log_and_print(self, message):
        self.log += f'\n{message}'
        print(message)

    def validate_cross(self, waitTime, tradeType, initialBound, finalBound, parameter, comparison, safetyMargin):
        if waitTime > 0:
            print(f'Cross detected. Waiting {waitTime} seconds to validate...')
        time.sleep(waitTime)
        if not self.validate_trade(tradeType, initialBound, finalBound, parameter, comparison, safetyMargin):
            print("Cheeky averages occurred. Fucking reptilians.")
            return False
        return True

    def simulate_option_1(self, tradeType, initialBound, finalBound, parameter, loss, comparison):
        fail = False
        if comparison == '>':
            reverseComparison = '<'
        else:
            reverseComparison = '>'

        while True:
            try:
                self.print_basic_information(loss)

                if fail:
                    print("Successfully reconnected.")
                    fail = False

                if not self.data_is_updated():
                    self.update_data()

                self.print_trade_type(tradeType, initialBound, finalBound, parameter)
                if self.buyLongPrice is None:
                    if self.validate_trade(tradeType, initialBound, finalBound, parameter, comparison):
                        print(f"{tradeType}({initialBound}) > {tradeType}({finalBound}). Going all in to buy long.")
                        self.buy_long()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Bought long as {tradeType}({initialBound}) > {tradeType}({finalBound}).'
                        })
                        if self.sellShortPrice is not None:
                            print("Buying short.")
                            self.buy_short()
                            self.simulatedTrades.append({
                                'date': datetime.utcnow(),
                                'action': f'Bought short as {tradeType}({initialBound}) > {tradeType}({finalBound}).'
                            })
                else:
                    if self.get_current_price() < self.buyLongPrice * (1 - loss):
                        print(f'Loss is greater than {loss * 100}%. Selling all BTC.')
                        self.sell_long()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Sold long because loss was greater than {loss * 100}%.'
                        })
                    elif self.validate_trade(tradeType, initialBound, finalBound, parameter, reverseComparison):
                        print(f'Cross detected - {tradeType}({initialBound}) < {tradeType}({finalBound}. Selling long.')
                        self.sell_long()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Sold long because {tradeType}({initialBound}) < {tradeType}({finalBound}.'
                        })
                        if self.sellShortPrice is None:
                            self.sell_short()
                            self.simulatedTrades.append({
                                'date': datetime.utcnow(),
                                'action': f'Sold short because {tradeType}({initialBound}) < {tradeType}({finalBound}..'
                            })

                if self.sellShortPrice is None:
                    if self.validate_trade(tradeType, initialBound, finalBound, parameter, reverseComparison):
                        print(f"{tradeType}({initialBound}) < {tradeType}({finalBound}). Going all in to sell short")
                        self.sell_short()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Sold short as {tradeType}({initialBound}) < {tradeType}({finalBound}).'
                        })
                        if self.buyLongPrice is not None:
                            print("Selling long.")
                            self.sell_long()
                            self.simulatedTrades.append({
                                'date': datetime.utcnow(),
                                'action': f'Sold long as {tradeType}({initialBound}) < {tradeType}({finalBound}).'
                            })
                else:
                    if self.get_current_price() > self.sellShortPrice * (1 + loss):
                        print(f'Loss is greater than {loss * 100}% in short trade. Returning all borrowed BTC.')
                        self.buy_short()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Bought short because loss was greater than {loss * 100}%.'
                        })
                    elif self.validate_trade(tradeType, initialBound, finalBound, parameter, comparison):
                        print("Cross detected. Buying short")
                        self.buy_short()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Bought short because {tradeType}({initialBound}) > {tradeType}({finalBound}.'
                        })
                        if self.buyLongPrice is None:
                            self.buy_long()
                            self.simulatedTrades.append({
                                'date': datetime.utcnow(),
                                'action': f'Bought long because {tradeType}({initialBound}) > {tradeType}({finalBound}.'
                            })

                print("Type CTRL-C to cancel the program at any time.")
                time.sleep(1)
            except KeyboardInterrupt:
                return
            except Exception as e:
                if not fail:
                    print(f'ERROR: {e}')
                    print("Something went wrong. Trying again in 5 seconds.")
                time.sleep(5)
                print("Attempting to fix error...")
                fail = True

    def simulate_option_2(self, tradeType, initialBound, finalBound, parameter, loss, trailingLoss, comparison, timer,
                          margin):
        fail = False
        waitShort = False
        waitLong = False
        waitTime = 0
        safetySleep = timer
        safetyMargin = margin
        self.longTrailingPrice = None
        self.shortTrailingPrice = None
        inLongPosition = False
        inShortPosition = False

        self.log += f'Simulation starting from {self.startingTime}.' \
                    f'\nSafety timer: {timer}.' \
                    f'\nSafety margin: {margin}' \
                    f'\nTrailing Loss: {trailingLoss}'

        if comparison == '>':
            reverseComparison = '<'
        else:
            reverseComparison = '>'

        while True:
            if len(self.simulatedTrades) > 0:
                waitTime = safetySleep
            try:
                self.print_basic_information(loss)

                if fail:
                    self.log_and_print("Successfully fixed error.")
                    fail = False

                if not self.data_is_updated():
                    self.update_data()

                self.print_trade_type(tradeType, initialBound, finalBound, parameter)

                currentPrice = self.get_current_price()
                if trailingLoss:
                    if self.longTrailingPrice is not None and currentPrice < self.longTrailingPrice:
                        self.longTrailingPrice = currentPrice
                    elif self.shortTrailingPrice is not None and currentPrice > self.shortTrailingPrice:
                        self.shortTrailingPrice = currentPrice

                if not inShortPosition:
                    if self.buyLongPrice is None and not inLongPosition:
                        if not waitLong:
                            if self.validate_trade(tradeType, initialBound, finalBound, parameter, comparison,
                                                   safetyMargin):
                                if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                                           comparison, safetyMargin):
                                    continue
                                self.log_and_print(f"{tradeType}({initialBound}) > {tradeType}({finalBound}). "
                                                   f"Buying long.")
                                self.buy_long()
                                if trailingLoss:
                                    self.longTrailingPrice = currentPrice
                                inLongPosition = True
                                self.add_trade(f'Bought long: {tradeType}({initialBound}) > {tradeType}({finalBound}).')
                        else:  # Checks if there is a cross to sell short.
                            if self.validate_trade(tradeType, initialBound, finalBound, parameter, reverseComparison,
                                                   safetyMargin):
                                self.log_and_print("Cross detected.")
                                waitLong = False

                    else:
                        if trailingLoss:
                            lossPrice = self.longTrailingPrice
                        else:
                            lossPrice = self.buyLongPrice

                        if currentPrice < lossPrice * (1 - loss):
                            self.log_and_print(f'Loss is greater than {loss * 100}%. Selling all BTC.')
                            self.sell_long()
                            self.longTrailingPrice = None
                            inLongPosition = False
                            waitLong = True
                            self.add_trade(f'Sold long because loss was greater than {loss * 100}%. Waiting for cross.')

                        elif self.validate_trade(tradeType, initialBound, finalBound, parameter, reverseComparison,
                                                 safetyMargin):
                            if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                                       reverseComparison, safetyMargin):
                                continue
                            self.log_and_print(f'{tradeType}({initialBound}) < {tradeType}({finalBound}). '
                                               f'Cross! Selling long.')
                            self.sell_long()
                            self.longTrailingPrice = None
                            inLongPosition = False
                            waitLong = False
                            self.add_trade(f'Sold long because a cross was detected.')

                if not inLongPosition:
                    if self.sellShortPrice is None and not inShortPosition:
                        if not waitShort:
                            if self.validate_trade(tradeType, initialBound, finalBound, parameter, reverseComparison,
                                                   safetyMargin):
                                if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                                           reverseComparison, safetyMargin):
                                    continue
                                self.log_and_print(f'{tradeType}({initialBound}) < {tradeType}({finalBound}). '
                                                   f'Selling short.')
                                self.sell_short()
                                if trailingLoss:
                                    self.shortTrailingPrice = currentPrice
                                inShortPosition = True
                                self.add_trade(f'Sold short as {tradeType}({initialBound}) < {tradeType}({finalBound})')
                        else:
                            if self.validate_trade(tradeType, initialBound, finalBound, parameter, comparison,
                                                   safetyMargin):
                                self.log_and_print("Cross detected!")
                                waitShort = False
                    else:
                        if trailingLoss:
                            lossPrice = self.shortTrailingPrice
                        else:
                            lossPrice = self.sellShortPrice

                        if currentPrice > lossPrice * (1 + loss):
                            self.log_and_print(f'Loss is greater than {loss * 100}%. Buying short.')
                            self.buy_short()
                            self.shortTrailingPrice = None
                            inShortPosition = False
                            self.add_trade(
                                f'Bought short because loss is greater than {loss * 100}%. Waiting for cross')
                            waitShort = True

                        elif self.validate_trade(tradeType, initialBound, finalBound, parameter, comparison,
                                                 safetyMargin):
                            if not self.validate_cross(waitTime, tradeType, initialBound, finalBound, parameter,
                                                       comparison, safetyMargin):
                                continue
                            self.log_and_print(f'{tradeType}({initialBound}) > {tradeType}({finalBound}). Cross! '
                                               f'Buying short.')
                            self.buy_short()
                            self.shortTrailingPrice = None
                            inShortPosition = False
                            self.add_trade(f'Bought short because a cross was detected.')
                            waitShort = False

                print("Type CTRL-C to cancel the program at any time.")
                time.sleep(1)
            except KeyboardInterrupt:
                return
            except Exception as e:
                if not fail:
                    self.log_and_print(f'ERROR: {e}')
                    self.log_and_print("Something went wrong. Trying again in 5 seconds.")
                time.sleep(5)
                self.log_and_print("Attempting to fix error...")
                fail = True

    def simulate(self, tradeType="WMA", parameter="high", initialBound=20, finalBound=24, loss=0.015, comparison='>'):
        """
        Starts a live simulation with given parameters.
        :param parameter: Type of parameter to use for averages. e.g close, open, high, low.
        :param tradeType: Type of trade. e.g. SMA, WMA, EMA.
        :param initialBound: Initial bound. e.g SMA(9) > SMA(11), initial bound would be 9.
        :param finalBound: Final bound. e.g SMA(9) > SMA(11), final bound would be 11.
        :param comparison: Comparison for trade type. SMA(1) > SMA(2) would be >.
        :param loss: Loss percentage at which we sell long or buy short.
        """
        parameter = parameter.lower()
        tradeType = tradeType.upper()
        self.simulatedTrades = []
        self.sellShortPrice = None
        self.buyLongPrice = None
        self.shortTrailingPrice = None
        self.longTrailingPrice = None
        self.balance = 1000
        self.simulationStartingBalance = self.balance
        self.startingTime = datetime.now()
        self.logFile = f'{self.startingTime.strftime("%Y-%m-%d_%H-%M-%S")}.log'
        self.log = ''

        if comparison != '>':
            temp = initialBound
            initialBound = finalBound
            finalBound = temp
            comparison = '>'

        self.easter_egg()

        simulationType = None
        while simulationType not in ('1', '2'):
            simulationType = input('Enter 1 for stop loss or 2 for trailing loss strategy>>')

        safetyTimer = None
        while safetyTimer is None:
            try:
                safetyTimer = int(input("Type in your safety timer (or 0 for no timer)>>"))
            except ValueError:
                print("Please type in a valid number.")

        safetyMargin = None
        while safetyMargin is None:
            try:
                safetyMargin = float(input("Type in your safety margin (for 2% type 0.02 or 0 for no margin)>>"))
            except ValueError:
                print("Please type in a valid number.")

        print("Starting simulation...")
        if simulationType == '1':
            self.simulate_option_2(tradeType, initialBound, finalBound, parameter, loss, False, comparison, safetyTimer,
                                   safetyMargin)
        elif simulationType == '2':
            self.simulate_option_2(tradeType, initialBound, finalBound, parameter, loss, True, comparison, safetyTimer,
                                   safetyMargin)
        print("\nExiting simulation.")
        self.endingTime = datetime.now()
        self.get_simulation_result()
        self.generate_log_file()

    def get_profit(self):
        balance = self.balance
        currentPrice = self.get_current_price()
        balance += self.btc * currentPrice * (1 - self.transactionFee)
        balance -= self.btcOwed * currentPrice * (1 + self.transactionFee)
        return balance - self.simulationStartingBalance

    def print_basic_information(self, loss):
        """
        Prints out basic information about trades.
        """
        self.log_and_print('---------------------------------------------------')
        profit = 0
        currentPrice = self.get_current_price()
        self.log_and_print(f'\nCurrent time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        if self.btc > 0:
            self.log_and_print(f'BTC: {self.btc}')
            self.log_and_print(f'Price bot bought BTC long for: ${self.buyLongPrice}')
        if self.btcOwed > 0:
            self.log_and_print(f'BTC owed: {self.btcOwed}')
            self.log_and_print(f'BTC owed price: ${self.btcOwedPrice}')
            self.log_and_print(f'Price bot sold BTC short for: ${self.sellShortPrice}')
        if self.longTrailingPrice is not None:
            self.log_and_print(f'\nCurrent in long position.')
            self.log_and_print(f'Long trailing loss value: ${round(self.longTrailingPrice * (1 - loss), 2)}')
        if self.shortTrailingPrice is not None:
            self.log_and_print(f'\nCurrent in short position.')
            self.log_and_print(f'Short trailing loss value: ${round(self.shortTrailingPrice * (1 + loss), 2)}')
        if self.shortTrailingPrice is None and self.longTrailingPrice is None:
            if self.buyLongPrice is not None:
                self.log_and_print(f'Stop loss: {round(self.buyLongPrice * (1 - loss), 2)}')
            elif self.sellShortPrice is not None:
                self.log_and_print(f'Stop loss: {round(self.sellShortPrice * (1 + loss), 2)}')

        self.log_and_print(f'\nCurrent BTC price: ${currentPrice}')
        self.log_and_print(f'Balance: ${round(self.balance, 2)}')
        self.log_and_print(f'Debt: ${round(self.btcOwed * currentPrice, 2)}')
        self.log_and_print(f'Liquid Cash: ${round(self.balance - self.btcOwed * currentPrice, 2)}')
        self.log_and_print(f'\nTrades conducted this simulation: {len(self.simulatedTrades)}')
        profit = round(self.get_profit(), 2)
        if profit > 0:
            self.log_and_print(f'Profit: ${profit}')
        elif profit < 0:
            self.log_and_print(f'Loss: ${-profit}')
        else:
            self.log_and_print(f'No profit or loss currently.')
        self.log_and_print('')

    def get_simulation_result(self):
        """
        Gets end result of simulation.
        """
        if self.btc > 0:
            self.log_and_print("Selling all BTC...")
            self.sell_long()
            self.simulatedTrades.append({
                'date': datetime.utcnow(),
                'action': f'Sold long as simulation ended.'
            })
        if self.btcOwed > 0:
            self.log_and_print("Returning all borrowed BTC...")
            self.buy_short()
            self.simulatedTrades.append({
                'date': datetime.utcnow(),
                'action': f'Bought short as simulation ended.'
            })
        self.log_and_print("\nResults:")
        self.log_and_print(f'Starting time: {self.startingTime}')
        self.log_and_print(f'End time: {self.endingTime}')
        self.log_and_print(f'Elapsed time: {self.endingTime - self.startingTime}')
        self.log_and_print(f'Starting balance: ${self.simulationStartingBalance}')
        self.log_and_print(f'Ending balance: ${round(self.balance, 2)}')
        self.log_and_print(f'Trades conducted: {len(self.simulatedTrades)}')
        if self.balance > self.simulationStartingBalance:
            profit = self.balance - self.simulationStartingBalance
            self.log_and_print(f"Profit: ${round(profit, 2)}")
        elif self.balance < self.simulationStartingBalance:
            loss = self.simulationStartingBalance - self.balance
            self.log_and_print(f'Loss: ${round(loss, 2)}')
        else:
            self.log_and_print("No profit or loss occurred.")

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

    def print_trade_type(self, tradeType, initialBound, finalBound, parameter):
        """
        Prints out general information about current trade.
        :param tradeType: Current trade type.
        :param initialBound: Initial bound for trade algorithm.
        :param finalBound: Final bound for trade algorithm.
        :param parameter: Type of parameter used.
        """
        self.log_and_print(f'Parameter: {parameter}')
        if tradeType == 'SMA':
            self.log_and_print(f'{tradeType}({initialBound}) = {self.get_sma(initialBound, parameter)}')
            self.log_and_print(f'{tradeType}({finalBound}) = {self.get_sma(finalBound, parameter)}')
        elif tradeType == 'WMA':
            self.log_and_print(f'{tradeType}({initialBound}) = {self.get_wma(initialBound, parameter)}')
            self.log_and_print(f'{tradeType}({finalBound}) = {self.get_wma(finalBound, parameter)}')
        elif tradeType == 'EMA':
            self.log_and_print(f'{tradeType}({initialBound}) = {self.get_ema(initialBound, parameter)}')
            self.log_and_print(f'{tradeType}({finalBound}) = {self.get_ema(finalBound, parameter)}')
        else:
            self.log_and_print(f'Unknown trade type {tradeType}.')

    def validate_trade(self, tradeType, initialBound, finalBound, parameter, comparison, safetyMargin=0):
        """
        Checks if bot should go ahead with trade. If trade-type with initial bound is logically compared with trade-type
        with final bound, a boolean is returned whether it is true or false.
        :param safetyMargin: Safety margin to check if cross has occurred.
        :param tradeType: Type of trade conducted.
        :param initialBound: Initial bound for trade algorithm.
        :param finalBound: Final bound for trade algorithm.
        :param parameter: Parameter to use for trade algorithm.
        :param comparison: Comparison whether trade type is greater than or less than.
        :return: A boolean whether trade should be performed or not.
        """
        if tradeType == 'SMA':
            sma = self.get_sma(initialBound, parameter)
            if comparison == '>':
                return sma + sma * safetyMargin > self.get_sma(finalBound, parameter)
            else:
                return sma + sma * safetyMargin < self.get_sma(finalBound, parameter)
        elif tradeType == 'WMA':
            wma = self.get_wma(initialBound, parameter)
            if comparison == '>':
                return wma + wma * safetyMargin > self.get_wma(finalBound, parameter)
            else:
                return wma + wma * safetyMargin < self.get_wma(finalBound, parameter)
        elif tradeType == 'EMA':
            ema = self.get_ema(initialBound, parameter)
            if comparison == '>':
                return ema + ema * safetyMargin > self.get_ema(finalBound, parameter)
            else:
                return ema + ema * safetyMargin < self.get_ema(finalBound, parameter)
        else:
            print(f'Unknown trading type {tradeType}.')
            return False

    def check_cross(self, tradeType, initialBound, finalBound, parameter, comparison, previousCondition):
        pass
        # """
        # Checks if there is a cross.
        # :param previousCondition: Previous condition whether it was in a short or long position.
        # :param comparison: Previous comparison.
        # :param tradeType: Algorithm used type. e.g. SMA, WMA, or EMA
        # :param initialBound: First bound for algorithm.
        # :param finalBound: Final bound for algorithm.
        # :param parameter: Type of parameter used. eg. high, close, low, open
        # :return: A boolean whether there is a cross or not.
        # """
        # if tradeType == 'SMA':
        #     if comparison == '>':
        #         if previousCondition == 'long':
        #             return False
        #         return self.get_sma(initialBound, parameter) > self.get_sma(finalBound, parameter)
        #     else:
        #         if previousCondition == 'long':
        #             return False
        #         return self.get_sma(initialBound, parameter) < self.get_sma(finalBound, parameter)
        # elif tradeType == 'EMA':
        #     if comparison == '>':
        #         return self.get_ema(initialBound, parameter) > self.get_ema(finalBound, parameter)
        #     else:
        #         return self.get_ema(initialBound, parameter) < self.get_ema(finalBound, parameter)
        # elif tradeType == 'WMA':
        #     if comparison == '>':
        #         return self.get_wma(initialBound, parameter) > self.get_wma(finalBound, parameter)
        #     else:
        #         return self.get_wma(initialBound, parameter) < self.get_wma(finalBound, parameter)
        # else:
        #     return False

    @staticmethod
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
            print("Rush B P90 no stop. Suka blyat pidaras tvoya mat.")
        elif number == 11:
            print('Wakanda forever.')
        elif number == 12:
            print('Read the manuals. Read the books.')
        elif number == 13:
            print('4 cases in New Zealand? Lock down everything again!')
        elif number == 14:
            print('Plandemic pandemic.')
        elif number == 15:
            print('You think money is a powerful tool? Fuck that, fear will always fuck you up.')
        else:
            print("Fucking shape shifting reptilians, bro. Fucking causing this virus and shit.")

        time.sleep(sleepTime)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f'Trader(startingBalance={self.startingBalance})'
