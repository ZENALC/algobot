from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from credentials import telegramApi


class TelegramBot:
    def __init__(self, trader):
        updater = Updater(telegramApi, use_context=True)

        # Get the dispatcher to register handlers
        self.trader = trader
        dp = updater.dispatcher

        # on different commands - answer in Telegram
        dp.add_handler(CommandHandler("help", self.help_telegram))
        dp.add_handler(CommandHandler("override", self.override_telegram))
        dp.add_handler(CommandHandler(('stats', 'statistics'), self.get_statistics_telegram))
        dp.add_handler(CommandHandler("forcelong", self.force_long_telegram))
        dp.add_handler(CommandHandler("forceshort", self.force_short_telegram))
        dp.add_handler(CommandHandler('exitposition', self.exit_position_telegram))
        dp.add_handler(CommandHandler(("position", 'getposition'), self.get_position_telegram))
        dp.add_handler(CommandHandler(('fuckpeter', 'ispetergay', 'fuckyoupeter'), self.peter))
        dp.add_handler(CommandHandler(('ismihirgay', 'fuckmihir', 'fuckyoumihir'), self.mihir))
        dp.add_handler(CommandHandler(('praisemihir', 'mihirisalegend', 'phonkboi'), self.mihir1))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        updater.idle()

    @staticmethod
    def help_telegram(update, context):
        update.message.reply_text("Here are your help commands available:\n"
                                  "/help -> To get commands available.\n"
                                  "/forcelong  -> To force long.\n"
                                  "/forceshort -> To force short.\n"
                                  "/position or /getposition -> To get position.\n"
                                  "/stats or /statistics -> To get current statistics.\n"
                                  "/override -> To exit trade and wait for next cross.\n"
                                  "/exitposition -> To exit position.")

    def get_statistics_telegram(self, update, context):
        update.message.reply_text(f"Here are your statistics:\n"
                                  f"Coin owned: {self.trader.coin}\n"
                                  f"Coin owed: {self.trader.coinOwed}\n"
                                  f"Starting balance: ${self.trader.startingBalance}\n"
                                  f"Balance: ${self.trader.balance}\n"
                                  f"Profit: ${self.trader.get_profit()}\n"
                                  f"Profit percentage: {self.trader.get_profit_percentage()}%\n"
                                  f"Current BTC price: ${self.trader.dataView.currentPrice}"
                                  )

    @staticmethod
    def override_telegram(update, context):
        update.message.reply_text("Overriding.")

    @staticmethod
    def force_long_telegram(update, context):
        update.message.reply_text("Forcing long.")

    @staticmethod
    def force_short_telegram(update, context):
        update.message.reply_text("Forcing short.")

    @staticmethod
    def exit_position_telegram(update, context):
        update.message.reply_text("Exiting position.")

    @staticmethod
    def get_position_telegram(update, context):
        update.message.reply_text("Bot is currently in a short position.")

    @staticmethod
    def peter(update, context):
        update.message.reply_text("Yes, you are right because Peter is an australian wanker kangaroo cunt.")

    @staticmethod
    def mihir(update, context):
        update.message.reply_text('No, do not say those things. Mihir is a legend.')

    @staticmethod
    def mihir1(update, context):
        update.message.reply_text("Praise be mihir. PHONKBOIZ UNITED")


def main():
    """Start the bot."""
    t = TelegramBot()


if __name__ == '__main__':
    main()
