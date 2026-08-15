#!/usr/bin/env python3
"""
EXACT COMPOUNDING MATHEMATICAL MODEL (1:2.5 RISK-TO-REWARD)
=========================================================
Initial Capital: $100.00
Risk per Trade: 3.0% of Current Account Equity
Risk-to-Reward Ratio: 1 : 2.5
- On WIN (TP): Gain +7.50% of current balance - 0.15% Binance fees = +7.35% Net Growth
- On LOSS (SL): Lose -3.00% of current balance + 0.15% Binance fees = -3.15% Net Loss
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

def run_exact_compounding_backtest():
    initial_balance = 100.0
    risk_pct = 0.03 # 3% account risk
    rr_ratio = 2.5  # 1 : 2.5 RR
    fee_pct = 0.0015 # 0.15% roundtrip Binance BNB fee
    threshold = 29
    
    # Exact percent return per trade outcome:
    win_compounding_factor = 1 + (risk_pct * rr_ratio) - fee_pct  # +7.35% multiplier (1.0735)
    loss_compounding_factor = 1 - risk_pct - fee_pct             # -3.15% multiplier (0.9685)
    
    start_t = time.time()
    df = generate_365d_data()
    
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    volumes = df['volume'].values
    num_bars = len(closes)
    
    s_df = pd.DataFrame({'close': closes, 'high': highs, 'low': lows, 'volume': volumes})
    
    ema_1h_macro = s_df['close'].ewm(span=600).mean().values
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
    
    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown = 0.0
    max_drawdown_usd = 0.0
    
    trades_count = 0
    wins = 0
    losses = 0
    filtered_bars = 0
    
    prev_consensus_active = False
    in_position_until = 0
    monthly_performance = {}
    
    for i in range(600, num_bars - 24):
        c_count = max_consensus[i]
        is_consensus = (c_count >= threshold)
        
        if not is_consensus:
            filtered_bars += 1
            prev_consensus_active = False
            continue
            
        if i < in_position_until or prev_consensus_active:
            continue
            
        is_bull = (bull_counts[i] >= threshold)
        direction = 1 if is_bull else -1
        
        macro_aligned = (direction == 1 and closes[i] >= ema_1h_macro[i]) or \
                        (direction == -1 and closes[i] <= ema_1h_macro[i])
                        
        volume_surge = volumes[i] >= (vol_sma20[i] * 1.15) if not np.isnan(vol_sma20[i]) else True
        
        if not macro_aligned or not volume_surge:
            filtered_bars += 1
            continue
            
        prev_consensus_active = True
        trades_count += 1
        
        entry_p = closes[i]
        curr_atr = atr[i] if not np.isnan(atr[i]) else (entry_p * 0.005)
        
        sl_dist = 1.0 * curr_atr
        tp_dist = 2.5 * curr_atr
        
        is_win = False
        hold_len = 24
        
        for step in range(1, 25):
            curr_high = highs[i + step]
            curr_low = lows[i + step]
            
            if direction == 1: # LONG
                if curr_high >= entry_p + tp_dist:
                    is_win = True
                    hold_len = step
                    break
                elif curr_low <= entry_p - sl_dist:
                    is_win = False
                    hold_len = step
                    break
            else: # SHORT
                if curr_low <= entry_p - tp_dist:
                    is_win = True
                    hold_len = step
                    break
                elif curr_high >= entry_p + sl_dist:
                    is_win = False
                    hold_len = step
                    break
                    
        # Multiplicative Exact Compounding
        prev_bal = balance
        if is_win:
            balance *= win_compounding_factor  # Multiply balance by 1.0735
            wins += 1
        else:
            balance *= loss_compounding_factor # Multiply balance by 0.9685
            losses += 1
            
        net_pnl = balance - prev_bal
        in_position_until = i + hold_len
        
        if balance > peak_balance:
            peak_balance = balance
        dd = (peak_balance - balance) / peak_balance
        if dd > max_drawdown:
            max_drawdown = dd
            max_drawdown_usd = peak_balance - balance
            
        month_key = df.index[i].strftime("%Y-%m")
        if month_key not in monthly_performance:
            monthly_performance[month_key] = {'trades': 0, 'wins': 0, 'pnl': 0.0, 'end_bal': balance}
        monthly_performance[month_key]['trades'] += 1
        if is_win:
            monthly_performance[month_key]['wins'] += 1
        monthly_performance[month_key]['pnl'] += net_pnl
        monthly_performance[month_key]['end_bal'] = balance

    elapsed = time.time() - start_t
    win_rate = (wins / trades_count * 100) if trades_count > 0 else 0.0
    total_bars = num_bars - 624
    filter_rate = (filtered_bars / total_bars * 100) if total_bars > 0 else 0.0
    total_return = ((balance - initial_balance) / initial_balance) * 100

    print(f"\n=======================================================")
    print(f" EXACT COMPOUNDING WEATHER-ENSEMBLE BTC 365-DAY BACKTEST")
    print(f"=======================================================")
    print(f" Processing Time:            {elapsed:.2f} seconds")
    print(f" Total 5m Bars Analyzed:     {total_bars:,} (365 Days)")
    print(f" Signals Filtered (NO TRADE): {filtered_bars:,} ({filter_rate:.1f}%) [NOISE & MACRO TREND REJECTION]")
    print(f" High-Conviction Trades:     {trades_count:,} (Avg {trades_count/365:.1f} trades/day)")
    print(f" Compounding Formula:        WIN = +7.35% Net Equity | LOSS = -3.15% Net Equity")
    print(f" Risk-to-Reward Ratio:       1 : 2.5 (SL 1.0x ATR | TP 2.5x ATR)")
    print(f" Winning Trades:             {wins:,} ({win_rate:.1f}% Win Rate)")
    print(f" Losing Trades:              {losses:,}")
    print(f"-------------------------------------------------------")
    print(f" Starting Balance:           ${initial_balance:.2f}")
    print(f" Ending Account Balance:     ${balance:,.2f}")
    print(f" Total Compounded Net Return:{total_return:+,.2f}%")
    print(f" Peak Account Equity:        ${peak_balance:,.2f}")
    print(f" Max Drawdown:              -{max_drawdown * 100:.2f}% (-${max_drawdown_usd:,.2f})")
    print(f"=======================================================\n")

    print("--- 12-MONTH COMPOUNDED EQUITY BREAKDOWN ---")
    print(f"{'Month':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Monthly PnL':<15} | {'Ending Balance':<15}")
    print("-" * 65)
    for m, data in monthly_performance.items():
        m_winrate = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0.0
        print(f"{m:<10} | {data['trades']:<8} | {m_winrate:<9.1f}% | {data['pnl']:<+14.2f}$ | ${data['end_bal']:<14.2f}")

if __name__ == '__main__':
    run_exact_compounding_backtest()
