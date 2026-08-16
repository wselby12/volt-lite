# VOLT-Lite

VOLT-Lite is an automated Pump.fun momentum trader for Solana. It monitors Pump.fun bonding curves, scores momentum signals, and can execute trades through Pump.fun's swap API.

WARNING: Trading on memecoins and bonding curves is highly risky. Use at your own risk. This repository intentionally requires real credentials via environment variables. Do NOT commit private keys or secrets.

Features
- WebSocket programSubscribe-based monitoring of Pump.fun bonding curve accounts
- Signal extraction and VOLT scoring to detect momentum
- Automated buy/sell using Pump.fun swap API (simulated and validated before submit)
- Persistent SQLite storage of positions and events
- Risk controls: daily limits, per-hour limits, max open positions, kill switch
- Railway-compatible worker

Quickstart
1. Copy .env.example to .env and fill in values (never commit .env).
2. Install dependencies:
   pip install -r requirements.txt
3. Run:
   python -m app.main

Architecture
See app/ for modules: pump, strategy, trading, storage, and wiring in app.main

License: MIT
