import math
from typing import Dict, Any

# Improved utilities to interpret Pump.fun bonding curve account data.
# NOTE: Pump.fun account layout is not publicly specified here. This module provides a best-effort
# parser that extracts two 8-byte little-endian integers for SOL and token reserves if present.
# Replace with the official account layout parsing for production use.


def parse_progress_from_account(data: bytes) -> float:
    """Estimate graduation progress (0-100) from account data.

    Heuristic used here:
    - If account contains two 8-byte values, treat them as sol_reserve and token_reserve.
    - Progress is computed as token_reserve / (token_reserve + sol_reserve) scaled to 0-100.
    - If amounts are zero or layout unknown, fallback to a deterministic pseudo-hash mapping.
    """
    if not data:
        return 0.0

    # if at least 16 bytes available, parse reserves
    if len(data) >= 16:
        sol_reserve = int.from_bytes(data[0:8], "little")
        token_reserve = int.from_bytes(data[8:16], "little")
        denom = token_reserve + sol_reserve
        if denom <= 0:
            return 0.0
        progress = (token_reserve / denom) * 100.0
        # clamp
        return max(0.0, min(100.0, progress))

    # fallback deterministic heuristic
    v = sum(data) % 100
    return float(v)


def extract_reserves(data: bytes) -> Dict[str, Any]:
    """Extract reserve estimates from account data. Returns sol_reserve (lamports) and token_reserve (units).
    Uses the same 0-16 byte heuristic as parse_progress_from_account.
    """
    if not data or len(data) < 16:
        return {"sol_reserve": 0, "token_reserve": 0}
    sol_reserve = int.from_bytes(data[0:8], "little")
    token_reserve = int.from_bytes(data[8:16], "little")
    return {"sol_reserve": sol_reserve, "token_reserve": token_reserve}
