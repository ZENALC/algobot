import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup


class Trader:
    def __init__(self):
        self.url = 'https://coinmarketcap.com/currencies/bitcoin/historical-data/'
        self.jsonFile = 'btc.json'

        if not self.updated_data():
            self.data = self.get_data()
            with open(self.jsonFile, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        else:
            with open(self.jsonFile, 'r', encoding='utf-8') as f:
                self.data = json.load(f)

    def updated_data(self):
        today = datetime.today().date()
        try:
            with open(self.jsonFile, 'r', encoding='utf-8') as f:
                date = datetime.strptime(json.load(f)[0]['date'], '%b %d, %Y').date()
                return date == today
        except FileNotFoundError:
            return False

    def get_data(self):
        response = requests.get(self.url)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr', attrs={'class': 'cmc-table-row'})
        values = []

        for row in rows:
            cols = row.find_all('td')
            values.append({'date': cols[0].text,
                           'open': cols[1].text,
                           'high': cols[2].text,
                           'low': cols[3].text,
                           'close': cols[4].text,
                           'volume': cols[5].text,
                           'marketCap': cols[6].text,
                           })
        return values

    def get_sma(self, days, value):
        """
        Returns the simple moving average with data provided.
        :param int days: Number of days for average
        :param str value: Parameter to get the average of (e.g. open, close, high or low values)
        """
        data = self.data[:days]
        return sum([float(day[value].replace(',', '')) for day in data]) / days

    def get_ema(self, days, value, initial_value=None):
        if not initial_value:
            initial_value = self.get_sma(days, value)
        multiplier = 2 / (days + 1)

    def __str__(self):
        return f'Trader()'

    def __repr__(self):
        return 'Trader()'



