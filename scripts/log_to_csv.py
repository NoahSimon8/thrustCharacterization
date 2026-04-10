"""
Parse PlatformIO monitor log files and emit CSVs for READ_CSV lines.

Usage:
    python scripts/log_to_csv.py [--battery 15.8] [logfile1.log logfile2.log ...]

If no arguments are provided, all .log files in ./logs are processed.
Outputs (created in the logs directory by default):
    logs/readings.csv -> time_ms, loadcell, grams, raw, scale, tare, throttle, battery_voltage (+ clock_time, source_file)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


def find_logs(args: List[str]) -> Tuple[List[Path], Path]:
    if args:
        files = [Path(a) for a in args]
        out_dir = files[0].parent if files else Path("logs")
    else:
        out_dir = Path("logs")
        files = sorted(out_dir.glob("*.log"))
    return files, out_dir


def parse_logs(paths: Iterable[Path]):
    read_rows = []

    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if ">" not in line:
                    continue
                clock_time, payload = line.split(">", 1)
                clock_time = clock_time.strip()
                payload = payload.strip()
                if payload.startswith("READ_CSV,"):
                    parts = payload.split(",")
                    if len(parts) < 7:
                        continue
                    try:
                        throttle_val = float(parts[7]) if len(parts) > 7 else None
                        read_rows.append(
                            {
                                "clock_time": clock_time,
                                "time_ms": int(parts[1]),
                                "loadcell": int(parts[2]),
                                "grams": float(parts[3]),
                                "raw": int(parts[4]),
                                "scale": float(parts[5]),
                                "tare": int(parts[6]),
                                "throttle": throttle_val,
                                "source_file": path.name,
                            }
                        )
                    except ValueError:
                        continue
    return read_rows


def write_csv(path: Path, fieldnames: List[str], rows: List[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Convert monitor logs to readings.csv")
    parser.add_argument("--battery", "-b", type=float, default=None, help="Battery voltage to include in output rows")
    parser.add_argument("logs", nargs="*", help="Optional list of .log files; defaults to logs/*.log")
    args = parser.parse_args(argv)

    files, out_dir = find_logs(args.logs)
    if not files:
        print("No log files found.")
        return 1

    read_rows = parse_logs(files)
    if args.battery is not None:
        for row in read_rows:
            row["battery_voltage"] = args.battery
    else:
        for row in read_rows:
            row["battery_voltage"] = None

    write_csv(
        out_dir / "readings.csv",
        ["source_file", "clock_time", "time_ms", "loadcell", "grams", "raw", "scale", "tare", "throttle", "battery_voltage"],
        read_rows,
    )

    print(f"Wrote {len(read_rows)} reading rows to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
