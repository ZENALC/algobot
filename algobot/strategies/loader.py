"""
Strategies loader.
"""
import json
import os
from typing import Callable, Dict, Optional

from talib import abstract

from algobot.enums import TRENDS
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

    for trend, trend_items in loaded_dict.items():
        if trend not in TRENDS:
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


def get_json_strategies(callback: Optional[Callable] = None) -> Dict[str, dict]:
    """
    Get JSON strategies.
    :return: Dictionary of strategies.
    """
    # Just in case if the directory doesn't already exist.
    os.makedirs(STRATEGIES_DIR, exist_ok=True)

    # We must create absolute paths with os.path.join() or else we'll just get file names.
    strategy_files = [os.path.join(STRATEGIES_DIR, file_name) for file_name in os.listdir(STRATEGIES_DIR)
                      if file_name.lower().endswith('.json')]

    # We must ensure that there aren't any strategies with the same name.
    strategies = {}
    duplicates = set()

    for json_file in strategy_files:
        parsed_json = parse_custom_strategy_json(json_file)
        parsed_json['path'] = json_file

        strategy_name = parsed_json['name']

        if strategy_name in duplicates:
            continue

        if strategy_name in strategies:
            duplicates.add(strategy_name)
            strategies.pop(strategy_name)
            continue

        strategies[strategy_name] = parsed_json

    if len(duplicates) > 0:
        if callback is not None:
            callback(f"Found duplicate strategies: {duplicates}. Algobot will ignore them. If you want to use them "
                     f"anyway, rename them.")
        else:
            print(f"Found duplicate strategies: {duplicates}. Ignoring them.")

    return strategies


if __name__ == '__main__':
    import pprint
    pprint.pprint(get_json_strategies())
