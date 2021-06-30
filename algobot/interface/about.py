from PyQt5.QtWidgets import QDialog, QHBoxLayout, QMainWindow, QPlainTextEdit

import algobot


class About(QDialog):
    def __init__(self, parent: QMainWindow = None):
        super(About, self).__init__(parent)
        layout = QHBoxLayout()

        version = algobot.CURRENT_VERSION
        latest_version = algobot.LATEST_VERSION
        version_text = f"({latest_version} available)" if version != latest_version else "(latest version)"
        description = f"Algobot Version {version} {version_text}\n\n" \
                      f"Algobot is an open-source software written in Python that enables users to create automated " \
                      f"bots that can trade, simulate, optimize, or backtest with strategies implemented.\n\n" \
                      f"This program is not responsible for any financial burdens or debt incurred.\n\n" \
                      f"Use at your own risk.\n\n" \
                      f"For contribution, bug reports, or feature requests, visit https://github.com/ZENALC/algobot"

        plain_text_edit = QPlainTextEdit()
        plain_text_edit.setPlainText(description)
        plain_text_edit.setReadOnly(True)
        layout.addWidget(plain_text_edit)

        self.setWindowTitle('About Algobot')
        self.setLayout(layout)
        self.setFixedSize(plain_text_edit.size())
