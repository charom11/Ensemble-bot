#!/usr/bin/env python3
"""
WEATHER-ENSEMBLE ADVANCED LOOP OPTIMIZER
========================================
Iterates over 243 Hyperparameter Combinations:
- Consensus Threshold: 27, 28, 29, 30 / 31 Models
- Macro Trend Filter: EMA 300, EMA 600, EMA 900
- Risk-to-Reward Ratio: 1:2.0, 1:2.5, 1:3.0
- Volume Surge Multiplier: 1.0x, 1.15x, 1.25x
- Cooldown Hold Duration: 12, 18, 24 bars
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

def run_loop_optimization():
    start_t = time.time()
    df = generate_365d_data()
    
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    volumes = df['volume'].values
    num_bars = len(closes)
    
    s_df = pd.DataFrame({'close': closes, 'high': highs, 'low': lows, 'volume': volumes})
    
    ema_300 = s_df['close'].ewm(span=300).mean().values
    ema_600 = s_df['close'].ewm(span=600).mean().values
    ema_900 = s_df['close'].ewm(span=900).mean().values
    
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
    
    thresholds = [27, 28, 29, 30]
    macro_ema_map = {'EMA_300': ema_300, 'EMA_600': ema_600, 'EMA_900': ema_900}
    rr_configs = [
        {'name': '1:2.0', 'sl_mult': 1.0, 'tp_mult': 2.0},
        {'name': '1:2.5', 'sl_mult': 1.0, 'tp_mult': 2.5},
        {'name': '1:3.0', 'sl_mult': 1.0, 'tp_mult': 3.0}
    ]
    vol_mults = [1.0, 1.15, 1.25]
    cooldowns = [12, 18, 24]
    
    results = []
    
    for thresh in thresholds:
        for ema_name, ema_array in macro_ema_map.items():
            for rr in rr_configs:
                for v_mult in vol_mults:
                    for cooldown_bars in cooldowns:
                        
                        balance = 100.0
                        risk_pct = 0.03 # 3% per trade
                        fee_rate = 0.00075 # 0.075% BNB fee
                        
                        peak_balance = balance
                        max_dd = 0.0
                        trades = 0
                        wins = 0
                        losses = 0
                        
                        in_pos_until = 0
                        prev_active = False
                        
                        for i in range(900, num_bars - cooldown_bars):
                            c_cnt = max_consensus[i]
                            if c_cnt < thresh:
                                prev_active = False
                                continue
                                
                            if i < in_pos_until or prev_active:
                                continue
                                
                            direction = 1 if bull_counts[i] >= thresh else -1
                            
                            macro_aligned = (direction == 1 and closes[i] >= ema_array[i]) or \
                                            (direction == -1 and closes[i] <= ema_array[i])
                            vol_surge = volumes[i] >= (vol_sma20[i] * v_mult) if not np.isnan(vol_sma20[i]) else True
                            
                            if not macro_aligned or not vol_surge:
                                continue
                                
                            prev_active = True
                            trades += 1
                            
                            entry_p = closes[i]
                            curr_atr = atr[i] if not np.isnan(atr[i]) else (entry_p * 0.005)
                            
                            sl_dist = rr['sl_mult'] * curr_atr
                            tp_dist = rr['tp_mult'] * curr_atr
                            
                            is_win = False
                            hold_len = cooldown_bars
                            
                            for step in range(1, cooldown_bars + 1):
                                curr_h = highs[i + step]
                                curr_l = lows[i + step]
                                
                                if direction == 1: # LONG
                                    if curr_h >= entry_p + tp_dist:
                                        is_win = True
                                        hold_len = step
                                        break
                                    elif curr_l <= entry_p - sl_dist:
                                        is_win = False
                                        hold_len = step
                                        break
                                else: # SHORT
                                    if curr_l <= entry_p - tp_dist:
                                        is_win = True
                                        hold_len = step
                                        break
                                    elif curr_h >= entry_p + sl_dist:
                                        is_win = False
                                        hold_len = step
                                        break
                                        
                            pos_size = balance * risk_pct
                            fee_cost = pos_size * (fee_rate * 2)
                            
                            if is_win:
                                raw_return = (tp_dist / entry_p)
                                net_pnl = (pos_size * (raw_return * 4.5)) - fee_cost
                                balance += net_pnl
                                wins += 1
                            else:
                                raw_return = -(sl_dist / entry_p)
                                net_pnl = (pos_size * (raw_return * 4.5)) - fee_cost
                                balance += net_pnl
                                losses += 1
                                
                            in_pos_until = i + hold_len
                            if balance > peak_balance:
                                peak_balance = balance
                            dd = (peak_balance - balance) / peak_balance
                            if dd > max_dd:
                                max_dd = dd
                                
                        win_rate = (wins / trades * 100) if trades > 0 else 0.0
                        total_ret = ((balance - 100.0) / 100.0) * 100
                        
                        sharpe_score = total_ret / (max_dd * 100 + 1e-5) if max_dd > 0 else total_ret
                        
                        results.append({
                            'threshold': thresh,
                            'macro_trend': ema_name,
                            'rr_ratio': rr['name'],
                            'vol_mult': v_mult,
                            'cooldown_bars': cooldown_bars,
                            'trades': trades,
                            'win_rate': round(win_rate, 1),
                            'ending_bal': round(balance, 2),
                            'total_return_pct': round(total_ret, 2),
                            'max_dd_pct': round(max_dd * 100, 2),
                            'sharpe_score': round(sharpe_score, 2)
                        })

    elapsed = time.time() - start_t
    results_df = pd.DataFrame(results)
    sorted_df = results_df.sort_values(by='sharpe_score', ascending=False)
    
    print("\n" + "=" * 95)
    print(" TOP 10 OPTIMIZED STRATEGY CONFIGURATIONS (RANKED BY SHARPE RATIO & RISK-ADJUSTED RETURNS)")
    print("=" * 95)
    print(f"{'Rank':<5} | {'Thresh':<6} | {'Macro Trend':<11} | {'RR Ratio':<8} | {'Vol Mult':<8} | {'Trades':<6} | {'Win Rate':<8} | {'Max DD':<7} | {'Total Return':<14} | {'Sharpe':<6}")
    print("-" * 95)
    
    top10 = sorted_df.head(10)
    for idx, (_, row) in enumerate(top10.iterrows(), 1):
        print(f"#{idx:<4} | {row['threshold']}/31   | {row['macro_trend']:<11} | {row['rr_ratio']:<8} | {row['vol_mult']:<8}x | {row['trades']:<6} | {row['win_rate']:<7.1f}% | -{row['max_dd_pct']:<5.2f}% | {row['total_return_pct']:>+12.2f}% | {row['sharpe_score']:<6.2f}")

if __name__ == '__main__':
    run_loop_optimization()
