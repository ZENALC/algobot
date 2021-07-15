import unittest

from algobot.enums import OrderType


class OrderTypeTest(unittest.TestCase):
    def test_from_str(self):
        self.assertEqual(OrderType.from_str("Stop"), OrderType.STOP)
        self.assertEqual(OrderType.from_str("Trailing"), OrderType.TRAILING)

    def test_from_str_unsupported(self):
        with self.assertRaises(ValueError):
            OrderType.from_str("Random")

    def test_to_str(self):
        self.assertEqual(OrderType.to_str(OrderType.STOP), "Stop")
        self.assertEqual(OrderType.to_str(OrderType.TRAILING), "Trailing")
        self.assertEqual(OrderType.to_str(None), "None")

    def test_to_str_unsupported(self):
        with self.assertRaises(ValueError):
            OrderType.to_str(100)
