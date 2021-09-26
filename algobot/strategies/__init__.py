"""
Initialization of all strategies.
"""
from collections import namedtuple
from dataclasses import dataclass
from os import listdir
from os.path import basename, dirname
from typing import Any, Callable, List, Type

import talib

__all__ = [basename(f)[:-3] for f in listdir(dirname(__file__)) if f[-3:] == ".py" and not f.endswith("__init__.py")]


@dataclass
class Arg:
    """
    Data class to map TALIB functions with names, types, and arguments.
    """
    name: str
    type: Type
    default: Any = None


STREAM = 'STREAM'
TALIB = 'TALIB'
ARGS = 'ARGS'


class TALIBEntry:
    """
    Entry class for TALIB Map defined below.
    """
    def __init__(self, name: str, stream: Callable, talib_func: Callable, args: List[namedtuple]):
        self.name = name
        self.stream = stream
        self.talib = talib_func
        self.args = args

    def get_func(self, arg: str) -> Callable:
        """
        Get func based on arg provided.
        :param arg: Argument for what type of function should be returned.
        :return: Argument type.
        """
        arg = arg.upper()

        if arg == STREAM:
            return self.stream
        if arg == TALIB:
            return self.talib

        raise ValueError("Invalid argument.")


class TALIBMap:
    """
    Main map that'll contain TALIB related information.
    """
    MA = ('DEMA', 'EMA', 'KAMA', 'SMA', 'TEMA', 'TRIMA', 'WMA')

    def __init__(self):

        # MA - related
        self.dema = TALIBEntry(  # TESTED
            name="DEMA",
            stream=lambda s, i: talib.DEMA(s, i).iloc[-1],
            talib_func=talib.DEMA,
            args=[Arg("Time Period", int)]
        )

        self.ema = TALIBEntry(  # TESTED
            name='EMA',
            stream=lambda s, i: talib.EMA(s, i).iloc[-1],
            talib_func=talib.EMA,
            args=[Arg("Time Period", int)]
        )

        self.fama = TALIBEntry(
            name='FAMA',
            stream=lambda s, i, fast, slow: talib.MAMA(s, i, fast, slow).iloc[-1][1],  # 0th is MAMA, 1st is FAMA.
            talib_func=talib.MAMA,
            args=[Arg("Time Period", int), Arg("Fast Limit", int), Arg("Slow Limit", int)]
        )

        self.kama = TALIBEntry(  # TESTED
            name='KAMA',
            stream=lambda s, i: talib.KAMA(s, i).iloc[-1],
            talib_func=talib.KAMA,
            args=[Arg("Time Period", int)]
        )

        self.mama = TALIBEntry(
            name='MAMA',
            stream=lambda s, i, fast, slow: talib.MAMA(s, i, fast, slow).iloc[-1][0],  # 0th is MAMA, 1st is FAMA.
            talib_func=talib.MAMA,
            args=[Arg("Time Period", int), Arg("Fast Limit", int), Arg("Slow Limit", int)]
        )

        self.sma = TALIBEntry(  # TESTED
            name='SMA',
            stream=talib.stream.SMA,
            talib_func=talib.SMA,
            args=[Arg("Time Period", int)]
        )

        self.tema = TALIBEntry(  # TESTED
            name='TEMA',
            stream=lambda s, i: talib.TEMA(s, i).iloc[-1],
            talib_func=talib.TEMA,
            args=[Arg("Time Period", int)]
        )

        self.trima = TALIBEntry(  # TESTED
            name='TRIMA',
            stream=lambda s, i: talib.TRIMA(s, i).iloc[-1],
            talib_func=talib.TRIMA,
            args=[Arg("Time Period", int)]
        )

        # pylint: disable=invalid-name
        self.t3 = TALIBEntry(
            name='T3',
            stream=lambda s, i, v: talib.T3(s, i, v).iloc[-1],
            talib_func=talib.T3,
            args=[Arg("Time Period", int), Arg("V Factor", float)]
        )

        self.wma = TALIBEntry(  # TESTED
            name='WMA',
            stream=talib.stream.WMA,
            talib_func=talib.WMA,
            args=[Arg("Time Period", int)]
        )

        self.bbands = TALIBEntry(  # TESTED
            name='Bollinger Band',
            stream=talib.stream.BBANDS,
            talib_func=talib.BBANDS,
            args=[Arg("Time Period", int), Arg("NB Dev Up", int, 2), Arg("NB Dev Down", int, 2)]
        )

    def get_entry(self, entry: str) -> TALIBEntry:
        """
        Get TALIB entry based on entry provided. It will parse the entry into underscores when it encounters a space.
        :param entry: Entry to get TALIB entry of.
        :return: TALIB entry.
        """
        parsed = '_'.join(entry.lower().split(' '))
        return getattr(self, parsed)


TALIB_MAP_SINGLETON = TALIBMap()
