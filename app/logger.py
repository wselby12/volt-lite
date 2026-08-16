import logging
import structlog


def setup_logging(cfg):
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    pre_chain = [
        structlog.stdlib.add_log_level,
        timestamper,
    ]

    structlog.configure(
        processors=pre_chain + [structlog.processors.JSONRenderer()],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    logger = structlog.get_logger()
    logger = logger.bind(service="volt-lite")
    return logger
