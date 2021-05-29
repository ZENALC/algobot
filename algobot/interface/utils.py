from PyQt5.QtWidgets import QMessageBox


def create_popup(parent, msg: str, title='Warning'):
    """
    Creates a popup with message provided.
    :param parent: Parent object to create popup on.
    :param title: Title for message box. By default, it is warning.
    :param msg: Message provided.
    """
    QMessageBox.about(parent, title, msg)


def open_from_msg_box(text: str, title: str):
    """
    Create a message box with an open/close dialog with text and title provided and return true or false depending
    on whether the user wants to open it or not.
    :param text: Text to put in message box.
    :param title: Title to put in message box.
    """
    msgBox = QMessageBox()
    msgBox.setIcon(QMessageBox.Information)
    msgBox.setText(text)
    msgBox.setWindowTitle(title)
    msgBox.setStandardButtons(QMessageBox.Open | QMessageBox.Close)
    return msgBox.exec_() == QMessageBox.Open
