import sys
from pathlib import Path
from loguru import logger
from app.config.settings_manager import get_app_dir

def setup_logger():
    """Configures loguru according to section 17 of the specification."""
    log_file = get_app_dir() / "indexo.log"

    logger.remove()
    
    # Console sink (only if stderr is available, e.g. in terminal mode)
    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO"
        )

    # File sink: 5MB rotation, 1 backup retention
    logger.add(
        str(log_file),
        rotation="5 MB",
        retention=1,
        level="INFO",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    logger.info("Indexo logger initialized at {}", log_file)
    return logger
