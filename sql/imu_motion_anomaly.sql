/*
motion_anomalies.sql — Rolling acceleration anomaly detection per run

Analyzes IMU acceleration magnitude over time per run and identifies:
  1. Total acceleration magnitude  — computed as √(ax² + ay² + az²)
  2. Rolling mean                  — local average acceleration magnitude
  3. Rolling standard deviation    — local variation in acceleration magnitude
  4. Z-score anomalies             — samples whose acceleration deviates strongly
                                     from recent behavior

This view detects short-term motion spikes or abnormal movement patterns using
a rolling statistical window over IMU telemetry.

NOTE: A rolling window of the current row plus the previous 10 rows is used.
Rows are flagged as anomalies when:
    |z_score| >= 3.0
where:
    z_score = (accel_mag - rolling_mean) / rolling_std
*/
CREATE OR REPLACE VIEW motion_anomalies AS
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
    FROM sensor_data
    WHERE imu_ax_mps2 IS NOT NULL
      AND imu_ay_mps2 IS NOT NULL
      AND imu_az_mps2 IS NOT NULL
),
rolling_stats AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        accel_mag,
        AVG(accel_mag) OVER (
            PARTITION BY run_id
            ORDER BY timestamp_utc, seq
            ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
        ) AS rolling_mean,
        STDDEV_SAMP(accel_mag) OVER (
            PARTITION BY run_id
            ORDER BY timestamp_utc, seq
            ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
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
SELECT
    run_id,
    timestamp_utc,
    seq,
    accel_mag,
    rolling_mean,
    rolling_std,
    z_score
FROM scored
WHERE ABS(z_score) >= 3.0;
