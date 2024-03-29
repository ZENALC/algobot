"""
Telegram helper functions for configuration.py can be found here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import telegram
from telegram.ext import Updater

if TYPE_CHECKING:
    from algobot.interface.configuration import Configuration


def reset_telegram_state(config_obj: Configuration):
    """
    Resets telegram state once something is changed in the Telegram configuration GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config_obj.chat_pass = False
    config_obj.token_pass = False
    config_obj.telegrationConnectionResult.setText("Telegram credentials not yet tested.")


def test_telegram(config_obj: Configuration):
    """
    Tests Telegram connection and updates respective GUI elements.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    token_pass = chat_pass = False
    message = error = ''

    try:
        telegram_api_key = config_obj.telegramApiKey.text()
        chat_id = config_obj.telegramChatID.text()
        Updater(telegram_api_key, use_context=True)
        token_pass = True
        telegram.Bot(token=telegram_api_key).send_message(chat_id=chat_id, text='Testing connection with Chat ID.')
        chat_pass = True
    except Exception as e:
        error = repr(e)
        if 'ConnectionError' in error:
            error = 'There was a connection error. Please check your connection.'

    if token_pass:
        if 'Unauthorized' in error:
            message = 'Token authorization was unsuccessful. Please recheck your token.'
        else:
            message += "Token authorization was successful. "
            if chat_pass:
                message += "Chat ID checked and connected to successfully. "
            else:
                if 'Chat not found' in error:
                    message += "However, the specified chat ID is invalid."
                else:
                    message += f'However, chat ID error occurred: "{error}".'
    else:
        message = f'Error: {error}'

    config_obj.telegrationConnectionResult.setText(message)
    config_obj.chat_pass = chat_pass
    config_obj.token_pass = token_pass
