### Energy consumption per run

Estimates total battery energy usage for each run in watt-hours using voltage and current telemetry. The output is grouped by `run_id` so runs can be compared directly.

### Dive profile and phase segmentation

Uses depth over time to identify major parts of a run, such as descent, steady-depth, and ascent. The output summarizes depth behavior for each run or phase.

### Voltage sag and high-load event detection

Finds points where voltage drops while current increases. This is meant to highlight possible high-load moments in the battery data.

### Motion intensity and anomaly detection

Uses IMU acceleration data to estimate overall motion intensity and flag unusually large changes. The output identifies timestamps where motion differs sharply from nearby readings.