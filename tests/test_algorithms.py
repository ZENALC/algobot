"""
Unit tests for algorithms or technical indicators.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pytest

from algobot.algorithms import (
    get_accumulation_distribution_indicator,
    get_bandwidth,
    get_basic_volatility,
    get_bollinger_bands,
    get_ema,
    get_gk_volatility,
    get_intraday_intensity_indicator,
    get_money_flow_index,
    get_normal_volume_oscillator,
    get_normalized_intraday_intensity,
    get_parkinson_volatility,
    get_percent_b,
    get_rs_volatility,
    get_sma,
    get_wma,
    get_zh_volatility,
)

DATA_HINT = List[Dict[str, float]]


@pytest.fixture(name="dummy_data")
def get_dummy_data():
    return [
        {
            "open": 1,
            "close": 5,
            "high": 10,
            "low": 0,
            "volume": 2500,
            "date_utc": datetime.now() - timedelta(minutes=1),
        },
        {
            "open": 2,
            "close": 3,
            "high": 15,
            "low": 3,
            "volume": 2500,
            "date_utc": datetime.now() - timedelta(minutes=2),
        },
        {
            "open": 3,
            "close": 2,
            "low": 2,
            "high": 20,
            "volume": 2500,
            "date_utc": datetime.now() - timedelta(minutes=3),
        },
        {
            "open": 4,
            "close": 7,
            "low": 0.5,
            "high": 9,
            "volume": 2500,
            "date_utc": datetime.now() - timedelta(minutes=4),
        },
    ]


@pytest.mark.parametrize(
    "prices, parameter, expected", [(4, "open", 2.5), (4, "close", 4.25)]
)
def test_sma(dummy_data: DATA_HINT, prices: int, parameter: str, expected: float):
    assert get_sma(data=dummy_data, prices=prices, parameter=parameter) == expected


@pytest.mark.parametrize(
    "prices, parameter, desc, expected",
    ((4, "open", False, 3.0), (4, "close", False, 4.5)),
)
def test_wma(
    dummy_data: DATA_HINT, prices: int, parameter: str, desc: bool, expected: float
):
    assert (
        get_wma(data=dummy_data, prices=prices, parameter=parameter, desc=desc)
        == expected
    )


@pytest.mark.parametrize(
    "prices, parameter, sma_prices, expected",
    [(3, "open", 2, 3.125), (2, "close", 1, 5.518518518518518)],
)
def test_ema(
    dummy_data: DATA_HINT, prices: int, parameter: str, sma_prices: int, expected: float
):
    ema, _ = get_ema(
        data=dummy_data,
        prices=prices,
        parameter=parameter,
        sma_prices=sma_prices,
        desc=False,
    )
    assert ema == expected


@pytest.mark.parametrize(
    "data, expected",
    [
        ({"close": 5, "open": 10, "high": 12, "low": 4, "volume": 155}, -96.875),
        ({"close": 1, "open": 15, "high": 25, "low": 0, "volume": 251}, -140.56),
    ],
)
def test_accumulation_distribution_indicator(data: Dict[str, float], expected: float):
    assert get_accumulation_distribution_indicator(data) == expected


@pytest.mark.parametrize(
    "ad_cache, periods, expected", [([1, 2], 5, None), ([1, 2], 2, 0.0006)]
)
def test_normal_volume_oscillator(
    dummy_data: DATA_HINT, ad_cache: List[float], periods: int, expected: float
):
    assert (
        get_normal_volume_oscillator(
            data=dummy_data, ad_cache=ad_cache, periods=periods
        )
        == expected
    )


@pytest.mark.parametrize(
    "index, expected",
    [
        (0, 0),
        (1, -2500.0),
        (2, -2500.0),
        (3, 1323.5294117647059),
    ],
)
def test_intraday_intensity_indicator(
    dummy_data: DATA_HINT, index: int, expected: float
):
    assert get_intraday_intensity_indicator(dummy_data[index]) == expected


@pytest.mark.parametrize(
    "periods, intraday_cache, expected",
    [
        (15, [1, 2], None),
        (3, [1, 2, 3], 0.0008),
    ],
)
def test_normalized_intraday_intensity(
    dummy_data: DATA_HINT, periods: int, intraday_cache: List[float], expected: float
):
    assert (
        get_normalized_intraday_intensity(
            periods=periods, data=dummy_data, intraday_intensity_cache=intraday_cache
        )
        == expected
    )


@pytest.fixture(name="volatility_data")
def get_volatility_data():
    return [
        {
            "high": 0.0082,
            "low": 0.00555,
            "close": 0.005781,
            "open": 0.006088,
        },
        {
            "high": 0.005929,
            "low": 0.00485,
            "close": 0.00511,
            "open": 0.005788,
        },
        {
            "high": 0.005962,
            "low": 0.005012,
            "close": 0.005262,
            "open": 0.005088,
        },
        {"high": 0.00547, "low": 0.005001, "close": 0.005237, "open": 0.005264},
        {"high": 0.005695, "low": 0.005105, "close": 0.005472, "open": 0.005237},
        {"high": 0.005684, "low": 0.005192, "close": 0.005313, "open": 0.005473},
        {
            "high": 0.005705,
            "low": 0.005203,
            "close": 0.005675,
            "open": 0.005314,
        },
        {"high": 0.006168, "low": 0.005554, "close": 0.006045, "open": 0.005676},
        {"high": 0.006949, "low": 0.005825, "close": 0.00638, "open": 0.006044},
        {"high": 0.006447, "low": 0.005947, "close": 0.006202, "open": 0.006397},
        {"high": 0.0068, "low": 0.006151, "close": 0.00659, "open": 0.006202},
    ]


@pytest.mark.parametrize(
    "periods, expected, use_returns, stdev_type",
    [
        (10, 0.0593474375889191, True, "sample"),
        (8, 0.04253494804852161, True, "sample"),
        (7, 0.00047902728821763686, False, "sample"),
        (9, 0.03751254848636268, True, "population"),
        (11, 0.00048397375449638004, False, "population"),
    ],
)
def test_basic_volatility(
    volatility_data: DATA_HINT,
    periods: int,
    expected: float,
    use_returns: bool,
    stdev_type: str,
):
    assert (
        get_basic_volatility(
            periods=periods,
            data=volatility_data,
            use_returns=use_returns,
            stdev_type=stdev_type,
        )
        == expected
    )


@pytest.mark.parametrize(
    "periods, expected", [(10, 0.07734426892046951), (5, 0.06961744039623198)]
)
def test_parkinson_volatility(
    volatility_data: DATA_HINT, periods: int, expected: float
):
    assert get_parkinson_volatility(periods=periods, data=volatility_data) == expected


@pytest.mark.parametrize(
    "periods, expected", [(10, 0.09827614438649765), (7, 0.08525759356946656)]
)
def test_gk_volatility(volatility_data: DATA_HINT, periods: int, expected: float):
    assert get_gk_volatility(data=volatility_data, periods=periods) == expected


@pytest.mark.parametrize(
    "periods, expected", [(10, 0.08607419520730895), (7, 0.07241871087258109)]
)
def test_rs_volatility(volatility_data: DATA_HINT, periods: int, expected: float):
    assert get_rs_volatility(data=volatility_data, periods=periods) == expected


@pytest.mark.parametrize(
    "periods, expected, stdev_type",
    [
        (10, 0.10324062709358658, "sample"),
        (7, 0.0818737245934366, "sample"),
        (8, 0.0803648056187744, "sample"),
        (9, 0.08771349273185311, "sample"),
    ],
)
def test_zh_volatility(
    volatility_data: DATA_HINT, periods: int, expected: float, stdev_type: str
):
    assert (
        get_zh_volatility(periods=periods, data=volatility_data, stdev_type=stdev_type)
        == expected
    )


@pytest.fixture(name="money_flow_fixture")
def get_money_flow_fixture():
    return [
        {
            "open": 10,
            "high": 15,
            "low": 8,
            "close": 12,
            "volume": 120,
        },
        {
            "open": 12,
            "high": 16,
            "low": 11,
            "close": 13,
            "volume": 150,
        },
        {
            "open": 13,
            "high": 17,
            "low": 12,
            "close": 14,
            "volume": 160,
        },
        {
            "open": 14,
            "high": 18,
            "low": 13,
            "close": 15,
            "volume": 130,
        },
        {
            "open": 15,
            "high": 19,
            "low": 14,
            "close": 16,
            "volume": 160,
        },
        {
            "open": 16,
            "high": 19,
            "low": 5,
            "close": 12,
            "volume": 120,
        },
        {
            "open": 11,
            "high": 14,
            "low": 8,
            "close": 13,
            "volume": 180,
        },
        {
            "open": 13,
            "high": 21,
            "low": 6,
            "close": 7,
            "volume": 230,
        },
        {
            "open": 7,
            "high": 15,
            "low": 4,
            "close": 8,
            "volume": 130,
        },
        {
            "open": 8,
            "high": 14,
            "low": 4,
            "close": 6,
            "volume": 80,
        },
        {
            "open": 6,
            "high": 14,
            "low": 7,
            "close": 8,
            "volume": 111,
        },
    ]


@pytest.mark.parametrize(
    "periods, expected", [(3, 37.21817551161983), (7, 31.661370208136503)]
)
def test_money_flow_index(money_flow_fixture, periods: int, expected: float):
    assert get_money_flow_index(data=money_flow_fixture, periods=periods) == expected


@pytest.fixture(name="bollinger_fixture")
def get_bollinger_fixture():
    return [
        {"close": 10},
        {"close": 13},
        {"close": 7},
        {"close": 9},
        {"close": 11},
        {"close": 8},
        {"close": 4},
        {"close": 13},
        {"close": 17},
        {"close": 12},
    ]


@pytest.mark.parametrize(
    "moving_average_n, moving_average, moving_average_param, volatility_look_back_n, volatility, bb, expected",
    [
        (
            2,
            "SMA",
            "close",
            3,
            "basic",
            2,
            (-24.058858093951244, 14.5, 53.058858093951244),
        )
    ],
)
def test_bollinger_bands(
    bollinger_fixture: DATA_HINT,
    moving_average_n: int,
    moving_average: str,
    moving_average_param: str,
    volatility_look_back_n: int,
    volatility: str,
    bb: float,
    expected: float,
):
    bollinger_bands = get_bollinger_bands(
        moving_average_periods=moving_average_n,
        moving_average=moving_average,
        volatility_look_back_periods=volatility_look_back_n,
        volatility=volatility,
        data=bollinger_fixture,
        moving_average_parameter=moving_average_param,
        bb_coefficient=bb,
    )

    assert bollinger_bands == expected


@pytest.mark.parametrize(
    "bollinger_bands, data, expected",
    [((5.833333, 7, 8.4), [{"close": 7.2}], 0.5324675931860269)],
)
def test_get_percent_b(
    bollinger_bands: Tuple[float, float, float], data: DATA_HINT, expected: float
):
    assert get_percent_b(bollinger_bands=bollinger_bands, data=data) == expected


@pytest.mark.parametrize(
    "bollinger_bands, expected",
    [
        ((5.833333, 7, 8.4), 0.3666667142857144),
    ],
)
def test_get_bandwidth(bollinger_bands: Tuple[float, float, float], expected: float):
    assert get_bandwidth(bollinger_bands) == expected
