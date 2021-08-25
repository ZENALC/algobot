"""
Enum classes and constants.
"""

from enum import IntEnum

BULLISH = "Bullish"
BEARISH = "Bearish"
ENTER_LONG = "Enter Long"
EXIT_LONG = "Exit Long"
ENTER_SHORT = "Enter Short"
EXIT_SHORT = "Exit Short"


class GraphType(IntEnum):
    """
    Graph type enums.
    """
    NET = "NET"
    AVG = "AVG"


LONG = "Long"
SHORT = "Short"

TRAILING = "Trailing"
STOP = "Stop"

BACKTEST = "Backtest"
SIMULATION = "Simulation"
LIVE = "Live"
OPTIMIZER = "Optimizer"
