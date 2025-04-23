# timing_logger.py
import logging

timing_logger = logging.getLogger("timing_logger")
timing_logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("timing.log")
formatter = logging.Formatter('%(asctime)s - %(message)s')
file_handler.setFormatter(formatter)

if not timing_logger.hasHandlers():
    timing_logger.addHandler(file_handler)
