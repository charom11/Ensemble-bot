# Weather-Ensemble Backtesting & Research Suite

This directory contains research models, parameter sweeps, portfolio simulations, and Monte Carlo probability forecasts developed for the **Weather-Ensemble 31-Model Trading AI**.

---

## Suite Directory & Script Reference

| Script | Purpose & Description |
| :--- | :--- |
| `backtest_365d.py` | 365-day 5-minute compounding backtest simulation with 1:2.5 Risk-to-Reward ratio and taker fee modeling. |
| `backtest_100x_compounding.py` | Geometric compounding performance test targeting 100x wallet expansion with dynamic ATR trailing stops. |
| `compounding_3pct_log.py` | Logarithmic progression tracker demonstrating 3% capital sizing curve and risk envelope. |
| `leverage_optimizer.py` | Evaluates Sharpe ratio, profit factor, and liquidation distance across 5x, 10x, 20x, 50x, and 100x leverage. |
| `loop_optimizer.py` | Grid search parameter sweep across consensus thresholds (20 to 31) and ATR multiples. |
| `master_production_optimizer.py` | Multi-pass strategy optimizer with 4-hour / 1-hour macro trend filter alignment and volume surge validation. |
| `monte_carlo_2026_2027.py` | 1,000-path bootstrap resampling Monte Carlo forecast with liquidity ceiling constraints. |
| `test_4_enhancements.py` | Evaluates 4 quantitative enhancements: Dynamic Model Weighting, Order Book Imbalance, Sentiment Guard, and Break-Even Taker Fee Lock. |
| `top10_portfolio_backtest.py` | Multi-asset portfolio backtest across the top 10 liquid cryptocurrencies. |
| `top10_improved_portfolio.py` | Top-10 asset portfolio test incorporating dynamic ATR trailing exits. |
| `top20_portfolio_backtest.py` | Top-20 cryptocurrency asset universe backtest. |
| `top20_realistic_capped_backtest.py` | Top-20 portfolio simulation with realistic Binance Futures liquidity caps and position sizing limits. |

---

## How to Run Any Backtest

```bash
# Run 365-day compounding backtest
python backtests/backtest_365d.py

# Run Master Strategy Optimizer
python backtests/master_production_optimizer.py

# Run Monte Carlo 1,000-path prediction
python backtests/monte_carlo_2026_2027.py
```
