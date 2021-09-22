"""
Basic indicators. TODO: Deprecate and move to TA-LIB.
"""

import math
from datetime import datetime
from typing import Dict, List, Tuple, Union

import numpy as np

from algobot.helpers import get_data_from_parameter


def get_ddof_from_stdev(stdev_type: str) -> int:
    """
    Get the DDOF from standard deviation (used for numpy).
    :param stdev_type: Standard deviation type.
    :return: DDOF integer.
    """
    if stdev_type.lower() == 'population':
        return 0
    elif stdev_type.lower() == 'sample':
        return 1
    else:
        raise ValueError("The only valid STDEV types are sample and population.")


def validate(periods: int, data: List[Dict[str, float]]):
    """
    Validates periods and data length and raises an error if not logical.
    :param periods: Periods of data to validate against.
    :param data: Data to check length against.
    """
    if periods > len(data):
        raise IndexError(f"Not enough data periods. Need {periods}, got {len(data)}.")


def get_moving_average(moving_average: str, moving_average_parameter: str, moving_average_periods: int,
                       data: List[Dict[str, Union[float, str, datetime]]], cache: dict = None) -> float:
    """
    Get the moving average value based on the arguments provided.
    :param moving_average: Moving average (SMA, WMA, EMA).
    :param moving_average_parameter: Parameter (high, low, open, close, high-low, open-close)
    :param moving_average_periods: Number of periods.
    :param data: Data to use to get the moving average.
    :param cache: Cache dictionary to use for EMA (not required).
    :return: Moving average value.
    """
    moving_average = moving_average.upper()
    moving_average_parameter = moving_average_parameter.lower()
    moving_data = data[-moving_average_periods:]
    if moving_average == 'WMA':
        return get_wma(data=moving_data, prices=moving_average_periods, parameter=moving_average_parameter)
    elif moving_average == 'SMA':
        return get_sma(data=moving_data, prices=moving_average_periods, parameter=moving_average_parameter)
    elif moving_average == 'EMA':
        ema, _ = get_ema(data=moving_data, prices=moving_average_periods, parameter=moving_average_parameter,
                         memo=cache)
        return ema
    else:
        raise ValueError("Invalid moving average provided. Available are: EMA, SMA, and WMA.")


def get_wma(data: List[Dict[str, float]], prices: int, parameter: str, desc: bool = False) -> float:
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

        for index, period_data in enumerate(data, start=1):
            total += index * get_data_from_parameter(period_data, parameter)

    divisor = prices * (prices + 1) / 2
    wma = total / divisor
    return wma


def get_sma(data: List[Dict[str, float]], prices: int, parameter: str) -> float:
    """
    Calculates the simple moving average from data provided.
    :param data: Data to calculate simple moving average.
    :param prices: Periods of data to get simple moving average.
    :param parameter: Parameter from data dictionary with which to get the simple moving average.
    :return: Simple moving average.
    """
    return sum([get_data_from_parameter(data=period, parameter=parameter) for period in data]) / prices


def get_ema(data: List[dict], prices: int, parameter: str, sma_prices: int = 5, memo: dict = None,
            desc: bool = False) -> Tuple[float, dict]:
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
    if sma_prices <= 0:
        raise ValueError("Initial amount of SMA values for initial EMA must be greater than 0.")

    if sma_prices > len(data):
        sma_prices = len(data) - 1

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

# Volume Indicators


def get_money_flow_index(periods: int, data: List[Dict[str, float]]) -> float:
    """
    Returns the money flow index based on periods and data provided.
    :param periods: Number of periods to look previously.
    :param data: Dictionary containing open, high, close, low, and volume data.
    :return: Accumulation distribution indicator.
    """
    validate(periods=periods + 1, data=data)
    previous_typical_price = None
    negative_money_flows = 0
    positive_money_flows = 0
    for period in data[-periods - 1:]:
        typical_price = (period['high'] + period['low'] + period['close']) / 3
        raw_money_flow = typical_price * period['volume']
        if previous_typical_price is not None:
            if typical_price > previous_typical_price:  # If the typical price equals the previous one, then skip.
                positive_money_flows += raw_money_flow
            elif typical_price < previous_typical_price:
                negative_money_flows += raw_money_flow
        previous_typical_price = typical_price
    money_flow_ratio = positive_money_flows / negative_money_flows
    return 100 - 100 / (1 + money_flow_ratio)


def get_accumulation_distribution_indicator(data: Dict[str, float], option: str = 'bollinger') -> float:
    """
    Retrieve the accumulation distribution indicator based on open, close, high, low, and volume values.
    :param data: Dictionary containing open, high, close, low, and volume data.
    :param option: Method for accumulation distribution. It can either be Bollinger or Investopedia.
    :return: Accumulation distribution indicator.
    """
    if option.lower() == 'bollinger':
        return (data['close'] - data['open']) / (data['high'] - data['low']) * data['volume']
    elif option.lower() == 'investopedia':
        return (2 * data['close'] - data['low'] - data['high']) / (data['high'] - data['low']) * data['volume']
    else:
        raise ValueError("Please input either bollinger or investopedia for option type.")


def get_normal_volume_oscillator(periods: int, ad_cache: List[float], data: List[Dict[str, float]]) -> \
        Union[float, None]:
    """
    Gets the normal value oscillator based on the periods, past accumulation distribution indicator values, and volumes.
    :param periods: Number of periods to look previously.
    :param ad_cache: Data containing previous accumulation distribution indicator values.
    :param data: List containing previous periods' data.
    :return: Normal volume oscillator.
    """
    if len(ad_cache) < periods or len(data) < periods:
        return None
    else:
        volumes = [data_period['volume'] for data_period in data[-periods:]]
        ad_values = ad_cache[-periods:]
        return sum(ad_values) / sum(volumes)


def get_intraday_intensity_indicator(data: Dict[str, float]) -> float:
    """
    Returns the intraday intensity indicator based on the data provided.
    :param data: Dictionary containing open, high, close, low, and volume data.
    :return: Intraday intensity indicator.
    """
    return (2 * data['close'] - data['high'] - data['low']) / (data['high'] - data['low']) * data['volume']


def get_normalized_intraday_intensity(periods: int, intraday_intensity_cache: List[float],
                                      data: List[Dict[str, float]]) -> Union[float, None]:
    """
    Returns the normalized intraday intensity value based on the periods, past intraday intensity values, and past
    data period values.
    :param periods: Number of periods to look previously.
    :param intraday_intensity_cache: Cache of previous intraday intensities.
    :param data: List containing previous periods' data.
    :return: Normalized intraday intensity.
    """
    if len(intraday_intensity_cache) < periods or len(data) < periods:
        return None
    else:
        intraday_intensities = intraday_intensity_cache[-periods:]
        volumes = [data_period['volume'] for data_period in data[-periods:]]
        return sum(intraday_intensities) / sum(volumes)


def get_basic_volatility(periods: int, data: List[Dict[str, float]], use_returns: bool = True,
                         stdev_type: str = 'population') -> float:
    """
    Retrieves the basic volatility based on periods and data provided.
    :param periods: Amount of periods to traverse behind for basic volatility.
    :param use_returns: If true, this will use the returns option, and if false, it'll use the previous closes option.
    :param data: Data to get close values from.
    :param stdev_type: Standard deviation type for the basic volatility.
    """
    validate(periods=periods + int(use_returns), data=data)
    closes = []
    if use_returns:
        previous_close = data[-periods - 1]['close']
        for period in data[-periods:]:
            close_average = period['close'] / previous_close - 1
            previous_close = period['close']
            closes.append(close_average)
    else:
        closes = [period['close'] for period in data[-periods:]]

    ddof = get_ddof_from_stdev(stdev_type)
    return float(np.std(closes, ddof=ddof))


def get_parkinson_volatility(periods: int, data: List[Dict[str, float]]) -> float:
    """
    Retrieves the Parkinson volatility based on periods and data provided.
    :param periods: Amount of periods to traverse behind for basic volatility.
    :param data: Data to get close values from.
    """
    validate(periods, data)
    running_sum = 0
    for period in data[-periods:]:
        calculation = math.log(period['high'] / period['low']) ** 2
        running_sum += calculation

    return math.sqrt(running_sum / (4 * math.log(2) * periods))


def get_gk_volatility(periods: int, data: List[Dict[str, float]]) -> float:
    """
    Retrieves the Garman-Klass (GK) volatility based on periods and data provided.
    :param periods: Amount of periods to traverse behind for basic volatility.
    :param data: Data to get close values from.
    """
    validate(periods, data)
    running_sum = 0
    for period in data[-periods:]:
        high = period['high']
        low = period['low']
        close = period['close']
        open_ = period['open']  # open is a Python keyword
        calculation = 0.5 * math.log(high / low) ** 2 + (2 * math.log(2) - 1) * math.log(close / open_) ** 2
        running_sum += calculation

    return math.sqrt(running_sum / periods)


def get_rs_volatility(periods: int, data: List[Dict[str, float]]) -> float:
    """
    Retrieves the Rogers Satchell (RS) volatility based on periods and data provided.
    :param periods: Amount of periods to traverse behind for basic volatility.
    :param data: Data to get close values from.
    """
    validate(periods, data)
    running_sum = 0
    for period in data[-periods:]:
        u = math.log(period['high'] / period['open'])
        d = math.log(period['low'] / period['open'])
        c = math.log(period['close'] / period['open'])
        running_sum += u * (u - c) + d * (d - c)

    return math.sqrt(running_sum / periods)


def get_zh_volatility(periods: int, data: List[Dict[str, float]], stdev_type: str = 'population') -> float:
    """
    Retrieves the Yang Zhang (ZH) volatility based on periods and data provided.
    :param periods: Amount of periods to traverse behind for basic volatility.
    :param data: Data to get close values from.
    :param stdev_type: Standard deviation type for the basic volatility.
    """
    validate(periods, data)
    close_values = []
    open_values = []
    for period in data[-periods:]:
        o = math.log(period['open'] / period['close'])
        c = math.log(period['close'] / period['open'])
        close_values.append(c)
        open_values.append(o)

    ddof = get_ddof_from_stdev(stdev_type)
    open_std = float(np.std(open_values, ddof=ddof))
    close_std = float(np.std(close_values, ddof=ddof))
    k = 0.34 / (1.34 + (periods + 1) / (periods - 1))
    rs_volatility = get_rs_volatility(periods=periods, data=data)

    return math.sqrt(close_std ** 2 + k * open_std ** 2 + (1 - k) * rs_volatility ** 2)


def get_bollinger_bands(moving_average_periods: int, volatility_look_back_periods: int, volatility: str,
                        bb_coefficient: float, moving_average: str, moving_average_parameter: str,
                        data: List[Dict[str, float]], use_returns: bool = True,
                        dictionary: dict = None, stdev_type: str = 'sample') -> Tuple[float, float, float]:
    """
    Returns the bollinger bands based on inputs provided in the order of lower, middle, then upper bands.
    :param moving_average_periods: Amount of periods to loop behind for the moving average.
    :param moving_average_parameter: Parameter to use for the moving average - high, low, open, close.
    :param moving_average: Moving average to use.
    :param data: Data to use to retrieve the Bollinger bands.
    :param volatility: Volatility indicator to use - zh, basic, rs, gk, Parkinson.
    :param volatility_look_back_periods: Amount of periods to loop behind for the volatility indicator.
    :param use_returns: Boolean for whether the basic volatility strategy will use return values for calculation.
    :param bb_coefficient: BB coefficient itself.
    :param dictionary: Optional dictionary to populate volatility data with if provided.
    :param stdev_type: Standard deviation type which can either be sample or population.
    """
    middle_band = get_moving_average(moving_average, moving_average_parameter, moving_average_periods, data)
    volatility = volatility.lower()
    if volatility == 'zh' or 'yang zhang' in volatility:
        volatility_measure = get_zh_volatility(periods=volatility_look_back_periods, data=data, stdev_type=stdev_type)
    elif volatility == 'rs' or 'rogers satchell' in volatility:
        volatility_measure = get_rs_volatility(periods=volatility_look_back_periods, data=data)
    elif volatility == 'gk' or 'garman-klass' in volatility:
        volatility_measure = get_gk_volatility(periods=volatility_look_back_periods, data=data)
    elif volatility == 'parkinson':
        volatility_measure = get_parkinson_volatility(periods=volatility_look_back_periods, data=data)
    elif volatility == 'basic':
        volatility_measure = get_basic_volatility(periods=volatility_look_back_periods, data=data,
                                                  use_returns=use_returns, stdev_type=stdev_type)
    else:
        raise ValueError("Invalid type of volatility specified.")

    if use_returns:
        upper_band = middle_band + bb_coefficient * volatility_measure * middle_band
        lower_band = middle_band - bb_coefficient * volatility_measure * middle_band
    else:
        upper_band = middle_band + bb_coefficient * volatility_measure
        lower_band = middle_band - bb_coefficient * volatility_measure

    if dictionary:  # Optional dictionary to populate with volatility measure.
        dictionary['Volatility Measure'] = volatility_measure

    return lower_band, middle_band, upper_band


def get_percent_b(data: List[Dict[str, float]], bollinger_bands: Tuple[float, float, float]) -> float:
    """
    Returns the percentage B indicator.
    :param bollinger_bands: Bollinger bands.
    :param data: :param data: List containing previous periods' data.
    """
    lower_band, _, upper_band = bollinger_bands
    current_price = data[-1]['close']
    return (current_price - lower_band) / (upper_band - lower_band)


def get_bandwidth(bollinger_bands: Tuple[float, float, float]) -> float:
    """
    Returns the bandwidth indicator.
    :param bollinger_bands: Bollinger bands.
    """
    lower_band, middle_band, upper_band = bollinger_bands
    return (upper_band - lower_band) / middle_band
