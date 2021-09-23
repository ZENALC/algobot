"""
Main typing hints for Algobot defined here.
"""

from datetime import datetime
from typing import Dict, List, Union

DictType = Dict[str, Union[datetime, float]]
DataType = List[DictType]
