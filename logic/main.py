from logic.trader import Trader

trader1 = Trader()
print(trader1.get_ema(sma_days=1, ema_days=20, parameter='close'))
