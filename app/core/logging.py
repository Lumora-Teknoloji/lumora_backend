import logging
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter — SOC2 uyumlu."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    """Logging yapılandırmasını başlatır — JSON format + rotation."""
    # JSON formatter
    json_formatter = JSONFormatter()
    # Konsol formatter (okunabilir)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    # Rotating file handler — max 10MB, 5 yedek = max 60MB
    file_handler = RotatingFileHandler(
        "backend.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(json_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )
