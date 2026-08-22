#!/usr/bin/env python3
"""
===========================================================================
⚡ WEATHER-ENSEMBLE V2 UPGRADED ENGINE: FULL 1-YEAR HEAD-TO-HEAD BACKTEST
===========================================================================
Compares BASELINE (current live strategy) vs V2 UPGRADED (all 5 improvements):

  Upgrade 1: 1H Market Structure Shift (MSS) — Faster Reversal Detection
  Upgrade 2: ADX(14) Chop Filter — Anti-Whipsaw Gate (ADX < 20 = Pause)
  Upgrade 3: Directional Exposure Cap — Max 3 Same-Direction Positions
  Upgrade 4: 3-Stage Scale-Out — 33% TP1 / 33% TP2 / 34% TP3 Trailing Runner
  Upgrade 5: Daily PnL Summary Report — Auto-Generated Performance Ledger

Execution: Option B framework with full VIP0+BNB fee friction schedule.
===========================================================================
"""

import sys
import os
import argparse
import math
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from collections import defaultdict

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from weather_ensemble_bot import (
    WeatherEnsembleBot,
    check_fibonacci_setup,
    detect_fractal_swings_series,
    OPTIMIZED_SYMBOLS
)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historical_data_cache")

SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'SUIUSDT', 'NEARUSDT',
    'AVAXUSDT', 'LINKUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT'
]

FEE_TIERS = {
    'vip0_bnb': {
        'maker': 0.00018,    # 0.018% Maker Limit Order
        'taker': 0.00045,    # 0.045% Taker Stop/Market
        'slippage': 0.00015, # 0.015% Slippage on market orders
        'funding_8h': 0.00010# 0.010% per 8 hours holding cost
    },
    'vip0_standard': {
        'maker': 0.00020,
        'taker': 0.00050,
        'slippage': 0.00020,
        'funding_8h': 0.00010
    }
}


# ==========================================================================
# Upgrade 2 Helper: ADX(14) Calculation (Pure NumPy — No Look-Ahead)
# ==========================================================================
def calc_adx(highs, lows, closes, period=14):
    """
    Calculates ADX (Average Directional Index) from arrays.
    Returns the latest ADX value. ADX < 20 = chop zone / no trend.
    """
    n = len(closes)
    if n < period * 2 + 1:
        return 25.0  # Default to "trending" if not enough data

    # True Range
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))

    # +DM / -DM
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder's Smoothing (EMA-like with alpha = 1/period)
    def wilder_smooth(arr, p):
        result = np.zeros(len(arr))
        result[p] = np.sum(arr[1:p + 1])
        for i in range(p + 1, len(arr)):
            result[i] = result[i - 1] - (result[i - 1] / p) + arr[i]
        return result

    atr_smoothed = wilder_smooth(tr, period)
    plus_dm_smoothed = wilder_smooth(plus_dm, period)
    minus_dm_smoothed = wilder_smooth(minus_dm, period)

    # +DI / -DI
    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    dx = np.zeros(n)
    for i in range(period, n):
        if atr_smoothed[i] > 0:
            plus_di[i] = 100.0 * plus_dm_smoothed[i] / atr_smoothed[i]
            minus_di[i] = 100.0 * minus_dm_smoothed[i] / atr_smoothed[i]
        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum

    # ADX = Wilder-smoothed DX
    adx = np.zeros(n)
    start_idx = period * 2
    if start_idx < n:
        adx[start_idx] = np.mean(dx[period:start_idx + 1])
        for i in range(start_idx + 1, n):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return float(adx[-1]) if n > 0 else 25.0


# ==========================================================================
# Upgrade 1 Helper: 1H Market Structure Shift (MSS) Detection
# ==========================================================================
def detect_1h_mss(h1_highs, h1_lows, h1_closes, window=3):
    """
    Detects 1H Market Structure Shift:
    - Bearish MSS: Price breaks below last confirmed 1H swing low
    - Bullish MSS: Price breaks above last confirmed 1H swing high
    Returns: ('BULLISH', 'BEARISH', or 'NEUTRAL')
    """
    if len(h1_closes) < window * 2 + 5:
        return 'NEUTRAL'

    sh_list, sl_list = detect_fractal_swings_series(h1_highs, h1_lows, window=window)

    if not sh_list or not sl_list:
        return 'NEUTRAL'

    last_sh_price = sh_list[-1][1]
    last_sl_price = sl_list[-1][1]
    curr_close = h1_closes[-1]
    curr_low = h1_lows[-1]
    curr_high = h1_highs[-1]

    # Bearish MSS: Current bar broke below the last swing low
    if curr_low < last_sl_price and curr_close < last_sl_price:
        return 'BEARISH'

    # Bullish MSS: Current bar broke above the last swing high
    if curr_high > last_sh_price and curr_close > last_sh_price:
        return 'BULLISH'

    return 'NEUTRAL'


def resample_15m_to_1h(highs_15m, lows_15m, closes_15m, opens_15m=None):
    """
    Aggregates 15m bars into 1H bars (every 4 bars = 1 hour).
    Returns: (h1_highs, h1_lows, h1_closes) as numpy arrays.
    """
    n = len(closes_15m)
    n_1h = n // 4
    if n_1h < 5:
        return np.array([]), np.array([]), np.array([])

    h1_highs = np.array([np.max(highs_15m[i * 4:(i + 1) * 4]) for i in range(n_1h)])
    h1_lows = np.array([np.min(lows_15m[i * 4:(i + 1) * 4]) for i in range(n_1h)])
    h1_closes = np.array([closes_15m[(i + 1) * 4 - 1] for i in range(n_1h)])
    return h1_highs, h1_lows, h1_closes


# ==========================================================================
# Base Backtester Class (Shared Framework for Both Baseline & V2)
# ==========================================================================
class BaseBacktester:
    """
    Core backtesting framework with Option B execution.
    Subclasses override specific methods to inject upgrades.
    """

    def __init__(self, label="BASELINE", initial_balance=100.0, leverage=50,
                 max_positions=5, margin_pct=0.03, fee_tier='vip0_bnb',
                 min_weather_consensus=18, min_pillar_agreement=5, max_notional=50000.0):
        self.label = label
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.leverage = int(leverage)
        self.max_positions = int(max_positions)
        self.margin_pct = float(margin_pct)
        self.min_weather_consensus = int(min_weather_consensus)
        self.min_pillar_agreement = int(min_pillar_agreement)
        self.fee_tier = fee_tier
        self.max_notional = float(max_notional) if max_notional else None

        fees = FEE_TIERS.get(fee_tier, FEE_TIERS['vip0_bnb'])
        self.maker_fee = fees['maker']
        self.taker_fee = fees['taker']
        self.slippage = fees['slippage']
        self.funding_rate_8h = fees['funding_8h']

        self.bot = WeatherEnsembleBot(timeframe='15m', live_trading=False)
        self.active_positions = {}
        self.trade_history = []

        self.total_maker_fees = 0.0
        self.total_taker_fees = 0.0
        self.total_funding_fees = 0.0
        self.total_slippage_cost = 0.0
        self.gross_profit_raw = 0.0
        self.gross_loss_raw = 0.0

        self.monthly_pnl = {}
        self.daily_pnl = {}  # Upgrade 5: Daily tracking
        self.equity_curve = []
        self.peak_balance = float(initial_balance)
        self.max_drawdown_pct = 0.0

    # ---------------------------------------------------------------
    # Override Points for V2 Upgrades
    # ---------------------------------------------------------------
    def get_effective_threshold(self, bar_idx, np_data):
        """Override to implement ADX chop filter (Upgrade 2)."""
        return self.min_weather_consensus

    def get_effective_pillar_threshold(self, bar_idx, np_data):
        """Override to implement ADX chop filter for pillars (Upgrade 2)."""
        return self.min_pillar_agreement

    def check_macro_bias(self, sym, side, bar_idx, np_data):
        """
        Override to implement faster MSS reversal (Upgrade 1).
        Returns True if macro bias aligns with target side.
        """
        # Baseline: 4H EMA20/EMA50 check using available 15m data
        lookback_4h = min(bar_idx + 1, 200)
        closes_4h = np_data[sym]['close'][bar_idx - lookback_4h + 1:bar_idx + 1]

        # Approximate 4H from 15m: Use every 16th bar
        c4h = closes_4h[::16] if len(closes_4h) >= 32 else closes_4h
        if len(c4h) < 20:
            return True  # Not enough data, allow trade

        ema20 = pd.Series(c4h).ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = pd.Series(c4h).ewm(span=min(50, len(c4h)), adjust=False).mean().iloc[-1]
        curr = c4h[-1]

        is_bull = curr > ema50 and ema20 >= ema50
        is_bear = curr < ema50 and ema20 <= ema50

        if side in ['BUY', 'LONG'] and is_bear:
            return False
        if side in ['SELL', 'SHORT'] and is_bull:
            return False
        return True

    def check_directional_cap(self, side):
        """Override to implement directional exposure cap (Upgrade 3)."""
        return True  # Baseline: no directional cap

    def get_scale_out_config(self):
        """
        Override to implement 3-stage scale-out (Upgrade 4).
        Returns list of (fraction, label) tuples for TP stages.
        Baseline: 50% TP1 + 50% trailing runner.
        """
        return [
            (0.50, 'TP1'),   # 50% scale-out at TP1
        ]

    # ---------------------------------------------------------------
    # Core Trade Management (Option B)
    # ---------------------------------------------------------------
    def manage_positions(self, bar_idx, np_data, month_key, day_key):
        """Manages all active positions: SL checks, TP scaling, trailing stops."""
        closed_syms = []

        for sym, pos in list(self.active_positions.items()):
            bar_h = np_data[sym]['high'][bar_idx]
            bar_l = np_data[sym]['low'][bar_idx]
            bar_c = np_data[sym]['close'][bar_idx]
            side = pos['side'].upper()
            is_long = side in ['BUY', 'LONG']

            # --- Check Stop Loss ---
            hit_sl = False
            if is_long and bar_l <= pos['sl']:
                hit_sl = True
                sl_exit_price = min(bar_c, pos['sl']) * (1.0 - self.slippage)
            elif not is_long and bar_h >= pos['sl']:
                hit_sl = True
                sl_exit_price = max(bar_c, pos['sl']) * (1.0 + self.slippage)

            if hit_sl:
                rem_qty = pos['rem_qty']
                raw_pnl = rem_qty * (sl_exit_price - pos['entry_price']) if is_long else rem_qty * (pos['entry_price'] - sl_exit_price)
                taker_fee = rem_qty * sl_exit_price * self.taker_fee
                self.total_taker_fees += taker_fee
                if raw_pnl > 0:
                    self.gross_profit_raw += raw_pnl
                else:
                    self.gross_loss_raw += abs(raw_pnl)

                net_pnl = raw_pnl - taker_fee
                self.balance += net_pnl
                self.monthly_pnl[month_key] = self.monthly_pnl.get(month_key, 0.0) + net_pnl
                self.daily_pnl[day_key]['pnl'] += net_pnl
                self.daily_pnl[day_key]['trades_closed'] += 1
                if net_pnl > 0:
                    self.daily_pnl[day_key]['wins'] += 1
                    self.daily_pnl[day_key]['largest_win'] = max(self.daily_pnl[day_key]['largest_win'], net_pnl)
                else:
                    self.daily_pnl[day_key]['largest_loss'] = min(self.daily_pnl[day_key]['largest_loss'], net_pnl)

                pos['realized_pnl'] += net_pnl
                if pos.get('trailing_active'):
                    pos['exit_reason'] = 'TP_TRAILED_WIN'
                elif pos.get('tp1_hit'):
                    pos['exit_reason'] = 'SL_BE'
                else:
                    pos['exit_reason'] = 'STOP_LOSS'
                self.trade_history.append(pos)
                closed_syms.append(sym)
                continue

            # --- Check TP Stages ---
            self._check_tp_stages(pos, bar_h, bar_l, bar_c, is_long, month_key, day_key)

            # --- Dynamic Trailing Stop ---
            if pos.get('trailing_active'):
                atr_val = pos.get('atr', pos['entry_price'] * 0.008)
                trail_dist = 1.2 * atr_val

                if is_long:
                    if bar_h > pos['highest_mark']:
                        pos['highest_mark'] = bar_h
                    calc_trail = pos['highest_mark'] - trail_dist
                    if calc_trail > pos['sl'] and calc_trail > pos['entry_price']:
                        pos['sl'] = calc_trail
                else:
                    if bar_l < pos['lowest_mark']:
                        pos['lowest_mark'] = bar_l
                    calc_trail = pos['lowest_mark'] + trail_dist
                    if calc_trail < pos['sl'] and calc_trail < pos['entry_price']:
                        pos['sl'] = calc_trail

        for sym in closed_syms:
            if sym in self.active_positions:
                del self.active_positions[sym]

    def _check_tp_stages(self, pos, bar_h, bar_l, bar_c, is_long, month_key, day_key):
        """Baseline: 50% TP1 scale-out + breakeven."""
        if not pos.get('tp1_hit'):
            tp1_hit = (is_long and bar_h >= pos['tp1']) or (not is_long and bar_l <= pos['tp1'])
            if tp1_hit:
                pos['tp1_hit'] = True
                close_qty = pos['initial_qty'] * 0.50
                pos['rem_qty'] -= close_qty

                tp_p = pos['tp1']
                raw_pnl = close_qty * (tp_p - pos['entry_price']) if is_long else close_qty * (pos['entry_price'] - tp_p)
                maker_fee = close_qty * tp_p * self.maker_fee
                self.total_maker_fees += maker_fee
                self.gross_profit_raw += raw_pnl

                net_pnl = raw_pnl - maker_fee
                self.balance += net_pnl
                self.monthly_pnl[month_key] = self.monthly_pnl.get(month_key, 0.0) + net_pnl
                self.daily_pnl[day_key]['pnl'] += net_pnl

                # Move SL to breakeven + activate trailing
                be_price = pos['entry_price'] * 1.0005 if is_long else pos['entry_price'] * 0.9995
                pos['sl'] = be_price
                pos['trailing_active'] = True
                pos['highest_mark'] = bar_h
                pos['lowest_mark'] = bar_l

    # ---------------------------------------------------------------
    # Signal Evaluation & Entry
    # ---------------------------------------------------------------
    def evaluate_and_enter(self, bar_idx, np_data, raw_data, month_key, day_key, last_trade_bar):
        """Evaluates signals and opens new positions."""
        if len(self.active_positions) >= self.max_positions:
            return last_trade_bar

        lookback = 45

        # BTC Master Trend Filter
        btc_closes = np_data['BTCUSDT']['close'][max(0, bar_idx - 25):bar_idx + 1]
        btc_ret = (btc_closes[-1] - btc_closes[-2]) / btc_closes[-2] if len(btc_closes) >= 2 else 0
        btc_ema20 = pd.Series(btc_closes).ewm(span=20, adjust=False).mean().iloc[-1]
        btc_dumping = (btc_closes[-1] < btc_ema20 and btc_ret < -0.0050)
        btc_pumping = (btc_closes[-1] > btc_ema20 and btc_ret > +0.0060)

        # Get effective thresholds (may be adjusted by ADX filter in V2)
        eff_consensus = self.get_effective_threshold(bar_idx, np_data)
        eff_pillar = self.get_effective_pillar_threshold(bar_idx, np_data)

        for sym in SYMBOLS:
            if sym in self.active_positions:
                continue
            if (bar_idx - last_trade_bar.get(sym, -100)) < 8:
                continue
            if len(self.active_positions) >= self.max_positions:
                break

            df_slice = raw_data[sym].iloc[bar_idx - lookback + 1:bar_idx + 1]
            if len(df_slice) < 35:
                continue

            # --- Channel 0: Fibonacci Golden Pocket ---
            fib_setup = check_fibonacci_setup(df_slice, sym)

            if fib_setup.get('is_setup') and fib_setup.get('rr', 0) >= 1.8:
                side = fib_setup['side']

                # Macro bias check (Upgrade 1: may use 1H MSS in V2)
                if not self.check_macro_bias(sym, side, bar_idx, np_data):
                    continue

                # Directional cap check (Upgrade 3)
                if not self.check_directional_cap(side):
                    continue

                # BTC filter for altcoins
                if sym != 'BTCUSDT':
                    if side in ['BUY', 'LONG'] and btc_dumping:
                        continue
                    if side in ['SELL', 'SHORT'] and btc_pumping:
                        continue

                # Weather Ensemble confirmation
                weather_signals = self.bot.evaluate_31_models(df_slice)
                bull_models = weather_signals.count('BULLISH')
                bear_models = weather_signals.count('BEARISH')
                pillar_bull, pillar_bear, _ = self.bot.compute_pillar_consensus(weather_signals)

                weather_aligned = False
                if side == 'BUY':
                    weather_aligned = (bull_models >= eff_consensus) or (pillar_bull >= eff_pillar)
                elif side == 'SELL':
                    weather_aligned = (bear_models >= eff_consensus) or (pillar_bear >= eff_pillar)

                if weather_aligned:
                    self._open_position(
                        sym, side, fib_setup, bar_idx, np_data, month_key, day_key,
                        bull_models if side == 'BUY' else bear_models,
                        pillar_bull if side == 'BUY' else pillar_bear,
                        'WEATHER_FIBONACCI_CONFLUENCE'
                    )
                    last_trade_bar[sym] = bar_idx

        return last_trade_bar

    def _open_position(self, sym, side, fib_setup, bar_idx, np_data, month_key, day_key,
                       consensus, pillars, channel):
        """Opens a new position with TP/SL brackets."""
        entry_p = fib_setup['entry_price']
        sl_p = fib_setup['sl']
        tp1_p = fib_setup['tp1']
        tp2_p = fib_setup['tp2']
        tp3_p = fib_setup['tp3']

        margin = self.balance * self.margin_pct
        notional = margin * self.leverage
        if self.max_notional is not None and notional > self.max_notional:
            notional = self.max_notional
            margin = notional / self.leverage
        if notional < 5.0:
            notional = 5.0
            margin = notional / self.leverage

        if self.balance < margin:
            return

        qty = notional / entry_p

        # Entry Maker Fee
        entry_fee = notional * self.maker_fee
        self.total_maker_fees += entry_fee
        self.balance -= entry_fee
        self.monthly_pnl[month_key] = self.monthly_pnl.get(month_key, 0.0) - entry_fee
        self.daily_pnl[day_key]['pnl'] -= entry_fee

        # Compute ATR for trailing stop
        lookback_atr = min(bar_idx + 1, 50)
        h_arr = np_data[sym]['high'][bar_idx - lookback_atr + 1:bar_idx + 1]
        l_arr = np_data[sym]['low'][bar_idx - lookback_atr + 1:bar_idx + 1]
        c_arr = np_data[sym]['close'][bar_idx - lookback_atr + 1:bar_idx + 1]
        if len(c_arr) >= 15:
            tr_vals = np.maximum(
                h_arr[1:] - l_arr[1:],
                np.maximum(np.abs(h_arr[1:] - c_arr[:-1]), np.abs(l_arr[1:] - c_arr[:-1]))
            )
            atr_val = float(np.mean(tr_vals[-14:])) if len(tr_vals) >= 14 else entry_p * 0.008
        else:
            atr_val = entry_p * 0.008

        self.active_positions[sym] = {
            'symbol': sym,
            'side': side,
            'entry_price': entry_p,
            'initial_qty': qty,
            'rem_qty': qty,
            'sl': sl_p,
            'tp1': tp1_p,
            'tp2': tp2_p,
            'tp3': tp3_p,
            'tp1_hit': False,
            'tp2_hit': False,
            'trailing_active': False,
            'atr': atr_val,
            'highest_mark': entry_p,
            'lowest_mark': entry_p,
            'realized_pnl': -entry_fee,
            'channel': channel,
            'consensus': consensus,
            'pillars': pillars
        }
        self.daily_pnl[day_key]['trades_opened'] += 1

    # ---------------------------------------------------------------
    # Main Run Loop
    # ---------------------------------------------------------------
    def run(self, raw_data, np_data):
        """Main backtesting loop."""
        min_len = min(len(df) for df in raw_data.values())
        lookback = 45
        last_funding_bar = 0
        last_trade_bar = {sym: -100 for sym in SYMBOLS}

        for bar_idx in range(lookback, min_len):
            current_time = pd.to_datetime(np_data['BTCUSDT']['open_time'][bar_idx])
            month_key = current_time.strftime('%Y-%m')
            day_key = current_time.strftime('%Y-%m-%d')

            if month_key not in self.monthly_pnl:
                self.monthly_pnl[month_key] = 0.0

            if day_key not in self.daily_pnl:
                self.daily_pnl[day_key] = {
                    'start_balance': self.balance,
                    'pnl': 0.0,
                    'trades_opened': 0,
                    'trades_closed': 0,
                    'wins': 0,
                    'largest_win': 0.0,
                    'largest_loss': 0.0,
                }

            # 8-Hour Funding Rate Deduction
            if (bar_idx - last_funding_bar) >= 32:
                last_funding_bar = bar_idx
                for sym, pos in self.active_positions.items():
                    bar_c = np_data[sym]['close'][bar_idx]
                    pos_val = pos['rem_qty'] * bar_c
                    funding_cost = pos_val * self.funding_rate_8h
                    self.total_funding_fees += funding_cost
                    self.balance -= funding_cost
                    self.monthly_pnl[month_key] -= funding_cost
                    self.daily_pnl[day_key]['pnl'] -= funding_cost

            # 1. Manage Active Positions
            self.manage_positions(bar_idx, np_data, month_key, day_key)

            # 2. Evaluate and Enter
            last_trade_bar = self.evaluate_and_enter(bar_idx, np_data, raw_data, month_key, day_key, last_trade_bar)

            # Track equity curve and drawdown
            self.equity_curve.append(self.balance)
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance
            dd = (self.peak_balance - self.balance) / self.peak_balance * 100 if self.peak_balance > 0 else 0
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd

        # Close remaining positions at final bar
        final_day_key = pd.to_datetime(np_data['BTCUSDT']['open_time'][min_len - 1]).strftime('%Y-%m-%d')
        final_month_key = pd.to_datetime(np_data['BTCUSDT']['open_time'][min_len - 1]).strftime('%Y-%m')
        if final_day_key not in self.daily_pnl:
            self.daily_pnl[final_day_key] = {'start_balance': self.balance, 'pnl': 0.0,
                                              'trades_opened': 0, 'trades_closed': 0, 'wins': 0,
                                              'largest_win': 0.0, 'largest_loss': 0.0}

        for sym, pos in list(self.active_positions.items()):
            bar_c = np_data[sym]['close'][min_len - 1]
            rem_qty = pos['rem_qty']
            is_long = pos['side'] in ['BUY', 'LONG']
            raw_pnl = rem_qty * (bar_c - pos['entry_price']) if is_long else rem_qty * (pos['entry_price'] - bar_c)
            taker_fee = rem_qty * bar_c * self.taker_fee
            self.total_taker_fees += taker_fee
            if raw_pnl > 0:
                self.gross_profit_raw += raw_pnl
            else:
                self.gross_loss_raw += abs(raw_pnl)
            net_pnl = raw_pnl - taker_fee
            self.balance += net_pnl
            pos['realized_pnl'] += net_pnl
            pos['exit_reason'] = 'MARKET_END'
            self.trade_history.append(pos)

    def get_results(self):
        """Computes and returns results summary dict."""
        total_trades = len(self.trade_history)
        if total_trades == 0:
            return {'label': self.label, 'total_trades': 0}

        wins = [t for t in self.trade_history if t['realized_pnl'] > 0]
        losses = [t for t in self.trade_history if t['realized_pnl'] <= 0]
        win_rate = (len(wins) / total_trades) * 100
        gross_profit = sum(t['realized_pnl'] for t in wins)
        gross_loss = abs(sum(t['realized_pnl'] for t in losses))
        profit_factor = gross_profit / (gross_loss + 1e-9)
        total_return_pct = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        hard_sls = len([t for t in self.trade_history if t.get('exit_reason') == 'STOP_LOSS'])
        be_sls = len([t for t in self.trade_history if t.get('exit_reason') == 'SL_BE'])
        trailed_wins = len([t for t in self.trade_history if t.get('exit_reason') == 'TP_TRAILED_WIN'])
        total_friction = self.total_maker_fees + self.total_taker_fees + self.total_funding_fees + self.total_slippage_cost
        green_months = sum(1 for p in self.monthly_pnl.values() if p > 0)

        avg_win = np.mean([t['realized_pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t['realized_pnl']) for t in losses]) if losses else 0

        return {
            'label': self.label,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'wins': len(wins),
            'losses': len(losses),
            'profit_factor': profit_factor,
            'total_return_pct': total_return_pct,
            'final_balance': self.balance,
            'max_drawdown_pct': self.max_drawdown_pct,
            'hard_sls': hard_sls,
            'be_sls': be_sls,
            'trailed_wins': trailed_wins,
            'gross_profit_raw': self.gross_profit_raw,
            'gross_loss_raw': self.gross_loss_raw,
            'total_maker_fees': self.total_maker_fees,
            'total_taker_fees': self.total_taker_fees,
            'total_funding_fees': self.total_funding_fees,
            'total_slippage_cost': self.total_slippage_cost,
            'total_friction': total_friction,
            'green_months': green_months,
            'total_months': len(self.monthly_pnl),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'monthly_pnl': self.monthly_pnl,
            'daily_pnl': self.daily_pnl,
        }


# ==========================================================================
# V2 Upgraded Backtester (All 5 Improvements)
# ==========================================================================
class V2UpgradedBacktester(BaseBacktester):
    """
    V2 Engine with all 5 upgrades:
      1. 1H MSS fast reversal detection
      2. ADX(14) chop filter
      3. Directional exposure cap (max 3 same-direction)
      4. 3-stage scale-out (33/33/34)
      5. Daily PnL tracking (inherited from base, enhanced reporting)
    """

    def __init__(self, adx_chop_threshold=20, max_same_direction=3, **kwargs):
        super().__init__(label="V2 UPGRADED", **kwargs)
        self.adx_chop_threshold = adx_chop_threshold
        self.max_same_direction = max_same_direction

    # ---------------------------------------------------------------
    # Upgrade 2: ADX Chop Filter
    # ---------------------------------------------------------------
    def _get_btc_adx(self, bar_idx, np_data):
        """Calculates ADX(14) from BTC 15m data as a market-wide regime proxy."""
        lookback_adx = min(bar_idx + 1, 100)
        h = np_data['BTCUSDT']['high'][bar_idx - lookback_adx + 1:bar_idx + 1]
        l = np_data['BTCUSDT']['low'][bar_idx - lookback_adx + 1:bar_idx + 1]
        c = np_data['BTCUSDT']['close'][bar_idx - lookback_adx + 1:bar_idx + 1]
        return calc_adx(h, l, c, period=14)

    def get_effective_threshold(self, bar_idx, np_data):
        """ADX < 20 -> raise consensus to 31 (effectively pause entries)."""
        adx = self._get_btc_adx(bar_idx, np_data)
        if adx < self.adx_chop_threshold:
            return 31  # Require unanimous vote in chop
        return self.min_weather_consensus

    def get_effective_pillar_threshold(self, bar_idx, np_data):
        """ADX < 20 -> raise pillar requirement to 9/9."""
        adx = self._get_btc_adx(bar_idx, np_data)
        if adx < self.adx_chop_threshold:
            return 9  # Require all 9 pillars in chop
        return self.min_pillar_agreement

    # ---------------------------------------------------------------
    # Upgrade 1: 1H Market Structure Shift
    # ---------------------------------------------------------------
    def check_macro_bias(self, sym, side, bar_idx, np_data):
        """
        First checks 1H MSS for faster reversal detection.
        Falls back to 4H EMA20/EMA50 if MSS is NEUTRAL.
        """
        # Build 1H bars from 15m data
        lookback_1h = min(bar_idx + 1, 200)
        h_15m = np_data[sym]['high'][bar_idx - lookback_1h + 1:bar_idx + 1]
        l_15m = np_data[sym]['low'][bar_idx - lookback_1h + 1:bar_idx + 1]
        c_15m = np_data[sym]['close'][bar_idx - lookback_1h + 1:bar_idx + 1]

        h1_highs, h1_lows, h1_closes = resample_15m_to_1h(h_15m, l_15m, c_15m)

        if len(h1_closes) >= 12:
            mss = detect_1h_mss(h1_highs, h1_lows, h1_closes, window=3)

            if mss == 'BEARISH' and side in ['BUY', 'LONG']:
                return False  # 1H structure broke bearish -> block longs
            if mss == 'BULLISH' and side in ['SELL', 'SHORT']:
                return False  # 1H structure broke bullish -> block shorts

            # If MSS confirms direction, allow immediately
            if mss == 'BULLISH' and side in ['BUY', 'LONG']:
                return True
            if mss == 'BEARISH' and side in ['SELL', 'SHORT']:
                return True

        # Fallback: 4H EMA check (same as baseline)
        return super().check_macro_bias(sym, side, bar_idx, np_data)

    # ---------------------------------------------------------------
    # Upgrade 3: Directional Exposure Cap
    # ---------------------------------------------------------------
    def check_directional_cap(self, side):
        """Max 3 positions in the same direction unless existing ones are at breakeven."""
        long_count = 0
        short_count = 0
        for sym, pos in self.active_positions.items():
            pos_side = pos['side'].upper()
            # Positions already at breakeven (tp1_hit) don't count against the cap
            if pos.get('tp1_hit'):
                continue
            if pos_side in ['BUY', 'LONG']:
                long_count += 1
            else:
                short_count += 1

        if side in ['BUY', 'LONG'] and long_count >= self.max_same_direction:
            return False
        if side in ['SELL', 'SHORT'] and short_count >= self.max_same_direction:
            return False
        return True

    # ---------------------------------------------------------------
    # Upgrade 4: 3-Stage Scale-Out (33% / 33% / 34%)
    # ---------------------------------------------------------------
    def _check_tp_stages(self, pos, bar_h, bar_l, bar_c, is_long, month_key, day_key):
        """
        3-Stage Scale-Out:
          TP1 (33%): Quick 1.5R -> SL to Breakeven
          TP2 (33%): Structural target -> Lock major profit, tighten trailing
          TP3 (34% Runner): Dynamic ATR trailing stop rides macro swings
        """
        # --- Stage 1: TP1 (33% scale-out) ---
        if not pos.get('tp1_hit'):
            tp1_hit = (is_long and bar_h >= pos['tp1']) or (not is_long and bar_l <= pos['tp1'])
            if tp1_hit:
                pos['tp1_hit'] = True
                close_qty = pos['initial_qty'] * 0.33
                pos['rem_qty'] -= close_qty

                tp_p = pos['tp1']
                raw_pnl = close_qty * (tp_p - pos['entry_price']) if is_long else close_qty * (pos['entry_price'] - tp_p)
                maker_fee = close_qty * tp_p * self.maker_fee
                self.total_maker_fees += maker_fee
                self.gross_profit_raw += raw_pnl

                net_pnl = raw_pnl - maker_fee
                self.balance += net_pnl
                self.monthly_pnl[month_key] = self.monthly_pnl.get(month_key, 0.0) + net_pnl
                self.daily_pnl[day_key]['pnl'] += net_pnl

                # Move SL to Breakeven + activate trailing
                be_price = pos['entry_price'] * 1.0005 if is_long else pos['entry_price'] * 0.9995
                pos['sl'] = be_price
                pos['trailing_active'] = True
                pos['highest_mark'] = bar_h
                pos['lowest_mark'] = bar_l

        # --- Stage 2: TP2 (33% scale-out at structural target) ---
        elif not pos.get('tp2_hit') and pos.get('tp1_hit'):
            tp2_hit = (is_long and bar_h >= pos['tp2']) or (not is_long and bar_l <= pos['tp2'])
            if tp2_hit:
                pos['tp2_hit'] = True
                close_qty = pos['initial_qty'] * 0.33
                # Don't close more than remaining qty
                close_qty = min(close_qty, pos['rem_qty'] * 0.99)
                if close_qty > 0:
                    pos['rem_qty'] -= close_qty

                    tp_p = pos['tp2']
                    raw_pnl = close_qty * (tp_p - pos['entry_price']) if is_long else close_qty * (pos['entry_price'] - tp_p)
                    maker_fee = close_qty * tp_p * self.maker_fee
                    self.total_maker_fees += maker_fee
                    self.gross_profit_raw += raw_pnl

                    net_pnl = raw_pnl - maker_fee
                    self.balance += net_pnl
                    self.monthly_pnl[month_key] = self.monthly_pnl.get(month_key, 0.0) + net_pnl
                    self.daily_pnl[day_key]['pnl'] += net_pnl
                    self.daily_pnl[day_key]['largest_win'] = max(self.daily_pnl[day_key]['largest_win'], net_pnl)

                    # Tighten trailing stop: lock more profit
                    atr_val = pos.get('atr', pos['entry_price'] * 0.008)
                    if is_long:
                        tighter_sl = pos['highest_mark'] - (0.8 * atr_val)
                        if tighter_sl > pos['sl']:
                            pos['sl'] = tighter_sl
                    else:
                        tighter_sl = pos['lowest_mark'] + (0.8 * atr_val)
                        if tighter_sl < pos['sl']:
                            pos['sl'] = tighter_sl


# ==========================================================================
# Head-to-Head Comparison Runner
# ==========================================================================
def load_cached_data():
    """Loads all 15m historical data from cache."""
    data = {}
    for sym in SYMBOLS:
        fname = f"{sym}_15m_from_2025-07-01.csv"
        fpath = os.path.join(CACHE_DIR, fname)
        if not os.path.exists(fpath):
            print(f"Error: Missing cache file {fpath}")
            continue
        df = pd.read_csv(fpath)
        t_col = 'open_time' if 'open_time' in df.columns else 'timestamp'
        df['open_time'] = pd.to_datetime(df[t_col])
        df = df.sort_values('open_time').reset_index(drop=True)
        data[sym] = df
    return data


def prepare_np_data(raw_data):
    """Converts DataFrames to numpy arrays for fast access."""
    np_data = {}
    for sym, df in raw_data.items():
        np_data[sym] = {
            'open_time': df['open_time'].values,
            'open': df['open'].values.astype(float),
            'high': df['high'].values.astype(float),
            'low': df['low'].values.astype(float),
            'close': df['close'].values.astype(float),
            'volume': df['volume'].values.astype(float)
        }
    return np_data


def print_comparison(baseline_res, v2_res):
    """Prints a head-to-head comparison table."""
    print("\n" + "=" * 85)
    print("  HEAD-TO-HEAD COMPARISON: BASELINE vs V2 UPGRADED (ALL 5 IMPROVEMENTS)")
    print("=" * 85)

    metrics = [
        ("Total Trades", 'total_trades', '{:d}', False),
        ("Win Rate", 'win_rate', '{:.2f}%', False),
        ("Profit Factor", 'profit_factor', '{:.2f}', False),
        ("Total Return", 'total_return_pct', '{:+.2f}%', False),
        ("Final Balance", 'final_balance', '${:,.2f}', False),
        ("Max Drawdown", 'max_drawdown_pct', '{:.2f}%', True),
        ("Avg Win", 'avg_win', '${:.4f}', False),
        ("Avg Loss", 'avg_loss', '${:.4f}', True),
        ("Hard Stop-Losses", 'hard_sls', '{:d}', True),
        ("Breakeven Exits", 'be_sls', '{:d}', False),
        ("Trailed Big Wins", 'trailed_wins', '{:d}', False),
        ("Total Fees & Friction", 'total_friction', '${:.4f}', True),
        ("Green Months", 'green_months', '{:d}', False),
    ]

    header = f"\n{'Metric':<28} {'BASELINE':>18} {'V2 UPGRADED':>18} {'DELTA':>14}"
    print(header)
    print("-" * 80)

    for name, key, fmt, lower_is_better in metrics:
        bv = baseline_res.get(key, 0)
        vv = v2_res.get(key, 0)

        b_str = fmt.format(bv)
        v_str = fmt.format(vv)
        delta = vv - bv

        if isinstance(bv, float):
            if lower_is_better:
                indicator = "[+]" if delta < 0 else ("[-]" if delta > 0 else "[=]")
            else:
                indicator = "[+]" if delta > 0 else ("[-]" if delta < 0 else "[=]")
            d_str = f"{indicator} {delta:+.2f}"
        else:
            if lower_is_better:
                indicator = "[+]" if delta < 0 else ("[-]" if delta > 0 else "[=]")
            else:
                indicator = "[+]" if delta > 0 else ("[-]" if delta < 0 else "[=]")
            d_str = f"{indicator} {delta:+d}"

        print(f"  {name:<26} {b_str:>18} {v_str:>18} {d_str:>14}")

    # Monthly Breakdown
    print("\n" + "-" * 80)
    print("MONTHLY PROFITABILITY COMPARISON:")
    all_months = sorted(set(list(baseline_res.get('monthly_pnl', {}).keys()) +
                            list(v2_res.get('monthly_pnl', {}).keys())))
    for m in all_months:
        b_pnl = baseline_res.get('monthly_pnl', {}).get(m, 0)
        v_pnl = v2_res.get('monthly_pnl', {}).get(m, 0)
        b_bar = "[G]" if b_pnl >= 0 else "[R]"
        v_bar = "[G]" if v_pnl >= 0 else "[R]"
        winner = "V2 WINS" if v_pnl > b_pnl else ("BASE WINS" if b_pnl > v_pnl else "TIE")
        print(f"  {m}: {b_bar} Base ${b_pnl:+8.2f}  |  {v_bar} V2 ${v_pnl:+8.2f}  |  {winner}")

    # Itemized Fee & Friction Audit
    print("\n" + "-" * 80)
    print("EXCHANGE FEE & FRICTION ITEMIZATION AUDIT (BINANCE VIP0 + BNB):")
    print(f"  {'Fee Component':<30} {'BASELINE':>20} {'V2 UPGRADED':>20} {'SAVINGS':>12}")
    print("  " + "-" * 76)
    
    fee_items = [
        ("Maker Limit Entry/TP (0.018%)", 'total_maker_fees'),
        ("Taker Stop-Loss Fees (0.045%)", 'total_taker_fees'),
        ("8-Hour Funding Rate (0.010%)", 'total_funding_fees'),
        ("Execution Slippage (0.015%)", 'total_slippage_cost'),
        ("TOTAL ALL FEES & FRICTION", 'total_friction')
    ]
    for lbl, k in fee_items:
        bf = baseline_res.get(k, 0.0)
        vf = v2_res.get(k, 0.0)
        sav = bf - vf
        pct_sav = (sav / bf * 100) if bf > 0 else 0
        print(f"  {lbl:<30} ${bf:>19.2f} ${vf:>19.2f}   [+{pct_sav:.1f}%]")

    print("=" * 85)

    # Upgrade Impact Summary
    print("\nUPGRADE IMPACT SUMMARY:")
    print("-" * 50)

    wr_delta = v2_res.get('win_rate', 0) - baseline_res.get('win_rate', 0)
    pf_delta = v2_res.get('profit_factor', 0) - baseline_res.get('profit_factor', 0)
    dd_delta = v2_res.get('max_drawdown_pct', 0) - baseline_res.get('max_drawdown_pct', 0)
    ret_delta = v2_res.get('total_return_pct', 0) - baseline_res.get('total_return_pct', 0)

    improvements = 0
    if wr_delta > 0:
        improvements += 1
        print(f"  [OK] Win Rate:       +{wr_delta:.2f}% improvement")
    else:
        print(f"  [!!] Win Rate:       {wr_delta:+.2f}%")

    if pf_delta > 0:
        improvements += 1
        print(f"  [OK] Profit Factor:  +{pf_delta:.2f} improvement")
    else:
        print(f"  [!!] Profit Factor:  {pf_delta:+.2f}")

    if dd_delta < 0:
        improvements += 1
        print(f"  [OK] Max Drawdown:   {dd_delta:+.2f}% reduction (safer)")
    else:
        print(f"  [!!] Max Drawdown:   +{dd_delta:.2f}% (riskier)")

    if ret_delta > 0:
        improvements += 1
        print(f"  [OK] Total Return:   +{ret_delta:.2f}% more profit")
    else:
        print(f"  [!!] Total Return:   {ret_delta:+.2f}%")

    sl_delta = v2_res.get('hard_sls', 0) - baseline_res.get('hard_sls', 0)
    if sl_delta < 0:
        improvements += 1
        print(f"  [OK] Stop-Losses:    {sl_delta:+d} fewer hard stops")
    elif sl_delta > 0:
        print(f"  [!!] Stop-Losses:    +{sl_delta} more hard stops")

    print(f"\n  V2 improved {improvements}/5 key metrics vs Baseline.")

    verdict = "RECOMMEND DEPLOYING V2 TO LIVE" if improvements >= 3 else "FURTHER TUNING NEEDED BEFORE DEPLOY"
    print(f"  VERDICT: {verdict}")
    print("=" * 85 + "\n")


def print_daily_summary(v2_res):
    """Prints the daily PnL summary table (Upgrade 5 validation)."""
    daily = v2_res.get('daily_pnl', {})
    if not daily:
        return

    print("\n" + "=" * 100)
    print("V2 DAILY PnL SUMMARY REPORT (Upgrade 5 - Telegram Report Preview)")
    print("=" * 100)
    print(f"{'Date':<14} {'Start Bal':>12} {'End Bal':>12} {'Daily PnL':>12} {'Trades':>8} {'Wins':>6} {'Win%':>8} {'Best Win':>11} {'Worst Loss':>11}")
    print("-" * 100)

    sorted_days = sorted(daily.keys())

    for day_key in sorted_days:
        d = daily[day_key]
        start_b = d['start_balance']
        end_b = start_b + d['pnl']
        total_closed = d['trades_closed']
        w = d['wins']
        wr = (w / total_closed * 100) if total_closed > 0 else 0
        opened = d['trades_opened']
        best = d['largest_win']
        worst = d['largest_loss']

        # Only print days with activity
        if opened > 0 or total_closed > 0 or abs(d['pnl']) > 0.001:
            status = "[G]" if d['pnl'] >= 0 else "[R]"
            print(f"  {status} {day_key:<11} ${start_b:>10.2f} ${end_b:>10.2f} ${d['pnl']:>+10.4f} {total_closed:>6d}   {w:>4d}  {wr:>6.1f}%  ${best:>+9.4f}  ${worst:>+9.4f}")

    # Summary stats
    active_days = [d for d in daily.values() if d['trades_closed'] > 0 or d['trades_opened'] > 0]
    green_days = sum(1 for d in active_days if d['pnl'] > 0)
    red_days = sum(1 for d in active_days if d['pnl'] < 0)
    total_active = len(active_days)

    print("-" * 100)
    print(f"  Active Trading Days: {total_active} | Green: {green_days} ({green_days/max(total_active,1)*100:.1f}%) | Red: {red_days} ({red_days/max(total_active,1)*100:.1f}%)")
    print("=" * 100 + "\n")


# ==========================================================================
# Main Entry Point
# ==========================================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="V2 Upgraded Engine - Head-to-Head 1-Year Backtest")
    parser.add_argument('--balance', type=float, default=100.0, help='Starting balance (USDT)')
    parser.add_argument('--leverage', type=int, default=50, help='Leverage multiplier')
    parser.add_argument('--margin-pct', type=float, default=0.03, help='Margin pct per position')
    parser.add_argument('--max-positions', type=int, default=5, help='Max concurrent positions')
    parser.add_argument('--fee-tier', type=str, default='vip0_bnb', help='Fee schedule tier')
    parser.add_argument('--adx-threshold', type=int, default=20, help='ADX chop threshold (Upgrade 2)')
    parser.add_argument('--max-same-dir', type=int, default=3, help='Max same-direction positions (Upgrade 3)')
    parser.add_argument('--max-notional', type=float, default=50000.0, help='Maximum allowed position notional (Binance 50x tier cap, default $50k)')
    parser.add_argument('--baseline-only', action='store_true', help='Run only baseline')
    parser.add_argument('--v2-only', action='store_true', help='Run only V2 upgraded')
    args = parser.parse_args()

    print("=" * 85)
    print("  WEATHER-ENSEMBLE V2 UPGRADED ENGINE: 1-YEAR HEAD-TO-HEAD BACKTEST")
    print("=" * 85)
    print(f"  Starting Balance:   ${args.balance:,.2f}")
    print(f"  Leverage:           {args.leverage}x")
    print(f"  Margin Per Slot:    {args.margin_pct * 100:.1f}%")
    print(f"  Max Position Cap:   ${args.max_notional:,.2f} Notional (Binance Tier Limit)")
    print(f"  Max Positions:      {args.max_positions}")
    print(f"  Fee Tier:           {args.fee_tier.upper()}")
    print(f"  ADX Chop Filter:    ADX < {args.adx_threshold} = Pause (Upgrade 2)")
    print(f"  Max Same Direction: {args.max_same_dir} (Upgrade 3)")
    print("=" * 85 + "\n")

    # Load data once
    print("[1/4] Loading historical 15m data from cache...")
    raw_data = load_cached_data()
    if not raw_data:
        print("No historical data found. Run the data downloader first.")
        sys.exit(1)

    min_len = min(len(df) for df in raw_data.values())
    print(f"      Loaded {len(raw_data)} assets | {min_len:,} bars per asset ({min_len * 15 / 60 / 24:.1f} days)\n")

    np_data = prepare_np_data(raw_data)

    common_kwargs = dict(
        initial_balance=args.balance,
        leverage=args.leverage,
        max_positions=args.max_positions,
        margin_pct=args.margin_pct,
        fee_tier=args.fee_tier,
        max_notional=args.max_notional,
    )

    baseline_res = None
    v2_res = None

    # --- Run Baseline ---
    if not args.v2_only:
        print("[2/4] Running BASELINE engine (current live strategy)...")
        baseline = BaseBacktester(label="BASELINE", **common_kwargs)
        baseline.run(raw_data, np_data)
        baseline_res = baseline.get_results()
        print(f"      Baseline complete: {baseline_res['total_trades']} trades | "
              f"Win Rate: {baseline_res.get('win_rate', 0):.1f}% | "
              f"Return: {baseline_res.get('total_return_pct', 0):+.2f}%\n")

    # --- Run V2 Upgraded ---
    if not args.baseline_only:
        print("[3/4] Running V2 UPGRADED engine (all 5 improvements)...")
        v2 = V2UpgradedBacktester(
            adx_chop_threshold=args.adx_threshold,
            max_same_direction=args.max_same_dir,
            **common_kwargs
        )
        v2.run(raw_data, np_data)
        v2_res = v2.get_results()
        print(f"      V2 complete: {v2_res['total_trades']} trades | "
              f"Win Rate: {v2_res.get('win_rate', 0):.1f}% | "
              f"Return: {v2_res.get('total_return_pct', 0):+.2f}%\n")

    # --- Print Results ---
    print("[4/4] Generating comparison report...\n")

    if baseline_res and v2_res:
        print_comparison(baseline_res, v2_res)
        print_daily_summary(v2_res)
    elif baseline_res:
        print(f"\nBASELINE ONLY: {baseline_res['total_trades']} trades | "
              f"Win Rate: {baseline_res.get('win_rate', 0):.1f}% | "
              f"Return: {baseline_res.get('total_return_pct', 0):+.2f}% | "
              f"Final: ${baseline_res.get('final_balance', 0):,.2f}")
    elif v2_res:
        print(f"\nV2 ONLY: {v2_res['total_trades']} trades | "
              f"Win Rate: {v2_res.get('win_rate', 0):.1f}% | "
              f"Return: {v2_res.get('total_return_pct', 0):+.2f}% | "
              f"Final: ${v2_res.get('final_balance', 0):,.2f}")
        print_daily_summary(v2_res)
