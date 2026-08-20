#!/usr/bin/env python3
"""
WEATHER-ENSEMBLE LIVE BOT HISTORICAL BACKTEST WITH FIBONACCI ENGINE
===================================================================
Direct Integration Test:
- Directly imports and executes `WeatherEnsembleBot` & `check_fibonacci_setup` from `weather_ensemble_bot.py`
- Runs across all 10 assets from July 2025 -> August 2026 (15m candles)
- 50x Leverage (Isolated/Cross Margin simulation)
- User Live Balance: $12.62 USDT default (or custom --balance)
- 3.0% Position margin allocation (--margin-pct 0.03)
- Max 5 concurrent slots (--max-positions 5)
- Binance $5.00 min notional compliance
- VIP0 + BNB Fee Schedule (0.018% Maker Entry/TP, 0.045% Taker SL) + 0.015% Slippage
"""

import os
import sys
import math
import argparse
from datetime import datetime, timezone
import numpy as np
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add parent directory to path to import live bot directly
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from weather_ensemble_bot import (
    WeatherEnsembleBot,
    check_fibonacci_setup,
    check_potato_sr_levels
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "historical_data_cache")
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "NEARUSDT"
]

def load_data(symbol, interval="15m"):
    fname = f"{symbol}_{interval}_from_2025-07-01.csv"
    fpath = os.path.join(CACHE_DIR, fname)
    if not os.path.exists(fpath):
        return None
    df = pd.read_csv(fpath)
    time_col = 'timestamp' if 'timestamp' in df.columns else 'open_time'
    df['open_time'] = pd.to_datetime(df[time_col])
    df = df.sort_values('open_time').reset_index(drop=True)
    return df

class LiveBotFibonacciBacktest:
    def __init__(self, initial_balance=12.62, leverage=50, max_positions=5, margin_pct=0.03, threshold=30):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.max_positions = max_positions
        self.margin_pct = margin_pct
        self.threshold = threshold
        
        # Instantiate actual bot class
        self.bot = WeatherEnsembleBot(
            consensus_threshold=threshold,
            live_trading=False,
            margin_pct=margin_pct,
            leverage=leverage,
            max_positions=max_positions
        )
        
        self.active_positions = {}  # symbol -> dict
        self.trade_history = []
        self.monthly_pnl = {}
        
        self.maker_fee = 0.00018  # 0.018% Binance maker
        self.taker_fee = 0.00045  # 0.045% Binance taker
        self.slippage = 0.00015   # 0.015% slippage

    def run(self):
        raw_data = {}
        for sym in SYMBOLS:
            df = load_data(sym, "15m")
            if df is not None:
                raw_data[sym] = df
        
        if not raw_data:
            print("No cached data found!")
            return

        min_len = min(len(df) for df in raw_data.values())
        print(f"Loaded {len(raw_data)} assets from cache. Total bars per asset: {min_len:,} (15m intervals)")
        print(f"Starting Wallet Balance: ${self.initial_balance:,.2f} USDT | Leverage: {self.leverage}x | Margin/trade: {self.margin_pct*100:.1f}%\n")

        # Convert to numpy for fast execution
        np_data = {}
        for sym in SYMBOLS:
            df = raw_data[sym]
            np_data[sym] = {
                'high': df['high'].values,
                'low': df['low'].values,
                'close': df['close'].values,
                'open_time': df['open_time'].values
            }

        last_trade_bar = {sym: -999 for sym in SYMBOLS}
        lookback = 100

        for bar_idx in range(lookback, min_len):
            current_time = pd.to_datetime(np_data['BTCUSDT']['open_time'][bar_idx])
            month_key = current_time.strftime('%Y-%m')
            if month_key not in self.monthly_pnl:
                self.monthly_pnl[month_key] = 0.0

            # 1. Manage Open Positions (TP1, TP2, TP3, SL, Breakeven)
            closed_syms = []
            for sym, pos in list(self.active_positions.items()):
                bar_h = np_data[sym]['high'][bar_idx]
                bar_l = np_data[sym]['low'][bar_idx]
                bar_c = np_data[sym]['close'][bar_idx]
                side = pos['side'].upper()
                is_long = side in ['BUY', 'LONG']
                is_short = side in ['SELL', 'SHORT']
                
                # Check Stop Loss first (worst-case execution)
                hit_sl = False
                sl_exit_price = pos['sl']
                if is_long and bar_l <= pos['sl']:
                    hit_sl = True
                    sl_exit_price = min(bar_c, pos['sl']) * (1.0 - self.slippage)
                elif is_short and bar_h >= pos['sl']:
                    hit_sl = True
                    sl_exit_price = max(bar_c, pos['sl']) * (1.0 + self.slippage)

                if hit_sl:
                    rem_qty = pos['rem_qty']
                    pnl = rem_qty * (sl_exit_price - pos['entry_price']) if is_long else rem_qty * (pos['entry_price'] - sl_exit_price)
                    fee = rem_qty * sl_exit_price * self.taker_fee
                    net_pnl = pnl - fee
                    self.balance += net_pnl
                    self.monthly_pnl[month_key] += net_pnl
                    
                    pos['realized_pnl'] += net_pnl
                    pos['exit_time'] = current_time
                    pos['exit_reason'] = 'SL_BE' if pos['tp1_hit'] else 'STOP_LOSS'
                    self.trade_history.append(pos)
                    closed_syms.append(sym)
                    continue

                # Check TP1 (0.000 Retest - 40% Scale Out + Move SL to Breakeven)
                if not pos['tp1_hit']:
                    tp1_hit = (is_long and bar_h >= pos['tp1']) or (is_short and bar_l <= pos['tp1'])
                    if tp1_hit:
                        pos['tp1_hit'] = True
                        close_qty = pos['initial_qty'] * 0.40
                        pos['rem_qty'] -= close_qty
                        
                        tp_p = pos['tp1']
                        pnl = close_qty * (tp_p - pos['entry_price']) if is_long else close_qty * (pos['entry_price'] - tp_p)
                        fee = close_qty * tp_p * self.maker_fee
                        net_pnl = pnl - fee
                        
                        self.balance += net_pnl
                        self.monthly_pnl[month_key] += net_pnl
                        pos['realized_pnl'] += net_pnl
                        
                        # Move stop to breakeven
                        pos['sl'] = pos['entry_price']

                # Check TP2 (-0.618 Extension - 40% Scale Out)
                if pos['tp1_hit'] and not pos['tp2_hit']:
                    tp2_hit = (is_long and bar_h >= pos['tp2']) or (is_short and bar_l <= pos['tp2'])
                    if tp2_hit:
                        pos['tp2_hit'] = True
                        close_qty = pos['initial_qty'] * 0.40
                        pos['rem_qty'] -= close_qty
                        
                        tp_p = pos['tp2']
                        pnl = close_qty * (tp_p - pos['entry_price']) if is_long else close_qty * (pos['entry_price'] - tp_p)
                        fee = close_qty * tp_p * self.maker_fee
                        net_pnl = pnl - fee
                        
                        self.balance += net_pnl
                        self.monthly_pnl[month_key] += net_pnl
                        pos['realized_pnl'] += net_pnl
                        
                        # Trail stop to TP1 level for remaining 20% runner
                        pos['sl'] = pos['tp1']

                # Check TP3 (-1.618 Runner - Remaining 20%)
                if pos['tp2_hit']:
                    tp3_hit = (is_long and bar_h >= pos['tp3']) or (is_short and bar_l <= pos['tp3'])
                    if tp3_hit:
                        close_qty = pos['rem_qty']
                        tp_p = pos['tp3']
                        pnl = close_qty * (tp_p - pos['entry_price']) if is_long else close_qty * (pos['entry_price'] - tp_p)
                        fee = close_qty * tp_p * self.maker_fee
                        net_pnl = pnl - fee
                        
                        self.balance += net_pnl
                        self.monthly_pnl[month_key] += net_pnl
                        pos['realized_pnl'] += net_pnl
                        
                        pos['exit_time'] = current_time
                        pos['exit_reason'] = 'FULL_TP3_RUNNER'
                        self.trade_history.append(pos)
                        closed_syms.append(sym)
                        continue

            for sym in closed_syms:
                if sym in self.active_positions:
                    del self.active_positions[sym]

            # 2. Evaluate Signals using live Bot's `check_fibonacci_setup`
            if len(self.active_positions) >= self.max_positions:
                continue

            for sym in SYMBOLS:
                if sym in self.active_positions:
                    continue
                if (bar_idx - last_trade_bar[sym]) < 8:  # 2-hour trade spacing per asset
                    continue

                # Build slice dataframe for check_fibonacci_setup
                df_slice = raw_data[sym].iloc[bar_idx - lookback + 1 : bar_idx + 1]
                
                # Directly call live bot's check_fibonacci_setup
                fib_setup = check_fibonacci_setup(df_slice, sym)
                
                if fib_setup.get('is_setup') and fib_setup.get('rr', 0) >= 1.8:
                    side = fib_setup['side']
                    entry_p = fib_setup['entry_price']
                    sl_p = fib_setup['sl']
                    tp1_p = fib_setup['tp1']
                    tp2_p = fib_setup['tp2']
                    tp3_p = fib_setup['tp3']
                    
                    # Sizing with Binance $5.00 min notional enforcement
                    margin = self.balance * self.margin_pct
                    notional = margin * self.leverage
                    if notional < 5.0:
                        notional = 5.0
                        margin = notional / self.leverage
                    
                    if self.balance >= margin:
                        qty = notional / entry_p
                        
                        # Limit Maker entry fee (0.018%)
                        fee = notional * self.maker_fee
                        self.balance -= fee
                        self.monthly_pnl[month_key] -= fee

                        self.active_positions[sym] = {
                            'symbol': sym,
                            'side': side,
                            'entry_time': current_time,
                            'entry_price': entry_p,
                            'initial_qty': qty,
                            'rem_qty': qty,
                            'sl': sl_p,
                            'tp1': tp1_p,
                            'tp2': tp2_p,
                            'tp3': tp3_p,
                            'tp1_hit': False,
                            'tp2_hit': False,
                            'realized_pnl': -fee,
                            'channel': 'CHANNEL_0_FIBONACCI'
                        }
                        last_trade_bar[sym] = bar_idx
                        if len(self.active_positions) >= self.max_positions:
                            break

        # Close remaining open positions at last market close
        for sym, pos in list(self.active_positions.items()):
            bar_c = np_data[sym]['close'][-1]
            rem_qty = pos['rem_qty']
            pnl = rem_qty * (bar_c - pos['entry_price']) if pos['side'] == 'LONG' else rem_qty * (pos['entry_price'] - bar_c)
            fee = rem_qty * bar_c * self.taker_fee
            net_pnl = pnl - fee
            self.balance += net_pnl
            pos['realized_pnl'] += net_pnl
            pos['exit_time'] = pd.to_datetime(np_data[sym]['open_time'][-1])
            pos['exit_reason'] = 'MARKET_END'
            self.trade_history.append(pos)

        self.print_results()

    def print_results(self):
        total_trades = len(self.trade_history)
        if total_trades == 0:
            print("No trades triggered.")
            return

        wins = [t for t in self.trade_history if t['realized_pnl'] > 0]
        losses = [t for t in self.trade_history if t['realized_pnl'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100
        gross_profit = sum(t['realized_pnl'] for t in wins)
        gross_loss = abs(sum(t['realized_pnl'] for t in losses))
        profit_factor = gross_profit / (gross_loss + 1e-9)
        total_return_pct = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        hard_sls = len([t for t in self.trade_history if t['exit_reason'] == 'STOP_LOSS'])
        be_sls = len([t for t in self.trade_history if t['exit_reason'] == 'SL_BE'])
        tp2_hits = len([t for t in self.trade_history if t['tp2_hit'] and t['exit_reason'] != 'FULL_TP3_RUNNER'])
        tp3_hits = len([t for t in self.trade_history if t.get('exit_reason') == 'FULL_TP3_RUNNER'])

        print("\n" + "="*70)
        print("🎯 LIVE BOT + check_fibonacci_setup HISTORICAL BACKTEST RESULTS")
        print("="*70)
        print(f"Source Code:            weather_ensemble_bot.py -> check_fibonacci_setup")
        print(f"Initial Balance:        ${self.initial_balance:,.2f} USDT")
        print(f"Final Balance:          ${self.balance:,.2f} USDT")
        print(f"Total Net Return:       {total_return_pct:+,.2f}%")
        print(f"Profit Factor (PF):     {profit_factor:.2f}")
        print(f"Total Trades:           {total_trades}")
        print(f"Win Rate:               {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
        print(f"Average Trade PnL:      ${(self.balance - self.initial_balance)/total_trades:+,.2f}")
        print("-" * 70)
        print("📊 TRADE OUTCOME BREAKDOWN:")
        print(f" • Hard Stop Loss (Full -1R):        {hard_sls} ({hard_sls/total_trades*100:.1f}%)")
        print(f" • TP1 Hit -> SL Breakeven Exit:     {be_sls} ({be_sls/total_trades*100:.1f}%) -> Net Green (+1.06R)")
        print(f" • TP2 Hit (-0.618 Extension):       {tp2_hits} ({tp2_hits/total_trades*100:.1f}%) -> Big Win (+2.60R)")
        print(f" • TP3 Full Runner (-1.618 Ext):     {tp3_hits} ({tp3_hits/total_trades*100:.1f}%) -> Massive Trend Win (+4.53R)")
        print("-" * 70)
        print("📅 MONTHLY PnL BREAKDOWN (USDT):")
        for m, pnl in sorted(self.monthly_pnl.items()):
            bar = "🟩" if pnl >= 0 else "🟥"
            print(f" {bar} {m}:  {pnl:+8.2f} USDT")
        print("="*70 + "\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Live Bot Fibonacci Backtest')
    parser.add_argument('--balance', type=float, default=12.62, help='Initial balance in USDT (default: 12.62)')
    parser.add_argument('--leverage', type=int, default=50, help='Leverage multiplier (default: 50)')
    parser.add_argument('--margin-pct', type=float, default=0.03, help='Margin pct per trade (default: 0.03 = 3.0%)')
    parser.add_argument('--max-positions', type=int, default=5, help='Max concurrent positions (default: 5)')
    parser.add_argument('--threshold', type=int, default=30, help='Consensus threshold (default: 30)')
    args = parser.parse_args()

    engine = LiveBotFibonacciBacktest(
        initial_balance=args.balance,
        leverage=args.leverage,
        max_positions=args.max_positions,
        margin_pct=args.margin_pct,
        threshold=args.threshold
    )
    engine.run()
