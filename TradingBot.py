import MetaTrader5 as mt5
import pandas as pd
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TradingBot:
    def __init__(self):
        self.symbols = ['USDJPYm', 'AUDUSDm', 'NZDUSDm', 'CADJPY', 'CHFJPY', 'EURJPY', 'GBPUSD', 'XAUUSD']
        self.timeframe = mt5.TIMEFRAME_M15
        self.atr_period = 14
        self.ema_period = 50
        self.max_concurrent_trades = 2
        self.lot = 0.2
        self.strategy = None
        self.init_mt5()
        self.select_strategy()

    def init_mt5(self):
        if not mt5.initialize():
            logging.error("Failed to initialize MT5")
            quit()
        logging.info("MT5 initialized")

    def select_strategy(self):
        print("\n" + "="*50)
        print("TRADING BOT STRATEGY SELECTION")
        print("="*50)
        print("1. ABCD Harmonic Pattern Strategy (Enhanced)")
        print("2. Pure Price Action Strategy (Enhanced)")
        print("="*50)
        while True:
            choice = input("Select strategy (1 or 2): ")
            if choice == '1':
                self.strategy = 'abcd'
                logging.info("ABCD strategy selected")
                break
            elif choice == '2':
                self.strategy = 'price_action'
                logging.info("Price Action strategy selected")
                break
            else:
                print("Invalid input. Try 1 or 2.")

    def fetch_data(self, symbol, retries=3):
        for _ in range(retries):
            rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, 100)
            if rates is not None and len(rates) > 0:
                return pd.DataFrame(rates)
            time.sleep(1)
        logging.warning(f"Failed to fetch data for {symbol}")
        return pd.DataFrame()

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def calculate_ema(self, df, period=50):
        return df['close'].ewm(span=period, adjust=False).mean()

    def get_current_trades(self):
        positions = mt5.positions_get()
        return len(positions) if positions else 0

    # ========== ENHANCED ABCD STRATEGY ==========
    def detect_abcd_pattern(self, df, tolerance=0.15):
        if len(df) < 30:
            return None
        ema = self.calculate_ema(df, self.ema_period)
        trend = 'up' if df['close'].iloc[-1] > ema.iloc[-1] else 'down'

        highs = df['high'].values[-30:]
        lows = df['low'].values[-30:]

        for i in range(len(lows) - 4):
            A = lows[i]
            B = highs[i + 1]
            C = lows[i + 2]
            D = df['low'].iloc[-1]

            AB = B - A
            BC = B - C
            CD = D - C

            valid_bull = (AB > 0 and BC < 0 and CD > 0 and
                         abs((BC / AB) - 0.618) < tolerance and
                         abs((CD / BC) - 1.618) < tolerance)

            if valid_bull and trend == 'up':
                logging.info(f"ABCD Bullish pattern validated: AB={AB:.3f}, BC={BC:.3f}, CD={CD:.3f}")
                return 'buy'

            A = highs[i]
            B = lows[i + 1]
            C = highs[i + 2]
            D = df['high'].iloc[-1]

            AB = A - B
            BC = C - B
            CD = C - D

            valid_bear = (AB > 0 and BC > 0 and CD > 0 and
                         abs((BC / AB) - 0.618) < tolerance and
                         abs((CD / BC) - 1.618) < tolerance)

            if valid_bear and trend == 'down':
                logging.info(f"ABCD Bearish pattern validated: AB={AB:.3f}, BC={BC:.3f}, CD={CD:.3f}")
                return 'sell'
        return None

    # ========== ENHANCED PRICE ACTION STRATEGY ==========
    def detect_price_action(self, df):
        if len(df) < 5:
            return None

        current = df.iloc[-1]
        prev = df.iloc[-2]
        ema = self.calculate_ema(df, self.ema_period)
        trend = 'up' if current['close'] > ema.iloc[-1] else 'down'

        # Signal logic
        bullish_pin = (current['close'] > current['open'] and
                       (current['open'] - current['low']) > 2 * (current['high'] - current['close']))
        bearish_pin = (current['close'] < current['open'] and
                       (current['high'] - current['open']) > 2 * (current['close'] - current['low']))

        bullish_engulf = (prev['close'] < prev['open'] and
                          current['close'] > current['open'] and
                          current['open'] < prev['close'] and
                          current['close'] > prev['open'])

        bearish_engulf = (prev['close'] > prev['open'] and
                          current['close'] < current['open'] and
                          current['open'] > prev['close'] and
                          current['close'] < prev['open'])

        inside = current['high'] < prev['high'] and current['low'] > prev['low']
        breakout_up = inside and current['close'] > prev['high']
        breakout_down = inside and current['close'] < prev['low']

        if breakout_up and trend == 'up':
            logging.info("Inside bar breakout BUY")
            return 'buy'
        elif breakout_down and trend == 'down':
            logging.info("Inside bar breakout SELL")
            return 'sell'
        elif bullish_engulf and trend == 'up':
            logging.info("Bullish Engulfing detected")
            return 'buy'
        elif bearish_engulf and trend == 'down':
            logging.info("Bearish Engulfing detected")
            return 'sell'
        elif bullish_pin and trend == 'up':
            logging.info("Bullish Pin Bar detected")
            return 'buy'
        elif bearish_pin and trend == 'down':
            logging.info("Bearish Pin Bar detected")
            return 'sell'
        return None

    def place_order(self, symbol, signal, df):
        if self.get_current_trades() >= self.max_concurrent_trades:
            logging.info(f"Max trades reached. Skipping {symbol}")
            return False

        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if signal == 'buy' else tick.bid
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else self.calculate_atr(df, self.atr_period).iloc[-1]
        sl = price - atr * 2 if signal == 'buy' else price + atr * 2
        tp = price + atr * 3 if signal == 'buy' else price - atr * 3

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY if signal == 'buy' else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 10,
            "magic": 123456,
            "comment": f"{self.strategy}_{signal}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed: {result.retcode}")
            return False
        logging.info(f"{symbol} {signal.upper()} at {price:.5f} | SL={sl:.5f} | TP={tp:.5f}")
        return True

    def manage_trades(self):
        positions = mt5.positions_get()
        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            price = tick.bid if pos.type == 0 else tick.ask

            if pos.type == 0 and price > pos.price_open + (pos.price_open - pos.sl) * 1.5:
                new_sl = pos.price_open + (pos.price_open - pos.sl) * 0.5
                if new_sl > pos.sl:
                    self.modify_sl(pos, new_sl)
            elif pos.type == 1 and price < pos.price_open - (pos.sl - pos.price_open) * 1.5:
                new_sl = pos.price_open - (pos.sl - pos.price_open) * 0.5
                if new_sl < pos.sl:
                    self.modify_sl(pos, new_sl)

    def modify_sl(self, position, new_sl):
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.tp,
            "symbol": position.symbol,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"SL updated: {position.symbol} → {new_sl:.5f}")

    def run(self):
        logging.info(f"Bot running: {self.strategy.upper()} strategy")
        try:
            while True:
                if self.get_current_trades() < self.max_concurrent_trades:
                    for symbol in self.symbols:
                        df = self.fetch_data(symbol)
                        if df.empty:
                            continue
                        df['atr'] = self.calculate_atr(df)

                        signal = None
                        if self.strategy == 'abcd':
                            signal = self.detect_abcd_pattern(df)
                        elif self.strategy == 'price_action':
                            signal = self.detect_price_action(df)

                        if signal:
                            self.place_order(symbol, signal, df)
                            if self.get_current_trades() >= self.max_concurrent_trades:
                                break

                self.manage_trades()
                time.sleep(60)
        except KeyboardInterrupt:
            logging.info("Bot manually stopped.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
