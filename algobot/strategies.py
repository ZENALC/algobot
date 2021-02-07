from typing import List
from enums import BEARISH, BULLISH

# Create your strategies here.


class Strategy:
    def __init__(self, name: str, parent):
        """
        Create all your strategies from this parent strategy class.
        :param name: Name of strategy.
        :param parent: Parent object that'll use this strategy.
        """
        self.name = name
        self.parent = parent
        self.trend = None
        self.strategyDict = {}

    def get_trend(self, data: List[dict]) -> int:
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


class StoicStrategy(Strategy):
    def __init__(self, parent, input1: int, input2: int, input3: int):
        super().__init__(name='Stoic', parent=parent)

        self.stoicInput1: int = input1
        self.stoicInput2: int = input2
        self.stoicInput3: int = input3

    # noinspection DuplicatedCode
    def get_trend(self, data: List[dict], shift: int = 0):
        """
        Returns trend using the stoic strategy.
        :param data: Data to use to determine the trend.
        :param shift: Shift period to go to previous data periods.
        :return: Stoic trend.
        """
        parent = self.parent
        input1 = self.stoicInput1
        input2 = self.stoicInput2
        input3 = self.stoicInput3

        if len(data) <= max((input1, input2, input3)):
            return None

        rsi_values_one = [parent.get_rsi(data, input1, shift=shift) for shift in range(shift, input1 + shift)]
        rsi_values_two = [parent.get_rsi(data, input2, shift=shift) for shift in range(shift, input2 + shift)]

        seneca = max(rsi_values_one) - min(rsi_values_one)
        if 'seneca' in self.strategyDict:
            self.strategyDict['seneca'].insert(0, seneca)
        else:
            self.strategyDict['seneca'] = [seneca]

        zeno = rsi_values_one[0] - min(rsi_values_one)
        if 'zeno' in self.strategyDict:
            self.strategyDict['zeno'].insert(0, zeno)
        else:
            self.strategyDict['zeno'] = [zeno]

        gaius = rsi_values_two[0] - min(rsi_values_two)
        if 'gaius' in self.strategyDict:
            self.strategyDict['gaius'].insert(0, gaius)
        else:
            self.strategyDict['gaius'] = [gaius]

        philo = max(rsi_values_two) - min(rsi_values_two)
        if 'philo' in self.strategyDict:
            self.strategyDict['philo'].insert(0, philo)
        else:
            self.strategyDict['philo'] = [philo]

        if len(self.strategyDict['gaius']) < 3:
            self.trend = None
            return None

        hadot = sum(self.strategyDict['gaius'][:3]) / sum(self.strategyDict['philo'][:3]) * 100
        if 'hadot' in self.strategyDict:
            self.strategyDict['hadot'].insert(0, hadot)
        else:
            self.strategyDict['hadot'] = [hadot]

        if len(self.strategyDict['hadot']) < 3:
            self.trend = None
            return None

        stoic = sum(self.strategyDict['zeno'][:3]) / sum(self.strategyDict['seneca'][:3]) * 100
        marcus = sum(self.strategyDict['hadot'][:input3]) / input3

        if marcus > stoic:
            self.trend = BEARISH
        elif marcus < stoic:
            self.trend = BULLISH
        else:
            self.trend = None

        return self.trend

    def get_params(self) -> list:
        return [self.stoicInput1, self.stoicInput2, self.stoicInput3]


class ShrekStrategy(Strategy):
    def __init__(self, parent, one: int, two: int, three: int, four: int):
        super().__init__(name='Shrek', parent=parent)

        self.one: int = one
        self.two: int = two
        self.three: int = three
        self.four: int = four

    def get_params(self) -> list:
        return [self.one, self.two, self.three, self.four]

    def get_trend(self, data: List[dict]):
        """
        Returns trend using the Shrek strategy.
        :param data: Data to use to determine the trend.
        :return: Shrek trend.
        """
        parent = self.parent
        data = [rsi for rsi in [parent.get_rsi(data, self.two, shift=x) for x in range(self.two + 1)]]
        rsi_two = data[0]

        apple = max(data) - min(data)
        beetle = rsi_two - min(data)

        if 'apple' in self.strategyDict:
            self.strategyDict['apple'].append(apple)
        else:
            self.strategyDict['apple'] = [apple]

        if 'beetle' in self.strategyDict:
            self.strategyDict['beetle'].append(beetle)
        else:
            self.strategyDict['beetle'] = [beetle]

        if len(self.strategyDict['apple']) < self.three + 1:
            return None
        else:
            carrot = sum(self.strategyDict['beetle'][:self.three + 1])
            donkey = sum(self.strategyDict['apple'][:self.three + 1])
            self.strategyDict['beetle'] = self.strategyDict['beetle'][1:]
            self.strategyDict['apple'] = self.strategyDict['apple'][1:]
            onion = carrot / donkey * 100

            if self.one > onion:
                self.trend = BULLISH
            elif onion > self.four:
                self.trend = BEARISH
            else:
                self.trend = None

            return self.trend
