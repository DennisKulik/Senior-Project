/*
voltage_sag_events.sql — High-load electrical stress event detection per run

Analyzes battery voltage and current telemetry over time per run and identifies:
  1. Rolling voltage baseline  — recent average battery voltage
  2. Rolling current baseline  — recent average battery current
  3. Voltage sag events        — sudden voltage drops relative to recent behavior
  4. Current spike events      — sudden increases in current draw relative to
                                 recent behavior

This view detects short-term high-load electrical stress events using rolling
baselines computed from recent telemetry samples.

NOTE: Rolling baselines are computed using the previous 10 rows, excluding the
current row. Rows are flagged when:
    delta_voltage <= -0.45 V
    delta_current >= 8.0 A
where:
    delta_voltage = battery_voltage_v - baseline_voltage_v
    delta_current = battery_current_a - baseline_current_a
*/
CREATE OR REPLACE VIEW voltage_sag_events AS
WITH rolling_baseline AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        battery_voltage_v,
        battery_current_a,
        AVG(battery_voltage_v) OVER (
            PARTITION BY run_id
            ORDER BY timestamp_utc, seq
            ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
        ) AS baseline_voltage_v,
        AVG(battery_current_a) OVER (
            PARTITION BY run_id
            ORDER BY timestamp_utc, seq
            ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
        ) AS baseline_current_a
    FROM sensor_data
    WHERE battery_voltage_v IS NOT NULL
      AND battery_current_a IS NOT NULL
),
deltas AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        battery_voltage_v,
        battery_current_a,
        baseline_voltage_v,
        baseline_current_a,
        battery_voltage_v - baseline_voltage_v AS delta_voltage,
        battery_current_a - baseline_current_a AS delta_current
    FROM rolling_baseline
    WHERE baseline_voltage_v IS NOT NULL
      AND baseline_current_a IS NOT NULL
),
flagged AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        battery_voltage_v,
        battery_current_a,
        baseline_voltage_v,
        baseline_current_a,
        delta_voltage,
        delta_current
    FROM deltas
    WHERE delta_voltage <= -0.45
      AND delta_current >= 8.0
)
SELECT
    run_id,
    timestamp_utc,
    seq,
    battery_voltage_v,
    battery_current_a,
    baseline_voltage_v,
    baseline_current_a,
    delta_voltage,
    delta_current
FROM flagged;
