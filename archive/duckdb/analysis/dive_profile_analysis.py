from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR

import duckdb

DATA_FILE = DEFAULT_DATA_FILE


def main():
    con = duckdb.connect()

    # Create a view over the parquet
    con.execute(f"""
        CREATE OR REPLACE VIEW depth AS
        SELECT
            CAST(timestamp_utc AS TIMESTAMP) AS timestamp_utc,
            seq,
            run_id,
            depth_m
        FROM read_parquet('{DATA_FILE}')
    """)

    query = """
    WITH ordered AS (
        SELECT
            run_id,
            timestamp_utc,
            depth_m,
            LAG(depth_m) OVER (
                PARTITION BY run_id
                ORDER BY timestamp_utc
            ) AS prev_depth,
            LAG(timestamp_utc) OVER (
                PARTITION BY run_id
                ORDER BY timestamp_utc
            ) AS prev_time
        FROM depth
    ),
    with_rates AS (
        SELECT
            run_id,
            timestamp_utc,
            depth_m,
            EXTRACT(EPOCH FROM (timestamp_utc - prev_time)) AS delta_seconds,
            (depth_m - prev_depth) /
                NULLIF(EXTRACT(EPOCH FROM (timestamp_utc - prev_time)), 0)
                AS vertical_rate_mps
        FROM ordered
        WHERE prev_time IS NOT NULL
    ),
    per_run_stats AS (
        SELECT
            run_id,
            MAX(depth_m) AS max_depth_m,
            AVG(depth_m) AS avg_depth_m,
            AVG(CASE WHEN vertical_rate_mps > 0 THEN vertical_rate_mps END)
                AS avg_descent_rate_mps,
            AVG(CASE WHEN vertical_rate_mps < 0 THEN vertical_rate_mps END)
                AS avg_ascent_rate_mps
        FROM with_rates
        GROUP BY run_id
    ),
    bottom_time AS (
        SELECT
            r.run_id,
            SUM(w.delta_seconds) AS time_at_depth_seconds
        FROM with_rates w
        JOIN per_run_stats r
            ON w.run_id = r.run_id
        WHERE w.depth_m >= 0.9 * r.max_depth_m
        GROUP BY r.run_id
    )
    SELECT
        s.run_id,
        s.max_depth_m,
        s.avg_depth_m,
        s.avg_descent_rate_mps,
        s.avg_ascent_rate_mps,
        b.time_at_depth_seconds
    FROM per_run_stats s
    LEFT JOIN bottom_time b
        ON s.run_id = b.run_id
    ORDER BY s.run_id
    """

    result = con.execute(query).fetchdf()
    print(result)


if __name__ == "__main__":
    main()

