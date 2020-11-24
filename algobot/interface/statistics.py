import os

from helpers import ROOT_DIR
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog

statisticsUi = os.path.join(ROOT_DIR, 'UI', 'statistics.ui')


class Statistics(QDialog):
    def __init__(self, parent=None):
        super(Statistics, self).__init__(parent)  # Initializing object
        uic.loadUi(statisticsUi, self)  # Loading the main UI
