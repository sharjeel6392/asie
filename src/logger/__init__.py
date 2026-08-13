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
        # Return a CHILD of airflow.task, not airflow.task itself.
        #
        # Records propagate up to airflow.task's FileTaskHandler (so they land
        # in the task log), and Airflow sets airflow.task.propagate = False by
        # default, so they stop there and never reach the root logger.
        #
        # That last part is the whole point. Airflow replaces sys.stdout and
        # sys.stderr with StreamLogWriter, which *logs* whatever is written to
        # it. Libraries that call logging.basicConfig() -- mlflow and datasets
        # both do -- attach a StreamHandler to the ROOT logger bound to that
        # replaced stderr. A record reaching root then gets written to
        # StreamLogWriter, which logs it, which reaches root again:
        #   _propagate_log -> write -> flush -> handle -> emit -> _propagate_log
        # until the stack is exhausted. That surfaces as an opaque
        # "RecursionError: maximum recursion depth exceeded" from inside
        # logger.error(), with no hint of the real cause.
        logger = logging.getLogger("airflow.task.asie")
        logger.setLevel(logging.DEBUG)

        # Belt and braces: if a library already attached such a handler to
        # root before we got here, drop it. It is only ever a self-feeding
        # loop under Airflow.
        root = logging.getLogger()
        for handler in list(root.handlers):
            stream = getattr(handler, "stream", None)
            if stream is not None and type(stream).__name__ == "StreamLogWriter":
                root.removeHandler(handler)

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