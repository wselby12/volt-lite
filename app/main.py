import asyncio
import signal
from app.config import Config
from app.logger import setup_logging
from pump.listener import PumpListener
from trading.executor import TradingExecutor
from storage.database import Database


async def main_loop():
    cfg = Config.from_env()
    logger = setup_logging(cfg)
    logger.info("starting", module="app.main")

    db = Database(cfg.sqlite_path)
    await db.connect()

    executor = TradingExecutor(cfg, db, logger)

    listener = PumpListener(cfg, logger)

    # start tasks
    listener_task = asyncio.create_task(listener.run(executor.on_curve_update))
    manager_task = asyncio.create_task(executor.run())

    # graceful shutdown
    stop = asyncio.Event()

    def _signal(_signum, _frame):
        logger.info("shutdown_signal", signum=_signum)
        stop.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: _signal(signal.SIGINT, None))
    loop.add_signal_handler(signal.SIGTERM, lambda: _signal(signal.SIGTERM, None))

    await stop.wait()
    logger.info("shutting_down")

    listener_task.cancel()
    manager_task.cancel()
    await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except Exception as e:
        print("fatal", e)
