from typing import List

from data import Data
from enums import BEARISH, BULLISH
from option import Option


# Create your strategies here.


class Strategy:
    def __init__(self, name: str, parent, precision: int = 2):
        """
        Create all your strategies from this parent strategy class.
        :param name: Name of strategy.
        :param parent: Parent object that'll use this strategy.
        """
        self.name = name
        self.parent = parent
        self.precision = precision
        self.trend = None
        self.strategyDict = {}
        self.lowerIntervalDict = {}

    def get_trend(self, data: List[dict] or Data = None, log_data=False) -> int:
        """
        Implement your strategy here. Based on the strategy's algorithm, this should return a trend.
        A trend can be either bullish, bearish, or neither.
        :return: Enum representing the trend.
        """
        raise NotImplementedError("Implement a strategy to get trend.")

    def get_params(self) -> list:
        raise NotImplementedError("Implement a function to return parameters.")

    def reset_strategy_dictionary(self):
        """
        Clears strategy dictionary.
        """
        self.strategyDict = {}

    def get_appropriate_dictionary(self, data):
        if type(data) == list:
            return self.strategyDict
        elif type(data) == Data:
            if data == self.parent.dataView:
                return self.strategyDict
            else:
                return self.lowerIntervalDict
        else:
            raise ValueError("invalid type of data object.")


class StoicStrategy(Strategy):
    def __init__(self, parent, input1: int, input2: int, input3: int, precision: int = 2):
        super().__init__(name='Stoic', parent=parent, precision=precision)

        self.stoicInput1: int = input1
        self.stoicInput2: int = input2
        self.stoicInput3: int = input3

    # noinspection DuplicatedCode
    def get_trend(self, data: Data or List[dict] = None, shift: int = 0, update: bool = False, log_data=False):
        """
        Returns trend using the stoic strategy.
        :param log_data: Boolean that will determine where data is logged or not.
        :param update: Boolean to determine whether data needs to be updated or not.
        :param data: Data to use to determine the trend.
        :param shift: Shift period to go to previous data periods.
        :return: Stoic trend.
        """
        parent = self.parent
        input1 = self.stoicInput1
        input2 = self.stoicInput2
        input3 = self.stoicInput3

        if data:
            if type(data) == Data:
                rsi_values_one = [data.get_rsi(input1, shift=s, update=update) for s in range(shift, input1 + shift)]
                rsi_values_two = [data.get_rsi(input2, shift=s, update=update) for s in range(shift, input2 + shift)]
            elif type(data) == list:
                if len(data) <= max((input1, input2, input3)):
                    return None
                else:
                    rsi_values_one = [parent.get_rsi(data, input1, shift=s) for s in range(shift, input1 + shift)]
                    rsi_values_two = [parent.get_rsi(data, input2, shift=s) for s in range(shift, input2 + shift)]
            else:
                raise ValueError("Unknown type of data object provided.")
        else:  # Simulation Trader called this function.
            d = parent.dataView
            rsi_values_one = [d.get_rsi(input1, shift=s, update=update) for s in range(shift, input1 + shift)]
            rsi_values_two = [d.get_rsi(input2, shift=s, update=update) for s in range(shift, input2 + shift)]

        strategyDict = self.get_appropriate_dictionary(data)

        seneca = max(rsi_values_one) - min(rsi_values_one)
        if 'seneca' in strategyDict:
            strategyDict['seneca'].insert(0, seneca)
        else:
            strategyDict['seneca'] = [seneca]

        zeno = rsi_values_one[0] - min(rsi_values_one)
        if 'zeno' in strategyDict:
            strategyDict['zeno'].insert(0, zeno)
        else:
            strategyDict['zeno'] = [zeno]

        gaius = rsi_values_two[0] - min(rsi_values_two)
        if 'gaius' in strategyDict:
            strategyDict['gaius'].insert(0, gaius)
        else:
            strategyDict['gaius'] = [gaius]

        philo = max(rsi_values_two) - min(rsi_values_two)
        if 'philo' in strategyDict:
            strategyDict['philo'].insert(0, philo)
        else:
            strategyDict['philo'] = [philo]

        if len(strategyDict['gaius']) < 3:
            self.trend = None
            return None

        hadot = sum(strategyDict['gaius'][:3]) / sum(strategyDict['philo'][:3]) * 100
        if 'hadot' in strategyDict:
            strategyDict['hadot'].insert(0, hadot)
        else:
            strategyDict['hadot'] = [hadot]

        if len(strategyDict['hadot']) < 3:
            self.trend = None
            return None

        stoic = sum(strategyDict['zeno'][:3]) / sum(strategyDict['seneca'][:3]) * 100
        marcus = sum(strategyDict['hadot'][:input3]) / input3

        strategyDict['values'] = {
            'marcus': round(marcus, self.precision),
            'stoic': round(stoic, self.precision),
            'seneca': round(seneca, self.precision),
            'zeno': round(zeno, self.precision),
            'gaius': round(gaius, self.precision),
            'philo': round(philo, self.precision),
            'hadot': round(hadot, self.precision),
        }

        if marcus > stoic:
            self.trend = BEARISH
        elif marcus < stoic:
            self.trend = BULLISH
        else:
            self.trend = None

        for key in strategyDict:
            if key != 'values':
                strategyDict[key] = strategyDict[key][:3]

        return self.trend

    def get_params(self) -> list:
        return [self.stoicInput1, self.stoicInput2, self.stoicInput3]


class ShrekStrategy(Strategy):
    def __init__(self, parent, one: int, two: int, three: int, four: int, precision: int = 2):
        super().__init__(name='Shrek', parent=parent, precision=precision)

        self.one: int = one
        self.two: int = two
        self.three: int = three
        self.four: int = four

    def get_params(self) -> list:
        return [self.one, self.two, self.three, self.four]

    def get_trend(self, data: List[dict] or Data = None, shift: int = 0, update: bool = False, log_data=False):
        """
        Returns trend using the Shrek strategy.
        :param log_data: Boolean that will determine where data is logged or not.
        :param data: Data to use to determine the trend.
        :param update: Boolean to determine whether data needs to be updated or not.
        :param shift: Shift period to go to previous data periods.
        :return: Shrek trend.
        """
        parent = self.parent

        if data:
            if type(data) == list:
                if len(data) <= self.two + 1:
                    return None
                else:
                    data = [rsi for rsi in [parent.get_rsi(data, self.two, shift=x) for x in range(self.two + 1)]]
            elif type(data) == Data:
                data = [rsi for rsi in [data.get_rsi(self.two, update=update, shift=x) for x in range(self.two + 1)]]
            else:
                raise ValueError("Unknown type of data provided.")
        else:
            d = parent.dataView
            data = [rsi for rsi in [d.get_rsi(self.two, update=update, shift=x) for x in range(self.two + 1)]]

        rsi_two = data[0]
        apple = max(data) - min(data)
        beetle = rsi_two - min(data)

        strategyDict = self.get_appropriate_dictionary(data)

        if 'apple' in strategyDict:
            strategyDict['apple'].append(apple)
        else:
            strategyDict['apple'] = [apple]

        if 'beetle' in strategyDict:
            strategyDict['beetle'].append(beetle)
        else:
            strategyDict['beetle'] = [beetle]

        if len(strategyDict['apple']) < self.three + 1:
            return None
        else:
            carrot = sum(strategyDict['beetle'][:self.three + 1])
            donkey = sum(strategyDict['apple'][:self.three + 1])
            strategyDict['beetle'] = strategyDict['beetle'][1:]
            strategyDict['apple'] = strategyDict['apple'][1:]
            onion = carrot / donkey * 100

            strategyDict['values'] = {
                'apple': round(apple, self.precision),
                'beetle': round(beetle, self.precision),
                'carrot': round(carrot, self.precision),
                'donkey': round(donkey, self.precision),
                'onion': round(onion, self.precision)
            }

            if self.one > onion:
                self.trend = BULLISH
            elif onion > self.four:
                self.trend = BEARISH
            else:
                self.trend = None

            return self.trend


class MovingAverageStrategy(Strategy):
    def __init__(self, parent, tradingOptions, precision: int = 2):
        super().__init__(name='movingAverage', parent=parent, precision=precision)
        self.tradingOptions: List[Option] = tradingOptions
        self.validate_options()

    def get_min_option_period(self) -> int:
        """
        Returns the minimum period required to perform moving average calculations. For instance, if we needed to
        calculate SMA(25), we need at least 25 periods of data, and we'll only be able to start from the 26th period.
        :return: Minimum period of days required.
        """
        minimum = 0
        for option in self.tradingOptions:
            minimum = max(minimum, option.finalBound, option.initialBound)
        return minimum

    def get_params(self) -> list:
        return self.tradingOptions

    def get_trend(self, data: List[dict] or Data = None, log_data=False) -> int:
        parent = self.parent
        trends = []  # Current option trends. They all have to be the same to register a trend.

        if not data:
            data = parent.dataView

        if type(data) == Data:
            if not data.data_is_updated():
                data.update_data()

            if data == parent.dataView:
                parent.optionDetails = []
            else:
                parent.lowerOptionDetails = []

        for option in self.tradingOptions:
            movingAverage, parameter, initialBound, finalBound = option.get_all_params()
            initialName, finalName = option.get_pretty_option()

            if type(data) == list:
                avg1 = parent.get_moving_average(data, option.movingAverage, option.initialBound, option.parameter)
                avg2 = parent.get_moving_average(data, option.movingAverage, option.finalBound, option.parameter)
            else:
                avg1 = parent.get_average(movingAverage, parameter, initialBound, data, update=False)
                avg2 = parent.get_average(movingAverage, parameter, finalBound, data, update=False)

            if type(data) == Data:
                if data == parent.dataView:
                    if log_data:
                        parent.output_message(f'Regular interval ({data.interval}) data:')
                    parent.optionDetails.append((avg1, avg2, initialName, finalName))
                else:
                    if log_data:
                        parent.output_message(f'Lower interval ({data.interval}) data:')
                    parent.lowerOptionDetails.append((avg1, avg2, initialName, finalName))

                if log_data:
                    parent.output_message(f'{option.movingAverage}({option.initialBound}) = {avg1}')
                    parent.output_message(f'{option.movingAverage}({option.finalBound}) = {avg2}')

            if avg1 > avg2:
                trends.append(BULLISH)
            elif avg1 < avg2:
                trends.append(BEARISH)
            else:  # If they're the same, that means no trend.
                trends.append(None)

        if all(trend == BULLISH for trend in trends):
            self.trend = BULLISH
        elif all(trend == BEARISH for trend in trends):
            self.trend = BEARISH
        else:
            self.trend = None

        return self.trend

    def validate_options(self):
        """
        Validates options provided. If the list of options provided does not contain all options, an error is raised.
        """
        if len(self.tradingOptions) == 0:  # Checking whether options exist.
            raise ValueError("No trading options provided.")

        for option in self.tradingOptions:
            if type(option) != Option:
                raise TypeError(f"'{option}' is not a valid option type.")
