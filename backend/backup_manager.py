"""
Backup and Recovery Manager for PES Bank Management System (Issue #24).
Provides atomic online backups, SHA-256 integrity verification,
pre-restore safety snapshots, disaster recovery restoration, and CLI utilities.
Complies with SEC-07 and SEC-10.
"""

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_BACKUP_DIR_NAME = "backups"
MANIFEST_FILENAME = "backups_manifest.json"


def get_backup_dir(custom_dir: Optional[str] = None) -> str:
    """Return the absolute path to the backup storage directory, ensuring it exists."""
    if custom_dir:
        b_dir = os.path.abspath(custom_dir)
    else:
        b_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULT_BACKUP_DIR_NAME)
    os.makedirs(b_dir, exist_ok=True)
    return b_dir


def compute_sha256(filepath: str) -> str:
    """Calculate the SHA-256 checksum of a file in streaming chunks."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def verify_sqlite_integrity(filepath: str) -> Tuple[bool, str]:
    """Execute SQLite PRAGMA integrity_check on the specified database file."""
    if not os.path.isfile(filepath):
        return False, f"File does not exist: {filepath}"
    try:
        conn = sqlite3.connect(f"file:{filepath}?mode=ro", uri=True, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        rows = cursor.fetchall()
        conn.close()
        if rows and rows[0][0] == "ok":
            return True, "ok"
        messages = "; ".join(r[0] for r in rows)
        return False, messages
    except Exception as e:
        return False, str(e)


def get_tables_summary(filepath: str) -> Dict[str, int]:
    """Retrieve record counts for key banking tables from a database file."""
    summary = {}
    tables = [
        "users",
        "accounts",
        "transactions",
        "transfers",
        "loans",
        "beneficiaries",
        "audit_logs",
        "notifications",
    ]
    try:
        conn = sqlite3.connect(f"file:{filepath}?mode=ro", uri=True, timeout=5.0)
        cursor = conn.cursor()
        for t in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {t};")
                summary[t] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                summary[t] = 0
        conn.close()
    except Exception:
        pass
    return summary


def _load_manifest(backup_dir: str) -> Dict[str, Any]:
    """Load the file-based backups manifest."""
    manifest_path = os.path.join(backup_dir, MANIFEST_FILENAME)
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"backups": []}
    return {"backups": []}


def _save_manifest(backup_dir: str, data: Dict[str, Any]) -> None:
    """Save the file-based backups manifest atomically."""
    manifest_path = os.path.join(backup_dir, MANIFEST_FILENAME)
    temp_path = manifest_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    if os.path.isfile(manifest_path):
        os.remove(manifest_path)
    os.rename(temp_path, manifest_path)


def create_backup(
    db_path: str,
    backup_dir: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    trigger_type: str = "manual",
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Perform an online, non-blocking SQLite backup using the official SQLite backup API.
    Calculates SHA-256 checksum, runs integrity checks, updates manifest and database catalog.
    """
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Source database not found at {db_path}")

    b_dir = get_backup_dir(backup_dir)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_tag = uuid.uuid4().hex[:6]
    prefix = "safety_snapshot" if trigger_type == "pre_restore_safety" else "backup"
    filename = f"pesbank_{prefix}_{timestamp_str}_{rand_tag}.db"
    target_filepath = os.path.join(b_dir, filename)

    # Perform online SQLite atomic backup
    src_conn = sqlite3.connect(db_path, timeout=15.0)
    dst_conn = sqlite3.connect(target_filepath)
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    # Calculate checksum and file size
    file_size = os.path.getsize(target_filepath)
    sha256_hash = compute_sha256(target_filepath)

    # Verify backup integrity immediately
    is_valid, integrity_msg = verify_sqlite_integrity(target_filepath)
    if not is_valid:
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
        raise RuntimeError(f"Backup failed SQLite integrity check: {integrity_msg}")

    tables_summary = get_tables_summary(target_filepath)
    summary_json = json.dumps(tables_summary)

    backup_record = {
        "filename": filename,
        "filepath": target_filepath,
        "file_size_bytes": file_size,
        "sha256_checksum": sha256_hash,
        "trigger_type": trigger_type,
        "status": "valid",
        "tables_summary": tables_summary,
        "created_by": created_by_user_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
    }

    # Record in database if backups table exists
    try:
        db_conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = db_conn.cursor()
        cursor.execute(
            """
            INSERT INTO backups (filename, filepath, file_size_bytes, sha256_checksum, trigger_type, status, tables_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, target_filepath, file_size, sha256_hash, trigger_type, "valid", summary_json, created_by_user_id),
        )
        backup_record["id"] = cursor.lastrowid

        # Also write audit log entry if audit_logs table exists
        try:
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, action, details)
                VALUES (?, ?, ?)
                """,
                (
                    created_by_user_id,
                    "DATABASE_BACKUP_CREATED",
                    f"Created backup {filename} ({file_size} bytes, SHA-256: {sha256_hash[:16]}...)",
                ),
            )
        except sqlite3.OperationalError:
            pass

        db_conn.commit()
        db_conn.close()
    except Exception:
        # Fallback to file-based manifest if DB is locked/in-memory
        pass

    # Save to file-based manifest
    manifest = _load_manifest(b_dir)
    manifest["backups"].insert(0, backup_record)
    _save_manifest(b_dir, manifest)

    return backup_record


def verify_backup(
    backup_identifier: Any,
    db_path: Optional[str] = None,
    backup_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verify the integrity of a backup file against its recorded SHA-256 checksum
    and SQLite PRAGMA integrity check.
    """
    b_dir = get_backup_dir(backup_dir)
    target_path = None
    recorded_checksum = None

    # Check by filename directly
    if isinstance(backup_identifier, str):
        candidate = os.path.join(b_dir, os.path.basename(backup_identifier))
        if os.path.isfile(candidate):
            target_path = candidate
        elif os.path.isfile(backup_identifier):
            target_path = backup_identifier

    # If identifier is ID or we need recorded checksum from DB/manifest
    if db_path and os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            cursor = conn.cursor()
            if isinstance(backup_identifier, int) or (isinstance(backup_identifier, str) and backup_identifier.isdigit()):
                cursor.execute(
                    "SELECT id, filename, filepath, sha256_checksum FROM backups WHERE id = ?",
                    (int(backup_identifier),),
                )
            else:
                cursor.execute(
                    "SELECT id, filename, filepath, sha256_checksum FROM backups WHERE filename = ?",
                    (os.path.basename(str(backup_identifier)),),
                )
            row = cursor.fetchone()
            conn.close()
            if row:
                if not target_path:
                    target_path = row[2] if os.path.isfile(row[2]) else os.path.join(b_dir, row[1])
                recorded_checksum = row[3]
        except Exception:
            pass

    # Fall back to manifest if recorded_checksum not found
    if not recorded_checksum:
        manifest = _load_manifest(b_dir)
        for b in manifest.get("backups", []):
            if str(b.get("id")) == str(backup_identifier) or b.get("filename") == os.path.basename(str(backup_identifier)):
                if not target_path:
                    target_path = b.get("filepath")
                recorded_checksum = b.get("sha256_checksum")
                break

    if not target_path or not os.path.isfile(target_path):
        return {
            "valid": False,
            "error": f"Backup file not found for identifier: {backup_identifier}",
            "filename": os.path.basename(str(backup_identifier)),
        }

    current_checksum = compute_sha256(target_path)
    checksum_matches = (recorded_checksum is None) or (current_checksum.lower() == recorded_checksum.lower())
    is_valid_sqlite, integrity_msg = verify_sqlite_integrity(target_path)

    overall_valid = checksum_matches and is_valid_sqlite

    return {
        "valid": overall_valid,
        "filename": os.path.basename(target_path),
        "filepath": target_path,
        "file_size_bytes": os.path.getsize(target_path),
        "current_sha256": current_checksum,
        "recorded_sha256": recorded_checksum,
        "checksum_verified": checksum_matches,
        "integrity_check": integrity_msg,
        "tables_summary": get_tables_summary(target_path),
    }


def restore_backup(
    backup_identifier: Any,
    db_path: str,
    backup_dir: Optional[str] = None,
    restored_by_user_id: Optional[int] = None,
    live_conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """
    Restore the database from a verified backup file.
    Takes an automatic pre-restore safety snapshot first.
    Rejects corrupted or non-matching backups.
    """
    b_dir = get_backup_dir(backup_dir)

    # 1. Verification phase: ensure backup exists and passes SHA-256 + SQLite integrity checks
    verification = verify_backup(backup_identifier, db_path=db_path, backup_dir=b_dir)
    if not verification["valid"]:
        error_detail = verification.get("error") or f"Integrity check failed: {verification.get('integrity_check')}, checksum match: {verification.get('checksum_verified')}"
        raise ValueError(f"Cannot restore: backup verification failed ({error_detail})")

    target_backup_file = verification["filepath"]

    # 2. Safety phase: generate pre-restore safety snapshot of the live database
    safety_snapshot = None
    if os.path.isfile(db_path):
        safety_snapshot = create_backup(
            db_path=db_path,
            backup_dir=b_dir,
            created_by_user_id=restored_by_user_id,
            trigger_type="pre_restore_safety",
            note=f"Automatic safety snapshot prior to restoring {verification['filename']}",
        )

    # 3. Execution phase: restore backup into live database using SQLite backup API
    backup_src_conn = sqlite3.connect(f"file:{target_backup_file}?mode=ro", uri=True, timeout=10.0)

    # Target live connection
    if live_conn is not None:
        with live_conn:
            backup_src_conn.backup(live_conn)
    else:
        live_target_conn = sqlite3.connect(db_path, timeout=15.0)
        with live_target_conn:
            backup_src_conn.backup(live_target_conn)
        live_target_conn.close()

    backup_src_conn.close()

    # 4. Post-restore integrity verification
    post_valid, post_msg = verify_sqlite_integrity(db_path)
    if not post_valid:
        raise RuntimeError(f"Post-restore live database failed integrity check: {post_msg}")

    # 5. Audit log and manifest update
    restored_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        audit_conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = audit_conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (user_id, action, details)
            VALUES (?, ?, ?)
            """,
            (
                restored_by_user_id,
                "DATABASE_RESTORED",
                f"Restored system from backup {verification['filename']}. Safety snapshot: {safety_snapshot['filename'] if safety_snapshot else 'none'}",
            ),
        )
        try:
            cursor.execute(
                """
                UPDATE backups SET status = 'restored', restored_at = ?
                WHERE filename = ?
                """,
                (restored_timestamp, verification["filename"]),
            )
        except sqlite3.OperationalError:
            pass
        audit_conn.commit()
        audit_conn.close()
    except Exception:
        pass

    # Update manifest
    manifest = _load_manifest(b_dir)
    for b in manifest.get("backups", []):
        if b.get("filename") == verification["filename"]:
            b["status"] = "restored"
            b["restored_at"] = restored_timestamp
    _save_manifest(b_dir, manifest)

    return {
        "success": True,
        "restored_filename": verification["filename"],
        "safety_snapshot": safety_snapshot["filename"] if safety_snapshot else None,
        "restored_at": restored_timestamp,
        "tables_summary": get_tables_summary(db_path),
    }


def list_backups(
    db_path: Optional[str] = None,
    backup_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all available database backups, combining database catalog and filesystem manifest."""
    b_dir = get_backup_dir(backup_dir)
    backups_dict = {}

    # Read from filesystem manifest
    manifest = _load_manifest(b_dir)
    for b in manifest.get("backups", []):
        backups_dict[b["filename"]] = b

    # Read from database table if available
    if db_path and os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backups ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()
            for r in rows:
                fn = r["filename"]
                entry = {
                    "id": r["id"],
                    "filename": fn,
                    "filepath": r["filepath"],
                    "file_size_bytes": r["file_size_bytes"],
                    "sha256_checksum": r["sha256_checksum"],
                    "trigger_type": r["trigger_type"],
                    "status": r["status"],
                    "tables_summary": json.loads(r["tables_summary"]) if r["tables_summary"] else {},
                    "created_by": r["created_by"],
                    "created_at": str(r["created_at"]),
                    "restored_at": str(r["restored_at"]) if r["restored_at"] else None,
                }
                backups_dict[fn] = entry
        except Exception:
            pass

    # Scan backup_dir for any unindexed .db files
    for entry in os.listdir(b_dir):
        if entry.endswith(".db") and entry not in backups_dict:
            full_p = os.path.join(b_dir, entry)
            backups_dict[entry] = {
                "filename": entry,
                "filepath": full_p,
                "file_size_bytes": os.path.getsize(full_p),
                "sha256_checksum": compute_sha256(full_p),
                "trigger_type": "manual",
                "status": "valid",
                "tables_summary": get_tables_summary(full_p),
                "created_at": datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M:%S"),
            }

    # Sort newest first
    result = list(backups_dict.values())
    result.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return result


def main():
    """CLI utility for backup and recovery management."""
    default_db = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "bank.db"))

    if len(sys.argv) < 2:
        print("Usage: python backup_manager.py [backup|list|verify <filename>|restore <filename>|test-recovery]")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "backup":
        print(f"Creating online SQLite backup of {default_db}...")
        res = create_backup(default_db)
        print(f"[OK] Backup created: {res['filename']} ({res['file_size_bytes']} bytes)")
        print(f"     SHA-256: {res['sha256_checksum']}")
        print(f"     Tables: {res['tables_summary']}")

    elif cmd == "list":
        backups = list_backups(default_db)
        print(f"\n{'ID':<5} | {'Filename':<42} | {'Size':<10} | {'Status':<8} | {'Created At'}")
        print("-" * 90)
        for b in backups:
            bid = b.get("id", "-")
            size_kb = f"{b['file_size_bytes'] / 1024:.1f} KB"
            print(f"{str(bid):<5} | {b['filename']:<42} | {size_kb:<10} | {b['status']:<8} | {b.get('created_at')}")

    elif cmd == "verify":
        if len(sys.argv) < 3:
            print("Usage: python backup_manager.py verify <filename_or_id>")
            sys.exit(1)
        res = verify_backup(sys.argv[2], db_path=default_db)
        print(f"Verification result: {'PASS' if res['valid'] else 'FAIL'}")
        print(json.dumps(res, indent=2))

    elif cmd == "restore":
        if len(sys.argv) < 3:
            print("Usage: python backup_manager.py restore <filename_or_id>")
            sys.exit(1)
        print(f"Restoring {default_db} from backup {sys.argv[2]}...")
        res = restore_backup(sys.argv[2], db_path=default_db)
        print(f"[OK] Restoration successful!")
        print(f"     Safety snapshot created: {res['safety_snapshot']}")
        print(f"     Tables restored: {res['tables_summary']}")

    elif cmd == "test-recovery":
        print("Running end-to-end Backup & Recovery Self-Test (SEC-10)...")
        b = create_backup(default_db, trigger_type="manual", note="Self-test backup")
        print(f"1. Backup created: {b['filename']}")
        v = verify_backup(b["filename"], db_path=default_db)
        assert v["valid"], f"Verification failed: {v}"
        print("2. Backup verification: PASSED")
        r = restore_backup(b["filename"], db_path=default_db)
        assert r["success"], f"Restoration failed: {r}"
        print(f"3. Recovery restoration: PASSED (Safety snapshot: {r['safety_snapshot']})")
        print("All recovery tests PASSED successfully.")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
