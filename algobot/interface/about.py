import os

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog

from algobot.helpers import ROOT_DIR

aboutUi = os.path.join(ROOT_DIR, 'UI', 'about.ui')


class About(QDialog):
    def __init__(self, parent=None):
        super(About, self).__init__(parent)  # Initializing object
        uic.loadUi(aboutUi, self)  # Loading the main UI
