from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR

import duckdb

parquet_path = DEFAULT_DATA_FILE

con = duckdb.connect()
print("Reading first 10 rows of parquet")
result = con.execute(
    f"SELECT * FROM read_parquet('{parquet_path}') LIMIT 10;"
).fetchall()
for row in result:
    print(row)
count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}');").fetchone()
print("Total rows:", count[0] if count else "N/A")
con.close()

