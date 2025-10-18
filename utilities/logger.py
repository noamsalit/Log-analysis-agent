import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union
from enum import Enum

TRACE = 5
logging.addLevelName(TRACE, "TRACE")


class LogLevel(Enum):
    """Enumeration of supported logging levels."""
    TRACE = TRACE
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    
    @classmethod
    def from_string(cls, level_str: str) -> 'LogLevel':
        """
        Convert string to LogLevel enum.
        
        :param level_str: String representation of log level (case-insensitive)
        :return: Corresponding LogLevel enum value
        :raises ValueError: If level_str is not a valid log level
        """
        try:
            return cls[level_str.upper()]
        except KeyError:
            valid_levels = ', '.join([level.name for level in cls])
            raise ValueError(
                f"Invalid log level: {level_str}. "
                f"Valid levels are: {valid_levels}"
            )

def trace(self, message, *args, **kwargs):
    """Log message with TRACE severity for extremely verbose logging."""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

logging.Logger.trace = trace

def init_logger(
    name: Optional[str] = None,
    log_dir: Union[str, Path] = "logs",
    log_file: str = "schema_analysis_agent.log",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    format: Optional[str] = None,
    date_format: str = "%Y-%m-%d %H:%M:%S",
    log_to_console: bool = True,
    log_to_file: bool = True,
) -> logging.Logger:
    """
    Initialize and return a configured logger.

    :param name: Logger name; defaults to module name.
    :param log_dir: Directory for log files.
    :param log_file: Log file name inside log_dir.
    :param console_level: Logging level for console output.
    :param file_level: Logging level for file output.
    :param max_bytes: Max file size in bytes before rotation.
    :param backup_count: Number of rotated files to keep.
    :param format: Log message format. If None, a default is used.
    :param date_format: Datetime format for timestamps.
    :param log_to_console: Whether to attach console handler.
    :param log_to_file: Whether to attach rotating file handler.
    :return: Configured logger instance.
    """

    logger_name = name or __name__
    logger = logging.getLogger(logger_name)

    if getattr(logger, "_configured_by_init_logger", False):
        return logger

    logger.setLevel(min(console_level, file_level))

    if format is None:
        format = (
            "%(asctime)s [%(levelname)s] %(name)s "
            "%(filename)s:%(lineno)d in %(funcName)s - %(message)s"
        )

    formatter = logging.Formatter(fmt=format, datefmt=date_format)

    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_to_file:
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        file_path = log_dir_path / log_file

        file_handler = RotatingFileHandler(
            filename=str(file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False

    setattr(logger, "_configured_by_init_logger", True)
    return logger
