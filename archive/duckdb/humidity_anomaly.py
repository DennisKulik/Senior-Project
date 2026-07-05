"""
humidity_anomaly.py — Internal humidity rise detection

Monitors humidity_pct over time per run and flags:
  1. Threshold breaches  — K or more consecutive samples above a safe ceiling
  2. Rapid rise events   — rise rate above N% per minute (time-normalized)
  3. Sustained elevation — rolling average above ceiling for a whole run

A rising or spiking internal humidity on an underwater vehicle is a leading
indicator of water ingress / seal failure and warrants immediate inspection.

NOTE: Rolling window is row-based (samples), not time-based. If your logging
rate varies significantly between runs, interpret window sizes accordingly.

Usage:
    python humidity_anomaly.py
    python humidity_anomaly.py --data-dir /path/to/parquet_out
    python humidity_anomaly.py --threshold 70 --rise-rate 5.0 --window 10 --consecutive 3
"""

import argparse
from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR

import duckdb

# ==== Defaults ====
ROLLING_WINDOW = 10  # samples for rolling baseline (row-based)
CONSECUTIVE_K = 3  # consecutive samples above ceiling = sustained breach
DEFAULT_DATA_DIR = PARQUET_DIR
HUMIDITY_FILE = "humidity_pct.parquet"
SAFE_HUMIDITY_CEILING = 70.0
RAPID_RISE_RATE = 3.0  # % per minute rise rate threshold for flagging rapid rise events


def main():
    parser = argparse.ArgumentParser(
        description="Detect internal humidity anomalies in underwater vehicle telemetry"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing parquet files (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=SAFE_HUMIDITY_CEILING,
        help="Humidity %% ceiling (default: {SAFE_HUMIDITY_CEILING})",
    )
    parser.add_argument(
        "--rise-rate",
        type=float,
        default=RAPID_RISE_RATE,
        help="Max allowed %% rise per minute before flagging a spike (default: {RAPID_RISE_RATE})",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=ROLLING_WINDOW,
        help="Rolling window size in samples for baseline (default: {ROLLING_WINDOW})",
    )
    parser.add_argument(
        "--consecutive",
        type=int,
        default=CONSECUTIVE_K,
        help="Consecutive samples above ceiling count as sustained breach",
    )
    args = parser.parse_args()

    humidity_path = args.data_dir / HUMIDITY_FILE

    if not humidity_path.exists():
        print(f"ERROR: humidity parquet not found at {humidity_path}")
        raise SystemExit(1)

    con = duckdb.connect()

    # Filter to sane sensor range up front — nulls and out-of-range values
    # are excluded from all downstream analysis to avoid distorting averages.
    con.execute(f"""
        CREATE OR REPLACE VIEW humidity AS
        SELECT
            CAST(timestamp_utc AS TIMESTAMP) AS timestamp_utc,
            seq,
            run_id,
            humidity_pct
        FROM read_parquet('{humidity_path.as_posix()}')
        WHERE humidity_pct IS NOT NULL
          AND humidity_pct BETWEEN 0 AND 100
    """)

    # ==== Per-run summary ====
    print("\n=== Humidity Summary per Run ===")
    summary = con.execute("""
        SELECT
            run_id,
            ROUND(MIN(humidity_pct),                          2) AS min_pct,
            ROUND(AVG(humidity_pct),                          2) AS avg_pct,
            ROUND(MAX(humidity_pct),                          2) AS max_pct,
            ROUND(MAX(humidity_pct) - MIN(humidity_pct),      2) AS total_rise_pct
        FROM humidity
        GROUP BY run_id
        ORDER BY run_id
    """).fetchdf()
    print(summary.to_string(index=False))

    # ==== Sustained breach events (K consecutive samples above ceiling) ====
    # Uses a running group counter to identify unbroken streaks above threshold.
    print(
        print(
            f"\n=== Sustained Breach Events "
            f"({args.consecutive}+ consecutive samples > {args.threshold}%) ==="
        )
    )
    sustained_breaches = con.execute(f"""
        WITH flagged AS (
            SELECT
                run_id,
                timestamp_utc,
                seq,
                ROUND(humidity_pct, 2) AS humidity_pct,
                CASE WHEN humidity_pct > {args.threshold} THEN 1 ELSE 0 END AS above
            FROM humidity
        ),
        grouped AS (
            SELECT
                run_id,
                timestamp_utc,
                seq,
                humidity_pct,
                above,
                -- Each time 'above' changes, the group counter increments.
                -- This creates a unique group ID per consecutive streak.
                SUM(CASE WHEN above = 0 THEN 1 ELSE 0 END) OVER (
                    PARTITION BY run_id
                    ORDER BY timestamp_utc, seq
                    ROWS UNBOUNDED PRECEDING
                ) AS group_id
            FROM flagged
        ),
        streaks AS (
            SELECT
                run_id,
                group_id,
                COUNT(*)                    AS streak_length,
                MIN(timestamp_utc)          AS streak_start,
                MAX(timestamp_utc)          AS streak_end,
                ROUND(MAX(humidity_pct), 2) AS peak_humidity
            FROM grouped
            WHERE above = 1
            GROUP BY run_id, group_id
        )
        SELECT
            run_id,
            streak_start,
            streak_end,
            streak_length AS consecutive_samples,
            peak_humidity
        FROM streaks
        WHERE streak_length >= {args.consecutive}
        ORDER BY run_id, streak_start
    """).fetchdf()

    if sustained_breaches.empty:
        print(
            f"No sustained breaches detected "
            f"({args.consecutive}+ consecutive samples above {args.threshold}%)."
        )
    else:
        print(f"Detected {len(sustained_breaches)} sustained breach streak(s):")
        print(sustained_breaches.to_string(index=False))

        breach_summary = (
            sustained_breaches.groupby("run_id")
            .size()
            .reset_index(name="streak_count")
            .sort_values("run_id")
        )
        print("\nSustained breach streaks per run:")
        print(breach_summary.to_string(index=False))

    # ==== Rapid rise events (% per minute, time-normalized) ====
    print(f"\n=== Rapid Rise Events (rise rate > {args.rise_rate}% per minute) ===")
    rapid_rises = con.execute(f"""
        WITH ordered AS (
            SELECT
                run_id,
                timestamp_utc,
                seq,
                humidity_pct,
                LAG(humidity_pct)  OVER (PARTITION BY run_id ORDER BY timestamp_utc, seq) AS prev_humidity,
                LAG(timestamp_utc) OVER (PARTITION BY run_id ORDER BY timestamp_utc, seq) AS prev_time
            FROM humidity
        ),
        with_rate AS (
            SELECT
                run_id,
                timestamp_utc,
                ROUND(humidity_pct,  2) AS humidity_pct,
                ROUND(prev_humidity, 2) AS prev_humidity,
                -- time delta in minutes
                ROUND(
                    EXTRACT(EPOCH FROM (timestamp_utc - prev_time)) / 60.0,
                    4
                ) AS dt_minutes,
                -- rise rate: % per minute (null-safe: skip zero dt)
                ROUND(
                    (humidity_pct - prev_humidity) /
                    NULLIF(EXTRACT(EPOCH FROM (timestamp_utc - prev_time)) / 60.0, 0),
                    4
                ) AS rise_rate_per_min
            FROM ordered
            WHERE prev_humidity IS NOT NULL
              AND prev_time IS NOT NULL
        )
        SELECT *
        FROM with_rate
        WHERE rise_rate_per_min > {args.rise_rate}
        ORDER BY run_id, timestamp_utc
    """).fetchdf()

    if rapid_rises.empty:
        print(f"No rapid rises detected above {args.rise_rate}%/min.")
    else:
        print(f"Detected {len(rapid_rises)} rapid rise event(s):")
        print(rapid_rises.to_string(index=False))

        rise_summary = (
            rapid_rises.groupby("run_id")
            .size()
            .reset_index(name="rapid_rise_count")
            .sort_values("run_id")
        )
        print("\nRapid rise events per run:")
        print(rise_summary.to_string(index=False))

    # ==== Rolling baseline elevation ====
    # Window is row-based. Document the assumed sample rate if yours is stable.
    # (synth data is assumed semi-stable!!)
    print(
        f"\n=== Sustained Elevation — Rolling Avg > "
        f"{args.threshold}% (window={args.window} samples) ==="
    )
    rolling_elev = con.execute(f"""
        WITH rolling AS (
            SELECT
                run_id,
                timestamp_utc,
                seq,
                humidity_pct,
                AVG(humidity_pct) OVER (
                    PARTITION BY run_id
                    ORDER BY timestamp_utc, seq
                    ROWS BETWEEN {args.window} PRECEDING AND CURRENT ROW
                ) AS rolling_avg
            FROM humidity
        )
        SELECT
            run_id,
            COUNT(*)                      AS samples_elevated,
            ROUND(MAX(rolling_avg),  2)   AS peak_rolling_avg,
            ROUND(AVG(rolling_avg),  2)   AS mean_rolling_avg
        FROM rolling
        WHERE rolling_avg > {args.threshold}
        GROUP BY run_id
        ORDER BY run_id
    """).fetchdf()

    if rolling_elev.empty:
        print(f"No runs showed a sustained rolling average above {args.threshold}%.")
    else:
        print(f"Runs with elevated rolling average (>{args.threshold}%):")
        print(rolling_elev.to_string(index=False))

    con.close()


if __name__ == "__main__":
    main()

