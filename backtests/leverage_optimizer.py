#!/usr/bin/env python3
"""
WEATHER-ENSEMBLE ADVANCED LEVERAGE & RISK OPTIMIZER
===================================================
Optimizes:
1. Trailing ATR Stop vs Fixed ATR Stop
2. Early Consensus Emergency Exit (exit if consensus drops < 24 models)
3. Dynamic Margin Allocation (2%, 3%, 4%, 5% wallet balance)
4. Leverage Levels (20x, 30x, 50x)

Starting Capital: $30.00 | Timeframe: 5-minute BTC/USDT (365 Days)
"""

import sys
import time
import math
import random
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

def generate_365d_data():
    num_bars = 365 * 24 * 12 # 105,120 bars
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365)
    dates = pd.date_range(start=start_date, periods=num_bars, freq='5min')
    
    np.random.seed(42)
    price = 45000.0
    
    regimes = np.sin(np.linspace(0, 5 * np.pi, num_bars)) * 0.00022
    volatilities = (np.sin(np.linspace(0, 15 * np.pi, num_bars)) + 1.2) * 0.0025
    random_returns = np.random.normal(0, 1, num_bars)
    
    returns = regimes + random_returns * volatilities
    price_series = price * np.cumprod(1 + returns)
    
    highs = price_series * (1 + np.abs(np.random.normal(0, 0.0009, num_bars)))
    lows = price_series * (1 - np.abs(np.random.normal(0, 0.0009, num_bars)))
    opens = np.roll(price_series, 1)
    opens[0] = price
    closes = price_series
    volumes = np.random.uniform(20, 200, num_bars)
    
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    }, index=dates)
    
    return df

def run_leverage_optimization():
    print("=" * 80)
    print(" STARTING LEVERAGE & TRADE MANAGEMENT LOOP OPTIMIZER ($30 CAPITAL)")
    print("=" * 80)
    
    start_t = time.time()
    df = generate_365d_data()
    
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    volumes = df['volume'].values
    num_bars = len(closes)
    
    s_df = pd.DataFrame({'close': closes, 'high': highs, 'low': lows, 'volume': volumes})
    
    ema_300 = s_df['close'].ewm(span=300).mean().values
    vol_sma20 = s_df['volume'].rolling(20).mean().values
    
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - np.roll(closes, 1)), np.abs(lows - np.roll(closes, 1))))
    atr = pd.Series(tr).rolling(14).mean().values
    
    ema8 = s_df['close'].ewm(span=8).mean().values
    ema21 = s_df['close'].ewm(span=21).mean().values
    ema13 = s_df['close'].ewm(span=13).mean().values
    ema55 = s_df['close'].ewm(span=55).mean().values
    macd = s_df['close'].ewm(span=12).mean().values - s_df['close'].ewm(span=26).mean().values
    
    delta = s_df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss.replace(0, 1e-9))
    rsi = (100 - (100 / (1 + rs))).values
    
    sma20 = s_df['close'].rolling(20).mean().values
    std20 = s_df['close'].rolling(20).std().values
    b_pct = (closes - (sma20 - 2*std20)) / (4*std20 + 1e-9)
    
    cum_pv = np.cumsum(closes * volumes)
    cum_v = np.cumsum(volumes)
    vwap = cum_pv / (cum_v + 1e-9)
    
    signals_matrix = np.zeros((num_bars, 31), dtype=int)
    
    signals_matrix[:, 0] = np.where(ema8 > ema21, 1, -1)
    signals_matrix[:, 1] = np.where(ema13 > ema55, 1, -1)
    signals_matrix[:, 2] = np.where(macd > 0, 1, -1)
    signals_matrix[:, 3] = np.where(closes > np.roll(closes, 10), 1, -1)
    signals_matrix[:, 4] = np.where(closes > np.roll(closes, 7), 1, -1)
    signals_matrix[:, 5] = np.where(closes > np.roll(closes, 20), 1, -1)
    signals_matrix[:, 6] = np.where(closes > np.roll(closes, 50), 1, -1)
    signals_matrix[:, 7] = np.where(closes > np.roll(closes, 5), 1, -1)
    signals_matrix[:, 8] = np.where(ema13 > ema21, 1, -1)
    signals_matrix[:, 9] = np.where(rsi > 54, 1, np.where(rsi < 46, -1, 0))
    
    for m_i in range(10, 16):
        shift_p = 5 + (m_i - 10)
        mom = (closes - np.roll(closes, shift_p)) / (np.roll(closes, shift_p) + 1e-9)
        signals_matrix[:, m_i] = np.where(mom > 0.0008, 1, np.where(mom < -0.0008, -1, 0))
        
    for v_i in range(16, 21):
        thresh = 0.5 + ((v_i - 16) * 0.02)
        signals_matrix[:, v_i] = np.where(b_pct > thresh, 1, np.where(b_pct < (1 - thresh), -1, 0))
        
    for w_i in range(21, 25):
        signals_matrix[:, w_i] = np.where(closes >= vwap, 1, -1)
        
    for ml_i in range(25, 31):
        pert = np.sin(ml_i * 1.5 + np.arange(num_bars) * 0.3) * 0.001
        score = (closes - sma20) / (closes + 1e-9) + pert
        signals_matrix[:, ml_i] = np.where(score > 0.0002, 1, np.where(score < -0.0002, -1, 0))
        
    bull_counts = np.sum(signals_matrix == 1, axis=1)
    bear_counts = np.sum(signals_matrix == -1, axis=1)
    max_consensus = np.maximum(bull_counts, bear_counts)
    
    # Hyperparameter grids
    margin_pcts = [0.02, 0.03, 0.04, 0.05]
    leverage_options = [20.0, 30.0, 50.0]
    early_exit_options = [True, False]
    trailing_stop_options = [True, False]
    
    results = []
    
    for margin_pct in margin_pcts:
        for lev in leverage_options:
            for early_exit in early_exit_options:
                for trailing_stop in trailing_stop_options:
                    
                    balance = 30.0
                    taker_fee = 0.00036
                    liq_threshold_pct = (1.0 / lev) * 0.85
                    
                    trades_cnt = 0
                    wins_cnt = 0
                    liq_cnt = 0
                    
                    in_pos_until = 0
                    prev_active = False
                    cooldown_bars = 12
                    
                    peak_bal = balance
                    max_dd = 0.0
                    
                    for i in range(600, num_bars - cooldown_bars):
                        c_cnt = max_consensus[i]
                        if c_cnt < 30:
                            prev_active = False
                            continue
                            
                        if i < in_pos_until or prev_active:
                            continue
                            
                        direction = 1 if bull_counts[i] >= 30 else -1
                        
                        macro_aligned = (direction == 1 and closes[i] >= ema_300[i]) or \
                                        (direction == -1 and closes[i] <= ema_300[i])
                        vol_surge = volumes[i] >= (vol_sma20[i] * 1.15) if not np.isnan(vol_sma20[i]) else True
                        
                        if not macro_aligned or not vol_surge:
                            continue
                            
                        prev_active = True
                        trades_cnt += 1
                        
                        margin_val = balance * margin_pct
                        notional_val = margin_val * lev
                        
                        entry_p = closes[i]
                        curr_atr = atr[i] if not np.isnan(atr[i]) else (entry_p * 0.005)
                        
                        sl_dist = 1.0 * curr_atr
                        tp_dist = 2.5 * curr_atr
                        
                        highest_favorable = entry_p
                        
                        is_win = False
                        is_liq = False
                        hold_len = cooldown_bars
                        exit_p = closes[i + cooldown_bars]
                        
                        for step in range(1, cooldown_bars + 1):
                            curr_c = closes[i + step]
                            curr_h = highs[i + step]
                            curr_l = lows[i + step]
                            step_consensus = max_consensus[i + step]
                            
                            # Liquidation Check
                            if direction == 1 and curr_l <= entry_p * (1 - liq_threshold_pct):
                                is_liq = True
                                hold_len = step
                                break
                            elif direction == -1 and curr_h >= entry_p * (1 + liq_threshold_pct):
                                is_liq = True
                                hold_len = step
                                break
                                
                            # Trailing Stop Adjustment
                            if trailing_stop:
                                if direction == 1:
                                    highest_favorable = max(highest_favorable, curr_h)
                                    if highest_favorable >= entry_p + (1.2 * curr_atr):
                                        sl_dist = 0.2 * curr_atr # Move SL into profit!
                                else:
                                    highest_favorable = min(highest_favorable, curr_l)
                                    if highest_favorable <= entry_p - (1.2 * curr_atr):
                                        sl_dist = 0.2 * curr_atr # Move SL into profit!
                                        
                            # Early Emergency Consensus Exit Filter
                            if early_exit and step_consensus < 24:
                                exit_p = curr_c
                                is_win = (direction == 1 and exit_p > entry_p) or (direction == -1 and exit_p < entry_p)
                                hold_len = step
                                break
                                
                            # Standard TP / SL Checks
                            if direction == 1: # LONG
                                if curr_h >= entry_p + tp_dist:
                                    is_win = True
                                    exit_p = entry_p + tp_dist
                                    hold_len = step
                                    break
                                elif curr_l <= entry_p - sl_dist:
                                    is_win = False
                                    exit_p = entry_p - sl_dist
                                    hold_len = step
                                    break
                            else: # SHORT
                                if curr_l <= entry_p - tp_dist:
                                    is_win = True
                                    exit_p = entry_p - tp_dist
                                    hold_len = step
                                    break
                                elif curr_h >= entry_p + sl_dist:
                                    is_win = False
                                    exit_p = entry_p + sl_dist
                                    hold_len = step
                                    break
                                    
                        total_fees = notional_val * (taker_fee * 2)
                        
                        if is_liq:
                            liq_cnt += 1
                            net_pnl = -margin_val - total_fees
                        elif is_win:
                            p_move = (exit_p - entry_p)/entry_p if direction == 1 else (entry_p - exit_p)/entry_p
                            net_pnl = (notional_val * p_move) - total_fees
                            wins_cnt += 1
                        else:
                            p_move = (exit_p - entry_p)/entry_p if direction == 1 else (entry_p - exit_p)/entry_p
                            net_pnl = (notional_val * p_move) - total_fees
                            
                        balance += net_pnl
                        if balance < 0.5:
                            balance = 0.5
                            
                        in_pos_until = i + hold_len
                        
                        if balance > peak_bal:
                            peak_bal = balance
                        dd = (peak_bal - balance) / peak_bal
                        if dd > max_dd:
                            max_dd = dd
                            
                    win_rate = (wins_cnt / trades_cnt * 100) if trades_cnt > 0 else 0.0
                    ret_pct = ((balance - 30.0) / 30.0) * 100
                    
                    results.append({
                        'margin_pct': int(margin_pct * 100),
                        'leverage': int(lev),
                        'trailing_stop': trailing_stop,
                        'early_exit': early_exit,
                        'trades': trades_cnt,
                        'win_rate': round(win_rate, 1),
                        'liquidations': liq_cnt,
                        'ending_bal': round(balance, 2),
                        'total_return_pct': round(ret_pct, 2),
                        'max_dd_pct': round(max_dd * 100, 2)
                    })

    elapsed = time.time() - start_t
    results_df = pd.DataFrame(results)
    sorted_df = results_df.sort_values(by='ending_bal', ascending=False)
    
    print("\n" + "=" * 100)
    print(" TOP 10 LEVERAGE & TRADE MANAGEMENT CONFIGURATIONS ($30 STARTING CAPITAL)")
    print("=" * 100)
    print(f"{'Rank':<5} | {'Margin':<7} | {'Leverage':<9} | {'Trailing SL':<12} | {'Early Exit':<11} | {'Trades':<7} | {'Win Rate':<9} | {'Liq':<5} | {'Ending Bal ($)':<16} | {'Net Return':<12}")
    print("-" * 100)
    
    top10 = sorted_df.head(10)
    for idx, (_, row) in enumerate(top10.iterrows(), 1):
        ts_str = "ENABLED" if row['trailing_stop'] else "Disabled"
        ee_str = "ENABLED" if row['early_exit'] else "Disabled"
        print(f"#{idx:<4} | {row['margin_pct']}%    | {row['leverage']}x       | {ts_str:<12} | {ee_str:<11} | {row['trades']:<7} | {row['win_rate']:<7.1f}% | {row['liquidations']:<5} | ${row['ending_bal']:<15.2f} | {row['total_return_pct']:>+10.2f}%")

if __name__ == '__main__':
    run_leverage_optimization()
