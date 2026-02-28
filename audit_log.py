import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


_AUDIT_LOCK = Lock()


def get_audit_file_path() -> Path:
    audit_dir = Path(os.getenv('MAYMUNAI_AUDIT_DIR', './runtime/audit'))
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir / 'audit.jsonl'


def log_audit_event(
    event_type: str,
    actor: str = 'system',
    pack_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    audit_file_path: Optional[Path] = None,
) -> Dict[str, Any]:
    event = {
        'ts_utc': datetime.now(timezone.utc).isoformat(),
        'event_type': event_type,
        'actor': actor or 'system',
        'pack_id': pack_id,
        'details': details or {},
    }

    target = audit_file_path or get_audit_file_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    with _AUDIT_LOCK:
        with target.open('a', encoding='utf-8') as file:
            file.write(json.dumps(event, ensure_ascii=False) + '\n')

    return event


def tail_audit_events(n: int = 50, audit_file_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target = audit_file_path or get_audit_file_path()
    if n <= 0 or not target.exists():
        return []

    last_lines = deque(maxlen=n)
    with target.open('r', encoding='utf-8') as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                last_lines.append(stripped)

    events: List[Dict[str, Any]] = []
    for line in last_lines:
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                events.append(payload)
        except json.JSONDecodeError:
            continue

    return events
