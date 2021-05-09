from datetime import datetime, timedelta
from typing import Dict, List

import pytest

from algobot.algorithms import (get_accumulation_distribution_indicator,
                                get_ema, get_intraday_intensity_indicator,
                                get_normal_volume_oscillator,
                                get_normalized_intraday_intensity, get_sma,
                                get_wma)


@pytest.fixture(name='dummy_data')
def get_dummy_data():
    return [
        {
            'open': 1,
            'close': 5,
            'high': 10,
            'low': 0,
            'volume': 2500,
            'date_utc': datetime.now() - timedelta(minutes=1)
        },
        {
            'open': 2,
            'close': 3,
            'high': 15,
            'low': 3,
            'volume': 2500,
            'date_utc': datetime.now() - timedelta(minutes=2)
        },
        {
            'open': 3,
            'close': 2,
            'low': 2,
            'high': 20,
            'volume': 2500,
            'date_utc': datetime.now() - timedelta(minutes=3)
        },
        {
            'open': 4,
            'close': 7,
            'low': 0.5,
            'high': 9,
            'volume': 2500,
            'date_utc': datetime.now() - timedelta(minutes=4)
        },
    ]


@pytest.mark.parametrize(
    'prices, parameter, expected',
    [
        (4, 'open', 2.5),
        (4, 'close', 4.25)
    ]
)
def test_sma(dummy_data: List[Dict[str, float]], prices: int, parameter: str, expected: float):
    assert get_sma(data=dummy_data, prices=prices, parameter=parameter) == expected


@pytest.mark.parametrize(
    'prices, parameter, desc, expected',
    (
            (4, 'open', False, 3.0),
            (4, 'close', False, 4.5)
    )
)
def test_wma(dummy_data: List[Dict[str, float]], prices: int, parameter: str, desc: bool, expected: float):
    assert get_wma(data=dummy_data, prices=prices, parameter=parameter, desc=desc) == expected


@pytest.mark.parametrize(
    'prices, parameter, sma_prices, expected',
    [
        (3, 'open', 2, 3.125),
        (2, 'close', 1, 5.518518518518518)
    ]
)
def test_ema(dummy_data: List[Dict[str, float]], prices: int, parameter: str, sma_prices: int, expected: float):
    ema, _ = get_ema(data=dummy_data, prices=prices, parameter=parameter, sma_prices=sma_prices, desc=False)
    assert ema == expected


@pytest.mark.parametrize(
    'data, expected',
    [
        (
            {
                'close': 5,
                'open': 10,
                'high': 12,
                'low': 4,
                'volume': 155
            }, -96.875
        ),
        (
            {
                'close': 1,
                'open': 15,
                'high': 25,
                'low': 0,
                'volume': 251
            }, -140.56
        ),
    ]
)
def test_accumulation_distribution_indicator(data: Dict[str, float], expected: float):
    assert get_accumulation_distribution_indicator(data) == expected


@pytest.mark.parametrize(
    'ad_cache, periods, expected',
    [
        ([1, 2], 5, None),
        ([1, 2], 2, 0.0006)
    ]
)
def test_normal_volume_oscillator(dummy_data: List[Dict[str, float]], ad_cache: List[float], periods: int,
                                  expected: float):
    assert get_normal_volume_oscillator(data=dummy_data, ad_cache=ad_cache, periods=periods) == expected


@pytest.mark.parametrize(
    'index, expected',
    [
        (0, 0),
        (1, -2500.0),
        (2, -2500.0),
        (3, 1323.5294117647059),
    ]
)
def test_intraday_intensity_indicator(dummy_data: List[Dict[str, float]], index: int, expected: float):
    assert get_intraday_intensity_indicator(dummy_data[index]) == expected


@pytest.mark.parametrize(
    'periods, intraday_cache, expected',
    [
        (15, [1, 2], None),
        (3, [1, 2, 3], 0.0008),
    ]
)
def test_normalized_intraday_intensity(dummy_data: List[Dict[str, float]], periods: int, intraday_cache: List[float],
                                       expected: float):
    assert get_normalized_intraday_intensity(periods=periods, data=dummy_data,
                                             intraday_intensity_cache=intraday_cache) == expected
