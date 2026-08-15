#!/usr/bin/env python3
"""
WEATHER-ENSEMBLE BINANCE FUTURES DATA DOWNLOADER
================================================
Fetches real historical kline data from Binance Futures API (fapi.binance.com)
and saves it to a local CSV file for high-fidelity backtesting.
"""

import os
import sys
import time
import argparse
import pandas as pd
import requests
from datetime import datetime, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def download_historical_klines(symbol="BTCUSDT", interval="5m", days=90):
    symbol = symbol.upper()
    print("=" * 80)
    print(f" BINANCE FUTURES HISTORICAL DATA DOWNLOADER")
    print(f" Target Asset:   {symbol}")
    print(f" Timeframe:      {interval}")
    print(f" Data Window:    {days} Days")
    print("=" * 80)

    url = "https://fapi.binance.com/fapi/v1/klines"
    limit = 1500  # Binance API max limit per request
    
    # Calculate start and end timestamps in milliseconds
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 60 * 60 * 1000)
    
    all_klines = []
    current_start = start_ms
    
    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "startTime": current_start,
            "endTime": end_ms
        }
        
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                print(f"❌ Error fetching data: API returned status code {r.status_code}")
                break
                
            data = r.json()
            if not data or not isinstance(data, list):
                print("ℹ️ No more data returned from API.")
                break
                
            all_klines.extend(data)
            
            # Extract last candle's open timestamp
            last_ts = data[-1][0]
            
            # Prevent infinite loop if API returns the same time
            if last_ts == current_start:
                break
                
            current_start = last_ts + 1
            
            # Print feedback
            dt_str = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"✅ Fetched {len(data)} bars. Cumulative: {len(all_klines)} bars. Current progress: up to {dt_str}")
            
            # API rate limit safety sleep
            time.sleep(0.3)
            
        except Exception as e:
            print(f"❌ Exception occurred during request: {e}")
            break

    if not all_klines:
        print("❌ Download failed. No data collected.")
        return

    # Process raw lists into a structured DataFrame
    df_data = []
    for k in all_klines:
        df_data.append({
            'timestamp': datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
            'volume': float(k[5])
        })
        
    df = pd.DataFrame(df_data)
    
    # Drop duplicates in case of overlaps
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    # Save CSV
    filename = f"{symbol}_{interval}_{days}d.csv"
    filepath = os.path.join(os.getcwd(), filename)
    df.to_csv(filepath)
    
    print("-" * 80)
    print(f"🎉 DOWNLOAD SUCCESSFUL!")
    print(f" Saved {len(df):,} candles to: {filepath}")
    print(f" Price Range:  ${df['close'].iloc[0]:,.2f} ➡️ ${df['close'].iloc[-1]:,.2f}")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binance Futures Historical Data Downloader")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="USDT trading pair (e.g. BTCUSDT, ETHUSDT)")
    parser.add_argument("--interval", type=str, default="5m", help="Candle interval (e.g. 5m, 15m, 1h)")
    parser.add_argument("--days", type=int, default=90, help="Number of historical days to fetch")
    args = parser.parse_args()
    
    download_historical_klines(symbol=args.symbol, interval=args.interval, days=args.days)
