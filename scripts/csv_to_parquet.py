#!/usr/bin/env python3
"""
csv_to_parquet.py

Purpose:
Convert a Jetson-wide CSV (one row per time tick) into a single Parquet file.

Assumptions:
  - Sensors are asynchronous -> missing values are normal.
  - CSV is the raw transport format; the output Parquet is the analysis-ready view.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE
from typing import List, Iterable

import pandas as pd


# ---------- helpers ----------

def keep_existing(all_cols: Iterable[str], preferred: List[str]) -> List[str]:
    """
    ID columns are optional but useful.
    We keep whichever preferred ones actually exist instead of hard-failing.
    """
    s = set(all_cols)
    return [c for c in preferred if c in s]


def try_parse_time_cols(df: pd.DataFrame, id_cols: List[str]) -> None:
    """
    Attempt to parse timestamp-like ID columns.
    If parsing fails, values become NaT but the pipeline continues.
    """
    for c in id_cols:
        if "time" in c.lower() or "timestamp" in c.lower():
            df[c] = pd.to_datetime(df[c], errors="coerce", utc=True)


# ---------- core ----------

def csv_to_parquet(
    csv_path: Path,
    out_path: Path,
    id_cols_preferred: List[str],
    drop_all_nan_rows: bool = False,
) -> None:
    """
    Convert one wide CSV into one Parquet file.

    The output includes:
      - all ID columns that exist
      - all signal/data columns
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    columns = list(df.columns)

    id_cols = keep_existing(columns, id_cols_preferred)
    try_parse_time_cols(df, id_cols)

    # Preserve original column order, just using the CSV as-is.
    out = df.copy()

    if drop_all_nan_rows:
        signal_cols = [c for c in columns if c not in id_cols]
        if signal_cols:
            out = out.dropna(subset=signal_cols, how="all")

    out.to_parquet(out_path, index=False)


# ---------- CLI ----------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a Jetson-wide sensor CSV into a single Parquet file."
    )

    parser.add_argument("csv", type=Path, help="Input CSV (Jetson-wide schema)")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="Output Parquet file path",
    )

    # Preferred ID columns; only the ones that exist are used.
    parser.add_argument(
        "--id-cols",
        nargs="+",
        default=["timestamp_utc", "seq", "run_id", "source"],
    )

    parser.add_argument(
        "--drop-all-nan-rows",
        action="store_true",
        help="Drop rows where all non-ID columns are null",
    )

    args = parser.parse_args()

    csv_to_parquet(
        csv_path=args.csv,
        out_path=args.out,
        id_cols_preferred=args.id_cols,
        drop_all_nan_rows=args.drop_all_nan_rows,
    )

    print(f"Parquet generation complete -> {args.out.resolve()}")


if __name__ == "__main__":
    main()

