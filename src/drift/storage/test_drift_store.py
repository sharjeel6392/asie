from datetime import datetime, timedelta
from src.drift.storage.factory import get_drift_store

store = get_drift_store()

end = datetime.now()
start = end - timedelta(hours=1)

df = store.fetch_current(start.strftime("%Y-%m-%d %H:%M:%S"), 
                         end.strftime("%Y-%m-%d %H:%M:%S"))


print(df.shape)
print(df.columns)