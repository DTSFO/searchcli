import logging
import threading
from datetime import datetime

from .config import config


logger = logging.getLogger("grok_search")
logger.addHandler(logging.NullHandler())

_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_configure_lock = threading.Lock()
_file_handler: logging.FileHandler | None = None


def _ensure_file_handler() -> None:
    global _file_handler
    if _file_handler is not None:
        return
    with _configure_lock:
        if _file_handler is not None:
            return
        try:
            level = getattr(logging, config.log_level, logging.INFO)
            log_dir = config.log_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"grok_search_{datetime.now().strftime('%Y%m%d')}.log"
            handler = logging.FileHandler(log_file, encoding="utf-8")
            handler.setLevel(level)
            handler.setFormatter(_formatter)
            logger.setLevel(level)
            logger.addHandler(handler)
            _file_handler = handler
        except OSError:
            return


async def log_info(ctx, message: str, is_debug: bool = False):
    if is_debug:
        _ensure_file_handler()
        logger.info(message)


def debug(message: str) -> None:
    if config.debug_enabled:
        _ensure_file_handler()
        logger.info(message)
