from telegram import Bot
from telegram.ext import Updater, CommandHandler

from enums import LONG, SHORT, LIVE


class TelegramBot:
    def __init__(self, gui, token):
        self.token = token
        self.updater = Updater(token, use_context=True)
        self.bot = Bot(token=self.token)

        # Get the dispatcher to register handlers
        self.gui = gui
        dp = self.updater.dispatcher

        # on different commands - answer in Telegram
        dp.add_handler(CommandHandler("help", self.help_telegram))
        dp.add_handler(CommandHandler("override", self.override_telegram))
        dp.add_handler(CommandHandler('trades', self.get_trades_telegram))
        dp.add_handler(CommandHandler('resume', self.resume_telegram))
        dp.add_handler(CommandHandler('pause', self.pause_telegram))
        dp.add_handler(CommandHandler('removecustomstoploss', self.remove_custom_stop_loss))
        dp.add_handler(CommandHandler('setcustomstoploss', self.set_custom_stop_loss))
        dp.add_handler(CommandHandler("forcelong", self.force_long_telegram))
        dp.add_handler(CommandHandler("forceshort", self.force_short_telegram))
        dp.add_handler(CommandHandler('exitposition', self.exit_position_telegram))
        dp.add_handler(CommandHandler(('stats', 'statistics'), self.get_statistics_telegram))
        dp.add_handler(CommandHandler(("position", 'getposition'), self.get_position_telegram))

    def send_message(self, chatID, message):
        self.bot.send_message(chat_id=chatID, text=message)

    def start(self):
        # Start the Bot
        self.updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        # self.updater.idle()

    def stop(self):
        self.updater.stop()

    def get_trades_telegram(self, update, context):
        trader = self.gui.trader
        trades = trader.trades

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

    @staticmethod
    def help_telegram(update, context):
        update.message.reply_text("Here are your help commands available:\n"
                                  "/help -> To get commands available.\n"
                                  "/forcelong  -> To force long.\n"
                                  "/forceshort -> To force short.\n"
                                  "/position or /getposition -> To get position.\n"
                                  "/stats or /statistics -> To get current statistics.\n"
                                  "/override -> To exit trade and wait for next cross.\n"
                                  "/resume -> To resume bot logic.\n"
                                  "/pause -> To pause bot logic.\n"
                                  "/removecustomstoploss -> To remove currently set custom stop loss.\n"
                                  "/setcustomstoploss (your stop loss value here) -> To set custom stop loss.\n"
                                  "/exitposition -> To exit position.\n"
                                  "/trades -> To get list of trades made.\n")

    def get_statistics(self):
        trader = self.gui.trader
        net = trader.get_net()
        startingBalance = trader.startingBalance
        profit = trader.get_profit()
        profitPercentage = trader.get_profit_percentage(trader.startingBalance, net)
        coinName = trader.coinName
        profitLabel = trader.get_profit_or_loss_string(profit=profit)

        return (f'Symbol: {trader.symbol}\n'
                f'Position: {trader.get_position_string()}\n'
                f'Total trades made: {len(trader.trades)}\n'
                f"Coin owned: {trader.coin}\n"
                f"Coin owed: {trader.coinOwed}\n"
                f"Starting balance: ${round(startingBalance, 2)}\n"
                f"Balance: ${round(trader.balance, 2)}\n"
                f'Net: ${round(net, 2)}\n'
                f"{profitLabel}: ${round(abs(profit), 2)}\n"
                f'{profitLabel} Percentage: {round(abs(profitPercentage), 2)}%\n'
                f'Autonomous Mode: {not trader.inHumanControl}\n'
                f'Stop Loss: ${round(trader.get_stop_loss(), 2)}\n'
                f"Custom Stop Loss: ${trader.customStopLoss}\n"
                f"Current {coinName} price: ${trader.currentPrice}"
                )

    def send_statistics_telegram(self, chatID, period):
        message = f"Periodic statistics every {period}: \n"
        self.send_message(chatID, message + self.get_statistics())

    def get_statistics_telegram(self, update, context):
        message = "Here are your statistics as requested: \n"
        update.message.reply_text(message + self.get_statistics())

    def override_telegram(self, update, context):
        update.message.reply_text("Overriding.")
        self.gui.exit_position(False)
        update.message.reply_text("Successfully overrode.")

    def pause_telegram(self, update, context):
        if self.gui.trader.inHumanControl:
            update.message.reply_text("Bot is already in human control.")
        else:
            self.gui.pause_or_resume_bot(LIVE)
            update.message.reply_text("Bot has been paused successfully.")

    def resume_telegram(self, update, context):
        if not self.gui.trader.inHumanControl:
            update.message.reply_text("Bot is already in autonomous mode.")
        else:
            self.gui.pause_or_resume_bot(LIVE)
            update.message.reply_text("Bot logic has been resumed.")

    def remove_custom_stop_loss(self, update, context):
        if self.gui.trader.customStopLoss is None:
            update.message.reply_text("Bot already has no custom stop loss implemented.")
        else:
            self.gui.trader.customStopLoss = None
            update.message.reply_text("Bot's custom stop loss has been removed.")

    def set_custom_stop_loss(self, update, context):
        stopLoss = context.args[0]

        try:
            stopLoss = float(stopLoss)
        except ValueError:
            update.message.reply_text("Please make sure you specify a number for the custom stop loss.")
            return

        if stopLoss < 0:
            update.message.reply_text("Please make sure you specify a non-negative number for the custom stop loss.")
        else:
            self.gui.trader.customStopLoss = stopLoss
            update.message.reply_text(f"Stop loss has been successfully set to ${stopLoss}.")

    def force_long_telegram(self, update, context):
        position = self.gui.trader.get_position()
        if position == LONG:
            update.message.reply_text("Bot is already in a long position.")
        else:
            update.message.reply_text("Forcing long.")
            self.gui.force_long()
            update.message.reply_text("Successfully forced long.")

    def force_short_telegram(self, update, context):
        position = self.gui.trader.get_position()
        if position == SHORT:
            update.message.reply_text("Bot is already in a short position.")
        else:
            update.message.reply_text("Forcing short.")
            self.gui.force_short()
            update.message.reply_text("Successfully forced short.")

    def exit_position_telegram(self, update, context):
        if self.gui.trader.get_position() is None:
            update.message.reply_text("Bot is not in a position.")
        else:
            update.message.reply_text("Exiting position.")
            self.gui.exit_position(True)
            update.message.reply_text("Successfully exited position.")

    def get_position_telegram(self, update, context):
        position = self.gui.trader.get_position()
        if position == SHORT:
            update.message.reply_text("Bot is currently in a short position.")
        elif position == LONG:
            update.message.reply_text("Bot is currently in a long position.")
        else:
            update.message.reply_text("Bot is currently not in any position.")
