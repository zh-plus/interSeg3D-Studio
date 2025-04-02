import logging
import os
import sys
import time
import asyncio
from datetime import datetime
from functools import wraps
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("./logs")
logs_dir.mkdir(exist_ok=True)

# Configure the root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create a custom logger
logger = logging.getLogger("agile3d")
logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Create file handler for rotating logs
current_date = datetime.now().strftime("%Y-%m-%d")
file_handler = logging.FileHandler(logs_dir / f"agile3d_{current_date}.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Remove any duplicate handlers that might be inherited from root
logger.propagate = False


def timed(func=None, level=logging.INFO):
    """
    Decorator to log the execution time of a function.
    Can be used as @timed or @timed(level=logging.DEBUG)
    Supports both synchronous and asynchronous functions.
    """
    def decorator(f):
        if asyncio.iscoroutinefunction(f):
            # For async functions
            @wraps(f)
            async def async_wrapper(*args, **kwargs):
                func_name = f.__name__
                logger.log(level, f"Starting {func_name}")
                start_time = time.time()
                result = await f(*args, **kwargs)
                end_time = time.time()
                duration = end_time - start_time
                logger.log(level, f"Completed {func_name} in {duration:.3f} seconds")
                return result
            return async_wrapper
        else:
            # For regular functions
            @wraps(f)
            def sync_wrapper(*args, **kwargs):
                func_name = f.__name__
                logger.log(level, f"Starting {func_name}")
                start_time = time.time()
                result = f(*args, **kwargs)
                end_time = time.time()
                duration = end_time - start_time
                logger.log(level, f"Completed {func_name} in {duration:.3f} seconds")
                return result
            return sync_wrapper

    if func is None:
        return decorator
    return decorator(func)


class StepTimer:
    """
    Context manager for timing code blocks and logging the duration.
    """
    def __init__(self, step_name, level=logging.INFO):
        self.step_name = step_name
        self.level = level
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        logger.log(self.level, f"Starting step: {self.step_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        logger.log(self.level, f"Completed step: {self.step_name} in {duration:.3f} seconds")
        if exc_type:
            logger.error(f"Error in {self.step_name}: {exc_val}")
            return False
        return True

    # Add async context manager support
    async def __aenter__(self):
        self.start_time = time.time()
        logger.log(self.level, f"Starting step: {self.step_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        logger.log(self.level, f"Completed step: {self.step_name} in {duration:.3f} seconds")
        if exc_type:
            logger.error(f"Error in {self.step_name}: {exc_val}")
            return False
        return True


def get_logger(name=None):
    """
    Get a logger instance with the given name.
    If name is None, returns the main agile3d logger.
    """
    if name is None:
        return logger
    return logging.getLogger(f"agile3d.{name}")