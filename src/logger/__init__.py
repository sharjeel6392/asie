import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
import sys

from src.constants import LOGS_DIR as LOG_DIR

MAX_LOG_SIZE = 5 * 1024 * 1024
BACKUP_COUNT = 3

def configure_logger():
    airflow_context = (
        os.getenv("AIRFLOW_CTX_DAG_ID")
        or os.getenv("AIRFLOW_HOME")
        or os.getenv("AIRFLOW__CORE__DAGS_FOLDER")
    )

    if airflow_context:
        logger = logging.getLogger("airflow.task")
        logger.setLevel(logging.DEBUG)
        # Do not propagate to avoid re-entering Airflow's logging handlers
        # which can cause recursive log writes under some configurations.
        logger.propagate = False

        # Diagnostic dump: write current logging handlers and streams to a temp file
        try:
            dump_path = "/tmp/airflow_logger_dump.txt"
            with open(dump_path, "w", encoding="utf-8") as f:
                import sys as _sys
                f.write(f"sys.stderr: {type(_sys.stderr)} {repr(_sys.stderr)} id={id(_sys.stderr)}\n")
                f.write(f"sys.stdout: {type(_sys.stdout)} {repr(_sys.stdout)} id={id(_sys.stdout)}\n")
                root = logging.getLogger()
                f.write("\nRoot handlers:\n")
                for h in root.handlers:
                    try:
                        s = getattr(h, "stream", None)
                        f.write(f"  {type(h).__name__} stream={type(s).__name__} id={id(s)} repr={repr(s)} has_set_context={hasattr(h,'set_context')}\n")
                    except Exception as _e:
                        f.write(f"  {type(h).__name__} stream_lookup_error={_e}\n")

                f.write("\nAll loggers:\n")
                for name in sorted(logging.root.manager.loggerDict):
                    logger_obj = logging.getLogger(name)
                    f.write(f"LOGGER {name} level={logger_obj.level} propagate={logger_obj.propagate} handlers={[type(h).__name__ for h in logger_obj.handlers]}\n")
                    for h in logger_obj.handlers:
                        try:
                            s = getattr(h, "stream", None)
                            f.write(f"   handler {type(h).__name__} stream_type={type(s).__name__ if s else None} id={id(s)} repr={repr(s)} has_set_context={hasattr(h,'set_context')}\n")
                        except Exception as _e:
                            f.write(f"   handler {type(h).__name__} stream_lookup_error={_e}\n")

                last = getattr(logging, "lastResort", None)
                f.write(f"\nlogging.lastResort: {type(last).__name__ if last else None} stream={getattr(last, 'stream', None)}\n")
        except Exception:
            # Don't let diagnostics break logging configuration
            pass
        # Defensive: ensure logging.lastResort writes to the original stderr, not a wrapped one
        try:
            import logging as _logging, sys as _sys
            if hasattr(_logging, 'lastResort') and getattr(_logging, 'lastResort', None) is not None:
                try:
                    _logging.lastResort.stream = getattr(_sys, '__stderr__', _sys.stderr)
                except Exception:
                    pass
        except Exception:
            pass
        return logger

    logger = logging.getLogger("asie")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # FIX: Move file generation inside the call function to prevent import deadlocks
    LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
    root_dir = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
    log_dir_path = os.path.join(root_dir, LOG_DIR)
    os.makedirs(log_dir_path, exist_ok=True)
    log_file_path = os.path.join(log_dir_path, LOG_FILE)

    formatter = logging.Formatter("[ %(asctime)s ] %(name)s - %(levelname)s - %(message)s")

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger