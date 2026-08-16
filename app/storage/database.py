import aiosqlite
import time
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        # enable WAL for concurrency
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self._init()

    async def _init(self):
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                mint TEXT,
                entry_ts INTEGER,
                sol_spent REAL,
                tokens_received REAL,
                entry_price REAL,
                highest_value REAL,
                curve_progress REAL,
                volt_score INTEGER,
                tx_sig TEXT,
                closed INTEGER DEFAULT 0,
                exit_ts INTEGER,
                exit_tx TEXT
            )
            """
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                ts INTEGER,
                mint TEXT,
                side TEXT,
                sol_amount REAL,
                token_amount REAL,
                tx_sig TEXT
            )
            """
        )
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def add_trade(self, mint: str, side: str, sol_amount: float, token_amount: float, tx_sig: str):
        ts = int(time.time())
        await self.conn.execute(
            "INSERT INTO trades (ts, mint, side, sol_amount, token_amount, tx_sig) VALUES (?,?,?,?,?,?)",
            (ts, mint, side, sol_amount, token_amount, tx_sig),
        )
        await self.conn.commit()

    async def get_daily_buy_total(self) -> float:
        # sum sol_amount for buys in the last 24 hours
        since = int(time.time()) - 24 * 3600
        async with self.conn.execute("SELECT COALESCE(SUM(sol_amount),0) FROM trades WHERE side='buy' AND ts >= ?", (since,)) as cur:
            row = await cur.fetchone()
            return float(row[0] or 0.0)

    async def mark_position_closed(self, position_id: int, exit_tx: str):
        ts = int(time.time())
        await self.conn.execute("UPDATE positions SET closed=1, exit_ts=?, exit_tx=? WHERE id=?", (ts, exit_tx, position_id))
        await self.conn.commit()

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        async with self.conn.execute("SELECT * FROM positions WHERE closed=0") as cur:
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            results = []
            for row in rows:
                results.append({cols[i]: row[i] for i in range(len(cols))})
            return results
