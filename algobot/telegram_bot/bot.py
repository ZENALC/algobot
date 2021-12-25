"""
Telegram bot file.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional

import pkg_resources
from telegram import Bot, constants
from telegram.ext import CommandHandler, Updater

from algobot.enums import LIVE, LONG, SHORT, SIMULATION
from algobot.helpers import get_label_string
from algobot.traders.simulation_trader import SimulationTrader

if TYPE_CHECKING:
    from algobot.__main__ import Interface


class TelegramBot:
    """
    Telegram bot class.
    """

    def __init__(self, gui: Interface, token: str):
        self.token = token
        self.gui = gui
        self.updater = Updater(token, use_context=True)
        self.bot = Bot(token=self.token)

        self.joke_responses = self.load_text('texts/joke_responses.txt')
        self.print_responses = self.load_text('texts/print_responses.txt')
        self.thank_responses = self.load_text('texts/thank_responses.txt')
        self.wisdom_responses = self.load_text('texts/wisdom_responses.txt')

        # Alternate between these by setting the appropriate state through Telegram.
        self.trader: Optional[SimulationTrader] = None
        self.bot_thread = None

        # Get the dispatcher to register handlers.
        dispatcher = self.updater.dispatcher

        # Nn different commands - answer in Telegram.
        dispatcher.add_handler(CommandHandler("help", self.help_telegram))
        dispatcher.add_handler(CommandHandler("settrader", self.set_trader))
        dispatcher.add_handler(CommandHandler("override", self.override_telegram))
        dispatcher.add_handler(CommandHandler('trades', self.get_trades_telegram))
        dispatcher.add_handler(CommandHandler('resume', self.resume_telegram))
        dispatcher.add_handler(CommandHandler('pause', self.pause_telegram))
        dispatcher.add_handler(CommandHandler('removecustomstoploss', self.remove_custom_stop_loss))
        dispatcher.add_handler(CommandHandler('setcustomstoploss', self.set_custom_stop_loss))
        dispatcher.add_handler(CommandHandler("forcelong", self.force_long_telegram))
        dispatcher.add_handler(CommandHandler("forceshort", self.force_short_telegram))
        dispatcher.add_handler(CommandHandler('exitposition', self.exit_position_telegram))
        dispatcher.add_handler(CommandHandler('morestats', self.get_advanced_statistics_telegram))
        dispatcher.add_handler(CommandHandler(('stats', 'statistics'), self.get_statistics_telegram))
        dispatcher.add_handler(CommandHandler(("position", 'getposition'), self.get_position_telegram))
        dispatcher.add_handler(CommandHandler(("update", 'updatevalues'), self.update_values))
        dispatcher.add_handler(CommandHandler(("thanks", 'thanksbot', 'thankyou'), self.thank_bot_telegram))
        dispatcher.add_handler(CommandHandler(("print", 'makethatbread', 'printmoney'), self.print_telegram))
        dispatcher.add_handler(CommandHandler('joke', self.joke))
        dispatcher.add_handler(CommandHandler('wisdom', self.wisdom))

    @staticmethod
    def load_text(path: str) -> List[str]:
        """
        Load text from a file.
        :param path: Path to text file.
        :return: List of texts inside file.
        """
        path = pkg_resources.resource_filename('algobot.telegram_bot', path)
        with open(path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines()]

    def verify_bot(self, update) -> bool:
        """
        Verify telegram bot is actually set to a state (either sim or live).
        :param update: Update object to reply.
        :return: Boolean whether a state is set.
        """
        if not self.trader:
            update.message.reply_text("Please first select a trader with /settrader <SIM or LIVE>. If you've already "
                                      "selected a bot, then it may not be running.")
            return False

        bot_type = self.get_bot_caller(self.trader)
        bot_thread = self.gui.threads[bot_type]
        if bot_thread is None:
            bot_type = self.get_bot_caller(self.trader)
            update.message.reply_text(f"There is no {bot_type.lower()} bot being run.")
            return False

        return True

    def get_bot_caller(self, trader: Optional[SimulationTrader] = None) -> str:
        """
        Get bot type string -> it's either SIMULATION or LIVE.
        :param trader: Trader to get bot type from.
        :return: String of bot type.
        """
        if trader is None:
            trader = self.trader

        return SIMULATION if type(trader) is SimulationTrader else LIVE  # pylint: disable=unidiomatic-typecheck

    def set_trader(self, update, context):
        """
        Change state of telegram bot.
        """
        state = context.args[0].lower()

        if 'sim' in state:
            self.trader = self.gui.simulation_trader
            self.bot_thread = self.gui.threads[SIMULATION]
            update.message.reply_text("Telegram bot set to SIMULATION mode.")
        elif 'live' in state:
            self.trader = self.gui.trader
            self.bot_thread = self.gui.threads[LIVE]
            update.message.reply_text("Telegram bot set to LIVE mode.")
        else:
            update.message.reply_text("Could not understand the state. Acceptable values are SIM or LIVE.")

    def send_message(self, chat_id: str, message: str):
        """
        Sends provided message to specified chat ID using Telegram.
        :param chat_id: Chat ID in Telegram to send message to.
        :param message: Message to send.
        """
        self.bot.send_message(chat_id=chat_id, text=message)

    def start(self):
        """
        Starts the Telegram bot.
        """
        self.updater.start_polling()

    def stop(self):
        """
        Stops the Telegram bot.
        """
        self.updater.stop()

    def get_trades_telegram(self, update, *_args):
        """
        Sends trades information using Telegram bot to the chat that requested the trades using /trades.
        """
        if not self.verify_bot(update):
            return

        trades = self.trader.trades
        message = ''
        for index, trade in enumerate(trades, start=1):
            message += f'Trade {index}:\n'
            message += f'Date in UTC: {trade["date"].strftime("%m/%d/%Y, %H:%M:%S")}\n'
            message += f'Order ID: {trade["orderID"]}\n'
            message += f'Pair: {trade["pair"]}\n'
            message += f'Action: {trade["action"]}\n'
            message += f'Price: {trade["price"]}\n'
            message += f'Method: {trade["method"]}\n'
            message += f'Percentage: {trade["percentage"]}\n'
            message += f'Profit: {trade["profit"]}\n\n'

        if message == '':
            message = "No trades made yet."
            update.message.reply_text(message)
        else:
            limit = constants.MAX_MESSAGE_LENGTH
            message_parts = [message[i:i + limit] for i in range(0, len(message), limit)]
            for part in message_parts:
                update.message.reply_text(part)

    @staticmethod
    def help_telegram(update, *_args):
        """
        Sends available /help commands when called.
        """
        update.message.reply_text("Here are your help commands available:\n"
                                  "/help -> To get commands available.\n"
                                  "/forcelong  -> To force long.\n"
                                  "/forceshort -> To force short.\n"
                                  "/position or /getposition -> To get position.\n"
                                  "/morestats -> To get more detailed statistics.\n"
                                  "/stats or /statistics -> To get current statistics.\n"
                                  "/override -> To exit trade and wait for next cross.\n"
                                  "/resume -> To resume bot logic.\n"
                                  "/pause -> To pause bot logic.\n"
                                  "/removecustomstoploss -> To remove currently set custom stop loss.\n"
                                  "/setcustomstoploss <your stop loss value here> -> To set custom stop loss.\n"
                                  "/settrader <LIVE or SIM> -> To set the selected bot. (NEW)\n"
                                  "/exitposition -> To exit position.\n"
                                  "/trades -> To get list of trades made.\n"
                                  "/update or /updatevalues -> To update current coin values.\n"
                                  "/thanks or /thankyou or /thanksbot -> to thank the bot.\n")

    def update_values(self, update, *_args):
        """
        Updates trader bot values from refreshing its values using the Binance API.
        """
        if self.gui.trader is None or self.gui.threads[LIVE] is None:
            update.message.reply_text("There is no live bot running.")
        else:
            self.gui.trader.retrieve_margin_values()
            update.message.reply_text("Successfully retrieved new values from Binance.")

    def get_advanced_statistics(self) -> str:
        """
        Returns a lot more statistics from trader object.
        :return: String of huge statistics.
        """
        stat_dict = self.trader.get_grouped_statistics()

        total = ''
        for category_key in stat_dict:
            total += get_label_string(category_key) + ':\n'
            for key in stat_dict[category_key]:
                value = stat_dict[category_key][key]
                total += f'\t\t {get_label_string(key)} : {get_label_string(value)} \n'
        return total

    def get_advanced_statistics_telegram(self, update, *_args):
        """
        Sends advanced statistics.
        """
        if not self.verify_bot(update):
            return

        limit = constants.MAX_MESSAGE_LENGTH
        message = "Here are your advanced statistics as requested: \n" + self.get_advanced_statistics()
        message_parts = [message[i:i + limit] for i in range(0, len(message), limit)]

        for part in message_parts:
            update.message.reply_text(part)

    def get_statistics(self, trader: Optional[SimulationTrader] = None) -> str:
        """
        Retrieve available statistics to send using Telegram bot.
        :param trader: Bypass trader to use. Used for scheduling.
        """
        if not trader:
            trader = self.trader

        bot_type = self.get_bot_caller(trader)
        bot_thread = self.gui.threads[bot_type]

        profit = trader.get_profit()
        profit_label = trader.get_profit_or_loss_string(profit=profit)

        return (f'Symbol: {trader.symbol}\n'
                f'Position: {trader.get_position_string()}\n'
                f'Interval: {trader.data_view.interval}\n'
                f'Total trades made: {len(trader.trades)}\n'
                f"Coin owned: {trader.coin}\n"
                f"Coin owed: {trader.coin_owed}\n"
                f"Starting balance: ${round(trader.starting_balance, 2)}\n"
                f"Balance: ${round(trader.balance, 2)}\n"
                f'Net: ${round(trader.get_net(), 2)}\n'
                f"{profit_label}: ${round(abs(profit), 2)}\n"
                f'{profit_label} Percentage: {round(bot_thread.percentage, 2)}%\n'
                f'Daily Percentage: {round(bot_thread.daily_percentage, 2)}%\n'
                f'Autonomous Mode: {not trader.in_human_control}\n'
                f'Loss Strategy: {trader.get_stop_loss_strategy_string()}\n'
                f'Stop Loss Percentage: {round(trader.loss_percentage_decimal * 100, 2)}%\n'
                f'Stop Loss: {trader.get_safe_rounded_string(trader.get_stop_loss())}\n'
                f"Custom Stop Loss: {trader.get_safe_rounded_string(trader.custom_stop_loss)}\n"
                f"Current {trader.coin_name} price: ${trader.current_price}\n"
                f'Elapsed time: {bot_thread.elapsed}\n'
                f'Smart Stop Loss Initial Counter: {trader.smart_stop_loss_initial_counter}\n'
                f'Smart Stop Loss Counter: {trader.smart_stop_loss_counter}\n'
                f'Stop Loss Safety Timer: {trader.safety_timer}\n'
                )

    def send_statistics_telegram(self, chat_id: str, period: str, trader):
        """
        This function is used to periodically send statistics if enabled.
        :param chat_id: Chat ID to send statistics to.
        :param period: Time period within which to send statistics.
        :param trader: Trader object to use for statistics.
        """
        bot_type = self.get_bot_caller(trader)
        message = f"{bot_type} periodic statistics every {period}: \n"
        self.send_message(chat_id, message + self.get_statistics(trader))

    def get_statistics_telegram(self, update, *_args):
        """
        This function is called when /statistics is called. It replies with current bot statistics.
        """
        if not self.verify_bot(update):
            return

        message = "Here are your statistics as requested: \n"
        update.message.reply_text(message + self.get_statistics())

    def thank_bot_telegram(self, update, *_args):
        """
        Small easter egg. You can /thank the bot.
        """
        update.message.reply_text(random.choice(self.thank_responses))

    def print_telegram(self, update, *_args):
        """
        Small easter egg. You can tell bot to /print for it to joke around.
        """
        update.message.reply_text(random.choice(self.print_responses))

    def wisdom(self, update, *_args):
        """
        Small easter egg. You can tell bot to /wisdom for a random wisdom quote.
        """
        update.message.reply_text(random.choice(self.wisdom_responses))

    def joke(self, update, *_args):
        """
        Another small easter egg. You can /joke to let bot tell you a random one-liner joke.
        """
        update.message.reply_text(random.choice(self.joke_responses))

    def override_telegram(self, update, *_args):
        """
        Function called when /override is called. As the name suggests, it overrides the bot.
        """
        if not self.verify_bot(update):
            return

        bot_type = self.get_bot_caller()
        update.message.reply_text(f"Overriding {bot_type.lower()} bot.")
        self.bot_thread.signals.wait_override.emit(bot_type)
        update.message.reply_text("Successfully overrode.")

    def pause_telegram(self, update, *_args):
        """
        Function called when /pause is called. As the name suggests, it pauses the bot logic.
        """
        if not self.verify_bot(update):
            return

        bot_type = self.get_bot_caller()
        if self.trader.in_human_control:
            update.message.reply_text(f"{bot_type} bot is already in human control.")
        else:
            self.bot_thread.signals.pause.emit(bot_type)
            update.message.reply_text(f"{bot_type} bot has been paused successfully.")

    def resume_telegram(self, update, *_args):
        """
        Function called when /resume is called. As the name suggests, it resumes the bot logic.
        """
        if not self.verify_bot(update):
            return

        bot_type = self.get_bot_caller()
        if not self.trader.in_human_control:
            update.message.reply_text(f"{bot_type} bot is already in autonomous mode.")
        else:
            self.bot_thread.signals.resume.emit(bot_type)
            update.message.reply_text(f"{bot_type} bot logic has been resumed.")

    def remove_custom_stop_loss(self, update, *_args):
        """
        Function called when /removecustomstoploss is called. As the name suggests, it removes the current custom stop
        loss set.
        """
        if not self.verify_bot(update):
            return

        bot_type = self.get_bot_caller()
        if self.trader.custom_stop_loss is None:
            update.message.reply_text(f"{bot_type} bot already has no custom stop loss implemented.")
        else:
            self.bot_thread.signals.remove_custom_stop_loss.emit(bot_type)
            update.message.reply_text(f"{bot_type} bot's custom stop loss has been removed.")

    def set_custom_stop_loss(self, update, context):
        """
        Function called when /setcustomstoploss {value} is called. As the name suggests, it sets the custom stop
        loss with the value provided.
        """
        if not self.verify_bot(update):
            return

        stop_loss = context.args[0]

        try:
            stop_loss = float(stop_loss)
        except ValueError:
            update.message.reply_text("Please make sure you specify a number for the custom stop loss.")
            return
        except Exception as e:
            update.message.reply_text(f'An error occurred: {e}.')
            return

        if stop_loss < 0:
            update.message.reply_text("Please make sure you specify a non-negative number for the custom stop loss.")
        elif stop_loss > 10_000_000:
            update.message.reply_text("Please make sure you specify a number that is less than 10,000,000.")
        else:
            stop_loss = round(stop_loss, 6)
            bot_type = self.get_bot_caller()
            self.bot_thread.signals.set_custom_stop_loss.emit(bot_type, True, stop_loss)
            update.message.reply_text(f"{bot_type} stop loss has been successfully set to ${stop_loss}.")

    def force_long_telegram(self, update, *_args):
        """
        Function called when /forcelong is called. As the name suggests, it forces the bot to go long.
        """
        if not self.verify_bot(update):
            return

        bot_type = self.get_bot_caller()
        position = self.trader.get_position()
        if position == LONG:
            update.message.reply_text(f"{bot_type} bot is already in a long position.")
        else:
            update.message.reply_text(f"Forcing long on {bot_type.lower()} bot.")
            self.bot_thread.signals.force_long.emit(bot_type)
            update.message.reply_text("Successfully forced long.")

    def force_short_telegram(self, update, *_args):
        """
        Function called when /forceshort is called. As the name suggests, it forces the bot to go short.
        """
        if not self.verify_bot(update):
            return

        bot_type = self.get_bot_caller()
        position = self.trader.get_position()
        if position == SHORT:
            update.message.reply_text(f"{bot_type} bot is already in a short position.")
        else:
            update.message.reply_text(f"Forcing short on {bot_type.lower()} bot.")
            self.bot_thread.signals.force_short.emit(bot_type)
            update.message.reply_text("Successfully forced short.")

    def exit_position_telegram(self, update, *_args):
        """
        Function called when /exitposition is called. It forces the bot to exit its position provided it is in one.
        """
        bot_type = self.get_bot_caller()
        if self.trader.get_position() is None:
            update.message.reply_text(f"{bot_type} bot is not in a position.")
        else:
            update.message.reply_text(f"Exiting position on {bot_type.lower()} bot...")
            self.bot_thread.signals.exit_position.emit(bot_type)
            update.message.reply_text("Successfully exited position.")

    def get_position_telegram(self, update, *_args):
        """
        Function called when /getposition is called. It responds with the current position of the bot.
        """
        position = self.trader.get_position()
        bot_type = self.get_bot_caller()
        if position == SHORT:
            update.message.reply_text(f"{bot_type} bot is currently in a short position.")
        elif position == LONG:
            update.message.reply_text(f"{bot_type} bot is currently in a long position.")
        else:
            update.message.reply_text(f"{bot_type} bot is currently not in any position.")
