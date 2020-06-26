from trader import Trader


def user(bot):
    action = None
    while action != '':
        while action not in ('', 'sma', 'ema'):
            print("\nWhat do you wanna do? Type 'sma', 'ema', or nothing to quit.")
            action = input(">>").lower()
        if action in ('ema', 'sma'):
            print("Type in what you would like to find the period of.")
            print("Possible choices (currently) are high, low, open, close.")
            parameter = input(">>").lower()
            if action == 'sma':
                print("Type how many days you want to get the sma of")
                days = int(input(">>"))
                sma = bot.get_sma(days=days, parameter=parameter)
                print(f'The SMA of the last {days} days is ${sma}.')
            else:
                period = int(input("Type in your desired period>>"))
                ema = bot.get_ema(period=period, parameter=parameter)
                print(f'The EMA with period {period} and parameter {parameter} is ${ema}.')

        if action != "":
            action = None


def algorithm(bot):
    ema4 = bot.get_ema(period=4, parameter='open', round_value=False)
    ema8 = bot.get_ema(period=8, parameter='open', round_value=False)
    print(f'EMA(4) = {ema4} | EMA(8) = {ema8}')

    if ema4 > ema8:
        print("BUY")
    else:
        print("SELL")


def main():
    bot = Trader()
    algorithm(bot)


main()
