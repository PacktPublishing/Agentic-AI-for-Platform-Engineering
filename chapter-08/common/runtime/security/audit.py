"""A local hash chain, serialized across workers. Not an immutable external sink."""
import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class Audit:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('AUDIT_LOG', '/state/audit/security.jsonl'))

    def record(self, **fields):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a+', encoding='utf-8') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            lines = f.read().splitlines()
            prev = json.loads(lines[-1])['hash'] if lines else '0' * 64
            record = {'ts': datetime.now(timezone.utc).isoformat(), **fields, 'prev_hash': prev}
            body = json.dumps(record, sort_keys=True, separators=(',', ':'))
            record['hash'] = hashlib.sha256(body.encode()).hexdigest()
            f.write(json.dumps(record, sort_keys=True) + '\n')
            f.flush()
            os.fsync(f.fileno())
            return record['hash']
