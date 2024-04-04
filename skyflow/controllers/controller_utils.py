"""Utility functions for controllers."""
import logging
import os


def create_controller_logger(title: str, log_path: str, level=logging.INFO):
    """Creates a generic logger for controllers."""
    if level is None:
        # Fetch from env variable if level is not specified.
        level = os.getenv("LOG_LEVEL", "INFO")
    formatter = logging.Formatter(
        "%(name)s - %(asctime)s - %(levelname)s - %(message)s")

    logger = logging.getLogger(title)
    logger.setLevel(level)

    # Create log_path is it does not exist.
    if log_path:
        log_path = os.path.expanduser(log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        fh_channel = logging.FileHandler(log_path, mode='w')
        fh_channel.setLevel(level)
        fh_channel.setFormatter(formatter)
        logger.addHandler(fh_channel)

    stream_channel = logging.StreamHandler()
    stream_channel.setLevel(level)
    stream_channel.setFormatter(formatter)
    logger.addHandler(stream_channel)

    return logger
