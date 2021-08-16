"""
Credentials helper functions for configuration.py can be found here.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from binance.client import Client
from PyQt5.QtWidgets import QFileDialog

from algobot import helpers

if TYPE_CHECKING:
    from algobot.interface.configuration import Configuration


def test_binance_credentials(config_obj: Configuration):
    """
    Tests Binance credentials provided in configuration.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    api_key = config_obj.binanceApiKey.text()
    api_secret = config_obj.binanceApiSecret.text()
    try:
        Client(api_key, api_secret).get_account()
        config_obj.credentialResult.setText('Connected successfully.')
    except Exception as e:
        string_error = str(e)
        if '1000ms' in string_error:
            config_obj.credentialResult.setText('Time not synchronized. Please synchronize your system time.')
        else:
            config_obj.credentialResult.setText(string_error)


def save_credentials(config_obj: Configuration):
    """
    Function that saves credentials to base path in a JSON format. Obviously not very secure, but temp fix.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    target_folder = os.path.join(helpers.ROOT_DIR, config_obj.credentialsFolder)
    helpers.create_folder_if_needed(target_folder)

    api_key = config_obj.binanceApiKey.text()
    api_secret = config_obj.binanceApiSecret.text()
    telegram_api_key = config_obj.telegramApiKey.text()
    telegram_chat_id = config_obj.telegramChatID.text()

    default_path = os.path.join(target_folder, 'default.json')
    file_path, _ = QFileDialog.getSaveFileName(config_obj, 'Save Credentials', default_path, 'JSON (*.json)')
    file_path = file_path.strip()

    if file_path:
        helpers.write_json_file(filePath=file_path, apiKey=api_key, apiSecret=api_secret,
                                telegramApiKey=telegram_api_key, chatID=telegram_chat_id)
        config_obj.credentialResult.setText(f'Credentials saved successfully to {os.path.basename(file_path)}.')
    else:
        config_obj.credentialResult.setText('Credentials could not be saved.')


def load_credentials(config_obj: Configuration, auto: bool = True):
    """
    Attempts to load credentials automatically from path program regularly stores credentials in if auto is True.
    :param config_obj: Configuration QDialog object (from configuration.py)
    :param auto: Boolean regarding whether bot called this function or not. If bot called it, silently try to load
    credentials. If a user called it, however, open a file dialog to ask for the file path to credentials.
    """
    target_folder = os.path.join(helpers.ROOT_DIR, config_obj.credentialsFolder)
    if helpers.create_folder_if_needed(target_folder):
        config_obj.credentialResult.setText('No credentials found.')
        return

    if not auto:
        filePath, _ = QFileDialog.getOpenFileName(config_obj, 'Load Credentials', target_folder, "JSON (*.json)")
    else:
        filePath = os.path.join(target_folder, 'default.json')

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
