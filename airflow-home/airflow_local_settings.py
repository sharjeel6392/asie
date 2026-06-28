"""
Local Airflow settings loaded at startup. Defensive logging guard to prevent
logging.lastResort from using wrapped stderr objects that re-enter Airflow
handlers (causing recursion).
"""
import logging
import sys
from logging import StreamHandler


def _set_safe_last_resort():
    try:
        # Prefer original stderr (set by Python at interpreter start).
        stderr = getattr(sys, "__stderr__", sys.stderr)
        handler = StreamHandler(stderr)
        handler.setLevel(logging.NOTSET)
        # Assign a handler object as lastResort so .handle/.emit use it safely.
        logging.lastResort = handler
        # Also ensure the handler's stream is the original stderr
        try:
            logging.lastResort.stream = stderr
        except Exception:
            pass
    except Exception:
        # Never raise during Airflow startup
        pass


_set_safe_last_resort()
