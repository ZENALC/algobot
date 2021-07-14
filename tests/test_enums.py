import unittest

from algobot.enums import OrderType


class OrderTypeTest(unittest.TestCase):
    def test_get_trailing_or_stop_loss_string(self):
        self.assertEqual(OrderType.to_str(OrderType.STOP), "Stop")
        self.assertEqual(OrderType.to_str(OrderType.TRAILING), "Trailing")
        self.assertEqual(OrderType.to_str(None), "None")


class LossStrategyTest(unittest.TestCase):
    def test_get_trailing_or_stop_loss_string(self):
        self.assertEqual(OrderType.to_str(OrderType.STOP), "Stop")
        self.assertEqual(OrderType.to_str(OrderType.TRAILING), "Trailing")
        self.assertEqual(OrderType.to_str(None), "None")
