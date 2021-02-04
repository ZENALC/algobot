from typing import List, Tuple
from helpers import get_data_from_parameter


def get_wma(data: List[dict], prices: int, parameter: str) -> float:
    total = get_data_from_parameter(data=data[0], parameter=parameter) * prices
    data = data[1:]

    index = 0
    for x in range(prices - 1, 0, -1):
        total += x * get_data_from_parameter(data=data[index], parameter=parameter)
        index += 1

    divisor = prices * (prices + 1) / 2
    wma = total / divisor
    return wma


def get_sma(data: List[dict], prices: int, parameter: str) -> float:
    sma = sum([get_data_from_parameter(data=period, parameter=parameter) for period in data]) / prices
    return sma


def get_ema(data: List[dict], prices: int, parameter: str, sma_prices: int, memo: dict = None) -> Tuple[float, dict]:
    multiplier = 2 / (prices + 1)

    if memo and prices in memo and parameter in memo[prices]:
        current_price = get_data_from_parameter(data[0], parameter)
        if memo[prices][parameter][-1][1] == data[0]['date_utc']:
            previous_ema = memo[prices][parameter][-2][0]
            ema = current_price * multiplier + previous_ema * (1 - multiplier)
            memo[prices][parameter][-1][0] = ema
        elif memo[prices][parameter][-1][1] < data[0]['date_utc']:
            previous_ema = memo[prices][parameter][-1][0]
            ema = current_price * multiplier + previous_ema * (1 - multiplier)
            memo[prices][parameter].append([ema, data[0]['date_utc']])
        else:
            raise ValueError("Something went wrong in the calculation of the EMA.")
    else:
        sma_data = data[len(data) - sma_prices:]
        ema = get_sma(sma_data, sma_prices, parameter)
        values = [[ema, data[len(data) - sma_prices]['date_utc']]]

        data = data[:len(data) - sma_prices][::-1]  # Reverse the data to start from back to front.

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
