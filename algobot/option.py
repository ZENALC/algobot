from typing import Tuple


class Option:
    """
    Helper class object for trading options.
    """
    def __init__(self, movingAverage, parameter, initialBound, finalBound):
        self.movingAverage = movingAverage
        self.parameter = parameter
        self.initialBound = initialBound
        self.finalBound = finalBound
        self.previousInitialAverage = None
        self.previousFinalAverage = None

    def set_previous_initial_average(self, previousInitialAverage):
        """
        Sets previous initial average for trading option.
        """
        self.previousInitialAverage = previousInitialAverage

    def set_previous_final_average(self, previousFinalAverage):
        """
        Sets previous final average for trading option.
        """
        self.previousFinalAverage = previousFinalAverage

    def set_moving_average(self, movingAverage):
        """
        Sets moving average for trading option.
        """
        self.movingAverage = movingAverage

    def set_parameter(self, parameter):
        """
        Sets parameter for trading option.
        """
        self.parameter = parameter

    def set_initial_bound(self, initialBound):
        """
        Sets initial bound for trading option.
        """
        self.initialBound = initialBound

    def set_final_bound(self, initialBound):
        """
        Sets final bound for trading option.
        """
        self.initialBound = initialBound

    def get_moving_average(self):
        """
        Returns current trading option's moving average.
        """
        return self.movingAverage

    def get_parameter(self):
        """
        Returns current trading option's parameter.
        """
        return self.parameter

    def get_initial_bound(self):
        """
        Returns current trading option's initial bound.
        """
        return self.initialBound

    def get_final_bound(self):
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

    def __repr__(self):
        """
        Returns class representation of object.
        """
        return f'Option({self.movingAverage}, {self.parameter}, {self.initialBound}, {self.finalBound})'
