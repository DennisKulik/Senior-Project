#!/usr/bin/env python3
"""
jetson_csv_split_to_parquet.py

Purpose:
Split a Jetson-wide CSV (one row per time tick) into Parquet files.

Modes:
  - column:
      One Parquet per variable. This is the current default / intended mode.
  - group + groups.json:
      One Parquet per explicitly defined group (exact column names).
  - group + keyword_groups.json:
      One Parquet per group via substring matching (more flexible, less strict).

Assumptions:
  - Sensors are asynchronous → missing values are normal.
  - CSV is the raw transport format; Parquet files are logical views.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from src.utils.paths import DEFAULT_DATA_FILE, PARQUET_DIR, RAW_DATA_DIR, CONFIG_DIR
from typing import Dict, List, Iterable, Optional

import pandas as pd


# ---------- helpers ----------

def sanitize_filename(name: str) -> str:
    """
    Normalize column/group names so they’re safe as filenames.
    This is purely cosmetic; it doesn’t affect data semantics.
    """
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "out"


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


def build_groups_from_keywords(
    columns: List[str],
    keyword_groups: Dict[str, List[str]],
    id_cols: List[str],
) -> Dict[str, List[str]]:
    """
    Build column groups using substring matching.

    A column joins a group if ANY keyword appears in its name.
    This trades precision for flexibility and low maintenance.
    """
    groups: Dict[str, List[str]] = {}

    for group_name, keywords in keyword_groups.items():
        matches: List[str] = []

        for col in columns:
            if col in id_cols:
                continue

            lc = col.lower()
            if any(k.lower() in lc for k in keywords):
                matches.append(col)

        if matches:
            groups[group_name] = matches

    return groups


# ---------- core ----------

def split_csv_to_parquet(
    csv_path: Path,
    out_dir: Path,
    mode: str,
    id_cols_preferred: List[str],
    groups_json: Optional[Path],
    keyword_groups_json: Optional[Path],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read once. CSV is expected to be wide 
    df = pd.read_csv(csv_path)
    columns = list(df.columns)

    # ID columns go into every output file if present.
    id_cols = keep_existing(columns, id_cols_preferred)
    if not id_cols:
        raise ValueError(
            f"No ID columns found. Expected one of {id_cols_preferred}. "
            f"CSV header: {columns}"
        )

    try_parse_time_cols(df, id_cols)

    def write_parquet(name: str, signal_cols: List[str]) -> None:
        """
        Write a single Parquet file containing:
          - ID columns (time, seq, run_id, etc.)
          - One or more signal columns
        """
        # Filter defensively; don’t duplicate ID columns.
        signal_cols = [c for c in signal_cols if c in df.columns and c not in id_cols]
        if not signal_cols:
            return

        out = df[id_cols + signal_cols].copy()

        # Drop rows where this file has no actual data.
        # Keeps Parquets compact and avoids all-NaN rows.
        out = out.dropna(subset=signal_cols, how="all")

        out_path = out_dir / f"{sanitize_filename(name)}.parquet"
        out.to_parquet(out_path, index=False)

    # ----- column mode -----
    # Strictest option: one variable -> one file.
    if mode == "column":
        for col in columns:
            if col not in id_cols:
                write_parquet(col, [col])
        return

    # ----- group mode -----
    if mode != "group":
        raise ValueError("mode must be 'column' or 'group'")

    if groups_json:
        # Exact grouping. Most stable, least surprising.
        groups: Dict[str, List[str]] = json.loads(groups_json.read_text(encoding="utf-8"))
        for group_name, cols in groups.items():
            write_parquet(group_name, cols)
        return

    if keyword_groups_json:
        # Fuzzy grouping. Good for early iteration.
        keyword_groups: Dict[str, List[str]] = json.loads(
            keyword_groups_json.read_text(encoding="utf-8")
        )
        groups = build_groups_from_keywords(columns, keyword_groups, id_cols)
        for group_name, cols in groups.items():
            write_parquet(group_name, cols)
        return

    raise ValueError("Group mode requires --groups-json or --keyword-groups-json")


# ---------- CLI ----------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a Jetson-wide sensor CSV into Parquet files."
    )

    parser.add_argument("csv", type=Path, help="Input CSV (Jetson-wide schema)")
    parser.add_argument("--out", type=Path, default=PARQUET_DIR)
    parser.add_argument("--mode", choices=["column", "group"], default="column")

    # Preferred ID columns; only the ones that exist are used.
    parser.add_argument(
        "--id-cols",
        nargs="+",
        default=["timestamp_utc", "seq", "run_id", "source"],
    )

    # Group configs (only meaningful in group mode)
    parser.add_argument("--groups-json", type=Path, default=None)
    parser.add_argument("--keyword-groups-json", type=Path, default=None)

    args = parser.parse_args()

    split_csv_to_parquet(
        csv_path=args.csv,
        out_dir=args.out,
        mode=args.mode,
        id_cols_preferred=args.id_cols,
        groups_json=args.groups_json,
        keyword_groups_json=args.keyword_groups_json,
    )

    print(f"Parquet generation complete -> {args.out.resolve()}")


if __name__ == "__main__":
    main()

