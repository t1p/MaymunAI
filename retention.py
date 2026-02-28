import os
import time
from pathlib import Path
from typing import Dict


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def prune_files_older_than(directory: Path, retention_days: int) -> int:
    """Удаляет файлы в директории старше retention_days (по mtime)."""
    if not directory.exists() or retention_days <= 0:
        return 0

    threshold = time.time() - (retention_days * 24 * 60 * 60)
    removed = 0

    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        try:
            if entry.stat().st_mtime < threshold:
                entry.unlink(missing_ok=True)
                removed += 1
        except FileNotFoundError:
            continue

    return removed


def rotate_audit_if_needed(audit_file: Path, max_bytes: int, backups: int = 5) -> bool:
    """Ротирует audit.jsonl при превышении max_bytes."""
    if max_bytes <= 0 or not audit_file.exists():
        return False
    if audit_file.stat().st_size <= max_bytes:
        return False

    backups = max(1, backups)
    oldest = audit_file.with_name(f"{audit_file.name}.{backups}")
    if oldest.exists():
        oldest.unlink(missing_ok=True)

    for idx in range(backups - 1, 0, -1):
        src = audit_file.with_name(f"{audit_file.name}.{idx}")
        dst = audit_file.with_name(f"{audit_file.name}.{idx + 1}")
        if src.exists():
            src.replace(dst)

    audit_file.replace(audit_file.with_name(f"{audit_file.name}.1"))
    audit_file.touch(exist_ok=True)
    return True


def run_housekeeping() -> Dict[str, int]:
    """Однократная безопасная очистка runtime артефактов по retention/TTL."""
    log_dir = Path(os.getenv('MAYMUNAI_LOG_DIR', './runtime/logs'))
    audit_dir = Path(os.getenv('MAYMUNAI_AUDIT_DIR', './runtime/audit'))

    log_retention_days = _get_env_int('MAYMUNAI_LOG_RETENTION_DAYS', 14)
    audit_retention_days = _get_env_int('MAYMUNAI_AUDIT_RETENTION_DAYS', log_retention_days)
    audit_max_bytes = _get_env_int('MAYMUNAI_AUDIT_MAX_BYTES', 5 * 1024 * 1024)
    audit_backups = _get_env_int('MAYMUNAI_AUDIT_BACKUPS', 5)

    log_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    removed_logs = prune_files_older_than(log_dir, log_retention_days)
    removed_audit = prune_files_older_than(audit_dir, audit_retention_days)

    audit_file = audit_dir / 'audit.jsonl'
    rotated_audit = 1 if rotate_audit_if_needed(audit_file, audit_max_bytes, backups=audit_backups) else 0

    return {
        'removed_logs': removed_logs,
        'removed_audit': removed_audit,
        'rotated_audit': rotated_audit,
    }

