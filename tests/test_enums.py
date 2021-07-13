import unittest

from algobot.enums import LossStrategy, ProfitType


class ProfitTypeTest(unittest.TestCase):
    def test_get_trailing_or_stop_loss_string(self):
        self.assertEqual(ProfitType.to_str(ProfitType.STOP), "Stop")
        self.assertEqual(ProfitType.to_str(ProfitType.TRAILING), "Trailing")
        self.assertEqual(ProfitType.to_str(None), "None")


class LossStrategyTest(unittest.TestCase):
    def test_get_trailing_or_stop_loss_string(self):
        self.assertEqual(LossStrategy.to_str(ProfitType.STOP), "Stop")
        self.assertEqual(LossStrategy.to_str(ProfitType.TRAILING), "Trailing")
        self.assertEqual(LossStrategy.to_str(None), "None")
