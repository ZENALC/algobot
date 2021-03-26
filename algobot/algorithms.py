from typing import List, Tuple

from algobot.helpers import get_data_from_parameter


def get_wma(data: List[dict], prices: int, parameter: str, desc: bool = True) -> float:
    """
    Calculates the weighted moving average from data provided.
    The data is assumed to be in descending order - meaning newer dates are in the front of the list.
    :param desc: Order data is in. If descending, this will be true, else false.
    :param data: Data to calculate weighted moving average.
    :param prices: Periods of data to get weighted moving average.
    :param parameter: Parameter from data dictionary with which to get the weighted moving average.
    :return: Weighted moving average.
    """
    if desc:
        total = get_data_from_parameter(data=data[0], parameter=parameter) * prices
        data = data[1:]

        index = 0
        for x in range(prices - 1, 0, -1):
            total += x * get_data_from_parameter(data=data[index], parameter=parameter)
            index += 1
    else:
        total = get_data_from_parameter(data=data[-1], parameter=parameter) * prices
        data = data[:-1]

        for index, data in enumerate(data, start=1):
            total += index * get_data_from_parameter(data, parameter)

    divisor = prices * (prices + 1) / 2
    wma = total / divisor
    return wma


def get_sma(data: List[dict], prices: int, parameter: str) -> float:
    """
    Calculates the simple moving average from data provided.
    :param data: Data to calculate simple moving average.
    :param prices: Periods of data to get simple moving average.
    :param parameter: Parameter from data dictionary with which to get the simple moving average.
    :return: Simple moving average.
    """
    return sum([get_data_from_parameter(data=period, parameter=parameter) for period in data]) / prices


def get_ema(data: List[dict], prices: int, parameter: str, sma_prices: int, memo: dict = None, desc: bool = True) -> \
        Tuple[float, dict]:
    """
    Calculates the exponential moving average from data provided.
    The data is assumed to be in descending order - meaning newer dates are in the front of the list.
    :param desc: Order data is in. If descending, this will be true, else false.
    :param data: Data to calculate exponential moving average.
    :param prices: Periods to data to get exponential moving average.
    :param parameter: Parameter from data dictionary with which to get the exponential moving average.
    :param sma_prices: Initial SMA periods to use to calculate first exponential moving average.
    :param memo: Memoized dictionary containing past exponential moving averages data.
    :return: A tuple containing the exponential moving average and memoized dictionary.
    """
    multiplier = 2 / (prices + 1)

    if memo and prices in memo and parameter in memo[prices]:
        index = 0 if desc else -1
        current_price = get_data_from_parameter(data[index], parameter)
        if memo[prices][parameter][-1][1] == data[index]['date_utc']:
            previous_ema = memo[prices][parameter][-2][0]
            ema = current_price * multiplier + previous_ema * (1 - multiplier)
            memo[prices][parameter][-1][0] = ema
        elif memo[prices][parameter][-1][1] < data[index]['date_utc']:
            previous_ema = memo[prices][parameter][-1][0]
            ema = current_price * multiplier + previous_ema * (1 - multiplier)
            memo[prices][parameter].append([ema, data[index]['date_utc']])
        else:
            raise ValueError("Something went wrong in the calculation of the EMA.")
    else:
        if desc:
            sma_data = data[len(data) - sma_prices:]
        else:
            sma_data = data[:sma_prices]

        ema = get_sma(sma_data, sma_prices, parameter)
        if desc:
            values = [[ema, data[len(data) - sma_prices]['date_utc']]]
            data = data[:len(data) - sma_prices][::-1]  # Reverse the data to start from back to front.
        else:
            values = [[ema, data[sma_prices - 1]['date_utc']]]
            data = data[sma_prices:]

        for period in data:
            current_price = get_data_from_parameter(period, parameter=parameter)
            ema = current_price * multiplier + ema * (1 - multiplier)
            values.append([ema, period['date_utc']])

        if not memo:
            memo = {prices: {parameter: values}}
        elif memo and prices not in memo:
            memo[prices] = {parameter: values}
        else:
            memo[prices][parameter] = values

    return ema, memo


def get_rsi():
    pass
