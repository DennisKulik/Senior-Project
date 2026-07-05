timestamp_utc
  Jetson timestamp for the row (UTC). Ordering can jitter.

seq
  Monotonic row counter. Used to detect drops and ordering issues.

run_id
  Identifies a single logging session. Constant for a run.

battery_voltage_v
  Battery pack voltage (V).

battery_current_a
  Battery current draw (A).

depth_m
  Vehicle depth in meters.

imu_ax_mps2
  IMU acceleration, X axis (m/s²).

imu_ay_mps2
  IMU acceleration, Y axis (m/s²).

imu_az_mps2
  IMU acceleration, Z axis (m/s²).

humidity_pct
  Internal humidity percentage.
