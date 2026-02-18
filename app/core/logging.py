import logging
import os
import time
from fastapi import Request
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Configure logging to both console and file."""
    log_file = "app.log"
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(log_format)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024, # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    logging.info(f"Logging initialized. Outputting to {os.path.abspath(log_file)}")

async def log_request_middleware(request: Request, call_next):
    """Middleware to log request details including duration and status code."""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    
    # Use the root logger to ensure it goes to our configured handlers
    logger = logging.getLogger("app.main") 
    logger.info(
        f"{request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Time: {process_time:.2f}ms"
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    return response

if __name__ == "__main__":
    setup_logging()
    logging.info("Test log message")
