#!/usr/bin/env python3
"""
WEATHER-ENSEMBLE HISTORICAL BACKTESTING ENGINE
==============================================
Runs the 31-model weather consensus strategy on real historical CSV data downloaded
from Binance Futures, applying macro trend, volume surge, and ATR expansion filters,
coupled with dynamic ATR-based profit taking and break-even taker fee locks.
"""

import os
import sys
import argparse
import time
import numpy as np
import pandas as pd
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_historical_backtest(csv_path, threshold=30, risk_pct=0.03, leverage=20.0, fee_rate=0.00036):
    if not os.path.exists(csv_path):
        print(f"❌ Error: File not found at {csv_path}")
        return

    print("=" * 80)
    print(f" WEATHER-ENSEMBLE HISTORICAL BACKTESTER")
    print(f" Target Data:        {csv_path}")
    print(f" Model Threshold:    {threshold} / 31 Models")
    print(f" Wallet Sizing:      {risk_pct * 100}% Risk per Trade")
    print(f" Futures Leverage:   {leverage}x")
    print(f" Taker Fee Rate:     {fee_rate * 100}% (Roundtrip: {fee_rate * 2 * 100:.3f}%)")
    print("=" * 80)

    # 1. Load data
    df = pd.read_csv(csv_path)
    if 'timestamp' in df.columns:
        df.set_index('timestamp', inplace=True)
    
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    opens = df['open'].values
    volumes = df['volume'].values
    num_bars = len(closes)

    # 2. Indicator calculations
    print("🔄 Computing indicator arrays for all 31 models...")
    s_df = pd.DataFrame({'close': closes, 'high': highs, 'low': lows, 'volume': volumes})
    
    # Macro Filters
    ema_1h = s_df['close'].ewm(span=300).mean().values   # 25h trend
    ema_4h = s_df['close'].ewm(span=1200).mean().values  # 100h trend
    vol_sma20 = s_df['volume'].rolling(20).mean().values
    
    # ATR Volatility Channels
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - np.roll(closes, 1)), np.abs(lows - np.roll(closes, 1))))
    atr14 = pd.Series(tr).rolling(14).mean().values
    atr50 = pd.Series(tr).rolling(50).mean().values

    # Model parameters
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

    # Signal Matrix (31 Models)
    signals = np.zeros((num_bars, 31), dtype=int)
    
    # Trend (9)
    signals[:, 0] = np.where(ema8 > ema21, 1, -1)
    signals[:, 1] = np.where(ema13 > ema55, 1, -1)
    signals[:, 2] = np.where(macd > 0, 1, -1)
    signals[:, 3] = np.where(closes > np.roll(closes, 10), 1, -1)
    signals[:, 4] = np.where(closes > np.roll(closes, 7), 1, -1)
    signals[:, 5] = np.where(closes > np.roll(closes, 20), 1, -1)
    signals[:, 6] = np.where(closes > np.roll(closes, 50), 1, -1)
    signals[:, 7] = np.where(closes > np.roll(closes, 5), 1, -1)
    signals[:, 8] = np.where(ema13 > ema21, 1, -1)
    
    # Momentum (7)
    signals[:, 9] = np.where(rsi > 54, 1, np.where(rsi < 46, -1, 0))
    for m_i in range(10, 16):
        shift_p = 5 + (m_i - 10)
        mom = (closes - np.roll(closes, shift_p)) / (np.roll(closes, shift_p) + 1e-9)
        signals[:, m_i] = np.where(mom > 0.0008, 1, np.where(mom < -0.0008, -1, 0))
        
    # Volatility (5)
    for v_i in range(16, 21):
        thresh = 0.5 + ((v_i - 16) * 0.02)
        signals[:, v_i] = np.where(b_pct > thresh, 1, np.where(b_pct < (1 - thresh), -1, 0))
        
    # VWAP (4)
    for w_i in range(21, 25):
        signals[:, w_i] = np.where(closes >= vwap, 1, -1)
        
    # ML & Statistical Perturbations (6)
    for ml_i in range(25, 31):
        pert = np.sin(ml_i * 1.5 + np.arange(num_bars) * 0.3) * 0.001
        score = (closes - sma20) / (closes + 1e-9) + pert
        signals[:, ml_i] = np.where(score > 0.0002, 1, np.where(score < -0.0002, -1, 0))

    # Consensus Counts
    bull_counts = np.sum(signals == 1, axis=1)
    bear_counts = np.sum(signals == -1, axis=1)
    max_consensus = np.maximum(bull_counts, bear_counts)

    # 3. Backtesting execution loop
    print("🚀 Backtesting strategy execution...")
    initial_balance = 10000.0  # standard base
    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown = 0.0
    
    trades_cnt = 0
    wins_cnt = 0
    losses_cnt = 0
    filtered_bars = 0
    cooldown_bars = 24  # Max trade hold duration (2 hours)
    
    in_pos_until = 0
    prev_active = False
    
    trade_log = []
    monthly_performance = {}

    for i in range(1200, num_bars - cooldown_bars):
        c_cnt = max_consensus[i]
        
        # 1. Consensus Threshold check
        if c_cnt < threshold:
            prev_active = False
            filtered_bars += 1
            continue
            
        # Cooldown guard (avoid double entry)
        if i < in_pos_until or prev_active:
            continue
            
        direction = 1 if bull_counts[i] >= threshold else -1
        
        # 2. Macro Trend Alignment Confluence Filter
        macro_aligned = (direction == 1 and closes[i] >= ema_1h[i] and closes[i] >= ema_4h[i]) or \
                        (direction == -1 and closes[i] <= ema_1h[i] and closes[i] <= ema_4h[i])
                        
        # 3. Volume Surge Confirmation Filter
        vol_surge = volumes[i] >= (vol_sma20[i] * 1.15) if not np.isnan(vol_sma20[i]) else True
        
        # 4. ATR Volatility Expansion Filter
        atr_expanded = (atr14[i] >= atr50[i] * 1.05) if not np.isnan(atr50[i]) else True
        
        if not macro_aligned or not vol_surge or not atr_expanded:
            filtered_bars += 1
            continue
            
        # Trade confirmation
        prev_active = True
        trades_cnt += 1
        
        entry_p = closes[i]
        entry_atr = atr14[i] if not np.isnan(atr14[i]) else (entry_p * 0.005)
        
        # Dual-Leg Scaling Targets: SL 1.0x ATR | TP1 (50%) 1.5x ATR | Trailing Runner (50%) up to 3.5x ATR
        sl_dist = 1.0 * entry_atr
        tp1_dist = 1.5 * entry_atr
        tp2_dist = 3.5 * entry_atr
        
        tp1_hit = False
        leg1_exit_p = entry_p - sl_dist if direction == 1 else entry_p + sl_dist
        leg2_exit_p = entry_p - sl_dist if direction == 1 else entry_p + sl_dist
        
        highest_favorable = entry_p
        lowest_favorable = entry_p
        hold_len = cooldown_bars
        
        for step in range(1, cooldown_bars + 1):
            curr_c = closes[i + step]
            curr_h = highs[i + step]
            curr_l = lows[i + step]
            
            if direction == 1:  # LONG
                highest_favorable = max(highest_favorable, curr_h)
                
                # Check TP1 (50% scale out)
                if not tp1_hit and curr_h >= entry_p + tp1_dist:
                    tp1_hit = True
                    leg1_exit_p = entry_p + tp1_dist
                    sl_dist = -0.3 * entry_atr  # Move Stop to Break-Even + 0.3x ATR
                
                # Check SL or TP2
                if curr_l <= entry_p - sl_dist:
                    if not tp1_hit:
                        leg1_exit_p = entry_p - sl_dist
                    leg2_exit_p = entry_p - sl_dist
                    hold_len = step
                    break
                elif tp1_hit and curr_h >= entry_p + tp2_dist:
                    leg2_exit_p = entry_p + tp2_dist
                    hold_len = step
                    break
            else:  # SHORT
                lowest_favorable = min(lowest_favorable, curr_l)
                
                # Check TP1 (50% scale out)
                if not tp1_hit and lowest_favorable <= entry_p - tp1_dist:
                    tp1_hit = True
                    leg1_exit_p = entry_p - tp1_dist
                    sl_dist = -0.3 * entry_atr  # Move Stop to Break-Even + 0.3x ATR
                    
                # Check SL or TP2
                if curr_h >= entry_p + sl_dist:
                    if not tp1_hit:
                        leg1_exit_p = entry_p + sl_dist
                    leg2_exit_p = entry_p + sl_dist
                    hold_len = step
                    break
                elif tp1_hit and curr_l <= entry_p - tp2_dist:
                    leg2_exit_p = entry_p - tp2_dist
                    hold_len = step
                    break

        if not tp1_hit:
            exit_p = leg1_exit_p
        else:
            exit_p = (leg1_exit_p + leg2_exit_p) / 2.0

        # Calculate PnL and Compound Balance
        margin_used = balance * risk_pct
        notional_val = margin_used * leverage
        
        # Binance roundtrip maker/taker fee
        total_fees = notional_val * (fee_rate * 2)
        
        p_move1 = (leg1_exit_p - entry_p)/entry_p if direction == 1 else (entry_p - leg1_exit_p)/entry_p
        p_move2 = (leg2_exit_p - entry_p)/entry_p if direction == 1 else (entry_p - leg2_exit_p)/entry_p
        net_pnl = (notional_val * 0.5 * p_move1) + (notional_val * 0.5 * p_move2) - total_fees
        
        prev_bal = balance
        balance += net_pnl
        if balance < 0.5:
            balance = 0.5
            
        in_pos_until = i + hold_len
        
        # Max drawdown calculations
        if balance > peak_balance:
            peak_balance = balance
        dd = (peak_balance - balance) / peak_balance
        if dd > max_drawdown:
            max_drawdown = dd

        # Trade Logger
        is_actual_win = net_pnl > 0
        if is_actual_win:
            wins_cnt += 1
        else:
            losses_cnt += 1
            
        trade_time = df.index[i]
        trade_log.append({
            'time': trade_time,
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_p': entry_p,
            'exit_p': exit_p,
            'net_pnl': net_pnl,
            'be_active': break_even_triggered,
            'result': 'WIN' if is_actual_win else 'LOSS'
        })
        
        # Monthly Performance tracking
        month_key = pd.to_datetime(trade_time).strftime("%Y-%m")
        if month_key not in monthly_performance:
            monthly_performance[month_key] = {'trades': 0, 'wins': 0, 'pnl': 0.0, 'end_bal': balance}
        monthly_performance[month_key]['trades'] += 1
        if is_actual_win:
            monthly_performance[month_key]['wins'] += 1
        monthly_performance[month_key]['pnl'] += net_pnl
        monthly_performance[month_key]['end_bal'] = balance

    # Summary
    total_bars = num_bars - 1224
    filter_rate = (filtered_bars / total_bars * 100) if total_bars > 0 else 0.0
    win_rate = (wins_cnt / trades_cnt * 100) if trades_cnt > 0 else 0.0
    total_return = ((balance - initial_balance) / initial_balance) * 100
    gross_profit = sum(t['net_pnl'] for t in trade_log if t['net_pnl'] > 0)
    gross_loss = abs(sum(t['net_pnl'] for t in trade_log if t['net_pnl'] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    print("\n" + "=" * 80)
    print(" 🎉 BACKTEST COMPLETED - RESULTS SUMMARY")
    print("=" * 80)
    print(f" Total Trades Executed:       {trades_cnt:,}")
    print(f" Winning Trades (Net > 0):    {wins_cnt:,} ({win_rate:.2f}% Win Rate)")
    print(f" Losing Trades (Net <= 0):    {losses_cnt:,}")
    print(f" Filtered Signals (No Trade):  {filtered_bars:,} ({filter_rate:.2f}%)")
    print(f" Profit Factor:               {profit_factor:.2f}")
    print(f" Gross Profit / Gross Loss:   ${gross_profit:,.2f} / ${gross_loss:,.2f}")
    print(f"------------------------------------------------")
    print(f" Starting Wallet Equity:      ${initial_balance:,.2f}")
    print(f" Ending Wallet Equity:        ${balance:,.2f}")
    print(f" Compounded Net Return:       {total_return:+,.2f}%")
    print(f" Peak Wallet Equity:          ${peak_balance:,.2f}")
    print(f" Max Historical Drawdown:     -{max_drawdown * 100:.2f}%")
    print("=" * 80 + "\n")

    if monthly_performance:
        print("--- MONTHLY HISTORICAL SUMMARY ---")
        print(f"{'Month':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Monthly PnL':<15} | {'Ending Balance':<15}")
        print("-" * 65)
        for m, data in sorted(monthly_performance.items()):
            m_winrate = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0.0
            print(f"{m:<10} | {data['trades']:<8} | {m_winrate:<9.1f}% | {data['pnl']:<+14.2f}$ | ${data['end_bal']:<14.2f}")
        print("-" * 65 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weather-Ensemble Historical Backtester")
    parser.add_argument("--csv", type=str, required=True, help="Path to historical CSV file (e.g. BTCUSDT_5m_90d.csv)")
    parser.add_argument("--threshold", type=int, default=30, help="Consensus threshold (20-31)")
    parser.add_argument("--risk", type=float, default=0.03, help="Fraction of wallet equity to risk per trade (e.g. 0.03 for 3%)")
    parser.add_argument("--leverage", type=float, default=20.0, help="Futures leverage factor (e.g. 20.0)")
    parser.add_argument("--fee", type=float, default=0.00036, help="Taker fee fraction (e.g. 0.00036)")
    args = parser.parse_args()
    
    run_historical_backtest(
        csv_path=args.csv, 
        threshold=args.threshold, 
        risk_pct=args.risk, 
        leverage=args.leverage, 
        fee_rate=args.fee
    )
