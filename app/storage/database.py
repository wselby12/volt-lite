import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
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
                closed INTEGER DEFAULT 0
            )
            """
        )
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()
