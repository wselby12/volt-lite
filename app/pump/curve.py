import math
from typing import Dict, Any

# Utilities to interpret bonding curve account data.
# This implementation is intentionally simplified: Pump.fun private layout is not public in this simple version.
# We'll assume account.data contains bytes we can parse for reserves and supplies. In real implementation, use proper layout.


def parse_progress_from_account(data: bytes) -> float:
    """Return approximate graduation percentage (0-100).
    This is a stub heuristic: use lengths and some bytes to estimate. Replace with real parsing for production.
    """
    if not data:
        return 0.0
    # crude heuristic: use sum of bytes modulo 100
    v = sum(data) % 100
    return float(v)


def extract_reserves(data: bytes) -> Dict[str, Any]:
    # Stub: return synthetic reserves using sections of the data
    if len(data) < 16:
        return {"sol_reserve": 0, "token_reserve": 0}
    sol_reserve = int.from_bytes(data[0:8], "little")
    token_reserve = int.from_bytes(data[8:16], "little")
    return {"sol_reserve": sol_reserve, "token_reserve": token_reserve}
