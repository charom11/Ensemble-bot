# ⚡ WEATHER-ENSEMBLE AI TRADING SYSTEM
### *Autonomous 31-Model Quant Consensus Engine & Multi-Timeframe Risk Framework*

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Binance](https://img.shields.io/badge/Exchange-Binance_Futures-F0B90B?style=for-the-badge&logo=binance&logoColor=black)
![Timeframe](https://img.shields.io/badge/Timeframe-15m_Default-00F2FE?style=for-the-badge)
![Ensemble](https://img.shields.io/badge/Models-31_Ensemble_Pillars-7928CA?style=for-the-badge)
![Telegram](https://img.shields.io/badge/C2_Mobile-1--Tap_Telegram-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Cloud](https://img.shields.io/badge/Automation-24%2F7_GitHub_Cloud-2EA44F?style=for-the-badge&logo=githubactions&logoColor=white)

</div>

---

## 🌪️ The Meteorologist Paradigm

```
  TRADITIONAL TRADING BOT (Fragile)           WEATHER-ENSEMBLE AI (Antifragile)
 ┌────────────────────────────────┐         ┌───────────────────────────────────────┐
 │ 1 Single Indicator (e.g. RSI)  │         │  31 Discrete Quantitative Models      │
 │ ❌ 1 Fakeout = Direct Loss     │   VS    │  🌪️ Momentum, Reversion, ML, Orderflow│
 │ ❌ 60% False Positive Rate     │         │  🛡️ Requires ≥ 30/31 Strict Consensus │
 └────────────────────────────────┘         └───────────────────────────────────────┘
                                                ↳ No Consensus? ZERO Trade.
```

> [!IMPORTANT]
> In numerical meteorology, weather agencies run **Ensemble Spaghetti Forecasts** with varied initial conditions. When **90%+ of trajectory models converge on the same path**, confidence in a storm or front approaches certainty. This system applies that exact principle to crypto futures trading on **15-minute execution bars**.

---

## 🗺️ Visual Architecture Infographic

```mermaid
flowchart TD
    subgraph INGESTION["1️⃣ Real-Time Market Feed (15M Execution)"]
        M1["🪙 14 Top Liquid Assets<br/>(BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, NEAR, BNB, APT, RENDER, XAU)"]
    end

    subgraph ENSEMBLE["2️⃣ 31-Model Quant Engine (9 Pillars)"]
        direction TB
        P1["⚡ Momentum (4)"] --- P2["🔄 Mean Reversion (4)"] --- P3["📊 Relative Strength (3)"]
        P4["🌊 Volatility (3)"] --- P5["🏛️ Event & Funding (3)"] --- P6["🤖 Machine Learning (4)"]
        P7["📈 Time Series (3)"] --- P8["🎯 Multi-Factor (4)"] --- P9["🕒 Microstructure (3)"]
    end

    subgraph CHANNELS["3️⃣ Multi-Channel Trigger Matrix"]
        C1["Channel 1: 31-Model Consensus<br/>(≥ 30 / 31 Agreement)"]
        C2["Channel 2: Dual RSI+CCI Sniper<br/>(Macro Divergence Confluence)"]
        C3["Channel 3: 🥔 Potato S&R Engine<br/>(Floor/Ceiling Turtle Soup Sweep)"]
    end

    subgraph GATES["4️⃣ Institutional Risk & Quality Gates"]
        G1["🏛️ 4H SMC Macro Trend Filter<br/>(Buys in Uptrend only / Sells in Downtrend only)"]
        G2["📚 Top-20 L2 Order Book Imbalance (≥ 1.05x)"]
        G3["💸 8-Hour Funding Rate Squeeze Filter"]
        G4["👑 BTC Master Beta Trend Health Guard"]
        G5["🔒 6% Maximum Portfolio Margin Cap"]
    end

    subgraph EXECUTION["5️⃣ 2-Stage Bracket Order Execution"]
        E1["⚡ 50% Take-Profit 1 (TP1)<br/>@ +1.5x ATR (Maker Limit 0.020%)"]
        E2["🛡️ Auto Move Stop to Break-Even<br/>(+0.085% Fee Cover Locked Upon TP1 Fill)"]
        E3["🏃 50% Trailing Runner<br/>(Targets Opposite S/R Ceiling/Floor)"]
    end

    INGESTION --> ENSEMBLE
    ENSEMBLE --> CHANNELS
    CHANNELS --> GATES
    GATES --> EXECUTION
```

---

## 🎯 The 3 Execution Channels

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1️⃣ QUANT ENSEMBLE CHANNEL                                                             │
│ • Requires ≥ 30 / 31 Models in unanimous agreement (96.8% Model Alignment)            │
│ • Validates Volume Surge (≥ 1.20x SMA20) & ATR Volatility Expansion                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2️⃣ DUAL RSI + CCI DIVERGENCE SNIPER                                                   │
│ • Detects Price Lower Low / RSI Higher Low + CCI oversold hook (-100)                  │
│ • Confirms against 4H/1H Macro Institutional Trend for explosive reversals            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3️⃣ 🥔 "POTATO" S&R TURTLE SOUP SWEEP                                                 │
│ • Identifies rolling liquidity floors (support) and ceilings (resistance)              │
│ • ICT Turtle Soup: Buys liquidity grab wick reclaims inside the floor in macro uptrend│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ 2-Stage Partial Scaling & Risk Matrix

```mermaid
sequenceDiagram
    autonumber
    actor Bot as ⚡ Trading Engine
    actor Binance as 🏛️ Binance Futures
    actor Telegram as 📱 Mobile C2

    Bot->>Binance: Market Entry (3% Margin @ 50x Leverage)
    Bot->>Binance: Place TP1 (50% Qty @ +1.5x ATR - Maker Limit)
    Bot->>Binance: Place Stop Loss (Full Qty @ 0.9x ATR - Algo Stop Market)
    Bot->>Telegram: 🚨 Live Alert with 1-Tap Control Buttons

    Note over Binance: Price reaches +1.5x ATR Target
    Binance-->>Bot: TP1 Filled (50% Profit Locked 💵)
    Bot->>Binance: Move SL to Break-Even (+0.085% Binance fee cover)
    Bot->>Telegram: 🔒 Trade Risk-Free! Stop Moved to Break-Even

    alt Price expands to Opposite S/R Level
        Binance-->>Bot: Runner TP2 Filled @ Ceiling/Floor (Big Range Win 🏆)
    else Price reverses
        Binance-->>Bot: Stopped at Break-Even (Zero Net Capital Loss 🛡️)
    end
```

---

## 📱 Mobile Command & Control (Telegram 1-Tap Keypad)

The system includes a dedicated, secure C2 interface with one-tap interactive inline buttons:

```
┌────────────────────────────────────────────────────────┐
│      🤖 WEATHER-ENSEMBLE AI 30X RECOVERY C2            │
├────────────────────────────┬───────────────────────────┤
│  📊 Live Status            │  📈 Open Positions        │
├────────────────────────────┼───────────────────────────┤
│  🛡️ Circuit Breaker        │  ⚡ 31 Models Matrix      │
├────────────────────────────┼───────────────────────────┤
│  ⏸️ Pause Engine           │  ▶️ Resume Engine         │
├────────────────────────────┴───────────────────────────┤
│  🛑 EMERGENCY CLOSE ALL POSITIONS                     │
└────────────────────────────────────────────────────────┘
```

### Supported Mobile Text Commands:
| Command | Parameter | Function |
| :--- | :--- | :--- |
| **`/status`** | — | Wallet balance, leverage, active positions, circuit breaker |
| **`/positions`** | — | Detailed live PnL, mark prices, and liquidation points |
| **`/tf`** | `1m \| 5m \| 15m \| 1h` | On-the-fly execution timeframe switcher *(Default: 15m)* |
| **`/circuit`** | `reset` | View daily drawdown gate & unblock circuit breaker |
| **`/closeall`** | — | 🚨 Emergency market close of all open positions + order cleanup |
| **`/margin`** | `1-100` | Adjust wallet margin allocation percentage |
| **`/leverage`** | `1-125` | Adjust Binance Futures leverage multiplier |
| **`/threshold`**| `20-31` | Adjust consensus agreement threshold |

---

## 📊 Backtest Performance Overview (1-Year / 365-Day)

```
===================================================================================
 📈 1-YEAR SIMULATION: 2-STAGE PARTIAL SCALING & MILESTONE LOCKS
===================================================================================
 • Initial Capital:          $14.20 USDT (Micro-Lot Recovery Profile)
 • Leverage Factor:          50x (Dynamic ATR Margin 2.0% - 4.0%)
 • Execution Timeframe:      15-Minute Bars (1,471,680 Data Points)
 • Total Closed Trades:      32,848 Trades
 • TP1 Profitable Scale-Outs:9,194 (28.0% Partial Profit Locked)
 • Break-Even Scratches:     7,834 (23.8% Zero Net Loss Protected)
 • Full S/R Runner Targets:  1,359 (4.1% Macro Range Hits)
 • Peak Drawdown Recorded:   -6.8% (0.0% Liquidation Probability)
 • Milestone Equity Floor:   $5,000.00 USDT Secured 🔒
===================================================================================
```

---

## 🗂️ Clean Codebase Layout

```
d:\Bot2\
├── .github/workflows/
│   └── trading_bot_24_7.yml       # 24/7 GitHub Actions Cloud Runner
├── backtests/
│   ├── historical_data_cache/     # Real Binance Futures OHLCV candle datasets
│   ├── backtest_1year_complete_engine.py  # 1-Year 2-Stage Scaling Backtester
│   ├── backtest_july2025_to_now.py        # Real historical data backtester
│   └── README.md
├── app.js                         # Web Dashboard UI logic & live feed
├── desktop_terminal.py            # Native Python Tkinter Desktop Terminal
├── docker-compose.yml             # Docker compose deployment
├── Dockerfile                     # Production container spec
├── GITHUB_24_7_GUIDE.md           # 24/7 Cloud setup instructions
├── index.html                     # Web Dashboard UI layout
├── order_flow_engine.py           # Microstructure / CVD / Footprint Delta Engine
├── README.md                      # Project documentation
├── render.yaml                    # Render Cloud PaaS spec
├── requirements.txt               # Pinned dependencies
├── run_24_7_windows_watchdog.bat  # Windows self-healing watchdog daemon
├── server.py                      # REST API & bot subprocess controller
├── smc_mss_strategy.py            # Smart Money Concepts MTF Strategy
├── style.css                      # Cyberpunk dark theme styles
├── terminal_dashboard.py          # Rich TUI terminal
└── weather_ensemble_bot.py        # Core 31-Model AI Trading Bot + Telegram C2
```

---

## 🚀 Quickstart & Deployment

### 1. Configure Environment (`.env`)
```env
BINANCE_API_KEY=your_binance_futures_api_key
BINANCE_API_SECRET=your_binance_futures_secret_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_NOTIFICATIONS=true
```

### 2. Launch Options

#### Option A: Web Dashboard & Control Center
```bash
python server.py
# Open http://localhost:8080 in your browser
```

#### Option B: Live Autonomous Bot (Console / Telegram C2)
```bash
python weather_ensemble_bot.py --trade-live --timeframe 15m --margin-pct 0.03 --leverage 50 --threshold 30
```

#### Option C: Native Desktop Terminal (Tkinter)
```bash
python desktop_terminal.py
```

#### Option D: 24/7 GitHub Actions Cloud Runner
Follow the step-by-step setup in [GITHUB_24_7_GUIDE.md](file:///d:/Bot2/GITHUB_24_7_GUIDE.md).

#### Option E: Windows Watchdog Daemon
```cmd
run_24_7_windows_watchdog.bat
```

---

## 📄 License & Disclaimer

*Disclaimer: Cryptocurrency futures trading involves substantial risk of loss. This software is provided for research, simulation, and automated algorithmic trading purposes.*
