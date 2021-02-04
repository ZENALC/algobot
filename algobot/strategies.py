from typing import List


class Strategy:
    def __init__(self, args, data):
        self.args: List[dict] = args
        self.data = data

    def get_trend(self):
        pass
