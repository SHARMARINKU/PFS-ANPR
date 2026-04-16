"""
Maps QR packet scans to vehicles using SQLite: ANPR-driven sessions plus fallbacks.

vehicle_sessions tracks per-line stays: entry_at / last_seen_at / exit_at. Sessions are
opened on first plate read, last_seen is refreshed while the same plate is seen, closed
by idle timeout (exit_at = last_seen_at), exit ROI (exit_at = detection time), or a
different plate on the same line (exit_at = previous last_seen_at). QR rows use scan
time; truck is the session where entry_at <= scan <= exit (or open session). Export
reuses the same resolution for pending rows.
"""
from __future__ import annotations

import csv
import fcntl
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE, "config", "integration_config.json")

_lock = threading.Lock()
_db_path: Optional[str] = None
_plant_code: str = "3101"
_plant_name: str = "Plant"
_csv_export_dir: str = ""
_sftp_remote_subdir: str = "qr_mapping"
_hourly_started = False
_export_interval_sec: float = 3600.0
_run_immediately_on_start: bool = True
_db_fallback_done = False
_csv_file_prefix: str = "BPCL_ANPR"
_session_idle_sec: float = 15.0
_session_tick_sec: float = 2.0
_exit_boom_labels: List[str] = []
_session_sweeper_started = False


def _load_config() -> None:
    global _db_path, _plant_code, _plant_name, _csv_export_dir, _sftp_remote_subdir
    global _export_interval_sec, _run_immediately_on_start, _csv_file_prefix
    global _session_idle_sec, _session_tick_sec, _exit_boom_labels
    if os.path.isfile(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        plant_cfg = cfg.get("plant", {})
        db_cfg = cfg.get("database", {})
        export_cfg = cfg.get("export_service", {})
        sftp_cfg = cfg.get("sftp", {})
        sess_cfg = cfg.get("anpr_sessions", {}) or {}

        _plant_code = str(plant_cfg.get("plant_code", "3101"))
        _plant_name = str(plant_cfg.get("plant_name", "Plant"))
        rel_db = db_cfg.get("db_path", "/home/jbmai/PFS/Database/anpr.db")
        _db_path = os.path.join(_BASE, rel_db) if not os.path.isabs(rel_db) else rel_db
        rel_csv = export_cfg.get("csv_export_dir", "report/qr_mapping_export")
        _csv_export_dir = os.path.join(_BASE, rel_csv) if not os.path.isabs(rel_csv) else rel_csv
        _sftp_remote_subdir = str(sftp_cfg.get("remote_subdir", "qr_mapping"))
        _export_interval_sec = float(export_cfg.get("interval_sec", 3600))
        _run_immediately_on_start = bool(export_cfg.get("run_immediately_on_start", True))
        _csv_file_prefix = str(export_cfg.get("csv_file_prefix", "RINK_ANPR"))
        _session_idle_sec = float(sess_cfg.get("idle_sec", 15))
        _session_tick_sec = float(sess_cfg.get("sweeper_interval_sec", 2))
        _exit_boom_labels = [str(x) for x in (sess_cfg.get("exit_boom_labels") or []) if x]
    else:
        _db_path = "/home/jbmai/PFS/Database/anpr.db"
        _csv_export_dir = os.path.join(_BASE, "report", "qr_mapping_export")
        _session_idle_sec = 15.0
        _session_tick_sec = 2.0
        _exit_boom_labels = []


def _conn() -> sqlite3.Connection:
    assert _db_path is not None
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    c = sqlite3.connect(_db_path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _ensure_writable_db_path() -> None:
    global _db_path, _db_fallback_done
    assert _db_path is not None
    db_dir = os.path.dirname(_db_path)
    try:
        os.makedirs(db_dir, exist_ok=True)
        test_file = os.path.join(db_dir, ".db_write_test.tmp")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return
    except Exception as e:
        fallback = os.path.join(_BASE, "data", "anpr.db")
        if _db_path != fallback:
            logger.warning(
                "Configured DB path not writable: %s (%s). Using fallback DB: %s",
                _db_path,
                e,
                fallback,
            )
            _db_path = fallback
        if not _db_fallback_done:
            _db_fallback_done = True
        os.makedirs(os.path.dirname(_db_path), exist_ok=True)


def _norm_plate(p: str) -> str:
    return "".join(ch for ch in (p or "").upper() if not ch.isspace())


def _parse_ts_for_delta(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _close_idle_sessions() -> None:
    """Close open sessions where last_seen is older than idle_sec; exit_at := last_seen_at."""
    now = datetime.now()
    with _lock:
        with _conn() as c:
            rows = c.execute(
                "SELECT id, last_seen_at FROM vehicle_sessions WHERE exit_at IS NULL"
            ).fetchall()
            for row in rows:
                dt = _parse_ts_for_delta(str(row["last_seen_at"]))
                if dt is None:
                    continue
                if (now - dt).total_seconds() > _session_idle_sec:
                    c.execute(
                        "UPDATE vehicle_sessions SET exit_at = last_seen_at WHERE id = ?",
                        (int(row["id"]),),
                    )
                    logger.info(
                        "[SESSION] idle close id=%s exit_at=%s",
                        row["id"],
                        row["last_seen_at"],
                    )


def _session_sweeper_loop() -> None:
    while True:
        time.sleep(max(0.5, _session_tick_sec))
        try:
            init_db()
            _close_idle_sessions()
        except Exception as e:
            logger.exception("Session sweeper error: %s", e)


def ensure_session_sweeper_started() -> None:
    global _session_sweeper_started
    if _session_sweeper_started:
        return
    _session_sweeper_started = True
    t = threading.Thread(target=_session_sweeper_loop, daemon=True)
    t.start()
    logger.info(
        "[SESSION] Sweeper started (tick=%ss, idle_close=%ss).",
        _session_tick_sec,
        _session_idle_sec,
    )


def init_db() -> None:
    _load_config()
    _ensure_writable_db_path()
    os.makedirs(_csv_export_dir, exist_ok=True)
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS qr_vehicle_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_id INTEGER NOT NULL,
                qr_code TEXT NOT NULL,
                truck_number TEXT,
                plant_code TEXT NOT NULL,
                inserted_at TEXT NOT NULL,
                exported_at TEXT
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_qvm_export ON qr_vehicle_map(exported_at)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_qvm_inserted ON qr_vehicle_map(inserted_at)"
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS last_anpr_per_line (
                line_id INTEGER PRIMARY KEY,
                truck_number TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS anpr_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_id INTEGER,
                boom_label TEXT,
                truck_number TEXT NOT NULL,
                inserted_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_anpr_events_inserted ON anpr_events(inserted_at)"
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicle_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_id INTEGER NOT NULL,
                truck_number TEXT NOT NULL,
                entry_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                exit_at TEXT
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_vs_line_entry ON vehicle_sessions(line_id, entry_at)"
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS export_sequence (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
    ensure_session_sweeper_started()


def _next_export_sequence() -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT value FROM export_sequence WHERE name = ?",
            ("csv_file",),
        ).fetchone()
        if row is None:
            c.execute(
                "INSERT INTO export_sequence (name, value) VALUES (?, ?)",
                ("csv_file", 1),
            )
            return 1
        seq = int(row["value"]) + 1
        c.execute(
            "UPDATE export_sequence SET value = ? WHERE name = ?",
            (seq, "csv_file"),
        )
        return seq


def _boom_to_line(boom_label: str) -> Optional[int]:
    """Map ANPR ROI label to line 1/2 (Boom-1/2, LINE-1/2, or exit labels like Exit-LINE-2)."""
    s = (boom_label or "").strip().upper()
    if "BOOM-1" in s:
        return 1
    if "BOOM-2" in s:
        return 2
    if "LINE-1" in s and "LINE-2" not in s:
        return 1
    if "LINE-2" in s:
        return 2
    return None


def _line_name_to_id(line_name: str) -> Optional[int]:
    s = (line_name or "").upper()
    if "LINE-1" in s or s.endswith("1"):
        return 1
    if "LINE-2" in s or s.endswith("2"):
        return 2
    return None


def _is_exit_boom_label(boom_label: str) -> bool:
    """True if boom_label contains any configured exit ROI substring (case-insensitive)."""
    if not _exit_boom_labels:
        return False
    s = (boom_label or "").upper()
    for x in _exit_boom_labels:
        if x.upper() in s:
            return True
    return False


def _process_vehicle_session(
    c: sqlite3.Connection, line_id: int, raw_plate: str, ts: str, is_exit: bool
) -> None:
    """Update vehicle_sessions: exit ROI, same-plate refresh, plate change, or new session."""
    np = _norm_plate(raw_plate)
    row = c.execute(
        """
        SELECT id, truck_number, last_seen_at FROM vehicle_sessions
        WHERE line_id = ? AND exit_at IS NULL
        ORDER BY id DESC LIMIT 1
        """,
        (line_id,),
    ).fetchone()

    if is_exit:
        if row and _norm_plate(row["truck_number"]) == np:
            c.execute(
                "UPDATE vehicle_sessions SET exit_at = ? WHERE id = ?",
                (ts, int(row["id"])),
            )
            logger.info(
                "[SESSION] exit ROI line=%s plate=%s exit_at=%s",
                line_id,
                raw_plate,
                ts,
            )
        return

    if row:
        open_n = _norm_plate(row["truck_number"])
        if open_n == np:
            c.execute(
                "UPDATE vehicle_sessions SET last_seen_at = ? WHERE id = ?",
                (ts, int(row["id"])),
            )
            return
        c.execute(
            "UPDATE vehicle_sessions SET exit_at = ? WHERE id = ?",
            (row["last_seen_at"], int(row["id"])),
        )
        logger.info(
            "[SESSION] plate change line=%s old=%s exit_at=%s new=%s",
            line_id,
            row["truck_number"],
            row["last_seen_at"],
            raw_plate,
        )
    c.execute(
        """
        INSERT INTO vehicle_sessions (line_id, truck_number, entry_at, last_seen_at, exit_at)
        VALUES (?, ?, ?, ?, NULL)
        """,
        (line_id, raw_plate, ts, ts),
    )
    logger.info("[SESSION] start line=%s plate=%s entry=%s", line_id, raw_plate, ts)


def on_anpr_boom(vehicle_no: str, boom_label: str) -> None:
    """Call from ANPR when a plate is read inside Boom-1 or Boom-2 ROI (or exit ROI)."""
    init_db()
    line = _boom_to_line(boom_label)
    if line is None:
        logger.debug("Unknown boom label: %s", boom_label)
        return
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    is_exit = _is_exit_boom_label(boom_label)
    with _lock:
        with _conn() as c:
            c.execute(
                """
                INSERT INTO anpr_events (line_id, boom_label, truck_number, inserted_at)
                VALUES (?, ?, ?, ?)
                """,
                (line, boom_label, vehicle_no, now),
            )
            c.execute(
                """
                INSERT INTO last_anpr_per_line (line_id, truck_number, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(line_id) DO UPDATE SET
                    truck_number = excluded.truck_number,
                    updated_at = excluded.updated_at
                """,
                (line, vehicle_no, now),
            )
            _process_vehicle_session(c, line, vehicle_no, now, is_exit)
    logger.info("[MAPPING] ANPR line %s (%s) -> %s", line, boom_label, vehicle_no)


def _lookup_last_truck_for_line(line_id: int) -> Optional[str]:
    with _conn() as c:
        row = c.execute(
            "SELECT truck_number FROM last_anpr_per_line WHERE line_id = ?",
            (line_id,),
        ).fetchone()
    return row[0] if row else None


def _qr_scan_timestamp_iso(record: Dict[str, Any]) -> str:
    """Normalize QR scan time to 'YYYY-MM-DD HH:MM:SS' (matches anpr_events.inserted_at)."""
    ts: Any = record.get("timestamp")
    if isinstance(ts, datetime):
        return ts.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    if ts is not None:
        s = str(ts).strip().replace("T", " ")
        if len(s) >= 19:
            return s[:19]
        if s:
            return s
    return datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _last_truck_on_line_before(
    c: sqlite3.Connection, line_id: int, scan_ts: str
) -> Optional[str]:
    row = c.execute(
        """
        SELECT truck_number FROM anpr_events
        WHERE line_id = ? AND inserted_at <= ?
        ORDER BY inserted_at DESC, id DESC
        LIMIT 1
        """,
        (line_id, scan_ts),
    ).fetchone()
    if row and row[0]:
        return str(row[0]).strip() or None
    return None


def _truck_from_session_at(
    c: sqlite3.Connection, line_id: int, scan_ts: str
) -> Optional[str]:
    """Truck whose session window contains scan_ts: entry_at <= t <= exit_at (open if exit null)."""
    row = c.execute(
        """
        SELECT truck_number FROM vehicle_sessions
        WHERE line_id = ?
          AND entry_at <= ?
          AND (exit_at IS NULL OR ? <= exit_at)
        ORDER BY entry_at DESC
        LIMIT 1
        """,
        (line_id, scan_ts, scan_ts),
    ).fetchone()
    if row and row[0]:
        return str(row[0]).strip() or None
    return None


def _resolve_truck_for_qr_at_time(line_id: int, scan_ts: str) -> Optional[str]:
    """
    Prefer vehicle_sessions (entry/exit window), then anpr_events at/before scan time,
    then last_anpr / global fallbacks.
    """
    other = 2 if line_id == 1 else 1
    with _conn() as c:
        try:
            truck = _truck_from_session_at(c, line_id, scan_ts)
            if truck:
                return truck
            truck = _truck_from_session_at(c, other, scan_ts)
            if truck:
                logger.info(
                    "[MAPPING] truck from session line %s at %s for QR line %s",
                    other,
                    scan_ts,
                    line_id,
                )
                return truck
        except sqlite3.OperationalError:
            pass
        truck = _last_truck_on_line_before(c, line_id, scan_ts)
        if truck:
            return truck
        truck = _last_truck_on_line_before(c, other, scan_ts)
        if truck:
            logger.info(
                "[MAPPING] truck from line %s at/before %s for QR line %s",
                other,
                scan_ts,
                line_id,
            )
            return truck
        row = c.execute(
            """
            SELECT truck_number FROM anpr_events
            WHERE inserted_at <= ?
            ORDER BY inserted_at DESC, id DESC
            LIMIT 1
            """,
            (scan_ts,),
        ).fetchone()
        if row and row[0]:
            logger.info(
                "[MAPPING] latest truck globally at/before %s for QR line %s",
                scan_ts,
                line_id,
            )
            return str(row[0]).strip() or None
    # Clock skew / empty history: fall back to current last_anpr snapshot
    truck = _lookup_last_truck_for_line(line_id)
    if truck:
        return truck
    truck = _lookup_last_truck_for_line(other)
    if truck:
        logger.info(
            "[MAPPING] fallback last_anpr line %s for QR line %s (no ANPR at/before %s)",
            other,
            line_id,
            scan_ts,
        )
        return truck
    with _conn() as c:
        row = c.execute(
            """
            SELECT truck_number FROM anpr_events
            ORDER BY inserted_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    return str(row[0]).strip() if row and row[0] else None


def on_qr_record(record: Dict[str, Any]) -> None:
    """Call when a QR reader sends a line (from qr_tagging queue item)."""
    init_db()
    line = _line_name_to_id(str(record.get("line", "")))
    qr = (record.get("qr") or "").strip()
    if line is None or not qr:
        logger.warning("[MAPPING] Skip QR: bad line or empty qr: %s", record)
        return

    plant = str(record.get("plant_code", _plant_code))
    inserted = _qr_scan_timestamp_iso(record)
    with _lock:
        truck = _resolve_truck_for_qr_at_time(line, inserted)

    with _conn() as c:
        c.execute(
            """
            INSERT INTO qr_vehicle_map
            (line_id, qr_code, truck_number, plant_code, inserted_at, exported_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (line, qr, truck, plant, inserted),
        )

    logger.info(
        "[MAPPING] QR line %s qr=%s truck=%s",
        line,
        qr,
        truck or "(no ANPR yet)",
    )


_FETCH_UNEXPORTED_SQL = """
SELECT
  q.id,
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
WHERE q.exported_at IS NULL
ORDER BY q.inserted_at ASC, q.id ASC
"""


def _fetch_unexported() -> List[sqlite3.Row]:
    with _conn() as c:
        try:
            cur = c.execute(_FETCH_UNEXPORTED_SQL, (_plant_code,))
        except sqlite3.OperationalError:
            cur = c.execute(
                """
                SELECT id, qr_code, truck_number, plant_code, inserted_at
                FROM qr_vehicle_map
                WHERE exported_at IS NULL
                ORDER BY inserted_at ASC, id ASC
                """
            )
        return list(cur.fetchall())


def _mark_exported(ids: List[int]) -> None:
    if not ids:
        return
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    placeholders = ",".join("?" * len(ids))
    with _conn() as c:
        c.execute(
            f"UPDATE qr_vehicle_map SET exported_at = ? WHERE id IN ({placeholders})",
            [now] + ids,
        )


def export_pending_to_csv_and_upload() -> Optional[str]:
    """
    Writes all rows with exported_at IS NULL to a CSV (format per spec), uploads SFTP, marks exported.
    Returns local CSV path if written, else None.
    """
    init_db()
    lock_path = _db_path + ".export.lock"
    lock_f = open(lock_path, "a+")
    try:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
    except OSError:
        lock_f.close()
        return None

    try:
        rows = _fetch_unexported()
        if not rows:
            logger.info("[EXPORT] No pending QR/vehicle rows to export.")
            return None

        os.makedirs(_csv_export_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        seq = _next_export_sequence()
        fname = f"{_csv_file_prefix}_{_plant_code}_{ts}{seq:04d}.csv"
        path = os.path.join(_csv_export_dir, fname)

        serial = 1
        ids: List[int] = []
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                ["S.No.", "QR Code", "TruckNumber", "Plant Code", "Inserted At"]
            )
            for r in rows:
                ids.append(int(r["id"]))
                ins = r["inserted_at"]
                if "T" in ins:
                    ins = ins.replace("T", " ")
                try:
                    tpart = ins.split(" ")[-1]
                    if len(tpart) >= 8:
                        inserted_display = tpart[:8]
                    else:
                        inserted_display = tpart
                except Exception:
                    inserted_display = ins
                w.writerow(
                    [
                        serial,
                        r["qr_code"],
                        r["truck_number"] or "",
                        r["plant_code"],
                        inserted_display,
                    ]
                )
                serial += 1

        try:
            from sftp import upload_qr_mapping_csv

            upload_qr_mapping_csv(path, _sftp_remote_subdir)
        except Exception as e:
            logger.exception("SFTP upload failed: %s", e)
            return None

        _mark_exported(ids)
        logger.info("[EXPORT] Wrote %s, uploaded, marked %s rows exported.", path, len(ids))
        return path
    finally:
        try:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_f.close()


def _hourly_loop(interval_sec: float = 3600.0) -> None:
    while True:
        time.sleep(interval_sec)
        try:
            export_pending_to_csv_and_upload()
        except Exception as e:
            logger.exception("Hourly export error: %s", e)


def start_hourly_export_daemon(interval_sec: float = 3600.0) -> None:
    global _hourly_started
    if _hourly_started:
        return
    init_db()
    _hourly_started = True
    t = threading.Thread(target=_hourly_loop, args=(interval_sec,), daemon=True)
    t.start()
    logger.info("[EXPORT] Hourly CSV export thread started (every %s s).", interval_sec)


def start_qr_consumer(qr_queue, interval_sec: float = 3600.0) -> None:
    """Drain qr_tagging queue and persist mappings in DB (no export scheduler)."""

    def worker() -> None:
        import queue as queue_mod

        while True:
            try:
                item = qr_queue.get(timeout=1.0)
            except queue_mod.Empty:
                continue
            try:
                on_qr_record(item)
            except Exception as e:
                logger.exception("QR consumer error: %s", e)

    init_db()
    tw = threading.Thread(target=worker, daemon=True)
    tw.start()
    logger.info("[MAPPING] QR queue consumer started.")


def get_export_interval_sec(default_sec: float = 3600.0) -> float:
    init_db()
    if _export_interval_sec <= 0:
        return default_sec
    return _export_interval_sec


def should_run_export_immediately() -> bool:
    init_db()
    return _run_immediately_on_start

