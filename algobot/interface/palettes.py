from PyQt5.QtGui import QPalette, QColor


def get_bloomberg_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QColor(255, 140, 0))
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ToolTipText, QColor(255, 140, 0))
    palette.setColor(QPalette.Text, QColor(255, 140, 0))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QColor(255, 140, 0))
    palette.setColor(QPalette.BrightText, QColor(252, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(255, 140, 0))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    palette.setColor(QPalette.Disabled, QPalette.Button, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(200, 120, 0))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(200, 120, 0))
    palette.setColor(QPalette.Disabled, QPalette.Light, QColor(25, 25, 25))
    return palette


def get_green_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    palette.setColor(QPalette.WindowText, QColor(0, 255, 0))  # change
    palette.setColor(QPalette.ToolTipText, QColor(0, 255, 0))  # change
    palette.setColor(QPalette.Text, QColor(0, 255, 0))  # change
    palette.setColor(QPalette.ButtonText, QColor(0, 255, 0))  # change
    palette.setColor(QPalette.Highlight, QColor(0, 255, 0))  # change
    palette.setColor(QPalette.Disabled, QPalette.Button, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(35, 155, 35))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(35, 155, 35))
    palette.setColor(QPalette.Disabled, QPalette.Light, QColor(25, 25, 25))
    return palette


def get_red_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QColor(255, 0, 0))  # change
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ToolTipText, QColor(255, 0, 0))  # change
    palette.setColor(QPalette.Text, QColor(255, 0, 0))  # change
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QColor(255, 0, 0))  # change
    palette.setColor(QPalette.BrightText, QColor(252, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(255, 0, 0))  # change
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    palette.setColor(QPalette.Disabled, QPalette.Button, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(155, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(155, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.Light, QColor(25, 25, 25))
    return palette


def get_dark_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.Button, QColor(50, 50, 50))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(255, 255, 255))
    palette.setColor(QPalette.Highlight, QColor(255, 255, 255))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    palette.setColor(QPalette.Disabled, QPalette.Button, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(150, 150, 150))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(35, 35, 35))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(150, 150, 150))
    palette.setColor(QPalette.Disabled, QPalette.Light, QColor(25, 25, 25))
    return palette


def get_light_palette():
    palette = QPalette()
    return palette
