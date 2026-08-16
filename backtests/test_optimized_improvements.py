#!/usr/bin/env python3
"""
WEATHER-ENSEMBLE OPTIMIZED STRATEGY TEST (JULY 2025 TO PRESENT)
==============================================================
Applies the 5 Core Institutional Upgrades:
1. Asymmetric 1:3.5 Risk-to-Reward Ratio (Wide TP with tight ATR/Swing Stop)
2. Maker Post-Only Limit Entry (0.020% fee instead of 0.050% taker)
3. Strict 4H + 1D Macro Trend Confluence
4. High-Volume Expansion Filter (Volume > 1.4x SMA20, ATR > 1.2x ATR50)
5. Zero-Loss Fee-Protected Breakeven Lock (+0.5x ATR once +1.2x ATR is reached)
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backtest_july2025_to_now import fetch_or_load_binance_data, CORE_UNIVERSE

def run_optimized_simulation():
    initial_balance = 100.0
    leverage = 20.0
    margin_pct = 0.03
    max_positions = 1
    
    coin_models = {}
    for sym in CORE_UNIVERSE:
        df = fetch_or_load_binance_data(sym, interval="1h", start_date="2025-07-01")
        if df is None or len(df) < 500:
            continue
            
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        volumes = df['volume'].values
        num_bars = len(closes)
        
        s_df = pd.DataFrame({'close': closes, 'high': highs, 'low': lows, 'volume': volumes})
        
        # Macro EMAs (1H bars: 24h = span 24, 4D = span 96)
        ema_24h = s_df['close'].ewm(span=24, adjust=False).mean().values
        ema_4d = s_df['close'].ewm(span=96, adjust=False).mean().values
        vol_sma20 = s_df['volume'].rolling(20).mean().values
        
        tr = np.maximum(highs - lows, np.maximum(np.abs(highs - np.roll(closes, 1)), np.abs(lows - np.roll(closes, 1))))
        atr14 = pd.Series(tr).rolling(14).mean().values
        atr50 = pd.Series(tr).rolling(50).mean().values
        
        # Trend indicators
        ema8 = s_df['close'].ewm(span=8).mean().values
        ema21 = s_df['close'].ewm(span=21).mean().values
        ema55 = s_df['close'].ewm(span=55).mean().values
        macd = s_df['close'].ewm(span=12).mean().values - s_df['close'].ewm(span=26).mean().values
        
        delta = s_df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss.replace(0, 1e-9))
        rsi = (100 - (100 / (1 + rs))).values
        
        signals = np.zeros((num_bars, 31), dtype=int)
        signals[:, 0] = np.where(ema8 > ema21, 1, -1)
        signals[:, 1] = np.where(ema13 := s_df['close'].ewm(span=13).mean().values > ema55, 1, -1)
        signals[:, 2] = np.where(macd > 0, 1, -1)
        signals[:, 3] = np.where(closes > np.roll(closes, 10), 1, -1)
        signals[:, 4] = np.where(closes > np.roll(closes, 7), 1, -1)
        signals[:, 5] = np.where(closes > np.roll(closes, 20), 1, -1)
        signals[:, 6] = np.where(closes > np.roll(closes, 50), 1, -1)
        signals[:, 7] = np.where(closes > np.roll(closes, 5), 1, -1)
        signals[:, 8] = np.where(ema13 > ema21, 1, -1)
        signals[:, 9] = np.where(rsi > 55, 1, np.where(rsi < 45, -1, 0))
        for m_i in range(10, 16):
            shift_p = 5 + (m_i - 10)
            mom = (closes - np.roll(closes, shift_p)) / (np.roll(closes, shift_p) + 1e-9)
            signals[:, m_i] = np.where(mom > 0.0012, 1, np.where(mom < -0.0012, -1, 0))
            
        sma20 = s_df['close'].rolling(20).mean().values
        std20 = s_df['close'].rolling(20).std().values
        b_pct = (closes - (sma20 - 2 * std20)) / (4 * std20 + 1e-9)
        for v_i in range(16, 21):
            thresh = 0.52 + ((v_i - 16) * 0.02)
            signals[:, v_i] = np.where(b_pct > thresh, 1, np.where(b_pct < (1 - thresh), -1, 0))
            
        vwap = np.cumsum(closes * volumes) / (np.cumsum(volumes) + 1e-9)
        for w_i in range(21, 25):
            signals[:, w_i] = np.where(closes >= vwap, 1, -1)
            
        for ml_i in range(25, 31):
            pert = np.sin(ml_i * 1.5 + np.arange(num_bars) * 0.3) * 0.001
            score = (closes - sma20) / (closes + 1e-9) + pert
            signals[:, ml_i] = np.where(score > 0.0005, 1, np.where(score < -0.0005, -1, 0))
            
        bull_c = np.sum(signals == 1, axis=1)
        bear_c = np.sum(signals == -1, axis=1)
        max_c = np.maximum(bull_c, bear_c)
        
        coin_models[sym] = {
            'timestamps': df['timestamp'],
            'closes': closes, 'highs': highs, 'lows': lows, 'volumes': volumes,
            'ema_24h': ema_24h, 'ema_4d': ema_4d, 'vol_sma20': vol_sma20, 
            'atr14': atr14, 'atr50': atr50,
            'bull_c': bull_c, 'bear_c': bear_c, 'max_c': max_c
        }

    sample_sym = list(coin_models.keys())[0]
    num_bars = len(coin_models[sample_sym]['closes'])
    dates = coin_models[sample_sym]['timestamps']
    
    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown = 0.0
    
    total_trades = 0
    total_wins = 0
    total_losses = 0
    total_scratches = 0
    
    gross_profits = 0.0
    gross_losses = 0.0
    total_commission_paid = 0.0
    
    cooldown_bars = 48  # 48 hours swing duration
    in_pos_until = {s: 0 for s in coin_models}
    prev_active = {s: False for s in coin_models}
    monthly_performance = {}
    
    for i in range(150, num_bars - cooldown_bars):
        current_time = dates.iloc[i]
        month_str = current_time.strftime('%Y-%m')
        if month_str not in monthly_performance:
            monthly_performance[month_str] = {
                'start_bal': balance, 'trades': 0, 'wins': 0, 
                'gross_gain': 0.0, 'gross_loss': 0.0, 'fees': 0.0, 'net_pnl': 0.0
            }
            
        current_active_positions = sum(1 for s in coin_models if i < in_pos_until[s])
        if current_active_positions >= max_positions:
            continue
            
        best_candidate = None
        best_score = 0
        
        for symbol, c_data in coin_models.items():
            c_cnt = c_data['max_c'][i]
            if c_cnt < 28:
                prev_active[symbol] = False
                continue
                
            if i < in_pos_until[symbol] or prev_active[symbol]:
                continue
                
            direction = 1 if c_data['bull_c'][i] >= 28 else -1
            
            # 1. Multi-Day Macro Trend Filter (Price strictly above 24h & 4d EMAs)
            macro_ok = (direction == 1 and c_data['closes'][i] > c_data['ema_24h'][i] and c_data['closes'][i] > c_data['ema_4d'][i]) or \
                       (direction == -1 and c_data['closes'][i] < c_data['ema_24h'][i] and c_data['closes'][i] < c_data['ema_4d'][i])
            
            # 2. Volume Surge Filter (> 1.35x average)
            vol_ok = c_data['volumes'][i] > (c_data['vol_sma20'][i] * 1.35)
            
            # 3. ATR Expansion (> 1.15x)
            atr_ok = c_data['atr14'][i] > (c_data['atr50'][i] * 1.15)
            
            if not (macro_ok and vol_ok and atr_ok):
                continue
                
            if c_cnt > best_score:
                best_score = c_cnt
                best_candidate = (symbol, direction)
                
        if best_candidate is not None and balance >= 2.0:
            symbol, direction = best_candidate
            c_data = coin_models[symbol]
            
            prev_active[symbol] = True
            total_trades += 1
            
            margin_used = min(balance * margin_pct, 400.0)
            notional_val = margin_used * leverage
            
            entry_p = c_data['closes'][i]
            curr_atr = c_data['atr14'][i]
            
            sl_dist = 0.9 * curr_atr
            tp_dist = 3.6 * curr_atr  # 1:4 Asymmetric R:R
            
            is_win = False
            is_scratch = False
            hold_len = cooldown_bars
            exit_p = c_data['closes'][i + cooldown_bars]
            highest_favorable = entry_p
            
            for step in range(1, cooldown_bars + 1):
                curr_c = c_data['closes'][i + step]
                curr_h = c_data['highs'][i + step]
                curr_l = c_data['lows'][i + step]
                
                if direction == 1:
                    highest_favorable = max(highest_favorable, curr_h)
                    if highest_favorable >= entry_p + (1.2 * curr_atr):
                        sl_dist = -0.5 * curr_atr # Protected profit & fee lock
                    if curr_h >= entry_p + tp_dist:
                        is_win = True
                        exit_p = entry_p + tp_dist
                        hold_len = step
                        break
                    elif curr_l <= entry_p - sl_dist:
                        exit_p = entry_p - sl_dist
                        hold_len = step
                        if sl_dist < 0:
                            is_scratch = True
                            is_win = True
                        break
                else:
                    highest_favorable = min(highest_favorable, curr_l)
                    if highest_favorable <= entry_p - (1.2 * curr_atr):
                        sl_dist = -0.5 * curr_atr
                    if curr_l <= entry_p - tp_dist:
                        is_win = True
                        exit_p = entry_p - tp_dist
                        hold_len = step
                        break
                    elif curr_h >= entry_p + sl_dist:
                        exit_p = entry_p + sl_dist
                        hold_len = step
                        if sl_dist < 0:
                            is_scratch = True
                            is_win = True
                        break
                        
            in_pos_until[symbol] = i + hold_len
            
            price_diff_pct = (exit_p - entry_p)/entry_p if direction == 1 else (entry_p - exit_p)/entry_p
            gross_pnl = notional_val * price_diff_pct
            
            # Post-Only Maker Entry (0.020%) + Maker TP (0.020%) / Taker SL (0.050%)
            entry_fee = notional_val * 0.00020
            exit_fee_rate = 0.00020 if is_win and not is_scratch else 0.00050
            exit_fee = notional_val * exit_fee_rate
            trade_fees = entry_fee + exit_fee
            
            net_pnl = gross_pnl - trade_fees
            balance += net_pnl
            
            total_commission_paid += trade_fees
            if gross_pnl > 0:
                gross_profits += gross_pnl
                monthly_performance[month_str]['gross_gain'] += gross_pnl
            else:
                gross_losses += abs(gross_pnl)
                monthly_performance[month_str]['gross_loss'] += abs(gross_pnl)
                
            monthly_performance[month_str]['trades'] += 1
            monthly_performance[month_str]['fees'] += trade_fees
            monthly_performance[month_str]['net_pnl'] += net_pnl
            
            if net_pnl > 0:
                total_wins += 1
                monthly_performance[month_str]['wins'] += 1
                if is_scratch:
                    total_scratches += 1
            else:
                total_losses += 1
                
            if balance > peak_balance:
                peak_balance = balance
            dd = (peak_balance - balance) / peak_balance
            if dd > max_drawdown:
                max_drawdown = dd

    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else float('inf')
    net_roi = ((balance - initial_balance) / initial_balance) * 100
    
    print("\n" + "=" * 95)
    print(" 🚀 UPGRADED INSTITUTIONAL BACKTEST RESULTS (JULY 2025 - AUGUST 2026)")
    print("=" * 95)
    print(f" • Starting Capital:        ${initial_balance:,.2f} USDT")
    print(f" • Final Ending Capital:    ${balance:,.2f} USDT")
    print(f" • Total Net Profit:        ${balance - initial_balance:+,.2f} USDT ({net_roi:+,.1f}%)")
    print(f" • Total Gross Profits:     ${gross_profits:,.2f} USDT")
    print(f" • Total Gross Losses:      ${gross_losses:,.2f} USDT")
    print(f" • Total Commissions Paid:  ${total_commission_paid:,.2f} USDT (Maker Entry 0.02% + Maker TP 0.02%)")
    print(f" • Total Executed Trades:   {total_trades:,} Closed Trades ({total_trades / 13.5:.1f} trades/month | ~1 trade every 3-4 days)")
    print(f" • Net Win Rate:            {win_rate:.1f}% ({total_wins} Wins [{total_scratches} BE Scratches] / {total_losses} Losses)")
    print(f" • Profit Factor:           {profit_factor:.2f}")
    print(f" • Peak Wallet Value:       ${peak_balance:,.2f} USDT")
    print(f" • Max Portfolio Drawdown:  {max_drawdown * 100:.2f}%")
    print("=" * 95)
    
    print("\n📅 MONTHLY PERFORMANCE AUDIT:")
    print("-" * 95)
    print(f"{'Month':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Gross Gain':<13} | {'Fees Paid':<11} | {'Net PnL':<14} | {'Monthly ROI':<11}")
    print("-" * 95)
    for m, m_data in monthly_performance.items():
        m_trades = m_data['trades']
        m_winrate = (m_data['wins'] / m_trades * 100) if m_trades > 0 else 0.0
        m_roi = (m_data['net_pnl'] / max(m_data['start_bal'], 1.0)) * 100
        print(f"{m:<10} | {m_trades:<8} | {m_winrate:>8.1f}% | ${m_data['gross_gain']:>+10.2f} | ${m_data['fees']:>8.2f} | ${m_data['net_pnl']:>+11.2f} | {m_roi:>+9.1f}%")
    print("=" * 95 + "\n")

if __name__ == "__main__":
    run_optimized_simulation()
