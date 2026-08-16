import aiosqlite
from typing import Dict, Any


class PositionManager:
    def __init__(self, db, logger):
        self.db = db
        self.logger = logger

    async def reload_open_positions(self):
        # placeholder - in this version we rely directly on db.get_open_positions()
        return await self.db.get_open_positions()

    async def open_count(self) -> int:
        async with self.db.conn.execute("SELECT COUNT(*) FROM positions WHERE closed=0") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    async def has_mint(self, mint: str) -> bool:
        async with self.db.conn.execute("SELECT 1 FROM positions WHERE mint=? AND closed=0 LIMIT 1", (mint,)) as cur:
            row = await cur.fetchone()
            return bool(row)

    async def add_position(self, pos: Dict[str, Any]):
        await self.db.conn.execute(
            "INSERT INTO positions (mint, entry_ts, sol_spent, tokens_received, entry_price, highest_value, curve_progress, volt_score, tx_sig, closed) VALUES (?,?,?,?,?,?,?,?,?,0)",
            (pos.get("mint"), pos.get("entry_ts"), pos.get("sol_spent"), pos.get("tokens_received"), pos.get("entry_price"), pos.get("highest_value"), pos.get("curve_progress"), pos.get("volt_score"), pos.get("tx_sig")),
        )
        await self.db.conn.commit()
