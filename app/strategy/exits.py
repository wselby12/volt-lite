import time


class ExitManager:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger

    def evaluate_position(self, position):
        """Return an action dict when an exit should occur, otherwise None.

        position: dict with keys: entry_price, current_value, highest_value, tp1, tp2, tp3
        """
        cur = position.get("current_value")
        entry = position.get("entry_price")
        highest = position.get("highest_value") or cur
        if entry is None or entry <= 0 or cur is None:
            return None
        change_pct = (cur - entry) / entry * 100

        # Hard stop: sell all
        if change_pct <= -self.cfg.STOP_LOSS_PCT:
            return {"action": "sell_all", "reason": "stop_loss", "change_pct": change_pct}

        # Take profits: check sequential flags saved on position
        # TP1
        if change_pct >= self.cfg.TP1_PCT and not position.get("tp1_executed"):
            return {"action": "sell_partial", "reason": "tp1", "sell_pct": self.cfg.TP1_SELL_PCT}
        # TP2
        if change_pct >= self.cfg.TP2_PCT and not position.get("tp2_executed"):
            return {"action": "sell_partial", "reason": "tp2", "sell_pct": self.cfg.TP2_SELL_PCT}
        # TP3
        if change_pct >= self.cfg.TP3_PCT and not position.get("tp3_executed"):
            return {"action": "sell_partial", "reason": "tp3", "sell_pct": self.cfg.TP3_SELL_PCT}

        # Trailing stop on runner: if value has fallen TRAILING_STOP_PCT from highest
        if highest and cur < highest * (1 - self.cfg.TRAILING_STOP_PCT / 100.0):
            return {"action": "sell_all", "reason": "trailing_stop"}

        # Force exit near graduation
        if position.get("curve_progress") and position.get("curve_progress") >= self.cfg.FORCE_EXIT_CURVE_PROGRESS:
            return {"action": "sell_all", "reason": "force_exit_curve"}

        return None
