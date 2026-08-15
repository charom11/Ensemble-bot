# Weather-Ensemble 31-Model Crypto AI Trading System

> **"No finance degree. No Wall Street. Just one idea borrowed from meteorologists."**  
> Instead of trusting a single indicator or prediction, the system runs **31 autonomous model simulations** on 5-minute crypto markets and only enters a trade when **29 or more models (≥ 93.5%) agree**.  
> **No consensus? No trade.**

---

## Concept & Architecture

In numerical weather prediction, meteorologists use **Ensemble Forecasting** (spaghetti models) to run multiple simulations with slightly varied initial conditions, model structures, or parameters. When 90%+ of the weather trajectories overlap, confidence in a storm path or cold front is exceptionally high.

This trading system applies the exact same concept to 5-minute Binance Futures cryptocurrency trading (`BTC`, `ETH`, `SOL`, `BNB`, `XRP`, `ADA`, `DOGE`, `AVAX`, `LINK`, `SUI`, `NEAR`):

1. **31 Autonomous Sub-Models**:
   - **Trend Paradigm (9 Models)**: Fast/Slow EMAs, MACD Acceleration, Supertrend Alpha (3,10) & Fast (2,7), Donchian Channels (20 & 50), Parabolic SAR, Ichimoku Cloud.
   - **Momentum & Oscillator Paradigm (7 Models)**: RSI(14), Stochastic RSI, Williams %R, CCI (20), Rate of Change (ROC 10), RVI, Awesome Oscillator.
   - **Volatility & Envelope Paradigm (5 Models)**: Bollinger Band %B, BB Squeeze, Keltner Channel, ATR Volatility Expansion, Chaikin Volatility.
   - **Microstructure & VWAP Paradigm (4 Models)**: Intraday VWAP, Anchored VWAP Delta, Volume Force Index (VFI), Order Flow Delta.
   - **Machine Learning & Noise-Perturbed Models (6 Models)**: XGBoost Trees, LSTM Neural Ensemble, Markov Chain State Transition, Kalman Filter Trajectory, Monte Carlo Drift, Weather Spaghetti Core.

2. **Strict Consensus Policy ($\ge 29 / 31$ Models)**:
   - Evaluated on every 5-minute candlestick close.
   - **LONG ENTRY**: $\ge 29$ models output `BULLISH`.
   - **SHORT ENTRY**: $\ge 29$ models output `BEARISH`.
   - **HOLD / NO TRADE**: Consensus $< 29$. Filters out false signals and ranging chop.

3. **Risk Management & Exit Automation**:
   - **Dynamic ATR Sizing**: Stop Loss at $1.0\times\text{ATR}$ and Take Profit at $2.5\times\text{ATR}$ (1:2.5 RR Ratio).
   - **Break-Even Taker Fee Lock**: Once price moves $+1.0\times\text{ATR}$ favorably, trailing stop locks in profit covering roundtrip taker fees.

---

## Clean Repository Structure

```
Bot2/
├── .env                              # Binance API keys & Telegram bot tokens
├── .gitignore                        # Git exclusion rules (venv, cache, data)
├── README.md                         # Project documentation and quickstart
├── requirements.txt                  # Python dependencies (pandas, numpy, ccxt, requests)
├── server.py                         # Full-stack Web Dashboard server & Bot REST API
├── weather_ensemble_bot.py           # Core live trading engine & Telegram Command & Control
├── download_historical_data.py       # Binance Futures historical kline downloader
├── backtest_historical.py            # High-fidelity CSV historical backtest engine
├── meteo31_consensus_strategy.pine   # TradingView Pine Script strategy
├── index.html                        # Web dashboard user interface
├── style.css                         # Dark glassmorphic styling & weather radar visualizer
├── app.js                            # Frontend engine, Binance WebSocket & 31-model calculator
└── backtests/                        # Comprehensive research & simulation suite
    ├── README.md                     # Guide to all backtest & optimizer scripts
    ├── backtest_365d.py              # 365-day compounding model
    ├── backtest_100x_compounding.py  # 100x compounding simulation
    ├── compounding_3pct_log.py       # 3% compounding logarithmic progression
    ├── leverage_optimizer.py         # Dynamic leverage optimizer
    ├── loop_optimizer.py             # Strategy parameter grid sweep
    ├── master_production_optimizer.py# Master multi-pass strategy optimizer
    ├── monte_carlo_2026_2027.py      # Bootstrap resampling Monte Carlo forecast
    ├── test_4_enhancements.py        # 4-factor enhancement evaluator
    ├── top10_portfolio_backtest.py   # Top-10 asset portfolio backtest
    ├── top10_improved_portfolio.py   # Top-10 improved strategy test
    ├── top20_portfolio_backtest.py   # Top-20 asset portfolio backtest
    └── top20_realistic_capped_backtest.py # Top-20 realistic liquidity-capped backtest
```

---

## How to Run

### 1. Web Dashboard & Bot Control Server
Serve the interactive web dashboard with live Binance WebSocket feed and bot control:

```bash
# Start backend API server & web dashboard (Port 8080)
python server.py
```
Open **`http://localhost:8080`** in your browser. From here you can:
- View live 31-model spaghetti trajectories for BTC, ETH, SOL, XRP, SUI, etc.
- Calculate 3% capital margin and dynamic ATR targets.
- Start and stop the live trading bot with real-time log streaming.

---

### 2. Standalone Live Python Trading Bot & Telegram C2

Configure your `.env` file:
```env
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_NOTIFICATIONS=true
```

Run in live monitor mode (Paper / Alerts):
```bash
python weather_ensemble_bot.py --live --threshold 29
```

Run in live Binance Futures execution mode:
```bash
python weather_ensemble_bot.py --trade-live --leverage 20 --sizing-mode margin --margin-pct 0.03
```

#### Interactive Telegram Remote Commands
- `/status` — View current account balance, active positions, leverage, and engine state.
- `/models` — Real-time 31-model vote breakdown across monitored coins.
- `/threshold 29` — Dynamically update the consensus threshold on the fly.
- `/leverage 20` — Dynamically adjust the futures leverage factor.
- `/pause` / `/resume` — Instantly pause or resume autonomous trade execution.

---

### 3. Historical Data Download & Backtesting

1. **Download real historical Binance Futures kline data**:
```bash
python download_historical_data.py --symbol BTCUSDT --interval 5m --days 90
```

2. **Execute high-fidelity backtest on downloaded CSV**:
```bash
python backtest_historical.py --csv BTCUSDT_5m_90d.csv --threshold 29 --risk 0.03 --leverage 20
```

---

### 4. Running Research & Optimizer Sweeps

Explore the `backtests/` directory:
```bash
# Run 1,000-path Monte Carlo probability distribution
python backtests/monte_carlo_2026_2027.py

# Run Master Multi-Pass Optimizer
python backtests/master_production_optimizer.py
```
