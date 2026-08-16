import asyncio
import json
import base64
import traceback
from typing import Callable, Any
import websockets
from app.config import Config
from app.logger import setup_logging
from app.pump.constants import PUMP_PROGRAM_ID
from app.pump.curve import parse_progress_from_account, extract_reserves


class PumpListener:
    def __init__(self, cfg: Config, logger=None):
        self.cfg = cfg
        self.logger = logger or setup_logging(cfg)
        self.wss = cfg.SOLANA_WSS_URL
        self.program_id = PUMP_PROGRAM_ID
        self._backoff = 1
        self._max_backoff = 60
        self._ws = None

    async def run(self, on_update: Callable[[dict], Any]):
        """Main loop: maintain WebSocket connection with exponential backoff and forward candidate updates.
        on_update is an async callable accepting a dict with keys: pubkey, progress, reserves
        """
        while True:
            try:
                await self._connect(on_update)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error("RPC_ERROR", error=str(e), stack=traceback.format_exc())
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, self._max_backoff)
                self.logger.info("WS_RECONNECT", backoff=self._backoff)

    async def _connect(self, on_update: Callable[[dict], Any]):
        self.logger.info("connecting_wss", url=self.wss)
        async with websockets.connect(self.wss, ping_interval=20) as ws:
            self._ws = ws
            self._backoff = 1
            # subscribe to program using programSubscribe
            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "programSubscribe",
                "params": [
                    self.program_id,
                    {
                        "encoding": "base64",
                        # Filters can be added here to reduce noise. Without the official layout we keep it minimal.
                        # Example placeholder: "filters": [{"dataSize": 200}]
                    },
                ],
            }
            await ws.send(json.dumps(req))
            self.logger.info("subscribed_program", program=self.program_id)

            async for message in ws:
                try:
                    data = json.loads(message)
                except Exception:
                    self.logger.error("malformed_ws_message")
                    continue
                # notifications have a params.result.value.account.data field
                params = data.get("params") or {}
                result = params.get("result") or {}
                value = result.get("value") or {}
                account = value.get("account") or {}
                raw = account.get("data")
                if raw and isinstance(raw, list) and len(raw) >= 1:
                    b64 = raw[0]
                    try:
                        raw_bytes = base64.b64decode(b64)
                    except Exception:
                        self.logger.error("ws_base64_decode_failed")
                        continue
                    try:
                        progress = parse_progress_from_account(raw_bytes)
                        reserves = extract_reserves(raw_bytes)
                        update = {
                            "pubkey": value.get("pubkey") or result.get("pubkey"),
                            "progress": progress,
                            "reserves": reserves,
                        }
                        # Only forward candidates near threshold
                        if progress >= self.cfg.MIN_CURVE_PROGRESS:
                            try:
                                await on_update(update)
                            except Exception:
                                self.logger.error("on_update_handler_error", trace=traceback.format_exc())
                    except Exception as e:
                        self.logger.error("process_account_failed", error=str(e))

