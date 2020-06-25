import sqlite3
import requests
import csv
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


class Trader:
    def __init__(self):
        self.url = 'https://coinmarketcap.com/currencies/bitcoin/historical-data/'
        self.jsonFile = 'btc.json'
        self.csvFile = 'btc.csv'
        self.databaseFile = 'btc.db'
        self.databaseConnection = sqlite3.connect(self.databaseFile)
        self.databaseCursor = self.databaseConnection.cursor()
        self.data = []

        self.create_table()
        if not self.updated_data():
            self.update_data()
        else:
            self.data = self.get_data_from_database()

    def get_data_from_database(self):
        """
        Loads data from database and returns it as a list of dictionaries
        :return: List of dictionaries
        """
        self.databaseCursor.execute('SELECT * FROM BTC ORDER BY trade_date DESC')
        rows = self.databaseCursor.fetchall()
        values = []

        for row in rows:
            values.append({'date': datetime.strptime(row[0], '%Y-%m-%d').date(),
                           'open': float(row[1]),
                           'high': float(row[2]),
                           'low': float(row[3]),
                           'close': float(row[4]),
                           'volume': int(row[5]),
                           'marketCap': int(row[6]),
                           })
        return values

    def get_data_from_csv(self):
        """
        Retrieves information from CSV, parses it, and returns it as a list of dictionaries
        :return: List of dictionaries
        """
        with open(self.csvFile) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            next(csv_reader)  # skip over the header row
            values = []
            for row in csv_reader:
                values.append({'date': datetime.strptime(row[0], '%m/%d/%y').date(),
                               'open': float(row[1]),
                               'high': float(row[2]),
                               'low': float(row[3]),
                               'close': float(row[4]),
                               'volume': int(row[5]),
                               'marketCap': int(row[6]),
                               })
            return values

    def get_data_from_url(self):
        """
        Scrapes latest BTC values from CoinMarketCap and returns them in a list of dictionaries.
        :return: List of dictionaries
        """
        response = requests.get(self.url)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr', attrs={'class': 'cmc-table-row'})
        values = []

        for row in rows:
            cols = row.find_all('td')
            values.append({'date': datetime.strptime(cols[0].text, '%b %d, %Y').date(),
                           'open': float(cols[1].text.replace(',', '')),
                           'high': float(cols[2].text.replace(',', '')),
                           'low': float(cols[3].text.replace(',', '')),
                           'close': float(cols[4].text.replace(',', '')),
                           'volume': int(cols[5].text.replace(',', '')),
                           'marketCap': int(cols[6].text.replace(',', '')),
                           })
        return values

    def updated_data(self):
        """
        Checks if data is already updated with yesterday's latest values
        :return: A boolean whether data is updated or not
        """
        self.databaseCursor.execute('SELECT trade_date FROM BTC ORDER BY trade_date DESC LIMIT 1')
        result = self.databaseCursor.fetchone()
        if result is None:
            return False
        date = datetime.strptime(result[0], '%Y-%m-%d').date()
        yesterday = datetime.today().date() - timedelta(days=1)
        return yesterday == date

    def update_data(self):
        """
        Updates database by retrieving information from CSV and URL
        """
        self.data += self.get_data_from_csv()
        self.data += self.get_data_from_url()
        self.dump_to_table()

    def create_table(self):
        """
        Creates a new table 'BTC' if it does not exist
        """
        self.databaseCursor.execute('''
        CREATE TABLE IF NOT EXISTS BTC(
            trade_date TEXT PRIMARY KEY,
            open_price TEXT NOT NULL,
            close_price TEXT NOT NULL,
            high_price TEXT NOT NULL,
            low_price TEXT NOT NULL,
            volume TEXT NOT NULL,
            market_cap TEXT NOT NULL
        );''')

    def dump_to_table(self):
        """
        Dumps information from CSV and URL to database.
        """
        for data in self.data:
            try:
                self.databaseCursor.execute("INSERT INTO BTC VALUES (?, ?, ?, ?, ?, ?, ?);",
                                            (data['date'],
                                             data['open'],
                                             data['high'],
                                             data['low'],
                                             data['close'],
                                             data['volume'],
                                             data['marketCap']
                                             ))
                self.databaseConnection.commit()
            except sqlite3.IntegrityError:
                pass

    def get_sma(self, days, parameter, shift=0, round_value=True):
        """
        Returns the simple moving average with data provided.
        :param boolean round_value: Boolean that specifies whether return value should be rounded
        :param int days: Number of days for average
        :param int shift: Days shifted from today
        :param str parameter: Parameter to get the average of (e.g. open, close, high or low values)
        :return: SMA
        """
        data = self.data[shift:days + shift]
        sma = sum([day[parameter] for day in data]) / days
        if round_value:
            return round(sma, 2)
        return sma

    def get_ema(self, ema_days, parameter, sma_days=5, round_value=True):
        """
        Returns the exponential moving average with data provided.
        :param round_value: Boolean that specifies whether return value should be rounded
        :param int sma_days: SMA days to get first EMA
        :param int ema_days: Days to iterate EMA for
        :param str parameter: Parameter to get the average of (e.g. open, close, high, or low values)
        :return: EMA
        """
        shift = len(self.data) - sma_days
        ema = self.get_sma(sma_days, parameter, shift=shift, round_value=False)
        for day in range(len(self.data) - sma_days):
            multiplier = 2 / (ema_days + 1)
            current_index = len(self.data) - sma_days - day - 1
            current_price = self.data[current_index][parameter]
            ema = current_price * multiplier + ema * (1 - multiplier)
        if round_value:
            return round(ema, 2)
        return ema

    def __str__(self):
        return f'Trader()'

    def __repr__(self):
        return 'Trader()'
