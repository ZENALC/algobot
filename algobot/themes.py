"""
Algobot GUI themes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from algobot.interface.palettes import bloomberg_palette, dark_palette, green_palette, light_palette, red_palette

if TYPE_CHECKING:
    from algobot.__main__ import Interface


def bg_helper(color: str, gui: Interface):
    """
    Helper function to set the background.
    :param color: Color to set the background to.
    :param gui: GUI object to set background in.
    """
    for graph in gui.graphs:
        graph = graph['graph']
        graph.setBackground(color)


def set_dark_mode(app, gui: Interface):
    """
    Switches interface to a dark theme.
    """
    app.setPalette(dark_palette())
    bg_helper('k', gui)


def set_light_mode(app, gui: Interface):
    """
    Switches interface to a light theme.
    """
    app.setPalette(light_palette())
    bg_helper('w', gui)


def set_bloomberg_mode(app, gui: Interface):
    """
    Switches interface to bloomberg theme.
    """
    app.setPalette(bloomberg_palette())
    bg_helper('k', gui)


def set_bear_mode(app, gui: Interface):
    """
    Sets bear mode color theme. Theme is red and black mimicking a red day.
    """
    app.setPalette(red_palette())
    bg_helper('k', gui)


def set_bull_mode(app, gui: Interface):
    """
    Sets bull mode color theme. Theme is green and black mimicking a green day.
    """
    app.setPalette(green_palette())
    bg_helper('k', gui)
