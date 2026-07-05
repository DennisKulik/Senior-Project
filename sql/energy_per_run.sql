/*
energy_per_run.sql — Energy consumption summary per run

Analyzes battery voltage and current telemetry over time per run and summarizes:
  1. Instantaneous power  — computed as voltage × current (W)
  2. Time delta           — elapsed time between consecutive telemetry rows
  3. Total energy usage   — integrated power over time, reported in watt-hours

This view gives a high-level summary of electrical energy consumed during
each run using battery telemetry and timestamp spacing.

NOTE: Energy is computed by integrating instantaneous power over the time
between consecutive samples:
    energy_wh = Σ(power_w × delta_seconds) / 3600
*/

CREATE OR REPLACE VIEW energy_per_run AS
WITH with_power AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        battery_voltage_v,
        battery_current_a,
        (battery_voltage_v * battery_current_a) AS power_w
    FROM sensor_data
    WHERE battery_voltage_v IS NOT NULL
      AND battery_current_a IS NOT NULL
),
with_deltas AS (
    SELECT
        run_id,
        timestamp_utc,
        power_w,
        (
            to_unixtime(timestamp_utc) - 
            to_unixtime(
                LAG(timestamp_utc) OVER (
                    PARTITION BY run_id
                    ORDER BY timestamp_utc, seq
                )
            )
        ) AS delta_seconds
    FROM with_power
)
SELECT
    run_id,
    SUM(power_w * delta_seconds) / 3600.0 AS energy_wh
FROM with_deltas
WHERE delta_seconds IS NOT NULL
GROUP BY run_id
ORDER BY run_id;
