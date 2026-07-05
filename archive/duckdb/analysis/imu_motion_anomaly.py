from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR

import duckdb

DATA_FILE = DEFAULT_DATA_FILE

ROLLING_WINDOW = 10  # number of samples in rolling window
Z_SCORE_THRESHOLD = 3.0  # spike threshold (standard deviations)


def main():
    con = duckdb.connect()

    # Create view
    con.execute(f"""
        CREATE OR REPLACE VIEW imu AS
        SELECT
            CAST(timestamp_utc AS TIMESTAMP) AS timestamp_utc,
            seq,
            run_id,
            imu_ax_mps2,
            imu_ay_mps2,
            imu_az_mps2
        FROM read_parquet('{DATA_FILE}')
    """)

    query = f"""
    WITH magnitude AS (
        SELECT
            run_id,
            timestamp_utc,
            seq,
            SQRT(
                imu_ax_mps2 * imu_ax_mps2 +
                imu_ay_mps2 * imu_ay_mps2 +
                imu_az_mps2 * imu_az_mps2
            ) AS accel_mag
        FROM imu
    ),
    rolling_stats AS (
        SELECT
            run_id,
            timestamp_utc,
            seq,
            accel_mag,
            AVG(accel_mag) OVER (
                PARTITION BY run_id
                ORDER BY timestamp_utc
                ROWS BETWEEN {ROLLING_WINDOW} PRECEDING AND CURRENT ROW
            ) AS rolling_mean,
            STDDEV_SAMP(accel_mag) OVER (
                PARTITION BY run_id
                ORDER BY timestamp_utc
                ROWS BETWEEN {ROLLING_WINDOW} PRECEDING AND CURRENT ROW
            ) AS rolling_std
        FROM magnitude
    ),
    scored AS (
        SELECT
            run_id,
            timestamp_utc,
            seq,
            accel_mag,
            rolling_mean,
            rolling_std,
            CASE
                WHEN rolling_std > 0
                THEN (accel_mag - rolling_mean) / rolling_std
                ELSE 0
            END AS z_score
        FROM rolling_stats
    )
    SELECT *
    FROM scored
    WHERE ABS(z_score) >= {Z_SCORE_THRESHOLD}
    ORDER BY run_id, timestamp_utc
    """

    anomalies = con.execute(query).fetchdf()

    if anomalies.empty:
        print("No motion anomalies detected.")
    else:
        print(f"Detected {len(anomalies)} motion anomaly event(s):")
        print(anomalies.to_string(index=False))
        print()

    # Count anomalies per run
    if anomalies.empty:
        print("Anomaly count per run: none")
    else:
        summary = (
            anomalies.groupby("run_id")
            .size()
            .reset_index(name="anomaly_count")
            .sort_values("run_id")
        )

        print("Anomaly count per run:")
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
