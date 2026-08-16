from dataclasses import dataclass
import os
from typing import Optional

@dataclass
class Config:
    SOLANA_RPC_URL: str
    SOLANA_WSS_URL: str
    SOLANA_PRIVATE_KEY: Optional[str]
    TRADING_ENABLED: bool
    KILL_SWITCH: bool
    BUY_AMOUNT_SOL: float
    MAX_OPEN_POSITIONS: int
    MAX_BUYS_PER_HOUR: int
    MAX_DAILY_BUY_SOL: float
    MAX_DAILY_LOSS_SOL: float
    MIN_VOLT_SCORE: int
    MIN_CURVE_PROGRESS: int
    MAX_ENTRY_CURVE_PROGRESS: int
    FORCE_EXIT_CURVE_PROGRESS: int
    SLIPPAGE_PCT: float
    STOP_LOSS_PCT: float
    TP1_PCT: float
    TP1_SELL_PCT: float
    TP2_PCT: float
    TP2_SELL_PCT: float
    TP3_PCT: float
    TP3_SELL_PCT: float
    TRAILING_STOP_PCT: float
    sqlite_path: str

    @staticmethod
    def _get_bool(name: str, default: str = "false") -> bool:
        val = os.getenv(name, default)
        return str(val).lower() in ("1", "true", "yes")

    @classmethod
    def from_env(cls) -> "Config":
        # required
        SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL")
        SOLANA_WSS_URL = os.getenv("SOLANA_WSS_URL")
        if not SOLANA_RPC_URL or not SOLANA_WSS_URL:
            raise SystemExit("SOLANA_RPC_URL and SOLANA_WSS_URL are required")

        return cls(
            SOLANA_RPC_URL=SOLANA_RPC_URL,
            SOLANA_WSS_URL=SOLANA_WSS_URL,
            SOLANA_PRIVATE_KEY=os.getenv("SOLANA_PRIVATE_KEY"),
            TRADING_ENABLED=cls._get_bool("TRADING_ENABLED", "false"),
            KILL_SWITCH=cls._get_bool("KILL_SWITCH", "false"),
            BUY_AMOUNT_SOL=float(os.getenv("BUY_AMOUNT_SOL", "0.01")),
            MAX_OPEN_POSITIONS=int(os.getenv("MAX_OPEN_POSITIONS", "2")),
            MAX_BUYS_PER_HOUR=int(os.getenv("MAX_BUYS_PER_HOUR", "6")),
            MAX_DAILY_BUY_SOL=float(os.getenv("MAX_DAILY_BUY_SOL", "0.2")),
            MAX_DAILY_LOSS_SOL=float(os.getenv("MAX_DAILY_LOSS_SOL", "0.1")),
            MIN_VOLT_SCORE=int(os.getenv("MIN_VOLT_SCORE", "78")),
            MIN_CURVE_PROGRESS=int(os.getenv("MIN_CURVE_PROGRESS", "65")),
            MAX_ENTRY_CURVE_PROGRESS=int(os.getenv("MAX_ENTRY_CURVE_PROGRESS", "92")),
            FORCE_EXIT_CURVE_PROGRESS=int(os.getenv("FORCE_EXIT_CURVE_PROGRESS", "94")),
            SLIPPAGE_PCT=float(os.getenv("SLIPPAGE_PCT", "3")),
            STOP_LOSS_PCT=float(os.getenv("STOP_LOSS_PCT", "25")),
            TP1_PCT=float(os.getenv("TP1_PCT", "40")),
            TP1_SELL_PCT=float(os.getenv("TP1_SELL_PCT", "25")),
            TP2_PCT=float(os.getenv("TP2_PCT", "80")),
            TP2_SELL_PCT=float(os.getenv("TP2_SELL_PCT", "25")),
            TP3_PCT=float(os.getenv("TP3_PCT", "150")),
            TP3_SELL_PCT=float(os.getenv("TP3_SELL_PCT", "25")),
            TRAILING_STOP_PCT=float(os.getenv("TRAILING_STOP_PCT", "30")),
            sqlite_path=os.getenv("SQLITE_PATH", "./volt_lite.sqlite3"),
        )
