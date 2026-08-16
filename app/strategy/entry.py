import time
from app.strategy.features import Features
from app.strategy.scoring import score_from_features


class EntryManager:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger
        self.features = Features()

    def on_update(self, pubkey: str, reserves, progress: float):
        ts = time.time()
        self.features.update(pubkey, reserves, progress, ts)
        feats = self.features.compute(pubkey)
        score = score_from_features(feats)
        return {"pubkey": pubkey, "progress": progress, "features": feats, "score": score}
