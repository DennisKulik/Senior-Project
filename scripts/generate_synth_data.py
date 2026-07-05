from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_CONFIG = {
    "seed": 42,
    "hz": 10,
    "start_timestamp_ms": 1770308460000,
    "run_id": "run01",

    # values based on NTNU data
    "vertical_speed_mps": 0.117,

    "depth_noise_sd": 0.02,

    "imu_ax_noise_sd": 0.0457,
    "imu_ay_noise_sd": 0.0457,
    "imu_az_noise_sd": 0.019,
    "imu_az_mean": 9.81,

    "base_current_a": 2.5,
    "motion_current_scale": 18.0,
    "current_noise_sd": 0.15,

    "start_voltage_v": 16.0,
    "voltage_drain_v": 0.35,
    "voltage_sag_per_amp": 0.045,
    "voltage_noise_sd": 0.02,

    "humidity_start_pct": 45.0,
    "humidity_drift_pct": 0.8,
    "humidity_noise_sd": 0.15,
}


DEFAULT_DEPTH_TARGETS = [
    (0.0, 20),    # depth_m, hold_seconds
    (10.0, 55),
    (0.0, 20),
]


def get_total_duration_s(depth_targets, vertical_speed_mps):
    total_duration_s = 0.0
    current_depth = depth_targets[0][0]

    for target_depth, hold_duration_s in depth_targets:
        travel_distance = abs(target_depth - current_depth)
        travel_duration_s = travel_distance / vertical_speed_mps

        total_duration_s += travel_duration_s
        total_duration_s += hold_duration_s

        current_depth = target_depth

    return total_duration_s


def generate_depth_from_targets(time_s, depth_targets, config):
    depth_m = np.zeros_like(time_s)

    vertical_speed_mps = config["vertical_speed_mps"]
    cursor_s = 0.0
    current_depth = depth_targets[0][0]

    for target_depth, hold_duration_s in depth_targets:
        travel_distance = abs(target_depth - current_depth)
        travel_duration_s = travel_distance / vertical_speed_mps

        travel_start_s = cursor_s
        travel_end_s = travel_start_s + travel_duration_s

        travel_mask = (time_s >= travel_start_s) & (time_s < travel_end_s)

        if travel_duration_s > 0:
            progress = (time_s[travel_mask] - travel_start_s) / travel_duration_s
            depth_m[travel_mask] = current_depth + progress * (
                target_depth - current_depth
            )

        cursor_s = travel_end_s

        hold_start_s = cursor_s
        hold_end_s = hold_start_s + hold_duration_s

        hold_mask = (time_s >= hold_start_s) & (time_s < hold_end_s)
        depth_m[hold_mask] = target_depth

        cursor_s = hold_end_s
        current_depth = target_depth

    return np.maximum(depth_m, 0.0)


def generate_run(depth_targets=None, **overrides):
    config = DEFAULT_CONFIG | overrides
    depth_targets = depth_targets or DEFAULT_DEPTH_TARGETS

    rng = np.random.default_rng(config["seed"])
    hz = config["hz"]

    total_duration_s = get_total_duration_s(
        depth_targets,
        config["vertical_speed_mps"],
    )

    n = int(round(total_duration_s * hz))
    time_s = np.arange(n) / hz

    timestamp_utc_ms = (
        config["start_timestamp_ms"]
        + np.round(time_s * 1000).astype(np.int64)
    )

    timestamp_utc = pd.to_datetime(timestamp_utc_ms, unit="ms", utc=True)

    depth_m = generate_depth_from_targets(time_s, depth_targets, config)

    depth_m += rng.normal(0, config["depth_noise_sd"], size=n)
    depth_m = np.maximum(depth_m, 0.0)

    actual_vertical_speed = np.concatenate([[0.0], np.diff(depth_m)]) * hz
    motion_intensity = np.abs(actual_vertical_speed)

    imu_ax_mps2 = rng.normal(0, config["imu_ax_noise_sd"], size=n)
    imu_ay_mps2 = rng.normal(0, config["imu_ay_noise_sd"], size=n)
    imu_az_mps2 = rng.normal(
        config["imu_az_mean"],
        config["imu_az_noise_sd"],
        size=n,
    )

    imu_az_mps2 += 0.15 * actual_vertical_speed
    imu_ax_mps2 += rng.normal(0, 0.08 * motion_intensity, size=n)
    imu_ay_mps2 += rng.normal(0, 0.04 * motion_intensity, size=n)

    battery_current_a = (
        config["base_current_a"]
        + config["motion_current_scale"] * motion_intensity
        + rng.normal(0, config["current_noise_sd"], size=n)
    )
    battery_current_a = np.maximum(battery_current_a, 0.0)

    slow_drain = np.linspace(0, config["voltage_drain_v"], n)
    battery_voltage_v = (
        config["start_voltage_v"]
        - slow_drain
        - config["voltage_sag_per_amp"] * battery_current_a
        + rng.normal(0, config["voltage_noise_sd"], size=n)
    )

    humidity_pct = (
        config["humidity_start_pct"]
        + np.linspace(0, config["humidity_drift_pct"], n)
        + rng.normal(0, config["humidity_noise_sd"], size=n)
    )

    df = pd.DataFrame({
        "timestamp_utc": timestamp_utc,
        "seq": np.arange(n),
        "run_id": config["run_id"],
        "battery_voltage_v": np.round(battery_voltage_v, 3),
        "battery_current_a": np.round(battery_current_a, 3),
        "depth_m": np.round(depth_m, 3),
        "humidity_pct": np.round(humidity_pct, 2),
        "imu_ax_mps2": np.round(imu_ax_mps2, 4),
        "imu_ay_mps2": np.round(imu_ay_mps2, 4),
        "imu_az_mps2": np.round(imu_az_mps2, 4),
    })

    return df

BASE_START_TIMESTAMP_MS = 1770308460000
RUN_START_STEP_MS = 10 * 60 * 1000  # 10 minutes between run starts
BASE_SEED = 42

RUNS = [
    {
        "run_num": 1,
        "seed": 42,
        # run01 - basic
        "depth_targets": [
            (0.0, 20),    # start at surface and hold for 20s
            (4.0, 30),    # move to 4m and hold for 30s
            (10.0, 55),   # move to 10m and hold for 55s
            (6.0, 40),    # move to 6m and hold for 40s
            (0.0, 20),    # return to surface and hold for 20s
        ],
    },
    {
        "run_num": 2,
        "seed": 43,
        # run02 - basic deep dive
        "depth_targets": [
            (0.0, 25),
            (8.0, 40),
            (12.0, 80),
            (8.0, 30),
            (0.0, 25),
        ],
    },
    {
        "run_num": 3,
        "seed": 44,
        # run03 - descends in steps
        "depth_targets": [
            (0.0, 20),
            (3.0, 30),
            (6.0, 30),
            (9.0, 40),
            (12.0, 50),
            (9.0, 30),
            (5.0, 30),
            (0.0, 20),
        ],
    },
    {
        "run_num": 4,
        "seed": 45,
        # run04 - oscillating at mid depth
        "depth_targets": [
            (0.0, 20),
            (6.0, 40),
            (8.0, 25),
            (6.0, 25),
            (8.0, 25),
            (6.0, 25),
            (10.0, 40),
            (0.0, 20),
        ],
    },
    {
        "run_num": 5,
        "seed": 46,
        # run05 - shallow run, lots of movement
        "depth_targets": [
            (0.0, 20),
            (2.0, 25),
            (4.0, 25),
            (2.0, 25),
            (5.0, 30),
            (3.0, 20),
            (0.0, 20),
        ],
    },
    {
        "run_num": 6,
        "seed": 47,
        # run06 - deep dive, quick return
        "depth_targets": [
            (0.0, 20),
            (10.0, 30),
            (15.0, 40),
            (10.0, 20),
            (0.0, 20),
        ],
    },
]


def main():
    output_dir = Path(__file__).parent / "parquet_out" / "synth_runs"
    output_dir.mkdir(parents=True, exist_ok=True)

    for run in RUNS:
        run_num = run["run_num"]
        run_id = f"run{run_num:02d}"
        seed = run["seed"]
        start_timestamp_ms = (
            BASE_START_TIMESTAMP_MS
            + (run_num - 1) * RUN_START_STEP_MS
        )

        df = generate_run(
            depth_targets=run["depth_targets"],
            run_id=run_id,
            seed=seed,
            start_timestamp_ms=start_timestamp_ms,
            vertical_speed_mps=0.117,
            start_voltage_v=16.0,
        )

        output_path = output_dir / f"{run_id}.parquet"
        df.to_parquet(output_path, index=False)

        print(f"Wrote {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
