"""Database durability — a finance app must never lose committed money records.

Strategy:
- SQLite `VACUUM INTO` snapshots (consistent, atomic, no lock contention):
  * `backups/latest.db`  — refreshed every 60s AND immediately after money events
    (payment request created, payment captured) → worst-case RPO ~0 for money data.
  * `backups/hourly-<ts>.db` — rotating archive, newest 10 kept.
- On startup: if the main DB is missing or unreadable, auto-restore from latest.db.
- Admin endpoints list/restore backups explicitly.
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("core.backup")


def db_path() -> Path:
    url = get_settings().database_url
    # sqlite+aiosqlite:////abs/path or sqlite+aiosqlite:///./rel.db
    raw = url.split(":///", 1)[-1] if ":///" in url else url
    p = Path(raw if os.path.isabs(raw) else os.path.abspath(raw))
    return p


def backup_dir() -> Path:
    d = db_path().parent / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _vacuum_into(source: Path, dest: Path) -> None:
    tmp = dest.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(source, timeout=10)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM INTO ?", (str(tmp),))
    finally:
        conn.close()
    os.replace(tmp, dest)  # atomic swap — never a half-written backup


def make_backup(hourly: bool = False) -> str | None:
    src = db_path()
    if not src.exists():
        return None
    try:
        dest = backup_dir() / "latest.db"
        _vacuum_into(src, dest)
        tag = "latest"
        if hourly:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            (backup_dir() / f"hourly-{ts}.db").write_bytes(dest.read_bytes())
            tag = f"hourly-{ts}"
            _prune_hourly(keep=10)
        return tag
    except Exception as e:
        log.warning("backup.failed", error=str(e)[:150])
        return None


def _prune_hourly(keep: int) -> None:
    files = sorted(backup_dir().glob("hourly-*.db"))
    for old in files[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


def _table_row_count(db: Path, table: str) -> int:
    conn = sqlite3.connect(db, timeout=10)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return -1  # table missing / db unreadable
    finally:
        conn.close()


def restore_if_needed() -> str | None:
    """Startup guard: main DB missing or unreadable → recover from the newest backup."""
    src = db_path()
    latest = backup_dir() / "latest.db"
    if src.exists():
        # quick health probe: can we read a core table?
        conn = None
        try:
            conn = sqlite3.connect(src, timeout=5)
            conn.execute("SELECT 1 FROM invoices LIMIT 1").fetchone()
            return None  # healthy
        except sqlite3.Error:
            log.warning("backup.main_db_unreadable", path=str(src))
        finally:
            if conn:
                conn.close()
    if not latest.exists():
        return None
    try:
        corrupt = src.with_suffix(".corrupt")
        if src.exists():
            os.replace(src, corrupt)
        conn = sqlite3.connect(latest, timeout=10)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        import shutil

        shutil.copyfile(latest, src)
        n = _table_row_count(src, "invoices")
        log.info("backup.restored", from_file=str(latest), invoices=n)
        return str(latest)
    except Exception as e:
        log.error("backup.restore_failed", error=str(e)[:150])
        return None


def list_backups() -> list[dict]:
    out = []
    for f in sorted(backup_dir().glob("*.db"), reverse=True):
        out.append({
            "tag": f.stem,
            "size_bytes": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            "invoices": _table_row_count(f, "invoices"),
            "customers": _table_row_count(f, "customers"),
        })
    return out


def restore_tag(tag: str) -> dict:
    safe = backup_dir() / f"{tag}.db"
    if tag not in ("latest",) and not tag.startswith("hourly-"):
        return {"ok": False, "message": "Unknown backup tag"}
    if not safe.exists():
        return {"ok": False, "message": "Backup not found"}
    src = db_path()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if src.exists():
        os.replace(src, src.with_name(f"pre-restore-{ts}.db"))
    import shutil

    shutil.copyfile(safe, src)
    return {"ok": True, "restored": tag, "invoices": _table_row_count(src, "invoices")}


def start_backup_loop(interval_s: int = 60):
    import asyncio

    async def _loop():
        last_hourly = 0.0
        while True:
            await asyncio.sleep(interval_s)
            now = time.time()
            make_backup(hourly=(now - last_hourly) > 3600)
            if now - last_hourly > 3600:
                last_hourly = now

    return asyncio.create_task(_loop())
