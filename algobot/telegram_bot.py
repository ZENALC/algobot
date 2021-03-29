import random

from telegram import Bot, constants
from telegram.ext import CommandHandler, Updater

from algobot.enums import LIVE, LONG, SHORT
from algobot.helpers import get_label_string
from algobot.traders.simulationtrader import SimulationTrader


class TelegramBot:
    def __init__(self, gui, token: str, botThread):
        self.token = token
        self.gui = gui
        self.botThread = botThread
        self.updater = Updater(token, use_context=True)
        self.bot = Bot(token=self.token)

        # Get the dispatcher to register handlers
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
        dp.add_handler(CommandHandler('morestats', self.get_advanced_statistics_telegram))
        dp.add_handler(CommandHandler(('stats', 'statistics'), self.get_statistics_telegram))
        dp.add_handler(CommandHandler(("position", 'getposition'), self.get_position_telegram))
        dp.add_handler(CommandHandler(("update", 'updatevalues'), self.update_values))
        dp.add_handler(CommandHandler(("thanks", 'thanksbot', 'thankyou'), self.thank_bot_telegram))
        dp.add_handler(CommandHandler(("print", 'makethatbread', 'printmoney'), self.print_telegram))
        dp.add_handler(CommandHandler('joke', self.joke))
        dp.add_handler(CommandHandler('wisdom', self.wisdom))

    def send_message(self, chatID: str, message: str):
        """
        Sends provided message to specified chat ID using Telegram.
        :param chatID: Chat ID in Telegram to send message to.
        :param message: Message to send.
        """
        self.bot.send_message(chat_id=chatID, text=message)

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

    # noinspection PyUnusedLocal
    def get_trades_telegram(self, update, context):
        """
        Sends trades information using Telegram bot to chat that requested the trades using /trades.
        """
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
        else:
            limit = constants.MAX_MESSAGE_LENGTH
            messageParts = [message[i:i + limit] for i in range(0, len(message), limit)]
            for part in messageParts:
                update.message.reply_text(part)

    # noinspection PyUnusedLocal
    @staticmethod
    def help_telegram(update, context):
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
                                  "/setcustomstoploss (your stop loss value here) -> To set custom stop loss.\n"
                                  "/exitposition -> To exit position.\n"
                                  "/trades -> To get list of trades made.\n"
                                  "/update or /updatevalues -> To update current coin values.\n"
                                  "/thanks or /thankyou or /thanksbot -> to thank the bot.\n")

    # noinspection PyUnusedLocal
    def update_values(self, update, context):
        """
        Updates trader bot values from refreshing its values using the Binance API.
        """
        self.gui.trader.retrieve_margin_values()
        update.message.reply_text("Successfully retrieved new values from Binance.")

    def get_advanced_statistics(self) -> str:
        """
        Returns a lot more statistics from trader object.
        :return: String of huge statistics.
        """
        trader: SimulationTrader = self.gui.trader
        statDict = trader.get_grouped_statistics()

        total = ''

        for categoryKey in statDict:
            total += get_label_string(categoryKey) + ':\n'
            for key in statDict[categoryKey]:
                value = statDict[categoryKey][key]
                total += f'\t\t {get_label_string(key)} : {get_label_string(value)} \n'
        return total

    # noinspection PyUnusedLocal
    def get_advanced_statistics_telegram(self, update, context):
        """
        Sends advanced statistics.
        """
        limit = constants.MAX_MESSAGE_LENGTH

        message = "Here are your advanced statistics as requested: \n" + self.get_advanced_statistics()
        messageParts = [message[i:i + limit] for i in range(0, len(message), limit)]

        for part in messageParts:
            update.message.reply_text(part)

    def get_statistics(self) -> str:
        """
        Retrieve available statistics to send using Telegram bot.
        """
        trader: SimulationTrader = self.gui.trader

        if not trader or not self.botThread:
            return 'Something went wrong. Try again in a few minutes.'

        profit = trader.get_profit()
        profitLabel = trader.get_profit_or_loss_string(profit=profit)

        optionString = ''

        for option in self.botThread.optionDetails:  # previously trader.tradingOptions
            avg1, avg2, name1, name2 = option
            optionString += f'{name1}: ${round(avg1, trader.precision)}\n'
            optionString += f'{name2}: ${round(avg2, trader.precision)}\n'

        return (f'Symbol: {trader.symbol}\n'
                f'Position: {trader.get_position_string()}\n'
                f'Interval: {trader.dataView.interval}\n'
                f'Total trades made: {len(trader.trades)}\n'
                f"Coin owned: {trader.coin}\n"
                f"Coin owed: {trader.coinOwed}\n"
                f"Starting balance: ${round(trader.startingBalance, 2)}\n"
                f"Balance: ${round(trader.balance, 2)}\n"
                f'Net: ${round(trader.get_net(), 2)}\n'
                f"{profitLabel}: ${round(abs(profit), 2)}\n"
                f'{profitLabel} Percentage: {round(self.botThread.percentage, 2)}%\n'
                f'Daily Percentage: {round(self.botThread.dailyPercentage, 2)}%\n'
                f'Autonomous Mode: {not trader.inHumanControl}\n'
                f'Loss Strategy: {trader.get_stop_loss_strategy_string()}\n'
                f'Stop Loss Percentage: {round(trader.lossPercentageDecimal * 100, 2)}%\n'
                f'Stop Loss: {trader.get_safe_rounded_string(trader.get_stop_loss())}\n'
                f"Custom Stop Loss: {trader.get_safe_rounded_string(trader.customStopLoss)}\n"
                f"Current {trader.coinName} price: ${trader.currentPrice}\n"
                f'Elapsed time: {self.botThread.elapsed}\n'
                f'Smart Stop Loss Initial Counter: {trader.smartStopLossInitialCounter}\n'
                f'Smart Stop Loss Counter: {trader.smartStopLossCounter}\n'
                f'Stop Loss Safety Timer: {trader.safetyTimer}\n'
                f'{optionString}'
                )

    def send_statistics_telegram(self, chatID: str, period: str):
        """
        This function is used to periodically send statistics if enabled.
        :param chatID: Chat ID to send statistics to.
        :param period: Time period within which to send statistics.
        """
        message = f"Periodic statistics every {period}: \n"
        self.send_message(chatID, message + self.get_statistics())

    # noinspection PyUnusedLocal
    def get_statistics_telegram(self, update, context):
        """
        This function is called when /statistics is called. It replies with current bot statistics.
        """
        message = "Here are your statistics as requested: \n"
        update.message.reply_text(message + self.get_statistics())

    # noinspection PyUnusedLocal
    @staticmethod
    def thank_bot_telegram(update, context):
        """
        Small easter egg. You can /thank the bot.
        """
        messages = (
            "You're welcome.",
            "My pleasure.",
            "Embrace monke.",
            "No problem.",
            "Don't thank me. Thank Monke.",
            "Sure thing.",
            "The pleasure is all mine.",
            "Yes sirree."
        )
        update.message.reply_text(random.choice(messages))

    # noinspection PyUnusedLocal
    @staticmethod
    def print_telegram(update, context):
        """
        Small easter egg. You can tell bot to /print for it to joke around.
        """
        messages = [
            "Let's print this money. Printing...",
            "Opening a bakery soon. Printing...",
            "The FED will ask us for money.",
            "Alright. Printing in progress...",
            "It's literally free money. Printing...",
            "P r i n t i n g",
            "Printing in progress....",
            "Printing initialized...."
        ]
        update.message.reply_text(random.choice(messages))

    # noinspection PyUnusedLocal
    @staticmethod
    def wisdom(update, context):
        """
        Small easter egg. You can tell bot to /wisdom for a random wisdom quote.
        """
        quotes = [
            "Some people die at age 25, but aren't buried until 75.",
            "After accomplishing a goal just look around to see whether you lost something or someone.",
            "Holding on to anger is like grasping a hot coal with the intent of throwing it at someone else; "
            "you are the one who gets burned.",
            "There are only two kinds of people in this world; those who believe there are two kinds of people "
            "and those who know better.",
            "Many men go fishing all of their lives without knowing that it is not fish they are after.",
            "The smartest people are those that know what they don't know..",
            "Anywhere is walking distance if you've got the time.",
            "We stopped checking for monsters under our bed when we realized they were inside us.",
            "If you don't know where you're going, then any road will take you there.",
            "People take action with emotion then justify with logic.",
            "The two most important days of your life are the day you are born and the day you find out why.",
            "Just because everything is different doesn't mean anything has changed.",
            "Don't be so humble, you're not that great.",
            "Pride is not the opposite of shame, but it’s source.",
            "You don't know what you don't know.",
            "People will forget what you accomplished, but they will never forget how you made them feel.",
            "If you're going through hell, keep going.",
            "More is lost by indecision than a wrong decision.",
            "A ship is safe in harbor, but that's not what ships are for.",
            "You can be the ripest, tastiest peach in the world, and there'll still be someone who hates peaches.",
            "Nothing in the world can take the place of Persistence. Talent will not; nothing is more common than "
            "unsuccessful men with talent. Genius will not; unrewarded genius is almost a proverb. Education will not; "
            "the world is full of educated derelicts. Persistence and determination alone are omnipotent. "
            "The slogan 'Press On' has solved and always will solve the problems of the human race.",
            "Hard work beats Talent, when Talent doesn't work hard.",
            "Worrying is like paying interest on a debt you may never owe.",
            "Be the person your dog thinks you are.",
            "War doesn't decide who's right. War decides who's left.",
            "A year from now you will wish you had started today.",
            "Dude, sucking at something is the first step to being sorta good at something.",
            "We all make choices in life, but in the end our choices make us."
        ]
        update.message.reply_text(random.choice(quotes))

    # noinspection PyUnusedLocal
    @staticmethod
    def joke(update, context):
        """
        Another small easter egg. You can /joke to let bot tell you a random one-liner joke.
        """
        jokes = [
            "My uncle once said \"Go away kid, I'm not your uncle.\"",
            "I have an inferiority complex, but it's not a very good one.",
            "I have the heart of a lion and a lifetime ban from the Toronto zoo.",
            "A man walked into his house and was delighted when he discovered that someone had stolen all his lamps.",
            "I asked my North Korean friend how it was there, he said he couldn't complain.",
            "You've gotta hand it to blind prostitutes.",
            "You'd have to be really low to pickpocket a midget.",
            "I haven’t slept for ten days, because that would be too long.",
            "I discovered a substance that had no mass, and I was like \"0mg!\"",
            "Parallel lines have so much in common but it’s a shame they’ll never meet.",
            "They all laughed when I said I wanted to be a comedian; Well, they're not laughing now.",
            "Why do ballerinas always stand in their toes? Why don't they get taller dancers?.",
            "Say what you want about deaf people.",
            "How long is a Chinese name.",
            "I don't have a girlfriend, I just know a girl who would get really mad if she heard me say that.",
            "I, for one, like Roman numerals.",
            "On the other hand, you have different fingers.",
            "You're not completely useless, you can always serve as a bad example.",
            "How do you find Will Smith in the snow? Look for the fresh prints.",
            "On the other hand, you have different fingers.",
            "I remember a guy who was addicted to brake fluids. He said he could stop any time..",
            "I was at an ATM and this old lady asked me to help check her balance. So I pushed her over.",
            "I hate Russian dolls, they're so full of themselves.",
            "What do you call cheese that isn't yours? Nacho cheese.",
            "When cannibals ate a missionary, they got a taste of religion.",
            "As the shoe said to the hat, 'You go on ahead, and I'll follow on foot'.",
            "Talking to her about computer hardware I make my mother board.",
            "To write with a broken pencil is pointless.",
            "What does traffic jam taste like.",
            "Why are deer nuts better than beer nuts? . Beer nuts cost $1.50 but deer nuts are under a buck.",
            "I just bought shoes from my drug dealer. Don't know what he laced them with, but I been tripping all day.",
            "Which came first, the chicken or the egg? Neither, the rooster did.",
            "There are two types of people in this word: those who can extrapolate from incomplete data.",
        ]
        update.message.reply_text(random.choice(jokes))

    # noinspection PyUnusedLocal
    def override_telegram(self, update, context):
        """
        Function called when /override is called. As the name suggests, it overrides the bot.
        """
        update.message.reply_text("Overriding.")
        self.botThread.signals.waitOverride.emit()
        update.message.reply_text("Successfully overrode.")

    # noinspection PyUnusedLocal
    def pause_telegram(self, update, context):
        """
        Function called when /pause is called. As the name suggests, it pauses the bot logic.
        """
        if self.gui.trader.inHumanControl:
            update.message.reply_text("Bot is already in human control.")
        else:
            self.botThread.signals.pause.emit()
            update.message.reply_text("Bot has been paused successfully.")

    # noinspection PyUnusedLocal
    def resume_telegram(self, update, context):
        """
        Function called when /resume is called. As the name suggests, it resumes the bot logic.
        """
        if not self.gui.trader.inHumanControl:
            update.message.reply_text("Bot is already in autonomous mode.")
        else:
            self.botThread.signals.resume.emit()
            update.message.reply_text("Bot logic has been resumed.")

    # noinspection PyUnusedLocal
    def remove_custom_stop_loss(self, update, context):
        """
        Function called when /removecustomstoploss is called. As the name suggests, it removes the current custom stop
        loss set.
        """
        if self.gui.trader.customStopLoss is None:
            update.message.reply_text("Bot already has no custom stop loss implemented.")
        else:
            self.botThread.signals.removeCustomStopLoss.emit()
            update.message.reply_text("Bot's custom stop loss has been removed.")

    def set_custom_stop_loss(self, update, context):
        """
        Function called when /setcustomstoploss {value} is called. As the name suggests, it sets the custom stop
        loss with the value provided.
        """
        stopLoss = context.args[0]

        try:
            stopLoss = float(stopLoss)
        except ValueError:
            update.message.reply_text("Please make sure you specify a number for the custom stop loss.")
            return
        except Exception as e:
            update.message.reply_text(f'An error occurred: {e}.')
            return

        if stopLoss < 0:
            update.message.reply_text("Please make sure you specify a non-negative number for the custom stop loss.")
        elif stopLoss > 10_000_000:
            update.message.reply_text("Please make sure you specify a number that is less than 10,000,000.")
        else:
            stopLoss = round(stopLoss, 6)
            self.botThread.signals.setCustomStopLoss.emit(LIVE, True, stopLoss)
            update.message.reply_text(f"Stop loss has been successfully set to ${stopLoss}.")

    # noinspection PyUnusedLocal
    def force_long_telegram(self, update, context):
        """
        Function called when /forcelong is called. As the name suggests, it forces the bot to go long.
        """
        position = self.gui.trader.get_position()
        if position == LONG:
            update.message.reply_text("Bot is already in a long position.")
        else:
            update.message.reply_text("Forcing long.")
            self.botThread.signals.forceLong.emit()
            update.message.reply_text("Successfully forced long.")

    # noinspection PyUnusedLocal
    def force_short_telegram(self, update, context):
        """
        Function called when /forceshort is called. As the name suggests, it forces the bot to go short.
        """
        position = self.gui.trader.get_position()
        if position == SHORT:
            update.message.reply_text("Bot is already in a short position.")
        else:
            update.message.reply_text("Forcing short.")
            self.botThread.signals.forceShort.emit()
            update.message.reply_text("Successfully forced short.")

    # noinspection PyUnusedLocal
    def exit_position_telegram(self, update, context):
        """
        Function called when /exitposition is called. It forces the bot to exit its position provided it is in one.
        """
        if self.gui.trader.get_position() is None:
            update.message.reply_text("Bot is not in a position.")
        else:
            update.message.reply_text("Exiting position.")
            self.botThread.signals.exitPosition.emit()
            update.message.reply_text("Successfully exited position.")

    # noinspection PyUnusedLocal
    def get_position_telegram(self, update, context):
        """
        Function called when /getposition is called. It responds with the current position of the bot.
        """
        position = self.gui.trader.get_position()
        if position == SHORT:
            update.message.reply_text("Bot is currently in a short position.")
        elif position == LONG:
            update.message.reply_text("Bot is currently in a long position.")
        else:
            update.message.reply_text("Bot is currently not in any position.")
