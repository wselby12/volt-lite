from typing import Dict


def score_from_features(features: Dict[str, float]) -> int:
    # weights per spec
    lv = abs(features.get("liquidity_velocity", 0.0))
    buy_pressure = max(features.get("net_inflow", 0.0), 0.0)
    accel = features.get("momentum_accel", 0.0)
    consistency = features.get("consistency", 0.0)
    # normalize heuristics
    lv_score = min(35, int(min(lv * 1e-6, 35)))
    buy_score = min(20, int(min(buy_pressure * 1e-6, 20)))
    accel_score = min(15, int(min(accel * 1e-6, 15)))
    consistency_score = min(15, int(min(consistency, 15)))
    progression_speed_score = 15 if 0 else 0
    total = lv_score + buy_score + accel_score + consistency_score + progression_speed_score
    return int(total)
