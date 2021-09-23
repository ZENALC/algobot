"""
File containing helper functions for graphs.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List

from PyQt5.QtWidgets import QColorDialog, QDialog, QLabel
from pyqtgraph import InfiniteLine, PlotWidget, mkPen

from algobot.enums import GraphType
from algobot.interface.utils import show_and_bring_window_to_front
from algobot.traders.trader import Trader

GRAPH_LEEWAY = 10  # Amount of points to set extra for graph limits.

if TYPE_CHECKING:
    from algobot.__main__ import Interface


def get_and_set_line_color(view: QDialog, label: QLabel):
    """
    This function will open a dialog for the user to select a color then set it to the label provided.
    :param view: Parent view to use for the color selector to be on top of.
    :param label: Label to modify color with.
    """
    color = QColorDialog.getColor()
    show_and_bring_window_to_front(view)

    if color.isValid():
        set_color_to_label(label, color.name())


def set_color_to_label(label: QLabel, color: str):
    """
    Set a color to label provided.
    :param label: Label object to set color and color's text to.
    :param color: Color to use.
    """
    label.setText(color)
    label.setStyleSheet(f"background: {color};")


def set_backtest_graph_limits_and_empty_plots(gui: Interface, limit: int = 105):
    """
    Resets backtest graph and sets x-axis limits.
    :param gui: Graphical user interface in which to set up graphs.
    :param limit: Maximum x-axis limit to set in the graph.
    """
    initial_timestamp = gui.backtester.data[0]['date_utc'].timestamp()
    graph_dict = get_graph_dictionary(gui, gui.backtestGraph)
    graph_dict['graph'].setLimits(xMin=0, xMax=limit)
    plot = graph_dict['plots'][0]
    plot['x'] = [0]
    plot['y'] = [gui.backtester.startingBalance]
    plot['z'] = [initial_timestamp]
    plot['plot'].setData(plot['x'], plot['y'])


def update_backtest_graph_limits(gui: Interface, limit: int = 105):
    """
    Updates backtest graph limits based on the limit provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param limit: Maximum x-axis limit to set in the graph.
    """
    graph_dict = get_graph_dictionary(gui, gui.backtestGraph)
    graph_dict['graph'].setLimits(xMin=0, xMax=limit)


def get_graph_dictionary(gui: Interface, targetGraph: PlotWidget) -> dict:
    """
    Loops over list of graphs and returns appropriate graph dictionary.
    :param gui: Graphical user interface in which to set up graphs.
    :param targetGraph: Graph to find in list of graphs.
    :return: Dictionary with the graph values.
    """
    for graph in gui.graphs:
        if graph["graph"] == targetGraph:
            return graph


def legend_helper(graph_dict, x_val):
    """
    Helper for setting graph legends based on the graph dictionary and x value provided.
    :param graph_dict: Graph dictionary.
    :param x_val: X value in the graph.
    """
    legend = graph_dict['graph'].plotItem.legend.items
    date_object = datetime.utcfromtimestamp(graph_dict['plots'][0]['z'][x_val])
    total = f'X: {x_val} Datetime in UTC: {date_object.strftime("%m/%d/%Y, %H:%M:%S")}'

    for index, plotDict in enumerate(graph_dict['plots']):
        info = f' {plotDict["name"]}: {plotDict["y"][x_val]}'
        total += info
        legend[index][1].setText(info)  # The 2nd element in legend is the label, so we can just set text.

    graph_dict['label'].setText(total)


def onMouseMoved(gui: Interface, point, graph: PlotWidget):
    """
    Updates coordinates label when mouse is hovered over graph.
    :param gui: Graphical user interface in which to manipulate graphs.
    :param point: Point hovering over graph.
    :param graph: Graph being hovered on.
    """
    graph_dict = get_graph_dictionary(gui, graph)
    if graph_dict.get('line') is None:  # No line exists, just return.
        return

    plot_item = graph.plotItem
    p = plot_item.vb.mapSceneToView(point)

    view_range = plot_item.vb.viewRange()
    x_val, y_val = p.x(), p.y()
    x_min, x_max = view_range[0]  # X axis.
    y_min, y_max = view_range[1]  # Y axis.

    if x_val < x_min or x_val > x_max or y_val < y_min or y_val > y_max:
        graph_dict['line'].setPos(-1)
        legend_helper(graph_dict, -1)
        gui.reset_backtest_cursor()

    elif graph_dict['enable'] and p and graph_dict.get('line'):  # Ensure that the hover line is enabled.
        graph_dict['line'].setPos(x_val)

        if graph_dict['plots'][0]['x'][-1] > x_val > graph_dict['plots'][0]['x'][0]:
            legend_helper(graph_dict, int(x_val))
            if graph == gui.backtestGraph and gui.backtester is not None:
                gui.update_backtest_activity_based_on_graph(int(x_val))


def add_data_to_plot(gui: Interface,
                     target_graph: PlotWidget,
                     plot_index: int,
                     y: float,
                     timestamp: float):
    """
    Adds data to plot in provided graph.
    :param gui: Graphical user interface in which to set up graphs.
    :param target_graph: Graph to use for plot to add data to.
    :param plot_index: Index of plot in target graph's list of plots.
    :param y: Y value to add.
    :param timestamp: Timestamp value to add.
    """
    graph_dict = get_graph_dictionary(gui, targetGraph=target_graph)
    plot = graph_dict['plots'][plot_index]

    secondsInDay = 86400  # Reset graph every 24 hours (assuming data is updated only once a second).
    if len(plot['x']) >= secondsInDay:
        plot['x'] = [0]
        plot['y'] = [y]
        plot['z'] = [timestamp]
    else:
        plot['x'].append(plot['x'][-1] + 1)
        plot['y'].append(y)
        plot['z'].append(timestamp)
    plot['plot'].setData(plot['x'], plot['y'])


def setup_graph_plots(gui: Interface,
                      graph: PlotWidget,
                      trader: Trader,
                      graph_type: GraphType):
    """
    Setups graph plots for graph, trade, and graphType specified.
    :param gui: Graphical user interface in which to set up graphs.
    :param graph: Graph that will be setup.
    :param trader: Trade object that will use this graph.
    :param graph_type: Graph type; i.e. moving average or net balance.
    """
    colors = get_graph_colors(gui=gui)
    if gui.configuration.enableHoverLine.isChecked():
        create_infinite_line(gui, get_graph_dictionary(gui, graph), colors=colors)

    if graph_type == GraphType.NET:
        setup_net_graph_plot(gui, graph=graph, trader=trader, color=colors[0])
    elif graph_type == GraphType.AVG:
        setup_average_graph_plots(gui, graph=graph, trader=trader, colors=colors)
    else:
        raise TypeError(f"Invalid type ({graph_type}) of graph provided.")


def get_plot_dictionary(gui: Interface, graph: PlotWidget, color: str, y: float, name: str, timestamp: float) -> dict:
    """
    Creates a graph plot and returns a dictionary of it.
    :param gui: Graphical user interface in which to set up graphs.
    :param graph: Graph to add plot to.
    :param color: Color of plot.
    :param y: Y value to start with for plot.
    :param name: Name of plot.
    :param timestamp: First UTC timestamp of plot.
    :return: Dictionary of plot information.
    """
    plot = create_graph_plot(gui, graph, (0,), (y,), color=color, plotName=name)
    return {
        'plot': plot,
        'x': [0],
        'y': [y],
        'z': [timestamp],
        'name': name,
    }


def destroy_graph_plots(gui: Interface, target_graph: PlotWidget):
    """
    Resets graph plots for graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param target_graph: Graph to destroy plots for.
    """
    graph_dict = get_graph_dictionary(gui, targetGraph=target_graph)
    graph_dict['graph'].clear()
    graph_dict['plots'] = []


def setup_net_graph_plot(gui: Interface, graph: PlotWidget, trader: Trader, color: str):
    """
    Sets up net balance plot for graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param trader: Type of trader that will use this graph.
    :param graph: Graph where plot will be setup.
    :param color: Color plot will be setup in.
    """
    net = trader.startingBalance
    current_date_timestamp = datetime.utcnow().timestamp()
    plot = get_plot_dictionary(gui, graph=graph, color=color, y=net, name='Net', timestamp=current_date_timestamp)

    append_plot_to_graph(gui, graph, [plot])


def setup_average_graph_plots(gui: Interface, graph: PlotWidget, trader, colors: list):
    """
    Sets up moving average plots for graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param trader: Type of trader that will use this graph.
    :param graph: Graph where plots will be setup.
    :param colors: List of colors plots will be setup in.
    """
    if trader.currentPrice is None:
        trader.currentPrice = trader.dataView.get_current_price()

    current_price = trader.currentPrice
    current_date_timestamp = datetime.utcnow().timestamp()

    ticker_plot_dict = get_plot_dictionary(gui=gui,
                                           graph=graph,
                                           color=colors[0],
                                           y=current_price,
                                           name=trader.symbol,
                                           timestamp=current_date_timestamp)
    append_plot_to_graph(gui, graph, [ticker_plot_dict])

    # Every graph plot needs to have an index. We'll start from 1. (since 0 is for the price). Logically, we only need
    # the first index for each strategy dictionary, since we can iterate through it and add to it.
    index = 1

    for strategy in trader.strategies.values():
        strategy_plot_dict = strategy.get_plot_data()
        strategy_plot_dict['index'] = index
        for name, combined_data in strategy_plot_dict.items():

            if name == 'index':
                continue  # We don't want to iterate over the index.

            value, color = combined_data
            plot_dict = get_plot_dictionary(gui=gui,
                                            graph=graph,
                                            color=color,
                                            y=value,
                                            name=name,
                                            timestamp=current_date_timestamp)
            append_plot_to_graph(gui, graph, [plot_dict])
            index += 1


def append_plot_to_graph(gui: Interface, target_graph: PlotWidget, toAdd: list):
    """
    Appends plot to graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param target_graph: Graph to add plot to.
    :param toAdd: List of plots to add to target graph.
    """
    graph_dict = get_graph_dictionary(gui, targetGraph=target_graph)
    graph_dict['plots'] += toAdd


def create_infinite_line(gui: Interface, graph_dict: dict, colors: list = None):
    """
    Creates an infinite (hover) line and adds it as a reference to the graph dictionary provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param colors: Optional colors list.
    :param graph_dict: A reference to this infinite line will be added to this graph dictionary.
    """
    colors = get_graph_colors(gui=gui) if colors is None else colors
    hover_line = InfiniteLine(pos=0, pen=mkPen(colors[-1], width=1), movable=False)
    graph_dict['graph'].addItem(hover_line)
    graph_dict['line'] = hover_line


def create_graph_plot(gui: Interface, graph: PlotWidget, x: tuple, y: tuple, plotName: str, color: str):
    """
    Creates a graph plot with parameters provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param graph: Graph function will plot on.
    :param x: X values of graph.
    :param y: Y values of graph.
    :param plotName: Name of graph.
    :param color: Color graph will be drawn in.
    """
    pen = mkPen(color=color)
    plot = graph.plot(x, y, name=plotName, pen=pen, autoDownsample=True, downsampleMethod='subsample')
    plot.curve.scene().sigMouseMoved.connect(lambda point: onMouseMoved(gui=gui, point=point, graph=graph))
    return plot


def get_graph_colors(gui: Interface) -> List[str]:
    """
    Returns graph colors to be placed based on configuration.
    """
    return [
        gui.configuration.balanceColor.text(),
        gui.configuration.hoverLineColor.text()
    ]


def setup_graphs(gui: Interface):
    """
    Sets up all available graphs in application.
    :param gui: Graphical user interface in which to set up graphs.
    """
    for graphDict in gui.graphs:
        graph = graphDict['graph']
        graph.setLimits(xMin=0, xMax=GRAPH_LEEWAY, yMin=-1, yMax=1000_000_000_000_000)
        graph.setBackground('w')
        graph.setLabel('left', 'USDT')
        graph.setLabel('bottom', 'Data Points')
        graph.addLegend()

        if graph == gui.backtestGraph:
            graph.setTitle("Backtest Net")
        elif graph == gui.simulationGraph:
            graph.setTitle("Simulation Net")
        elif graph == gui.liveGraph:
            graph.setTitle("Live Net")
        elif graph == gui.simulationAvgGraph:
            graph.setTitle("Simulation Indicators")
        elif graph == gui.avgGraph:
            graph.setTitle("Live Indicators")


def smart_update(graph_dict: Dict[str, Any]):
    """
    Smartly update the legend based on the graph dictionary provided. If the graph dictionary doesn't have a hover-line
    enabled, then just update the legend with the latest data. If the hover-line is enabled, show what the graph
    dictionary holds at the hover-line's X position.
    :param graph_dict: Graph dictionary to use to smart update.
    """
    if graph_dict.get('line') is None:  # If hover line is turned off, then just update normally.
        legend_helper(graph_dict, -1)
    else:
        x = graph_dict['line'].getXPos()
        if x == -1:
            legend_helper(graph_dict, -1)


def update_main_graphs(gui: Interface, caller: int, valueDict: dict):
    """
    Updates graphs and moving averages from statistics based on caller.
    :param gui: GUI in which to update main graphs.
    :param valueDict: Dictionary with required values.
    :param caller: Caller that decides which graphs get updated.
    """
    precision = gui.get_trader(caller=caller).precision
    interface_dict = gui.interfaceDictionary[caller]
    current_utc = datetime.utcnow().timestamp()

    net_graph = interface_dict['mainInterface']['graph']
    average_graph = interface_dict['mainInterface']['averageGraph']

    graph_dict = get_graph_dictionary(gui, net_graph)
    graph_x_size = len(graph_dict['plots'][0]['x']) + GRAPH_LEEWAY
    net_graph.setLimits(xMin=0, xMax=graph_x_size)
    add_data_to_plot(gui, net_graph, 0, y=round(valueDict['net'], 2), timestamp=current_utc)
    smart_update(graph_dict)

    average_graph_dict = get_graph_dictionary(gui, average_graph)
    if average_graph_dict['enable']:
        average_graph.setLimits(xMin=0, xMax=graph_x_size)
        add_data_to_plot(gui, average_graph, 0, y=round(valueDict['price'], precision), timestamp=current_utc)

        trader = gui.get_trader(caller=caller)
        for strategy in trader.strategies.values():
            strategy_plot_dict = strategy.get_plot_data()
            index = strategy_plot_dict['index']
            for name, combined_data in strategy_plot_dict.items():

                if name == 'index':
                    continue

                value, _ = combined_data
                add_data_to_plot(
                    gui=gui,
                    target_graph=average_graph,
                    plot_index=index,
                    y=round(value, trader.precision),
                    timestamp=current_utc
                )
                index += 1
        smart_update(average_graph_dict)
