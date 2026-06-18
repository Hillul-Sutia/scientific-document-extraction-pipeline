import logging
from pathlib import Path

def setup_logger(name):
    safe_name = name.replace(".", "_")
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console logs
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # File logs
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(
            log_dir / f"{safe_name}.log",
            encoding="utf-8"
        )
        
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
