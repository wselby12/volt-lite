import aiohttp
import base64
import json
import asyncio
from solana.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.keypair import Keypair
from app.pump.constants import PUMP_SWAP_API, SOL_MINT
from app.logger import setup_logging
from typing import Optional
import os


class SwapClient:
    def __init__(self, cfg, logger=None):
        self.cfg = cfg
        self.logger = logger or setup_logging(cfg)

    async def build_swap(self, input_mint: str, output_mint: str, amount: int, user: str, fee_payer: str, slippage_pct: float):
        payload = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "user": user,
            "feePayer": fee_payer,
            "encoding": "base64",
            "slippagePct": slippage_pct,
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(PUMP_SWAP_API, json=payload, timeout=20) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        self.logger.error("swap_api_error", status=resp.status, body=text)
                        return None
                    data = json.loads(text)
                    return data
            except asyncio.TimeoutError:
                self.logger.error("swap_api_timeout")
                return None
            except Exception as e:
                self.logger.error("swap_api_exception", error=str(e))
                return None

    async def deserialize_and_simulate(self, client: AsyncClient, b64_tx: str) -> Optional[VersionedTransaction]:
        try:
            raw = base64.b64decode(b64_tx)
            tx = VersionedTransaction.deserialize(raw)
        except Exception as e:
            self.logger.error("deserialize_failed", error=str(e))
            return None

        # simulate
        try:
            # the RPC expects base64-encoded transaction for simulation input
            sim = await client.simulate_transaction(tx)
            if sim is None:
                self.logger.error("simulation_none_response")
                return None
            # Check for errors in returned structure (compatibility across RPCs may vary)
            val = sim.get("value") if isinstance(sim, dict) else None
            if isinstance(val, dict) and val.get("err"):
                self.logger.error("simulation_failed", result=sim)
                return None
        except Exception as e:
            self.logger.error("simulation_error", error=str(e))
            return None

        return tx

    def _load_keypair_from_env(self, private_key_env: str) -> Optional[Keypair]:
        if not private_key_env:
            return None
        try:
            sk = private_key_env.strip()
            if sk.startswith("["):
                import json as _json
                arr = _json.loads(sk)
                skb = bytes(arr)
            else:
                # assume base58
                import base58
                skb = base58.b58decode(sk)
            kp = Keypair.from_secret_key(skb)
            return kp
        except Exception as e:
            self.logger.error("parse_key_failed", error=str(e))
            return None

    async def sign_and_send(self, client: AsyncClient, tx: VersionedTransaction, private_key_env: str) -> Optional[str]:
        kp = self._load_keypair_from_env(private_key_env)
        if not kp:
            self.logger.error("no_private_key")
            return None

        # Sign the transaction with the single keypair
        try:
            # VersionedTransaction.sign expects a list of Signer-like objects
            tx.sign([kp])
            raw = tx.serialize()
            # send raw transaction bytes
            send_resp = await client.send_raw_transaction(raw)
            if not send_resp:
                self.logger.error("send_raw_no_response")
                return None
            sig = send_resp.get("result") or send_resp.get("signature")
            # confirm (best-effort)
            try:
                if sig:
                    await client.confirm_transaction(sig)
            except Exception:
                self.logger.info("confirm_failed_but_ignoring")
            return sig
        except Exception as e:
            self.logger.error("send_failed", error=str(e))
            return None
