import os
import shutil

from algobot.helpers import PATHS, AppDirTemp

os.environ["ALGOBOT_TESTING"] = "1"


def pytest_unconfigure(config):
    if isinstance(PATHS.app_dirs, AppDirTemp):
        shutil.rmtree(PATHS.app_dirs.root)
