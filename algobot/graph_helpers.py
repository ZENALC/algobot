from datetime import datetime

from pyqtgraph import InfiniteLine, PlotWidget, mkPen

GRAPH_LEEWAY = 10  # Amount of points to set extra for graph limits.


def create_infinite_line(gui, graphDict: dict, colors: list = None):
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


def create_graph_plot(gui, graph: PlotWidget, x: tuple, y: tuple, plotName: str, color: str):
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


def get_graph_colors(gui) -> list:
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


def setup_graphs(gui):
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


def update_main_graphs(gui, caller, valueDict):
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

    graphDict = gui.get_graph_dictionary(netGraph)
    graphXSize = len(graphDict['plots'][0]['x']) + GRAPH_LEEWAY
    netGraph.setLimits(xMin=0, xMax=graphXSize)
    gui.add_data_to_plot(netGraph, 0, y=round(net, 2), timestamp=currentUTC)

    averageGraphDict = gui.get_graph_dictionary(averageGraph)
    if averageGraphDict['enable']:
        averageGraph.setLimits(xMin=0, xMax=graphXSize)
        for index, optionDetail in enumerate(valueDict['optionDetails']):
            initialAverage, finalAverage = optionDetail[:2]
            gui.add_data_to_plot(averageGraph, index * 2, round(initialAverage, precision), currentUTC)
            gui.add_data_to_plot(averageGraph, index * 2 + 1, round(finalAverage, precision), currentUTC)

        gui.add_data_to_plot(averageGraph, -1, y=round(valueDict['price'], precision), timestamp=currentUTC)
