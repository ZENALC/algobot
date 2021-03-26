import unittest

from algobot.data import Data


class MyTestCase(unittest.TestCase):
    dataObject = Data(interval='1h', symbol='YFIUSDT', loadData=True)

    def test_initialization(self):
        self.assertTrue(self.dataObject.data, 'Data initialization test.')

    def test_validate_interval(self):
        self.dataObject.validate_interval('15m')
        self.dataObject.validate_interval('30m')
        self.assertRaises(ValueError, self.dataObject.validate_interval, '51m')

    def test_validate_symbol(self):
        self.dataObject.validate_symbol('BTCUSDT')
        self.dataObject.validate_symbol('YFIUSDT')
        self.assertRaises(ValueError, self.dataObject.validate_symbol, 'BAD')

    def test_get_latest_row(self):
        self.assertTrue(self.dataObject.get_latest_database_row())


if __name__ == '__main__':
    unittest.main()
