import time


class ExitManager:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger

    def evaluate_position(self, position):
        # position is a dict with entry_price, current_price, highest_price
        cur = position.get("current_value", position.get("tokens_received", 0))
        entry = position.get("entry_price", 0)
        if entry <= 0:
            return None
        change_pct = (cur - entry) / entry * 100
        # hard stop
        if change_pct <= -self.cfg.STOP_LOSS_PCT:
            return {"action": "sell_all", "reason": "stop_loss", "pct": change_pct}
        # TP1
        if change_pct >= self.cfg.TP1_PCT and not position.get("tp1");
        # We'll flag sells at executor level; simplified here
        return None
