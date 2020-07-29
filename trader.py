import sqlite3
import os
import csv
import time
from datetime import datetime, timedelta, timezone
from binance.client import Client


class Trader:
    def __init__(self, startingBalance=1000):
        self.databaseFile = 'btc.db'
        self.apiKey = os.environ.get('binance_api')
        self.apiSecret = os.environ.get('binance_secret')
        self.binanceClient = Client(self.apiKey, self.apiSecret)
        self.databaseConnection, self.databaseCursor = self.get_database_connectors()
        self.data = []
        self.ema_data = {}
        self.startingBalance = startingBalance
        self.balance = self.startingBalance
        self.btc = 0
        self.btcOwed = 0
        self.btcOwedPrice = 0
        self.transactionFee = 0.001
        self.buyLongPrice = None
        self.sellShortPrice = None
        self.simulatedTradesConducted = 0
        self.simulatedTrades = []

        self.create_table()
        self.get_data_from_database()
        if not self.updated_database():
            print("Updating data...")
            self.update_database()
        else:
            print("Database is up-to-date.")

    def get_database_connectors(self):
        connection = sqlite3.connect(self.databaseFile)
        cursor = connection.cursor()
        return connection, cursor

    def get_data_from_database(self):
        """
        Loads data from database and adds it to run-time data.
        """
        print("Retrieving data from database...")
        self.databaseCursor.execute('SELECT "trade_date", "open_price",'
                                    '"high_price", "low_price", "close_price"'
                                    'FROM BTC ORDER BY trade_date DESC')
        rows = self.databaseCursor.fetchall()

        for row in rows:
            self.data.append({'date': datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc),
                              'open': float(row[1]),
                              'high': float(row[2]),
                              'low': float(row[3]),
                              'close': float(row[4]),
                              })

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
                                  'close': float(row[1].replace(',', '')),
                                  'open': float(row[2].replace(',', '')),
                                  'high': float(row[3].replace(',', '')),
                                  'low': float(row[4].replace(',', '')),
                                  })

    def updated_data(self):
        """
        Checks whether data is fully updated or not.
        :return: A boolean whether data is updated or not with Binance values.
        """
        latestDate = self.data[0]['date']
        return latestDate + timedelta(hours=1) >= datetime.now(timezone.utc)

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
                                 'high': float(data[2]),
                                 'low': float(dataList[3]),
                                 'close': float(dataList[4]),
                                 })

    def update_data(self):
        """
        Updates run-time data with Binance API values.
        """
        latestDate = self.data[0]['date']
        timestamp = int(latestDate.timestamp()) * 1000
        print(f"Previous data found up to UTC {latestDate}.")
        if not self.updated_data():
            newData = self.binanceClient.get_historical_klines('BTCUSDT', '1h', timestamp, limit=1000)
            self.insert_data(newData)
            print("Data has been updated successfully.")
        else:
            print("Data is up-to-date.")

    def updated_database(self):
        """
        Checks if data is updated or not with database by 1 hour UTC time.
        :return: A boolean whether data is updated or not.
        """
        self.databaseCursor.execute('SELECT trade_date FROM BTC ORDER BY trade_date DESC LIMIT 1')
        result = self.databaseCursor.fetchone()
        if result is None:
            print("No data found.")
            return False
        latestDate = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return latestDate + timedelta(hours=1) >= datetime.now(timezone.utc)

    def update_database(self):
        """
        Updates database by retrieving information from Binance API
        """
        self.databaseCursor.execute('SELECT trade_date FROM BTC ORDER BY trade_date DESC LIMIT 1')
        result = self.databaseCursor.fetchone()
        if result is None:
            timestamp = self.binanceClient._get_earliest_valid_timestamp('BTCUSDT', '5m')
            print("Downloading all available historical data. This may take a while...")
        else:
            latestDate = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            timestamp = int(latestDate.timestamp()) * 1000
            print(f"Previous data found up to UTC {latestDate} found.")

        if not self.updated_database():
            newData = self.binanceClient.get_historical_klines('BTCUSDT', '1h', timestamp, limit=1000)
            print("Successfully downloaded all new data.")
            self.insert_data(newData)
            print("Storing updated data to database...")
            if self.dump_to_table():
                print("Successfully stored all new data to database.")
            else:
                print("Insertion to database failed. Will retry next run.")
        else:
            print("Database is up-to-date.")

    def create_table(self):
        """
        Creates a new table 'BTC' if it does not exist
        """
        self.databaseCursor.execute('''
        CREATE TABLE IF NOT EXISTS BTC(
            trade_date TEXT PRIMARY KEY,
            open_price TEXT NOT NULL,
            high_price TEXT NOT NULL,
            low_price TEXT NOT NULL,
            close_price TEXT NOT NULL
        );''')

    def dump_to_table(self):
        """
        Dumps date and price information to database.
        :return: A boolean whether data entry was successful or not.
        """
        success = True
        for data in self.data:
            try:
                self.databaseCursor.execute("INSERT INTO BTC(trade_date, open_price, high_price, low_price, "
                                            "close_price) VALUES (?, ?, ?, ?, ?);",
                                            (data['date'].strftime('%Y-%m-%d %H:%M:%S'),
                                             data['open'],
                                             data['high'],
                                             data['low'],
                                             data['close'],
                                             ))
                self.databaseConnection.commit()
            except sqlite3.IntegrityError:
                pass
            except sqlite3.OperationalError:
                print("Data insertion was unsuccessful.")
                success = False
                break
        return success

    def get_current_data(self):
        """
        Retrieves current market dictionary with open, high, low, close prices.
        :return: A dictionary with current open, high, low, and close prices.
        """
        current = datetime.now(tz=timezone.utc)
        currentHourDate = datetime(current.year, current.month, current.day, current.hour, tzinfo=timezone.utc)
        nextHourDate = currentHourDate + timedelta(hours=1)
        currentHourTimestamp = int(currentHourDate.timestamp() * 1000)
        nextHourTimestamp = int(nextHourDate.timestamp() * 1000)
        currentData = self.binanceClient.get_klines(symbol='BTCUSDT',
                                                    interval='1h',
                                                    startTime=currentHourTimestamp,
                                                    endTime=nextHourTimestamp,
                                                    )[0]
        currentDataDictionary = {'date': nextHourDate,
                                 'open': float(currentData[1]),
                                 'high': float(currentData[2]),
                                 'low': float(currentData[3]),
                                 'close': float(currentData[4])}
        return currentDataDictionary

    def get_sma(self, prices, parameter, shift=0, round_value=True, current=False):
        """
        Returns the simple moving average with run-time data and prices provided.
        :param current: Boolean that takes into account whether we use current price bar or not.
        :param boolean round_value: Boolean that specifies whether return value should be rounded
        :param int prices: Number of values for average
        :param int shift: Prices shifted from current price
        :param str parameter: Parameter to get the average of (e.g. open, close, high or low values)
        :return: SMA
        """
        data = self.data[shift:prices + shift]
        if current:
            data = [self.get_current_data()] + data[:len(data) - 1]

        if prices == 0:
            print("Prices cannot be 0.")
            return
        elif prices == 1:
            return data[0][parameter]

        sma = sum([day[parameter] for day in data]) / prices
        if round_value:
            return round(sma, 2)
        return sma

    def get_wma(self, prices, parameter, round_value=True, current=True):
        """
        Returns the weighted moving average with run-time data and prices provided.
        :param current: Boolean that takes into account whether we use current price bar or not.
        :param boolean round_value: Boolean that specifies whether return value should be rounded
        :param int prices: Number of prices to loop over for average
        :param parameter: Parameter to get the average of (e.g. open, close, high or low values)
        :return: WMA
        """
        if prices == 0:
            print("Prices cannot be 0.")
            return

        if current:
            total = self.get_current_data()[parameter] * prices
        else:
            total = self.data[0][parameter] * prices

        index = 0
        divisor = prices * (prices + 1) / 2
        for x in range(prices - 1, 0, -1):
            total += x * self.data[index][parameter]
            index += 1

        wma = total / divisor
        if round_value:
            return round(wma, 2)
        return wma

    def get_ema(self, period, parameter, sma_prices=5, round_value=True, current=True):
        """
        Returns the exponential moving average with data provided.
        :param round_value: Boolean that specifies whether return value should be rounded
        :param current: Boolean that takes into account whether we use current price bar or not.
        :param int sma_prices: SMA prices to get first EMA over
        :param int period: Days to iterate EMA over (or the period)
        :param str parameter: Parameter to get the average of (e.g. open, close, high, or low values)
        :return: EMA
        """
        if period > len(self.data) or period < 0:
            print("Invalid price entered.")
            return

        shift = len(self.data) - sma_prices
        ema = self.get_sma(sma_prices, parameter, shift=shift, round_value=False)
        values = [(round(ema, 2), str(self.data[shift]['date']))]
        multiplier = 2 / (period + 1)
        for day in range(len(self.data) - sma_prices):
            current_index = len(self.data) - sma_prices - day - 1
            current_price = self.data[current_index][parameter]
            ema = current_price * multiplier + ema * (1 - multiplier)
            values.append((round(ema, 2), str(self.data[current_index]['date'])))

        if current:
            ema = self.get_current_data()[parameter] * multiplier + ema * (1 - multiplier)
            values.append((round(ema, 2), str(self.get_current_data()['date'])))

        self.ema_data[period] = {parameter: values}

        if round_value:
            return round(ema, 2)
        return ema

    def get_current_price(self):
        """
        Returns the current market BTC price.
        :return: BTC market price
        """
        return float(self.binanceClient.get_symbol_ticker(symbol="BTCUSDT")['price'])

    def process_transaction(self):
        pass

    def print_basic_information(self):
        """
        Prints out basic information about trades.
        :return:
        """
        print(f'\nCurrent time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'Current BTC price: ${self.get_current_price()}')
        print(f'Balance: ${self.balance}')
        if self.btc != 0:
            print(f'BTC: {self.btc}')
            print(f'Price we bought BTC long for: ${self.buyLongPrice}')
        if self.btcOwed != 0:
            print(f'BTC Owed: {self.btcOwed}')
            print(f'BTC Owed Price: ${self.btcOwedPrice}')
            print(f'Price we sold BTC short for: ${self.sellShortPrice}')
        print()

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
            self.buyLongPrice = 0

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

    def simulate(self, tradeType="SMA", parameter="high", initialBound=11, finalBound=19, comparison='>', loss=0.02):
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
        startingBalance = self.balance
        if comparison != '>':
            temp = initialBound
            initialBound = finalBound
            finalBound = temp
            comparison = '>'

        while True:
            try:
                self.print_basic_information()
                if not self.updated_data():
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
                        self.simulatedTradesConducted += 1
                        if self.sellShortPrice is not None:
                            self.buy_short()
                            self.simulatedTrades.append({
                                'date': datetime.utcnow(),
                                'action': f'Bought short as {tradeType}({initialBound}) > {tradeType}({finalBound}).'
                            })
                            self.simulatedTradesConducted += 1
                else:
                    if self.get_current_price() < self.buyLongPrice * (1 - loss):
                        print(f'Loss is greater than {loss * 100}%. Selling all BTC.')
                        self.sell_long()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Sold long because loss was greater than {loss * 100}%.'
                        })
                        self.simulatedTradesConducted += 1
                    elif self.check_cross(tradeType, initialBound, finalBound, parameter):
                        print("Cross detected. Selling long and selling short.")
                        self.sell_long()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Sold long because a cross was detected.'
                        })
                        self.sell_short()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Sold short because a cross was detected.'
                        })
                        self.simulatedTradesConducted += 2

                if self.sellShortPrice is not None:
                    if self.get_current_price() > self.sellShortPrice * (1 + loss):
                        print(f'Loss is greater than {loss * 100}% in short trade. Returning all borrowed BTC.')
                        self.buy_short()
                        self.simulatedTrades.append({
                            'date': datetime.utcnow(),
                            'action': f'Bought short because loss was greater than {loss * 100}%.'
                        })
                        self.simulatedTradesConducted += 1

                print("Type CTRL-C to cancel the program at any time.")
                time.sleep(1)
            except KeyboardInterrupt:
                print("\nExiting simulation.")
                self.print_simulation_result(startingBalance)
                break

    def print_simulation_result(self, startingBalance):
        if self.btc > 0:
            print("Selling all BTC...")
            self.sell_long()
            self.simulatedTrades.append({
                'date': datetime.utcnow(),
                'action': f'Sold long as simulation ended.'
            })
        if self.btcOwed > 0:
            print("Returning all borrowed BTC...")
            self.buy_short()
            self.simulatedTrades.append({
                'date': datetime.utcnow(),
                'action': f'Bought short as simulation ended.'
            })
        print("\nResults:")
        print(f'Starting balance: ${startingBalance}')
        print(f'Ending balance: ${self.balance}')
        print(f'Trades conducted: {len(self.simulatedTrades)}')
        print(f'Lifetime trades conducted: {self.simulatedTradesConducted}')
        if self.balance > startingBalance:
            profit = self.balance - startingBalance
            print(f"Profit: ${profit}")
        elif self.balance < startingBalance:
            loss = startingBalance - self.balance
            print(f'Loss: ${loss}')
        else:
            print("No profit or loss occurred.")

        if len(self.simulatedTrades) > 0:
            print("\nYou can view the trades from the simulation in more detail.")
            print("Please type in bot.view_simulated_trades() to view them.")

    def view_simulated_trades(self):
        print(f'\nTotal trade(s) in previous simulation: {len(self.simulatedTrades)}')
        for counter, trade in enumerate(self.simulatedTrades, 1):
            print(f'\n{counter}. Date in UTC: {trade["date"]}')
            print(f'Action taken: {trade["action"]}')

    def print_trade_type(self, tradeType, initialBound, finalBound, parameter):
        print(f'Parameter: {parameter}')
        if tradeType == 'SMA':
            print(f'{tradeType}({initialBound}) = {self.get_sma(initialBound, parameter)}')
            print(f'{tradeType}({finalBound}) = {self.get_sma(finalBound, parameter)}')
        elif tradeType == 'WMA':
            print(f'{tradeType}({initialBound}) = {self.get_wma(initialBound, parameter)}')
            print(f'{tradeType}({finalBound}) = {self.get_wma(finalBound, parameter)}')
        elif tradeType == 'EMA':
            print(f'{tradeType}({initialBound}) = {self.get_ema(initialBound, parameter)}')
            print(f'{tradeType}({finalBound}) = {self.get_ema(finalBound, parameter)}')
        else:
            print(f'Unknown trade type {tradeType}.')

    def validate_trade(self, tradeType, initialBound, finalBound, parameter, comparison):
        if tradeType == 'SMA':
            if comparison == '>':
                return self.get_sma(initialBound, parameter) > self.get_sma(finalBound, parameter)
            else:
                return self.get_sma(initialBound, parameter) < self.get_sma(finalBound, parameter)
        elif tradeType == 'WMA':
            if comparison == '>':
                return self.get_wma(initialBound, parameter) > self.get_wma(finalBound, parameter)
            else:
                return self.get_wma(initialBound, parameter) < self.get_wma(finalBound, parameter)
        elif tradeType == 'EMA':
            if comparison == '>':
                return self.get_ema(initialBound, parameter) > self.get_ema(finalBound, parameter)
            else:
                return self.get_ema(initialBound, parameter) < self.get_ema(finalBound, parameter)
        else:
            print(f'Unknown trading type {tradeType}.')
            return False

    def check_cross(self, tradeType, initialBound, finalBound, parameter):
        """
        Checks if there is a cross.
        :param tradeType: Algorithm used type. e.g. SMA, WMA, or EMA
        :param initialBound: First bound for algorithm.
        :param finalBound: Final bound for algorithm.
        :param parameter: Type of parameter used. eg. high, close, low, open
        :return: A boolean whether there is a cross or not.
        """
        if tradeType == 'SMA':
            return self.get_sma(initialBound, parameter) == self.get_sma(finalBound, parameter)
        elif tradeType == 'EMA':
            return self.get_ema(initialBound, parameter) == self.get_ema(finalBound, parameter)
        elif tradeType == 'WMA':
            return self.get_wma(initialBound, parameter) == self.get_wma(finalBound, parameter)
        else:
            return False

    def __str__(self):
        return f'Trader()'

    def __repr__(self):
        return 'Trader()'
