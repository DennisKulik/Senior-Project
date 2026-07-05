import argparse
from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR

import duckdb


def connect():
    return duckdb.connect()


def register_data(con, parquet_path: str):
    # Create a view so you don't repeat read_parquet everywhere
    con.execute(f"""
        CREATE OR REPLACE VIEW telemetry AS
        SELECT * FROM read_parquet('{parquet_path}');
    """)


def max_depth(con):
    # returns a scalar
    return con.execute("SELECT MAX(depth_m) FROM telemetry;").fetchone()[0]


def avg_voltage(con):
    return con.execute("SELECT AVG(battery_v) FROM telemetry;").fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description="Run analysis of parquet")
    parser.add_argument(
        "query",
        choices=["max_depth", "avg_voltage", "all"],
        help="Which metric to query for",
    )
    parser.add_argument(
        "--parquet",
        default=str(DEFAULT_DATA_FILE),
        help="Path to Parquet file",
    )
    args = parser.parse_args()

    parquet_path = args.parquet.replace("\\", "/")  # safer for DuckDB on Windows

    con = connect()
    try:
        register_data(con, parquet_path)

        if args.query in ("max_depth", "all"):
            md = max_depth(con)
            print("\n=== Max depth (m) ===")
            print(md)

        if args.query in ("avg_voltage", "all"):
            av = avg_voltage(con)
            print("\n=== Avg battery voltage (V) ===")
            print(av)

    finally:
        con.close()


if __name__ == "__main__":
    main()

