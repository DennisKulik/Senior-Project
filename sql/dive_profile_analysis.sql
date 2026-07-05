/*
depth_run_summary.sql — Dive profile summary per run

Analyzes depth_m over time per run and summarizes:
  1. Maximum depth        — deepest point reached during the run
  2. Average depth        — mean recorded depth across the run
  3. Descent/ascent rate  — average vertical movement rate while depth is changing
  4. Time at depth        — total time spent near the run's maximum depth

This view gives a high-level summary of each run's dive profile using depth
telemetry and timestamp spacing.

NOTE: Time at depth is defined as time spent at or above 90% of the run's
maximum depth. 
*/

CREATE OR REPLACE VIEW depth_run_summary AS
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
    FROM sensor_data
    WHERE depth_m IS NOT NULL
),
with_rates AS (
    SELECT
        run_id,
        timestamp_utc,
        depth_m,
        (
            to_unixtime(timestamp_utc) - 
            to_unixtime(prev_time)
        ) as delta_seconds,
        (depth_m - prev_depth) / 
            NULLIF(
                to_unixtime(timestamp_utc) - 
                to_unixtime(prev_time),
                0.0
            ) as vertical_rate_mps
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
    ON s.run_id = b.run_id;
