from src.serving.inference_log_DB.database import get_connection

def log_inference(record: dict):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO inference_logs (
                   request_id,
                   timestamp,
                   input_data,
                   embedding_json,
                   input_length,
                   true_label,
                   primary_model_name,
                   primary_model_version,
                   primary_prediction,
                   primary_confidence,
                   primary_latency_ms,
                   shadow_model_name,
                   shadow_model_version,
                   shadow_predictions,
                   shadow_confidence,
                   shadow_latency_ms,
                   disagreement,
                   abs_diff,
                   request_source
                ) VALUES (
                   :request_id,
                   :timestamp,
                   :input_data,
                   :embedding_json,
                   :input_length,
                   :true_label,
                   :primary_model_name,
                   :primary_model_version,
                   :primary_prediction,
                   :primary_confidence,
                   :primary_latency_ms,
                   :shadow_model_name,
                   :shadow_model_version,
                   :shadow_predictions,
                   :shadow_confidence,
                   :shadow_latency_ms,
                   :disagreement,
                   :abs_diff,
                   :request_source
                   )

""", record)
    
    conn.commit()
    conn.close()
    