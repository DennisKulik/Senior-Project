@echo off
echo =====================================
echo Jetson CSV -> Parquet Splitter
echo =====================================
echo.
echo Choose output mode:
echo   1) Column mode (one parquet per variable)
echo   2) Group mode  (uses groups.json)
echo   3) Group mode  (uses keyword_groups.json)
echo.
set /p choice=Enter 1, 2, or 3:

if "%choice%"=="1" (
    python -m src.converters.csv_split_to_parquet data\raw\sensors.csv --out data\parquet_out --mode column
)

if "%choice%"=="2" (
    python -m src.converters.csv_split_to_parquet data\raw\sensors.csv --out data\parquet_out --mode group --groups-json config\groups.json
)

if "%choice%"=="3" (
    python -m src.converters.csv_split_to_parquet data\raw\sensors.csv --out data\parquet_out --mode group --keyword-groups-json config\keyword_groups.json
)

echo.
echo Done.
pause