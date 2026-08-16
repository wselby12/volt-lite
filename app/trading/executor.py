import asyncio
import time
from typing import Dict, Any
from app.config import Config
from app.logger import setup_logging
from pump.swap import SwapClient
from trading.positions import PositionManager
from storage.database import Database
from strategy.entry import EntryManager
from app.pump.constants import SOL_MINT
from solana.rpc.async_api import AsyncClient

class TradingExecutor:
    def __init__(self, cfg: Config, db: Database, logger=None):
        self.cfg = cfg
        self.logger = logger or setup_logging(cfg)
        self.db = db
        self.swap = SwapClient(cfg, self.logger)
        self.positions = PositionManager(db, self.logger)
        self.entry = EntryManager(cfg, self.logger)
        self.client = AsyncClient(cfg.SOLANA_RPC_URL)
        self._locks = {}
        self._buy_history = []  # timestamps of buys

    async def run(self):
        # periodic tasks like checking open positions
        while True:
            try:
                await asyncio.sleep(5)
                await self.positions.reload_open_positions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("executor_tick_error", error=str(e))

    async def on_curve_update(self, update: Dict[str, Any]):
        # Called by listener when curve progress crosses threshold
        pubkey = update.get("pubkey")
        progress = update.get("progress")
        reserves = update.get("reserves")
        # compute entry features
        result = self.entry.on_update(pubkey, reserves, progress)
        score = result.get("score")
        self.logger.info("SCORE_UPDATE", pubkey=pubkey, score=score, progress=progress)
        if score >= self.cfg.MIN_VOLT_SCORE:
            await self._attempt_entry(pubkey, progress, result)

    async def _attempt_entry(self, pubkey: str, progress: float, result: Dict[str, Any]):
        # risk checks
        if self.cfg.KILL_SWITCH:
            self.logger.info("KILL_SWITCH", action="block_entry")
            return
        if not self.cfg.TRADING_ENABLED:
            self.logger.info("TRADING_DISABLED", action="skip_submit")
            return
        # per-mint lock
        if self._locks.get(pubkey):
            self.logger.info("duplicate_candidate", pubkey=pubkey)
            return
        self._locks[pubkey] = True
        try:
            # simple checks
            if progress >= self.cfg.MAX_ENTRY_CURVE_PROGRESS:
                self.logger.info("too_close_to_graduation", pubkey=pubkey, progress=progress)
                return
            # buy limits
            now = time.time()
            # hourly buys
            one_hour = 3600
            buys_last_hour = [t for t in self._buy_history if now - t < one_hour]
            if len(buys_last_hour) >= self.cfg.MAX_BUYS_PER_HOUR:
                self.logger.info("hourly_limit", count=len(buys_last_hour))
                return
            # open positions
            open_count = await self.positions.open_count()
            if open_count >= self.cfg.MAX_OPEN_POSITIONS:
                self.logger.info("max_open_positions", open_count=open_count)
                return
            # prevent duplicate buys
            if await self.positions.has_mint(pubkey):
                self.logger.info("already_holding", pubkey=pubkey)
                return

            # build swap via Pump API
            lamports = int(self.cfg.BUY_AMOUNT_SOL * 1_000_000_000)
            user = self.client._provider._wallet.public_key if hasattr(self.client, "_provider") else None
            # user/fpayer should come from env wallet public key; fallback to None
            wallet_pub = None
            if self.cfg.SOLANA_PRIVATE_KEY:
                # try to derive public key without exposing private key
                from base58 import b58decode
                from solana.keypair import Keypair
                try:
                    sk = self.cfg.SOLANA_PRIVATE_KEY
                    if sk.strip().startswith("["):
                        import json as _json
                        arr = _json.loads(sk)
                        skb = bytes(arr)
                    else:
                        skb = b58decode(sk)
                    kp = Keypair.from_secret_key(skb)
                    wallet_pub = str(kp.public_key)
                except Exception:
                    wallet_pub = None
            if not wallet_pub:
                self.logger.error("missing_wallet_pubkey")
                return

            self.logger.info("ENTRY_SIGNAL", pubkey=pubkey, score=result.get("score"))

            swap = await self.swap.build_swap(SOL_MINT, pubkey, lamports, wallet_pub, wallet_pub, self.cfg.SLIPPAGE_PCT)
            if not swap or not swap.get("transaction"):
                self.logger.error("swap_build_failed", resp=swap)
                return
            tx_b64 = swap["transaction"]
            tx = await self.swap.deserialize_and_simulate(self.client, tx_b64)
            if not tx:
                self.logger.info("simulation_failed", pubkey=pubkey)
                return
            # sign and send
            sig = await self.swap.sign_and_send(self.client, tx, self.cfg.SOLANA_PRIVATE_KEY)
            if not sig:
                self.logger.error("buy_send_failed", pubkey=pubkey)
                return
            # record
            await self.positions.add_position({
                "mint": pubkey,
                "entry_ts": int(time.time()),
                "sol_spent": self.cfg.BUY_AMOUNT_SOL,
                "tokens_received": None,
                "entry_price": None,
                "highest_value": None,
                "curve_progress": progress,
                "volt_score": result.get("score"),
                "tx_sig": sig,
            })
            self._buy_history.append(time.time())
            self.logger.info("BUY_SUBMITTED", pubkey=pubkey, sig=sig)
        finally:
            self._locks.pop(pubkey, None)
