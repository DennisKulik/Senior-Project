/*
motion_zscore_summary.sql — Per-run IMU motion variability summary

Analyzes IMU acceleration magnitude over time per run and summarizes:
  1. Total acceleration magnitude  — computed as √(ax² + ay² + az²)
  2. Rolling z-score behavior      — how far each sample deviates from recent motion
  3. Maximum deviation             — largest absolute z-score observed during the run
  4. Percentile deviation values   — 95th and 99th percentile absolute z-scores

This view summarizes overall motion variability for each run, even when no
individual samples cross the anomaly threshold used by `motion_anomalies`.

NOTE: A rolling window of the current row plus the previous 10 rows is used.
Z-scores are computed as:
    z_score = (accel_mag - rolling_mean) / rolling_std
*/

CREATE OR REPLACE VIEW motion_zscore_summary AS
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
    COUNT(*) AS rows_seen,
    MAX(ABS(z_score)) AS max_abs_z_score,
    AVG(ABS(z_score)) AS avg_abs_z_score,
    approx_percentile(ABS(z_score), 0.95) AS p95_abs_z_score,
    approx_percentile(ABS(z_score), 0.99) AS p99_abs_z_score
FROM scored
GROUP BY run_id
ORDER BY run_id;
