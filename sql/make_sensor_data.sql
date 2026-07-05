/*
make_sensor_data.sql — Main Athena external table

Creates the main `sensor_data` external table over the Parquet telemetry files
stored in S3. Athena uses this table as the base data source for all analysis
views in this project.
*/

CREATE EXTERNAL TABLE IF NOT EXISTS sensor_data (
    timestamp_utc timestamp,
    seq int,
    run_id string,
    battery_voltage_v double,
    battery_current_a double,
    depth_m double,
    humidity_pct double,
    imu_ax_mps2 double,
    imu_ay_mps2 double,
    imu_az_mps2 double
)
STORED AS PARQUET
LOCATION 's3://senior-project-data-370852768002-us-east-1-an/curated/';