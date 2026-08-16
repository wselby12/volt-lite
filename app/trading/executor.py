import asyncio
import time
from typing import Dict, Any
from app.config import Config
from app.logger import setup_logging
from app.pump.swap import SwapClient
from app.trading.positions import PositionManager
from app.storage.database import Database
from app.strategy.entry import EntryManager
from app.strategy.exits import ExitManager
from app.pump.constants import SOL_MINT
from solana.rpc.async_api import AsyncClient
from base58 import b58decode
from solana.keypair import Keypair

class TradingExecutor:
    def __init__(self, cfg: Config, db: Database, logger=None):
        self.cfg = cfg
        self.logger = logger or setup_logging(cfg)
        self.db = db
        self.swap = SwapClient(cfg, self.logger)
        self.positions = PositionManager(db, self.logger)
        self.entry = EntryManager(cfg, self.logger)
        self.exit_mgr = ExitManager(cfg, self.logger)
        self.client = AsyncClient(cfg.SOLANA_RPC_URL)
        self._locks = {}
        self._buy_history = []  # timestamps of buys

    async def run(self):
        # periodic tasks like checking open positions
        while True:
            try:
                await asyncio.sleep(5)
                await self._check_positions()
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

            # daily spend check
            daily_spend = await self.db.get_daily_buy_total()
            if daily_spend + self.cfg.BUY_AMOUNT_SOL > self.cfg.MAX_DAILY_BUY_SOL:
                self.logger.info("daily_limit_reached", daily_spend=daily_spend)
                return

            # build swap via Pump API
            lamports = int(self.cfg.BUY_AMOUNT_SOL * 1_000_000_000)

            wallet_pub = self._derive_pubkey_from_env()
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

    def _derive_pubkey_from_env(self) -> str | None:
        sk = self.cfg.SOLANA_PRIVATE_KEY
        if not sk:
            return None
        try:
            if sk.strip().startswith("["):
                import json as _json
                arr = _json.loads(sk)
                skb = bytes(arr)
            else:
                skb = b58decode(sk)
            kp = Keypair.from_secret_key(skb)
            return str(kp.public_key)
        except Exception:
            return None

    async def _check_positions(self):
        # load open positions and evaluate exit conditions
        open_positions = await self.db.get_open_positions()
        for pos in open_positions:
            try:
                # refresh market estimate: TODO - derive current value via on-chain queries or price oracles
                # For now we use tokens_received * 0 as placeholder (needs real pricing)
                pos = dict(pos)
                pos["current_value"] = pos.get("highest_value") or pos.get("entry_price") or 0
                action = self.exit_mgr.evaluate_position(pos)
                if action:
                    await self._execute_exit(pos, action)
            except Exception as e:
                self.logger.error("position_check_error", error=str(e))

    async def _execute_exit(self, position: Dict[str, Any], action: Dict[str, Any]):
        mint = position.get("mint")
        if not mint:
            return
        # per-mint lock
        if self._locks.get(mint):
            return
        self._locks[mint] = True
        try:
            # build sell via Pump API (swap input=TOKEN, output=SOL)
            # amount: if sell_all -> use tokens_received from position; if partial -> calculate percent
            tokens = position.get("tokens_received") or 0
            if action.get("action") == "sell_all":
                amount = str(int(tokens))
            elif action.get("action") == "sell_partial":
                sell_pct = action.get("sell_pct", 0) / 100.0
                amount = str(int(tokens * sell_pct))
            else:
                return

            wallet_pub = self._derive_pubkey_from_env()
            if not wallet_pub:
                self.logger.error("missing_wallet_pubkey")
                return

            swap = await self.swap.build_swap(mint, SOL_MINT, amount, wallet_pub, wallet_pub, self.cfg.SLIPPAGE_PCT)
            if not swap or not swap.get("transaction"):
                self.logger.error("sell_build_failed", resp=swap)
                return
            tx_b64 = swap["transaction"]
            tx = await self.swap.deserialize_and_simulate(self.client, tx_b64)
            if not tx:
                self.logger.info("sell_simulation_failed", pubkey=mint)
                return
            sig = await self.swap.sign_and_send(self.client, tx, self.cfg.SOLANA_PRIVATE_KEY)
            if not sig:
                self.logger.error("sell_send_failed", pubkey=mint)
                return
            await self.db.mark_position_closed(position.get("id"), sig)
            self.logger.info("SELL_SUBMITTED", mint=mint, sig=sig, reason=action.get("reason"))
        finally:
            self._locks.pop(mint, None)
