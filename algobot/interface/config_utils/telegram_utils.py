"""
Telegram helper functions for configuration.py can be found here.
"""
import telegram
from telegram.ext import Updater


def reset_telegram_state(config_obj):
    """
    Resets telegram state once something is changed in the Telegram configuration GUI.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    config_obj.chatPass = False
    config_obj.tokenPass = False
    config_obj.telegrationConnectionResult.setText(
        "Telegram credentials not yet tested."
    )


def test_telegram(config_obj):
    """
    Tests Telegram connection and updates respective GUI elements.
    :param config_obj: Configuration QDialog object (from configuration.py)
    """
    tokenPass = chatPass = False
    message = error = ""

    try:
        telegramApikey = config_obj.telegramApiKey.text()
        chatID = config_obj.telegramChatID.text()
        Updater(telegramApikey, use_context=True)
        tokenPass = True
        telegram.Bot(token=telegramApikey).send_message(
            chat_id=chatID, text="Testing connection with Chat ID."
        )
        chatPass = True
    except Exception as e:
        error = repr(e)
        if "ConnectionError" in error:
            error = "There was a connection error. Please check your connection."

    if tokenPass:
        if "Unauthorized" in error:
            message = "Token authorization was unsuccessful. Please recheck your token."
        else:
            message += "Token authorization was successful. "
            if chatPass:
                message += "Chat ID checked and connected to successfully. "
            else:
                if "Chat not found" in error:
                    message += "However, the specified chat ID is invalid."
                else:
                    message += f'However, chat ID error occurred: "{error}".'
    else:
        message = f"Error: {error}"

    config_obj.telegrationConnectionResult.setText(message)
    config_obj.chatPass = chatPass
    config_obj.tokenPass = tokenPass
