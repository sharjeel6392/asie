from src.drift.storage.factory import get_drift_store
from src.drift.features import build_feature_dataframe
from datetime import datetime, timedelta

store = get_drift_store()

end = datetime.now()
start = end - timedelta(days=2)

df = store.fetch_current(
    start.strftime("%Y-%m-%d %H:%M:%S"),
    end.strftime("%Y-%m-%d %H:%M:%S")
)

features = build_feature_dataframe(df)

print(features.shape)
print(features.head())