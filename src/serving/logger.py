import uuid
from datetime import datetime
from sqlite3 import Connection

class InferenceLogger:
    def __init__(self, db: Connection):
        self.db = db

    def log(self, predictions: list, latency_ms: float):
        batch_id = str(uuid.uuid4())

        with self.db:
            cur = self.db.cursor()
            cur.execute("""
                INSERT INTO inference_batch (batch_id, batch_size, latency_ms, created_at) VALUES (%s, %s, %s, %s)
            """,(
                    batch_id,
                    len(predictions),
                    latency_ms,
                    datetime.now()
                )
            )

            prediction_rows = [
                (
                    batch_id,
                    p['text'],
                    p['label'],
                    p['score']
                )
                for p in predictions
            ]

            cur.executemany("""
                INSERT INTO inference_prediction (batch_id, text, label, score) VALUES (%s, %s, %s, %s)
            """, prediction_rows)

        self.db.commit()

        return batch_id