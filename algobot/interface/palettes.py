from PyQt5.QtGui import QColor, QPalette


def bloomberg_palette():
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


def green_palette():
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


def red_palette():
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


def dark_palette():
    palette = QPalette()  # These below were taken from qtModern.
    palette.setColor(QPalette.WindowText, QColor(180, 180, 180))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.Light, QColor(180, 180, 180))
    palette.setColor(QPalette.Midlight, QColor(90, 90, 90))
    palette.setColor(QPalette.Dark, QColor(35, 35, 35))
    palette.setColor(QPalette.Text, QColor(180, 180, 180))
    palette.setColor(QPalette.BrightText, QColor(180, 180, 180))
    palette.setColor(QPalette.ButtonText, QColor(180, 180, 180))
    palette.setColor(QPalette.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.Shadow, QColor(20, 20, 20))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(180, 180, 180))
    palette.setColor(QPalette.Link, QColor(56, 252, 196))
    palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
    palette.setColor(QPalette.ToolTipBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipText, QColor(180, 180, 180))
    palette.setColor(QPalette.LinkVisited, QColor(80, 80, 80))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(80, 80, 80))
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(127, 127, 127))
    return palette


def light_palette():
    palette = QPalette()
    return palette
