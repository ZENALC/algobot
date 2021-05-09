from typing import Dict, List

import pytest

from algobot.algorithms import (get_accumulation_distribution_indicator,
                                get_intraday_intensity_indicator, get_sma,
                                get_wma)


@pytest.fixture(name='dummy_data')
def get_dummy_data():
    return [
        {
            'open': 1,
            'close': 5,
            'high': 10,
            'low': 0,
            'volume': 2500
        },
        {
            'open': 2,
            'close': 3,
            'high': 15,
            'low': 3,
            'volume': 2500
        },
        {
            'open': 3,
            'close': 2,
            'low': 2,
            'high': 20,
            'volume': 2500
        },
        {
            'open': 4,
            'close': 7,
            'low': 0.5,
            'high': 9,
            'volume': 2500
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


def test_ema():
    pass


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


def test_normal_volume_oscillator():
    pass


@pytest.mark.parametrize(
    'index, expected',
    [
        (0, 0),
        (1, -2500.0),
        (2, -2500.0),
        (3, 1323.5294117647059),
    ]
)
def test_intraday_intensity_indicator(dummy_data, index, expected):
    assert get_intraday_intensity_indicator(dummy_data[index]) == expected


def test_normalized_intraday_intensity():
    pass
