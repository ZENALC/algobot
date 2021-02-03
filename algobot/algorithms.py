from helpers import get_data_from_parameter


def get_wma(data: list, prices: int, parameter: str) -> float:
    total = get_data_from_parameter(data=data[0], parameter=parameter) * prices
    data = data[1:]

    index = 0
    for x in range(prices - 1, 0, -1):
        total += x * get_data_from_parameter(data=data[index], parameter=parameter)
        index += 1

    divisor = prices * (prices + 1) / 2
    wma = total / divisor
    return wma


def get_sma(data: list, prices: int, parameter: str) -> float:
    sma = sum([get_data_from_parameter(data=period, parameter=parameter) for period in data]) / prices
    return sma
