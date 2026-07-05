/*
run_phase_segments.sql — Row-level dive phase classification

Analyzes depth over time per run and labels each telemetry row as:
  1. Surface         — vehicle is near the surface
  2. Descending      — depth is increasing above the movement threshold
  3. Ascending       — depth is decreasing below the movement threshold
  4. Holding depth   — vehicle is below the surface but not moving vertically
                       enough to count as ascent or descent

This view provides row-level phase labels that can be used for phase-based
analysis in Grafana, such as time spent per phase, average current/voltage per
phase, and energy consumption per phase.

NOTE: Surface is defined as depth <= 0.25 m. Vertical movement is classified
using a rate threshold of 0.03 m/s:
    descending      = vertical_rate_mps >= 0.03
    ascending       = vertical_rate_mps <= -0.03
    holding_depth   = all other below-surface rows
*/

CREATE OR REPLACE VIEW run_phase_segments AS
WITH ordered AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        depth_m,
        LAG(depth_m) OVER (
            PARTITION BY run_id
            ORDER BY timestamp_utc, seq
        ) AS prev_depth,
        LAG(timestamp_utc) OVER (
            PARTITION BY run_id
            ORDER BY timestamp_utc, seq
        ) AS prev_time
    FROM sensor_data
    WHERE depth_m IS NOT NULL
),
with_rates AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        depth_m,
        (
            to_unixtime(timestamp_utc) -
            to_unixtime(prev_time)
        ) AS delta_seconds,
        (
            depth_m - prev_depth
        ) / NULLIF(
            (
                to_unixtime(timestamp_utc) -
                to_unixtime(prev_time)
            ),
            0.0
        ) AS vertical_rate_mps
    FROM ordered
    WHERE prev_time IS NOT NULL
),
classified AS (
    SELECT
        run_id,
        timestamp_utc,
        seq,
        depth_m,
        delta_seconds,
        vertical_rate_mps,
        CASE
            WHEN depth_m <= 0.25 THEN 'surface'
            WHEN vertical_rate_mps >= 0.03 THEN 'descending'
            WHEN vertical_rate_mps <= -0.03 THEN 'ascending'
            ELSE 'holding_depth'
        END AS phase
    FROM with_rates
)
SELECT
    run_id,
    timestamp_utc,
    seq,
    depth_m,
    delta_seconds,
    vertical_rate_mps,
    phase
FROM classified
ORDER BY run_id, timestamp_utc, seq;
