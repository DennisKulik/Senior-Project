from src.utils.paths import RAW_DATA_DIR, PARQUET_DIR

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

csv_file_path = RAW_DATA_DIR / "sensors.csv"
parquet_file_path = PARQUET_DIR / "data.parquet"

df = pd.read_csv(csv_file_path)
table = pa.Table.from_pandas(df)

PARQUET_DIR.mkdir(parents=True, exist_ok=True)
pq.write_table(table, parquet_file_path)

print(f"Wrote parquet file to {parquet_file_path}")
