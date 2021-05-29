import os

from algobot import helpers


def load_state(config_obj):
    """
    This function will attempt to load previous basic configuration settings from config_obj.stateFilePath.
    :param config_obj: Configuration object.
    """
    if os.path.exists(config_obj.stateFilePath):
        try:
            config = helpers.load_json_file(config_obj.stateFilePath)

            config_obj.lightModeRadioButton.setChecked(config['lightTheme'])
            config_obj.darkModeRadioButton.setChecked(config['darkTheme'])
            config_obj.bloombergModeRadioButton.setChecked(config['bloombergTheme'])
            config_obj.bullModeRadioButton.setChecked(config['bullTheme'])
            config_obj.bearModeRadioButton.setChecked(config['bearTheme'])

            config_obj.balanceColor.setCurrentIndex(config['balanceColor'])
            config_obj.avg1Color.setCurrentIndex(config['avg1Color'])
            config_obj.avg2Color.setCurrentIndex(config['avg2Color'])
            config_obj.avg3Color.setCurrentIndex(config['avg3Color'])
            config_obj.avg4Color.setCurrentIndex(config['avg4Color'])
            config_obj.hoverLineColor.setCurrentIndex(config['lineColor'])

            config_obj.graphIndicatorsCheckBox.setChecked(config['averagePlot'])
            config_obj.failureLimitSpinBox.setValue(int(config['failureLimit']))
            config_obj.failureSleepSpinBox.setValue(int(config['failureSleep']))
            config_obj.tokenPass = config['tokenPass']
            config_obj.chatPass = config['chatPass']
            config_obj.telegrationConnectionResult.setText(config['telegramResult'])

            # Load saved tickers.
            config_obj.tickerLineEdit.setText(config['mainTicker'])
            config_obj.simulationTickerLineEdit.setText(config['simTicker'])
            config_obj.optimizerTickerLineEdit.setText(config['optimizerTicker'])
            config_obj.backtestTickerLineEdit.setText(config['backtestTicker'])

            if config_obj.parent:
                config_obj.parent.add_to_live_activity_monitor('Loaded previous state successfully.')
        except Exception as e:
            config_obj.logger.exception(str(e))

            if config_obj.parent:
                config_obj.parent.add_to_live_activity_monitor('Failed to fully load previous state because of a '
                                                               'potential new update/install. Try restarting Algobot.')


def save_state(config_obj):
    """
    Saves bot configuration to a JSON file for next application run.
    """
    config = {
        'lightTheme': config_obj.lightModeRadioButton.isChecked(),
        'darkTheme': config_obj.darkModeRadioButton.isChecked(),
        'bloombergTheme': config_obj.bloombergModeRadioButton.isChecked(),
        'bullTheme': config_obj.bullModeRadioButton.isChecked(),
        'bearTheme': config_obj.bearModeRadioButton.isChecked(),
        'balanceColor': config_obj.balanceColor.currentIndex(),
        'avg1Color': config_obj.avg1Color.currentIndex(),
        'avg2Color': config_obj.avg2Color.currentIndex(),
        'avg3Color': config_obj.avg3Color.currentIndex(),
        'avg4Color': config_obj.avg4Color.currentIndex(),
        'lineColor': config_obj.hoverLineColor.currentIndex(),
        'averagePlot': config_obj.graphIndicatorsCheckBox.isChecked(),
        'failureLimit': config_obj.failureLimitSpinBox.value(),
        'failureSleep': config_obj.failureSleepSpinBox.value(),
        'chatPass': config_obj.chatPass,
        'tokenPass': config_obj.tokenPass,
        'telegramResult': config_obj.telegrationConnectionResult.text(),
        'mainTicker': config_obj.tickerLineEdit.text(),
        'simTicker': config_obj.simulationTickerLineEdit.text(),
        'optimizerTicker': config_obj.optimizerTickerLineEdit.text(),
        'backtestTicker': config_obj.backtestTickerLineEdit.text()
    }

    helpers.write_json_file(config_obj.stateFilePath, **config)
