"""
Strategies loader.
"""
import json
import os

from talib import abstract

from algobot.helpers import STRATEGIES_DIR


def parse_custom_strategy_json(json_file: str) -> dict:
    """
    Parse JSON containing strategy. Since the JSON only contains indicator info, we must populate
     all the other information from TALIB.

    Here's a example info that TALIB returns given an indicator:

    {
        'name': 'BBANDS',
        'group': 'Overlap Studies',
        'display_name': 'Bollinger Bands',
        'function_flags': ['Output scale same as input'],
        'input_names': OrderedDict([('price', 'close')]),
        'parameters': OrderedDict([
            ('timeperiod', 5),
            ('nbdevup', 2),
            ('nbdevdn', 2),
            ('matype', 0)
        ]),
        'output_flags': OrderedDict([
            ('upperband', ['Values represent an upper limit']),
            ('middleband', ['Line']),
            ('lowerband', ['Values represent a lower limit'])
        ]),
        'output_names': ['upperband', 'middleband', 'lowerband']
    }

    :param json_file: JSON file to parse.
    :return: Parsed JSON.
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        loaded_dict = json.load(f)

    trend_keys = {'Buy Long', 'Sell Long', 'Sell Short', 'Buy Short'}
    for trend, trend_items in loaded_dict.items():
        if trend not in trend_keys:
            continue

        for uuid in trend_items:
            indicator = trend_items[uuid]['name']
            abstract_info = abstract.Function(indicator).info
            trend_items[uuid].update(abstract_info)

            # If the against value is another indicator, replace and populate as a dictionary.
            against_value = trend_items[uuid]['against']
            if not isinstance(against_value, (float, int)) and against_value != 'current_price':
                trend_items[uuid]['against'] = abstract.Function(against_value).info

    return loaded_dict


def get_json_strategies() -> list:
    """
    Get JSON strategies.
    :return: List of JSON strategies.
    """
    # We must create absolute paths with os.path.join() or else we'll just get file names.
    strategy_files = [os.path.join(STRATEGIES_DIR, file_name) for file_name in os.listdir(STRATEGIES_DIR)
                      if file_name.lower().endswith('.json')]

    return [parse_custom_strategy_json(json_file) for json_file in strategy_files]


if __name__ == '__main__':
    import pprint
    pprint.pprint(get_json_strategies()[0])
