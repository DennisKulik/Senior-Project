from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR

import duckdb

# Path to parquet file
DATA_FILE = DEFAULT_DATA_FILE


def main():
    con = duckdb.connect()

    # Create view over the parquet file
    con.execute(f"""
        CREATE OR REPLACE VIEW data AS
        SELECT timestamp_utc, seq, run_id, battery_voltage_v, battery_current_a
        FROM read_parquet('{DATA_FILE}')
    """)

    # Compute instantaneous power (W = V * A)
    # Compute time delta between rows
    # Integrate power over time to get energy in watt-hours

    query = """
    WITH with_power AS (
        SELECT
            run_id,
            timestamp_utc,
            seq,
            battery_voltage_v,
            battery_current_a,
            (battery_voltage_v * battery_current_a) AS power_w
        FROM data
    ),
    with_deltas AS (
        SELECT
            run_id,
            timestamp_utc,
            power_w,
            EXTRACT(EPOCH FROM (timestamp_utc
                - LAG(timestamp_utc) OVER (
                    PARTITION BY run_id
                    ORDER BY timestamp_utc
                )
            )) AS delta_seconds
        FROM with_power
    )
    SELECT
        run_id,
        SUM(power_w * delta_seconds) / 3600.0 AS energy_wh
    FROM with_deltas
    WHERE delta_seconds IS NOT NULL
    GROUP BY run_id
    ORDER BY run_id
    """

    result = con.execute(query).fetchdf()
    print(result)


if __name__ == "__main__":
    main()

