from typing import Tuple


class Option:
    """
    Helper class object for trading options.
    """
    def __init__(self, movingAverage: str, parameter: str, initialBound: int, finalBound: int):
        self.movingAverage = movingAverage.upper()
        self.parameter = parameter.lower()
        self.initialBound = initialBound
        self.finalBound = finalBound

    def get_all_params(self) -> Tuple[str, str, int, int]:
        """
        Returns all the option's parameters.
        :return: A tuple of option's parameters.
        """
        return self.movingAverage, self.parameter, self.initialBound, self.finalBound

    def set_moving_average(self, movingAverage: str):
        """
        Sets moving average for trading option.
        """
        self.movingAverage = movingAverage

    def set_parameter(self, parameter: str):
        """
        Sets parameter for trading option.
        """
        self.parameter = parameter

    def set_initial_bound(self, initialBound: int):
        """
        Sets initial bound for trading option.
        """
        self.initialBound = initialBound

    def set_final_bound(self, initialBound: int):
        """
        Sets final bound for trading option.
        """
        self.initialBound = initialBound

    def get_moving_average(self) -> str:
        """
        Returns current trading option's moving average.
        """
        return self.movingAverage

    def get_parameter(self) -> str:
        """
        Returns current trading option's parameter.
        """
        return self.parameter

    def get_initial_bound(self) -> int:
        """
        Returns current trading option's initial bound.
        """
        return self.initialBound

    def get_final_bound(self) -> int:
        """
        Returns current trading option's final bound.
        """
        return self.finalBound

    def get_pretty_option(self) -> Tuple[str, str]:
        """
        Returns a prettified tuple of option's initial and final bound.
        :return: A tuple of prettified option initial and final bound.
        """
        return (
            f'{self.movingAverage}({self.initialBound}) {self.parameter.capitalize()}',
            f'{self.movingAverage}({self.finalBound}) {self.parameter.capitalize()}',
        )

    def __repr__(self) -> str:
        """
        Returns class representation of object.
        """
        return f'Option({self.movingAverage}, {self.parameter}, {self.initialBound}, {self.finalBound})'
