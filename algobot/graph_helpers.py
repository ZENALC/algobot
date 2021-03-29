from datetime import datetime

from PyQt5.QtWidgets import QMainWindow
from pyqtgraph import InfiniteLine, PlotWidget, mkPen

from algobot.enums import AVG_GRAPH, NET_GRAPH
from algobot.traders.trader import Trader

GRAPH_LEEWAY = 10  # Amount of points to set extra for graph limits.


def set_backtest_graph_limits_and_empty_plots(gui: QMainWindow, limit: int = 105):
    """
    Resets backtest graph and sets x-axis limits.
    :param gui: Graphical user interface in which to set up graphs.
    :param limit: Maximum x-axis limit to set in the graph.
    """
    initialTimeStamp = gui.backtester.data[0]['date_utc'].timestamp()
    graphDict = get_graph_dictionary(gui, gui.backtestGraph)
    graphDict['graph'].setLimits(xMin=0, xMax=limit)
    plot = graphDict['plots'][0]
    plot['x'] = [0]
    plot['y'] = [gui.backtester.startingBalance]
    plot['z'] = [initialTimeStamp]
    plot['plot'].setData(plot['x'], plot['y'])


def update_backtest_graph_limits(gui: QMainWindow, limit: int = 105):
    """
    Updates backtest graph limits based on the limit provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param limit: Maximum x-axis limit to set in the graph.
    """
    graphDict = get_graph_dictionary(gui, gui.backtestGraph)
    graphDict['graph'].setLimits(xMin=0, xMax=limit + 1)


def get_graph_dictionary(gui: QMainWindow, targetGraph: PlotWidget) -> dict:
    """
    Loops over list of graphs and returns appropriate graph dictionary.
    :param gui: Graphical user interface in which to set up graphs.
    :param targetGraph: Graph to find in list of graphs.
    :return: Dictionary with the graph values.
    """
    for graph in gui.graphs:
        if graph["graph"] == targetGraph:
            return graph


def add_data_to_plot(gui: QMainWindow, targetGraph: PlotWidget, plotIndex: int, y: float, timestamp: float):
    """
    Adds data to plot in provided graph.
    :param gui: Graphical user interface in which to set up graphs.
    :param targetGraph: Graph to use for plot to add data to.
    :param plotIndex: Index of plot in target graph's list of plots.
    :param y: Y value to add.
    :param timestamp: Timestamp value to add.
    """
    graphDict = get_graph_dictionary(gui, targetGraph=targetGraph)
    plot = graphDict['plots'][plotIndex]

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


def setup_graph_plots(gui: QMainWindow, graph: PlotWidget, trader: Trader, graphType: int):
    """
    Setups graph plots for graph, trade, and graphType specified.
    :param gui: Graphical user interface in which to set up graphs.
    :param graph: Graph that will be setup.
    :param trader: Trade object that will use this graph.
    :param graphType: Graph type; i.e. moving average or net balance.
    """
    colors = get_graph_colors(gui=gui)
    if gui.configuration.enableHoverLine.isChecked():
        create_infinite_line(gui, get_graph_dictionary(gui, graph), colors=colors)

    if graphType == NET_GRAPH:
        setup_net_graph_plot(gui, graph=graph, trader=trader, color=colors[0])
    elif graphType == AVG_GRAPH:
        setup_average_graph_plots(gui, graph=graph, trader=trader, colors=colors)
    else:
        raise TypeError("Invalid type of graph provided.")


def get_plot_dictionary(gui: QMainWindow, graph: PlotWidget, color: str, y: float, name: str, timestamp: float) -> dict:
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


def destroy_graph_plots(gui: QMainWindow, targetGraph: PlotWidget):
    """
    Resets graph plots for graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param targetGraph: Graph to destroy plots for.
    """
    graphDict = get_graph_dictionary(gui, targetGraph=targetGraph)
    graphDict['graph'].clear()
    graphDict['plots'] = []


def setup_net_graph_plot(gui: QMainWindow, graph: PlotWidget, trader: Trader, color: str):
    """
    Sets up net balance plot for graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param trader: Type of trader that will use this graph.
    :param graph: Graph where plot will be setup.
    :param color: Color plot will be setup in.
    """
    net = trader.startingBalance
    currentDateTimestamp = datetime.utcnow().timestamp()
    plot = get_plot_dictionary(gui, graph=graph, color=color, y=net, name='Net', timestamp=currentDateTimestamp)

    append_plot_to_graph(gui, graph, [plot])


def setup_average_graph_plots(gui: QMainWindow, graph: PlotWidget, trader, colors: list):
    """
    Sets up moving average plots for graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param trader: Type of trader that will use this graph.
    :param graph: Graph where plots will be setup.
    :param colors: List of colors plots will be setup in.
    """
    if trader.currentPrice is None:
        trader.currentPrice = trader.dataView.get_current_price()

    currentPrice = trader.currentPrice
    currentDateTimestamp = datetime.utcnow().timestamp()
    colorCounter = 1

    if 'movingAverage' in trader.strategies:
        for option in trader.strategies['movingAverage'].get_params():
            initialAverage, finalAverage, initialName, finalName = gui.get_option_info(option, trader)
            initialPlotDict = get_plot_dictionary(gui=gui, graph=graph, color=colors[colorCounter % len(colors)],
                                                  y=initialAverage,
                                                  name=initialName, timestamp=currentDateTimestamp)
            secondaryPlotDict = get_plot_dictionary(gui=gui, graph=graph,
                                                    color=colors[(colorCounter + 1) % len(colors)],
                                                    y=finalAverage,
                                                    name=finalName, timestamp=currentDateTimestamp)
            colorCounter += 2
            append_plot_to_graph(gui, graph, [initialPlotDict, secondaryPlotDict])

    tickerPlotDict = get_plot_dictionary(gui=gui, graph=graph, color=colors[0], y=currentPrice, name=trader.symbol,
                                         timestamp=currentDateTimestamp)
    append_plot_to_graph(gui, graph, [tickerPlotDict])


def append_plot_to_graph(gui: QMainWindow, targetGraph: PlotWidget, toAdd: list):
    """
    Appends plot to graph provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param targetGraph: Graph to add plot to.
    :param toAdd: List of plots to add to target graph.
    """
    graphDict = get_graph_dictionary(gui, targetGraph=targetGraph)
    graphDict['plots'] += toAdd


def create_infinite_line(gui: QMainWindow, graphDict: dict, colors: list = None):
    """
    Creates an infinite (hover) line and adds it as a reference to the graph dictionary provided.
    :param gui: Graphical user interface in which to set up graphs.
    :param colors: Optional colors list.
    :param graphDict: A reference to this infinite line will be added to this graph dictionary.
    """
    colors = get_graph_colors(gui=gui) if colors is None else colors
    hoverLine = InfiniteLine(pos=0, pen=mkPen(colors[-1], width=1), movable=False)
    graphDict['graph'].addItem(hoverLine)
    graphDict['line'] = hoverLine


def create_graph_plot(gui: QMainWindow, graph: PlotWidget, x: tuple, y: tuple, plotName: str, color: str):
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
    plot.curve.scene().sigMouseMoved.connect(lambda point: gui.onMouseMoved(point=point, graph=graph))
    return plot


def get_graph_colors(gui: QMainWindow) -> list:
    """
    Returns graph colors to be placed based on configuration.
    """
    config = gui.configuration
    colorDict = {'blue': 'b',
                 'green': 'g',
                 'red': 'r',
                 'cyan': 'c',
                 'magenta': 'm',
                 'yellow': 'y',
                 'black': 'k',
                 'white': 'w'}
    colors = [config.balanceColor.currentText(), config.avg1Color.currentText(), config.avg2Color.currentText(),
              config.avg3Color.currentText(), config.avg4Color.currentText(), config.hoverLineColor.currentText()]
    return [colorDict[color.lower()] for color in colors]


def setup_graphs(gui: QMainWindow):
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
            graph.setTitle("Backtest Price Change")
        elif graph == gui.simulationGraph:
            graph.setTitle("Simulation Price Change")
        elif graph == gui.liveGraph:
            graph.setTitle("Live Price Change")
        elif graph == gui.simulationAvgGraph:
            graph.setTitle("Simulation Moving Averages")
        elif graph == gui.avgGraph:
            graph.setTitle("Live Moving Averages")


def update_main_graphs(gui: QMainWindow, caller: int, valueDict: dict):
    """
    Updates graphs and moving averages from statistics based on caller.
    :param gui: GUI in which to update main graphs.
    :param valueDict: Dictionary with required values.
    :param caller: Caller that decides which graphs get updated.
    """
    precision = gui.get_trader(caller=caller).precision
    interfaceDict = gui.interfaceDictionary[caller]
    currentUTC = datetime.utcnow().timestamp()
    net = valueDict['net']

    netGraph = interfaceDict['mainInterface']['graph']
    averageGraph = interfaceDict['mainInterface']['averageGraph']

    graphDict = get_graph_dictionary(gui, netGraph)
    graphXSize = len(graphDict['plots'][0]['x']) + GRAPH_LEEWAY
    netGraph.setLimits(xMin=0, xMax=graphXSize)
    add_data_to_plot(gui, netGraph, 0, y=round(net, 2), timestamp=currentUTC)

    averageGraphDict = get_graph_dictionary(gui, averageGraph)
    if averageGraphDict['enable']:
        averageGraph.setLimits(xMin=0, xMax=graphXSize)
        for index, optionDetail in enumerate(valueDict['optionDetails']):
            initialAverage, finalAverage = optionDetail[:2]
            add_data_to_plot(gui, averageGraph, index * 2, round(initialAverage, precision), currentUTC)
            add_data_to_plot(gui, averageGraph, index * 2 + 1, round(finalAverage, precision), currentUTC)

        add_data_to_plot(gui, averageGraph, -1, y=round(valueDict['price'], precision), timestamp=currentUTC)
