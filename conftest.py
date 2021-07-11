import os
import shutil

os.environ["ALGOBOT_TESTING"] = "1"


def pytest_unconfigure(config):
    from algobot.helpers import PATHS, AppDirTemp
    if isinstance(PATHS.app_dirs, AppDirTemp):
        shutil.rmtree(PATHS.app_dirs.root)
