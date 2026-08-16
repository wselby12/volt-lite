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
            async with session.post(PUMP_SWAP_API, json=payload, timeout=20) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    self.logger.error("swap_api_error", status=resp.status, body=text)
                    return None
                data = await resp.json()
                return data

    async def deserialize_and_simulate(self, client: AsyncClient, b64_tx: str) -> Optional[VersionedTransaction]:
        try:
            raw = base64.b64decode(b64_tx)
            tx = VersionedTransaction.deserialize(raw)
        except Exception as e:
            self.logger.error("deserialize_failed", error=str(e))
            return None

        # simulate
        try:
            # send base64 for simulation
            sim = await client.simulate_transaction(tx)
            if sim.get("error") or sim.get("value", {}).get("err"):
                self.logger.error("simulation_failed", result=sim)
                return None
        except Exception as e:
            self.logger.error("simulation_error", error=str(e))
            return None

        return tx

    async def sign_and_send(self, client: AsyncClient, tx: VersionedTransaction, private_key_env: str) -> Optional[str]:
        if not private_key_env:
            self.logger.error("no_private_key")
            return None
        # parse key: allow base58 or json array
        try:
            if private_key_env.strip().startswith("["):
                import json as _json
                arr = _json.loads(private_key_env)
                sk = bytes(arr)
            else:
                import base58
                sk = base58.b58decode(private_key_env)
            kp = Keypair.from_secret_key(sk)
        except Exception as e:
            self.logger.error("parse_key_failed", error=str(e))
            return None

        # sign
        try:
            tx.sign([kp])
            raw = tx.serialize()
            b64 = base64.b64encode(raw).decode()
            send_resp = await client.send_raw_transaction(raw)
            sig = send_resp.get("result")
            # confirm
            await client.confirm_transaction(sig)
            return sig
        except Exception as e:
            self.logger.error("send_failed", error=str(e))
            return None
