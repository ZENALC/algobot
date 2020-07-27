from trader import Trader


def user(bot):
    action = None
    while action != '':
        while action not in ('', 'sma', 'ema'):
            print("\nWhat do you wanna do? Type 'sma', 'ema', or nothing to quit.")
            action = input(">>").lower()
        if action in ('ema', 'sma'):
            parameter = ""
            success = False
            while parameter not in ('high', 'low', 'open', 'close'):
                print("Type in what you would like to find the period of.")
                print("Possible choices (currently) are high, low, open, close.")
                parameter = input(">>").lower()
            while not success:
                try:
                    if action == 'sma':
                        print("Type how many prices you want to get the SMA of. For example, for SMA(4) enter 4.")
                        prices = int(input(">>"))
                        sma = bot.get_sma(prices=prices, parameter=parameter)
                        print(f'The SMA of the last {prices} price(s) is ${sma}.')
                    else:
                        period = int(input("Type in your desired period>>"))
                        ema = bot.get_ema(period=period, parameter=parameter)
                        print(f'The EMA with period {period} and parameter {parameter} is ${ema}.')
                    success = True
                except ValueError:
                    print("Invalid input. Please type in an integer.")
                    continue

        if action != "":
            action = None


def main():
    bot = Trader()
    user(bot)


main()
