from PyQt5.QtWidgets import QMessageBox


def create_popup(parent, msg: str):
    """
    Creates a popup with message provided.
    :param parent: Parent object to create popup on.
    :param msg: Message provided.
    """
    QMessageBox.about(parent, 'Warning', msg)
