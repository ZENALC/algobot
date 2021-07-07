"""
Credentials helper functions for configuration.py can be found here.
"""

import os

from binance.client import Client
from PyQt5.QtWidgets import QFileDialog

from algobot import helpers


def test_binance_credentials(config_obj):
    """
    Tests Binance credentials provided in configuration.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    apiKey = config_obj.binanceApiKey.text()
    apiSecret = config_obj.binanceApiSecret.text()
    try:
        Client(apiKey, apiSecret).get_account()
        config_obj.credentialResult.setText('Connected successfully.')
    except Exception as e:
        stringError = str(e)
        if '1000ms' in stringError:
            config_obj.credentialResult.setText('Time not synchronized. Please synchronize your system time.')
        else:
            config_obj.credentialResult.setText(stringError)


def save_credentials(config_obj):
    """
    Function that saves credentials to base path in a JSON format. Obviously not very secure, but temp fix.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    targetFolder = config_obj.credentialsFolder
    helpers.create_folder_if_needed(targetFolder)

    apiKey = config_obj.binanceApiKey.text()
    apiSecret = config_obj.binanceApiSecret.text()
    telegramApiKey = config_obj.telegramApiKey.text()
    telegramChatId = config_obj.telegramChatID.text()

    defaultPath = os.path.join(targetFolder, 'default.json')
    filePath, _ = QFileDialog.getSaveFileName(config_obj, 'Save Credentials', defaultPath, 'JSON (*.json)')
    filePath = filePath.strip()

    if filePath:
        helpers.write_json_file(filePath=filePath, apiKey=apiKey, apiSecret=apiSecret,
                                telegramApiKey=telegramApiKey, chatID=telegramChatId)
        config_obj.credentialResult.setText(f'Credentials saved successfully to {os.path.basename(filePath)}.')
    else:
        config_obj.credentialResult.setText('Credentials could not be saved.')


def load_credentials(config_obj, auto: bool = True):
    """
    Attempts to load credentials automatically from path program regularly stores credentials in if auto is True.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param auto: Boolean regarding whether bot called this function or not. If bot called it, silently try to load
    credentials. If a user called it, however, open a file dialog to ask for the file path to credentials.
    """
    targetFolder = config_obj.credentialsFolder
    if helpers.create_folder_if_needed(targetFolder):
        config_obj.credentialResult.setText('No credentials found.')
        return

    if not auto:
        filePath, _ = QFileDialog.getOpenFileName(config_obj, 'Load Credentials', targetFolder, "JSON (*.json)")
    else:
        filePath = os.path.join(targetFolder, 'default.json')

    try:
        credentials = helpers.load_json_file(jsonfile=filePath)
        config_obj.binanceApiKey.setText(credentials['apiKey'])
        config_obj.binanceApiSecret.setText(credentials['apiSecret'])
        config_obj.telegramApiKey.setText(credentials['telegramApiKey'])
        config_obj.telegramChatID.setText(credentials['chatID'])
        config_obj.credentialResult.setText(f'Credentials loaded successfully from {os.path.basename(filePath)}.')
    except FileNotFoundError:
        config_obj.credentialResult.setText('Could not load credentials.')
    except Exception as e:
        config_obj.credentialResult.setText(str(e))
