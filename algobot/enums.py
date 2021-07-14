# TODO: Add unit tests.
from typing import Optional

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


class OrderType:
    TRAILING = 2
    STOP = 1

    @staticmethod
    def from_str(value: str) -> int:
        if value.lower() == "trailing":
            return OrderType.TRAILING
        elif value.lower() == "stop":
            return OrderType.STOP
        else:
            ValueError(f"{value} is unsupported")

    @staticmethod
    def to_str(loss_strategy: Optional[int]) -> str:
        if loss_strategy == OrderType.STOP:
            return "Stop"
        elif loss_strategy == OrderType.TRAILING:
            return "Trailing"
        elif loss_strategy is None:
            return "None"
        else:
            raise ValueError(f"Unknown type {loss_strategy}")


BACKTEST = 2
SIMULATION = 3
LIVE = 1
OPTIMIZER = 4
