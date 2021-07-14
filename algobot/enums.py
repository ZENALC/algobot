# TODO: Add unit tests.
from typing import Optional

BULLISH = 1
BEARISH = -1
ENTER_LONG = 2
EXIT_LONG = -2
ENTER_SHORT = -3
EXIT_SHORT = 3


class GraphType:
    # pylint: disable=too-few-public-methods
    NET = 1
    AVG = 2


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
    def to_str(order_type: Optional[int]) -> str:
        if order_type == OrderType.STOP:
            return "Stop"
        elif order_type == OrderType.TRAILING:
            return "Trailing"
        elif order_type is None:
            return "None"
        else:
            raise ValueError(f"Unknown OrderType with value {order_type}")


BACKTEST = 2
SIMULATION = 3
LIVE = 1
OPTIMIZER = 4
