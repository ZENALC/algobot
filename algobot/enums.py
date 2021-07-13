# TODO: Add unit tests.

BULLISH = 1
BEARISH = -1
ENTER_LONG = 2
EXIT_LONG = -2
ENTER_SHORT = -3
EXIT_SHORT = 3

NET_GRAPH = 1
AVG_GRAPH = 2

LONG = 1
SHORT = -1


class StopType:
    TRAILING = 2
    STOP = 1


class LossStrategy:
    TRAILING = 2
    STOP = 1


class ProfitType:
    TRAILING = 2
    STOP = 1


BACKTEST = 2
SIMULATION = 3
LIVE = 1
OPTIMIZER = 4
