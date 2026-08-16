from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class FeatureWindow:
    history: list


class Features:
    def __init__(self):
        self.state = {}

    def update(self, pubkey: str, reserves: Dict[str, Any], progress: float, ts: float):
        st = self.state.setdefault(pubkey, {"events": []})
        st["events"].append({"ts": ts, "reserves": reserves, "progress": progress})
        # keep last 120 events
        st["events"] = st["events"][-120:]

    def compute(self, pubkey: str) -> Dict[str, float]:
        st = self.state.get(pubkey)
        if not st:
            return {}
        ev = st["events"]
        # compute simple metrics
        sol_changes = []
        times = []
        for i in range(1, len(ev)):
            prev = ev[i - 1]
            cur = ev[i]
            delta = cur["reserves"]["sol_reserve"] - prev["reserves"]["sol_reserve"]
            dt = cur["ts"] - prev["ts"]
            if dt <= 0:
                continue
            sol_changes.append(delta / dt)
            times.append(dt)
        liquidity_velocity = sum(sol_changes) / len(sol_changes) if sol_changes else 0.0
        positive_changes = sum(1 for x in sol_changes if x > 0)
        negative_changes = sum(1 for x in sol_changes if x < 0)
        net_inflow = sum(sol_changes)
        momentum_accel = 0.0
        if len(sol_changes) >= 2:
            momentum_accel = (sol_changes[-1] - sol_changes[-2])
        consistency = (positive_changes / len(sol_changes)) * 100 if sol_changes else 0.0

        return {
            "liquidity_velocity": liquidity_velocity,
            "positive_changes": positive_changes,
            "negative_changes": negative_changes,
            "net_inflow": net_inflow,
            "momentum_accel": momentum_accel,
            "consistency": consistency,
        }
