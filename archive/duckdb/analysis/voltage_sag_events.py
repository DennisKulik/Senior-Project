from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR

import duckdb

DATA_FILE = DEFAULT_DATA_FILE

# Thresholds
VOLTAGE_DROP_THRESHOLD = -0.05  # volts
CURRENT_SPIKE_THRESHOLD = 0.5  # amps increase


def main():
    con = duckdb.connect()

    # Create view over parquet file
    con.execute(f"""
        CREATE OR REPLACE VIEW battery AS
        SELECT
            CAST(timestamp_utc AS TIMESTAMP) AS timestamp_utc,
            seq,
            run_id,
            battery_voltage_v,
            battery_current_a
        FROM read_parquet('{DATA_FILE}')
    """)

    query = f"""
    WITH deltas AS (
        SELECT
            run_id,
            timestamp_utc,
            battery_voltage_v,
            battery_current_a,
            battery_voltage_v
                - LAG(battery_voltage_v) OVER (
                    PARTITION BY run_id
                    ORDER BY timestamp_utc
                ) AS delta_voltage,
            battery_current_a
                - LAG(battery_current_a) OVER (
                    PARTITION BY run_id
                    ORDER BY timestamp_utc
                ) AS delta_current
        FROM battery
    ),
    flagged AS (
        SELECT
            run_id,
            timestamp_utc,
            battery_voltage_v,
            battery_current_a,
            delta_voltage,
            delta_current
        FROM deltas
        WHERE delta_voltage <= {VOLTAGE_DROP_THRESHOLD}
          AND delta_current >= {CURRENT_SPIKE_THRESHOLD}
    )
    SELECT *
    FROM flagged
    ORDER BY run_id, timestamp_utc
    """

    result = con.execute(query).fetchdf()

    if result.empty:
        print("No high-load voltage sag events detected.")
    else:
        print(f"Detected {len(result)} high-load voltage sag event(s):\n")
        print(result.to_string(index=False))

    # Count events per run
    if result.empty:
        print("\nEvent count per run: none")
    else:
        summary = (
            result.groupby("run_id")
            .size()
            .reset_index(name="event_count")
            .sort_values("run_id")
        )

        print("\nEvent count per run:")
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

