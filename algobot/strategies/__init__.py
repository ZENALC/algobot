"""
Initialization of all strategies.
"""
from collections import namedtuple
from os import listdir
from os.path import basename, dirname
from typing import Callable, Dict, List, Union

import talib

__all__ = [basename(f)[:-3] for f in listdir(dirname(__file__)) if f[-3:] == ".py" and not f.endswith("__init__.py")]
ARGUMENT = namedtuple("ARGUMENT", "name type")

STREAM = 'STREAM'
TALIB = 'TALIB'
ARGS = 'ARGS'


MA_STREAM_MAP: Dict[str, Dict[str, Union[Callable, List[namedtuple]]]] = {
    'DEMA': {  # TESTED
        STREAM: lambda s, i: talib.DEMA(s, i).iloc[-1],
        TALIB: talib.DEMA,
        ARGS: [
            ARGUMENT("Time period", int)
        ]
    },
    'EMA': {  # TESTED
        STREAM: lambda s, i: talib.EMA(s, i).iloc[-1],
        TALIB: talib.EMA,
        ARGS: [
            ARGUMENT("Time period", int)
        ]
    },
    'FAMA': {
        STREAM: lambda s, i, fast, slow: talib.MAMA(s, i, fast, slow).iloc[-1][1],  # 0th is MAMA, 1st is FAMA.
        TALIB: talib.MAMA,
        ARGS: [
            ARGUMENT("Time period", int), ARGUMENT("Fast Limit", int), ARGUMENT("Slow Limit", int)
        ]
    },
    'KAMA': {  # TESTED
        STREAM: lambda s, i: talib.KAMA(s, i).iloc[-1],
        TALIB: talib.KAMA,
        ARGS: [
            ARGUMENT("Time period", int)
        ]
    },
    'MAMA': {
        STREAM: lambda s, i, fast, slow: talib.MAMA(s, i, fast, slow).iloc[-1][0],  # 0th is MAMA, 1st is FAMA.
        TALIB: talib.MAMA,
        ARGS: [
            ARGUMENT("Time period", int), ARGUMENT("Fast Limit", int), ARGUMENT("Slow Limit", int)
        ]
    },
    'SMA': {  # TESTED
        STREAM: talib.stream.SMA,
        TALIB: talib.SMA,
        ARGS: [
            ARGUMENT("Time period", int)
        ]
    },
    'TEMA': {  # TESTED
        STREAM: lambda s, i: talib.TEMA(s, i).iloc[-1],
        TALIB: talib.TEMA,
        ARGS: [
            ARGUMENT("Time period", int)
        ]
    },
    'TRIMA': {  # TESTED
        'stream': lambda s, i: talib.TRIMA(s, i).iloc[-1],
        'talib': talib.TRIMA,
        'args': [
            ARGUMENT("Time period", int)
        ]
    },
    'T3': {
        STREAM: lambda s, i, v: talib.T3(s, i, v).iloc[-1],
        TALIB: talib.T3,
        ARGS: [
            ARGUMENT("Time period", int), ARGUMENT("V Factor", float)
        ]
    },
    'WMA': {  # TESTED
        STREAM: talib.stream.WMA,
        TALIB: talib.WMA,
        ARGS: [
            ARGUMENT("Time period", int)
        ]
    },
}
