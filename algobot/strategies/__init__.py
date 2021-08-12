"""
Initialization of all strategies.
"""

from os import listdir
from os.path import basename, dirname

import talib

__all__ = [basename(f)[:-3] for f in listdir(dirname(__file__)) if f[-3:] == ".py" and not f.endswith("__init__.py")]


MA_STREAM_MAP = {
    'DEMA': lambda s, i: talib.DEMA(s, i).iloc[-1],  # TESTED
    'EMA': lambda s, i: talib.EMA(s, i).iloc[-1],  # TESTED
    'KAMA': lambda s, i: talib.KAMA(s, i).iloc[-1],  # TESTED
    'SMA': talib.stream.SMA,  # TESTED
    'TEMA': lambda s, i: talib.TEMA(s, i).iloc[-1],  # TESTED
    'TRIMA': lambda s, i: talib.TRIMA(s, i).iloc[-1],  # TESTED
    'WMA': talib.stream.WMA  # TESTED
}

TALIB_MAP = {
    'DEMA': talib.DEMA,
    'EMA': talib.EMA,
    'KAMA': talib.KAMA,
    'SMA': talib.SMA,
    'TEMA': talib.TEMA,
    'TRIMA': talib.TRIMA,
    'WMA': talib.WMA
}
