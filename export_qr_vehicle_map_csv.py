#!/usr/bin/env python3
"""
Export one CSV in the BPCL layout: S.No., QR Code, TruckNumber, Plant Code, Inserted At.

Rows come from qr_vehicle_map (one row per QR/packet). If truck_number is NULL there,
this script fills it from vehicle_sessions (entry..exit window), then anpr_events at or
before inserted_at, then last_anpr_per_line and global fallbacks.

Filename: BPCL_ANPR_<plant>_<YYYYMMDDHHMMSS>0000.csv (time from last qr_vehicle_map row).

No JSON — edit DEFAULT_* or use CLI.

Examples:
  python3 export_qr_vehicle_map_csv.py
  python3 export_qr_vehicle_map_csv.py --db /path/to/anpr.db --plant-code 3101
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB_PATH = "/home/jbmai/PFS/Database/anpr.db"
DEFAULT_OUT_DIR = "/home/jbmai/PFS/Report/ANPR"
DEFAULT_PLANT_CODE = "3101"

_EXPORT_SQL = """
SELECT
  q.qr_code,
  COALESCE(
    NULLIF(TRIM(q.truck_number), ''),
    (SELECT vs.truck_number FROM vehicle_sessions vs
     WHERE vs.line_id = q.line_id
       AND vs.entry_at <= q.inserted_at
       AND (vs.exit_at IS NULL OR q.inserted_at <= vs.exit_at)
     ORDER BY vs.entry_at DESC LIMIT 1),
    (SELECT vs.truck_number FROM vehicle_sessions vs
     WHERE vs.line_id = CASE WHEN q.line_id = 1 THEN 2 WHEN q.line_id = 2 THEN 1 ELSE q.line_id END
       AND vs.entry_at <= q.inserted_at
       AND (vs.exit_at IS NULL OR q.inserted_at <= vs.exit_at)
     ORDER BY vs.entry_at DESC LIMIT 1),
    (SELECT e.truck_number FROM anpr_events e
     WHERE e.line_id = q.line_id AND e.inserted_at <= q.inserted_at
     ORDER BY e.inserted_at DESC, e.id DESC LIMIT 1),
    (SELECT e.truck_number FROM anpr_events e
     WHERE e.line_id = CASE WHEN q.line_id = 1 THEN 2 WHEN q.line_id = 2 THEN 1 ELSE q.line_id END
       AND e.inserted_at <= q.inserted_at
     ORDER BY e.inserted_at DESC, e.id DESC LIMIT 1),
    (SELECT e.truck_number FROM anpr_events e
     WHERE e.inserted_at <= q.inserted_at
     ORDER BY e.inserted_at DESC, e.id DESC LIMIT 1),
    NULLIF(TRIM(ls.truck_number), ''),
    NULLIF(TRIM(lo.truck_number), ''),
    (SELECT truck_number FROM anpr_events ORDER BY inserted_at DESC, id DESC LIMIT 1)
  ) AS truck_number,
  COALESCE(NULLIF(TRIM(q.plant_code), ''), ?) AS plant_code,
  q.inserted_at
FROM qr_vehicle_map q
LEFT JOIN last_anpr_per_line ls ON ls.line_id = q.line_id
LEFT JOIN last_anpr_per_line lo ON lo.line_id = CASE
  WHEN q.line_id = 1 THEN 2
  WHEN q.line_id = 2 THEN 1
  ELSE q.line_id
END
ORDER BY q.inserted_at ASC, q.id ASC
"""


def _parse_ts14(value: str) -> str:
    s = (value or "").strip().replace("T", " ")[:19]
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = datetime.now()
    return dt.strftime("%Y%m%d%H%M%S")


def _format_time_cell(value: str | None) -> str:
    if not value:
        return ""
    s = str(value).strip().replace("T", " ")
    if len(s) >= 19:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
        except ValueError:
            pass
    return s


def main() -> None:
    p = argparse.ArgumentParser(description="Export qr_vehicle_map (+ joined truck) to BPCL CSV")
    p.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path")
    p.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output folder")
    p.add_argument("--plant-code", default=DEFAULT_PLANT_CODE, help="Default plant if column empty")
    args = p.parse_args()

    if not os.path.isfile(args.db):
        print(f"DB not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(_EXPORT_SQL, (args.plant_code,)).fetchall()
    except sqlite3.OperationalError as e:
        print(
            "Export query failed (missing tables?). Falling back to qr_vehicle_map only.\n"
            f"  {e}",
            file=sys.stderr,
        )
        rows = con.execute(
            """
            SELECT qr_code, truck_number, plant_code, inserted_at
            FROM qr_vehicle_map
            ORDER BY inserted_at ASC, id ASC
            """
        ).fetchall()
    finally:
        con.close()

    if not rows:
        print("No data to export.", file=sys.stderr)
        sys.exit(1)

    ts14 = _parse_ts14(str(rows[-1]["inserted_at"]))
    fname = f"BPCL_ANPR_{args.plant_code}_{ts14}0000.csv"
    out_path = os.path.join(args.out_dir, fname)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["S.No.", "QR Code", "TruckNumber", "Plant Code", "Inserted At"])
        for i, r in enumerate(rows, start=1):
            w.writerow(
                [
                    i,
                    r["qr_code"] if r["qr_code"] is not None else "",
                    r["truck_number"] if r["truck_number"] is not None else "",
                    r["plant_code"] if r["plant_code"] is not None else "",
                    _format_time_cell(r["inserted_at"]),
                ]
            )

    print(out_path)


if __name__ == "__main__":
    main()

