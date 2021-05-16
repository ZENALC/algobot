"""
Data download and import helper functions for configuration.py can be found here.
"""
from PyQt5.QtWidgets import QFileDialog

from algobot import helpers
from algobot.enums import BACKTEST
from algobot.interface.config_utils.calendar_utils import setup_calendar
from algobot.threads import downloadThread


def import_data(config_obj, caller: int = BACKTEST):
    """
    Imports CSV data and loads it.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that'll determine who called this function -> OPTIMIZER or BACKTEST
    """
    config_obj.optimizer_backtest_dict[caller]['infoLabel'].setText("Importing data...")
    filePath, _ = QFileDialog.getOpenFileName(config_obj, 'Open file', helpers.ROOT_DIR, "CSV (*.csv)")
    if filePath == '':
        config_obj.optimizer_backtest_dict[caller]['infoLabel'].setText("Data not imported.")
    else:
        config_obj.optimizer_backtest_dict[caller]['data'] = helpers.load_from_csv(filePath, descending=False)
        config_obj.optimizer_backtest_dict[caller]['dataType'] = "Imported"
        config_obj.optimizer_backtest_dict[caller]['infoLabel'].setText("Imported data successfully.")
        config_obj.optimizer_backtest_dict[caller]['dataLabel'].setText('Using imported data to conduct backtest.')
        setup_calendar(config_obj=config_obj, caller=caller)


def download_data(config_obj, caller: int = BACKTEST):
    """
    Loads data from data object. If the data object is empty, it downloads it.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that'll determine who called this function -> OPTIMIZER or BACKTEST
    """
    config_obj.optimizer_backtest_dict[caller]['downloadButton'].setEnabled(False)
    config_obj.optimizer_backtest_dict[caller]['importButton'].setEnabled(False)
    set_download_progress(config_obj, progress=0, message="Attempting to download...", caller=caller, enableStop=False)

    symbol = config_obj.optimizer_backtest_dict[caller]['tickers'].text()
    interval = helpers.convert_long_interval(config_obj.optimizer_backtest_dict[caller]['intervals'].currentText())

    thread = downloadThread.DownloadThread(symbol=symbol, interval=interval, caller=caller, logger=config_obj.logger)
    thread.signals.progress.connect(lambda progress, msg: set_download_progress(config_obj=config_obj, message=msg,
                                                                                progress=progress,  caller=caller))
    thread.signals.finished.connect(lambda data, *_: set_downloaded_data(config_obj, data=data, caller=caller))
    thread.signals.error.connect(lambda e, *_: handle_download_failure(config_obj=config_obj, caller=caller, e=e))
    thread.signals.restore.connect(lambda: restore_download_state(config_obj=config_obj, caller=caller))
    thread.signals.locked.connect(lambda:
                                  config_obj.optimizer_backtest_dict[caller]['stopDownloadButton'].setEnabled(False))
    config_obj.optimizer_backtest_dict[caller]['downloadThread'] = thread
    config_obj.threadPool.start(thread)


def set_downloaded_data(config_obj, data, caller: int = BACKTEST):
    """
    If download is successful, the data passed is set to backtest data.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that'll determine which caller was used.
    :param data: Data to be used for backtesting.
    """
    symbol = config_obj.optimizer_backtest_dict[caller]['tickers'].text()
    interval = config_obj.optimizer_backtest_dict[caller]['intervals'].currentText().lower()

    config_obj.optimizer_backtest_dict[caller]['data'] = data
    config_obj.optimizer_backtest_dict[caller]['dataType'] = symbol
    config_obj.optimizer_backtest_dict[caller]['infoLabel'].setText(f"Downloaded {interval} {symbol} data.")
    config_obj.optimizer_backtest_dict[caller]['dataLabel'].setText(f'Using {interval} {symbol} data to run backtest.')
    setup_calendar(config_obj=config_obj, caller=caller)


def stop_download(config_obj, caller: int = BACKTEST):
    """
    Stops download if download is in progress.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that'll determine who called this function -> OPTIMIZER or BACKTEST
    """
    if config_obj.optimizer_backtest_dict[caller]['downloadThread'] is not None:
        config_obj.optimizer_backtest_dict[caller]['downloadLabel'].setText("Canceling download...")
        config_obj.optimizer_backtest_dict[caller]['downloadThread'].stop()


def set_download_progress(config_obj, progress: int, message: str, caller: int = BACKTEST, enableStop: bool = True):
    """
    Sets download progress and message with parameters passed.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param enableStop: Boolean that'll determine if download can be stopped or not.
    :param caller: Caller that'll determine which caller was used.
    :param progress: Progress value to set bar at.
    :param message: Message to display in label.
    """
    if enableStop:
        config_obj.optimizer_backtest_dict[caller]['stopDownloadButton'].setEnabled(True)

    if progress != -1:
        config_obj.optimizer_backtest_dict[caller]['downloadProgress'].setValue(progress)
    config_obj.optimizer_backtest_dict[caller]['downloadLabel'].setText(message)


def handle_download_failure(config_obj, e, caller: int = BACKTEST):
    """
    If download fails for backtest data, then GUI gets updated.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that'll determine which caller was used.
    :param e: Error for why download failed.
    """
    set_download_progress(config_obj, progress=-1, message='Download failed.', caller=caller, enableStop=False)
    config_obj.optimizer_backtest_dict[caller]['infoLabel'].setText(f"Error occurred during download: {e}")


def restore_download_state(config_obj, caller: int = BACKTEST):
    """
    Restores GUI to normal state.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param caller: Caller that'll determine who called this function -> OPTIMIZER or BACKTEST
    """
    config_obj.optimizer_backtest_dict[caller]['downloadThread'] = None
    config_obj.optimizer_backtest_dict[caller]['stopDownloadButton'].setEnabled(False)
    config_obj.optimizer_backtest_dict[caller]['importButton'].setEnabled(True)
    config_obj.optimizer_backtest_dict[caller]['downloadButton'].setEnabled(True)
