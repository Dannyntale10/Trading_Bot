# TradingBot.py - With trade limit and strategy selection
import MetaTrader5 as mt5
import pandas as pd
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TradingBot:
    def __init__(self):
        self.symbols = ['USDJPYm', 'AUDUSDm', 'NZDUSDm', 'CADJPY', 'CHFJPY', 'EURJPY', 'GBPUSD', 'XAUUSD']
        self.timeframe = mt5.TIMEFRAME_M15
        self.atr_period = 14
        self.max_concurrent_trades = 2  # Maximum trades allowed at once
        self.strategy = None
        self.init_mt5()
        self.select_strategy()

    def init_mt5(self):
        """Initialize MT5 connection"""
        if not mt5.initialize():
            logging.error("Failed to initialize MT5")
            quit()
        logging.info("MT5 initialized successfully")

    def select_strategy(self):
        """Prompt user to select trading strategy"""
        print("\n" + "="*50)
        print("TRADING BOT STRATEGY SELECTION")
        print("="*50)
        print("1. ABCD Harmonic Pattern Strategy")
        print("2. Pure Price Action Strategy")
        print("="*50)
        
        while True:
            choice = input("Please select strategy (1 or 2): ")
            if choice == '1':
                self.strategy = 'abcd'
                logging.info("ABCD Harmonic Pattern strategy selected")
                break
            elif choice == '2':
                self.strategy = 'price_action'
                logging.info("Pure Price Action strategy selected")
                break
            else:
                print("Invalid selection. Please enter 1 or 2.")

    def fetch_data(self, symbol):
        """Get price data for analysis"""
        rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, 100)
        return pd.DataFrame(rates) if rates is not None else pd.DataFrame()

    def calculate_atr(self, df, period=14):
        """Calculate Average True Range for volatility stops"""
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(period).mean()

    def get_current_trades(self):
        """Get count of currently open trades"""
        positions = mt5.positions_get()
        return len(positions) if positions else 0

    # ====================== ABCD PATTERN STRATEGY ======================
    def detect_abcd_pattern(self, df, tolerance=0.618):
        """Detect bullish/bearish ABCD harmonic patterns"""
        if len(df) < 10:
            return None
            
        highs = df['high'].values
        lows = df['low'].values
        
        for i in range(len(df)-20, len(df)-4):
            # Bullish ABCD pattern
            A = lows[i+1]
            B = highs[i+2]
            C = lows[i+3]
            D = lows[-1]
            
            if (B - A) > 0 and (C - B) < 0 and (D - C) > 0:
                AB = B - A
                BC = B - C
                CD = D - C
                
                if (abs(BC/AB - 0.618) < tolerance) and (abs(CD/BC - 1.618) < tolerance):
                    logging.info(f"Bullish ABCD pattern detected (AB={AB:.5f}, BC={BC:.5f}, CD={CD:.5f})")
                    return 'buy'
            
            # Bearish ABCD pattern
            A = highs[i+1]
            B = lows[i+2]
            C = highs[i+3]
            D = highs[-1]
            
            if (A - B) > 0 and (C - B) > 0 and (C - D) > 0:
                AB = A - B
                BC = C - B
                CD = C - D
                
                if (abs(BC/AB - 0.618) < tolerance) and (abs(CD/BC - 1.618) < tolerance):
                    logging.info(f"Bearish ABCD pattern detected (AB={AB:.5f}, BC={BC:.5f}, CD={CD:.5f})")
                    return 'sell'
        
        return None

    # ====================== PRICE ACTION STRATEGY ======================
    def detect_price_action(self, df):
        """Detect price action signals (Pin Bars, Engulfing, Inside Bars)"""
        if len(df) < 3:
            return None
            
        # Get last 3 candles
        current = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        
        # Bullish Signals
        bullish_pin = (current['close'] > current['open'] and 
                      (current['open'] - current['low']) > 2*(current['high'] - current['close']) and
                      (current['high'] - current['close']) < (current['close'] - current['open']))
        
        bullish_engulfing = (current['close'] > prev['open'] and 
                            current['open'] < prev['close'] and 
                            current['close'] > prev['high'] and
                            prev['close'] < prev['open'])
        
        # Bearish Signals
        bearish_pin = (current['close'] < current['open'] and 
                      (current['high'] - current['open']) > 2*(current['close'] - current['low']) and
                      (current['close'] - current['low']) < (current['open'] - current['high']))
        
        bearish_engulfing = (current['close'] < prev['open'] and 
                             current['open'] > prev['close'] and 
                             current['close'] < prev['low'] and
                             prev['close'] > prev['open'])
        
        if bullish_pin or bullish_engulfing:
            logging.info(f"Bullish price action detected - Pin Bar: {bullish_pin}, Engulfing: {bullish_engulfing}")
            return 'buy'
        elif bearish_pin or bearish_engulfing:
            logging.info(f"Bearish price action detected - Pin Bar: {bearish_pin}, Engulfing: {bearish_engulfing}")
            return 'sell'
        
        return None

    def place_order(self, symbol, signal, df):
        """Execute trade if under max concurrent trades limit"""
        current_trades = self.get_current_trades()
        if current_trades >= self.max_concurrent_trades:
            logging.info(f"Max trades reached ({current_trades}/{self.max_concurrent_trades}). Skipping new trade.")
            return False
            
        price = mt5.symbol_info_tick(symbol).ask if signal == 'buy' else mt5.symbol_info_tick(symbol).bid
        lot = 0.1
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else self.calculate_atr(df, self.atr_period).iloc[-1]
        
        # Risk management
        sl = price - atr * 2 if signal == 'buy' else price + atr * 2
        tp = price + atr * 3 if signal == 'buy' else price - atr * 3

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
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
        else:
            logging.info(f"{self.strategy.upper()} Trade: {symbol} {signal.upper()} at {price} (Trade {current_trades+1}/{self.max_concurrent_trades})")
            return True

    def manage_trades(self):
        """Manage open positions with trailing stops"""
        positions = mt5.positions_get()
        for pos in positions:
            current_price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask
            
            # Move SL to breakeven + 0.5x ATR after 1.5x initial risk
            if pos.type == 0:  # Buy position
                if current_price > pos.price_open + (pos.price_open - pos.sl) * 1.5:
                    new_sl = pos.price_open + (pos.price_open - pos.sl) * 0.5
                    if new_sl > pos.sl:
                        self.modify_sl(pos, new_sl)
            else:  # Sell position
                if current_price < pos.price_open - (pos.sl - pos.price_open) * 1.5:
                    new_sl = pos.price_open - (pos.sl - pos.price_open) * 0.5
                    if new_sl < pos.sl:
                        self.modify_sl(pos, new_sl)

    def modify_sl(self, position, new_sl):
        """Modify stop loss of an open position"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.tp,
            "symbol": position.symbol,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"SL updated to {new_sl:.5f} for {position.symbol}")

    def run(self):
        """Main trading loop"""
        logging.info(f"Starting Trading Bot with {self.strategy.upper()} strategy (Max {self.max_concurrent_trades} concurrent trades)")
        try:
            while True:
                current_trades = self.get_current_trades()
                logging.info(f"Current open trades: {current_trades}/{self.max_concurrent_trades}")
                
                if current_trades < self.max_concurrent_trades:
                    for symbol in self.symbols:
                        df = self.fetch_data(symbol)
                        if df.empty:
                            continue
                            
                        df['atr'] = self.calculate_atr(df, self.atr_period)
                        
                        if self.strategy == 'abcd':
                            signal = self.detect_abcd_pattern(df)
                        elif self.strategy == 'price_action':
                            signal = self.detect_price_action(df)
                        
                        if signal in ['buy', 'sell']:
                            self.place_order(symbol, signal, df)
                            # Check if we've reached max trades after this order
                            if self.get_current_trades() >= self.max_concurrent_trades:
                                break
                
                self.manage_trades()
                time.sleep(60)
                
        except KeyboardInterrupt:
            logging.info("Shutting down trading bot...")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()