"""Tamper-evident audit trail for AI-assisted steps.

Each event is a JSON line carrying the hash of the previous line, so any
later edit, deletion or reordering is detected by ``verify_trail``. This
makes the *auditor* auditable (Principle 6): which model saw what, what
it answered, and what EPI-LEAN accepted or rejected.

It is tamper-*evident*, not tamper-proof: someone who can rewrite the
whole file can recompute the chain. Anchor the final hash externally
(CI log, signed commit) when that matters.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _digest(event: dict, previous: str) -> str:
    body = json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((previous + body).encode("utf-8")).hexdigest()


class AuditTrail:
    def __init__(self, path: Path, clock=None):
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        ok, count, error = verify_trail(self.path) if self.path.is_file() else (True, 0, None)
        if not ok:
            raise ValueError(f"existing trail {self.path} is corrupt: {error}")
        self._seq = count
        self._last = GENESIS
        if count:
            self._last = json.loads(self.path.read_text(encoding="utf-8").splitlines()[-1])["hash"]

    @property
    def head(self) -> str:
        return self._last

    def append(self, kind: str, **data) -> dict:
        event = {"seq": self._seq, "ts": self._clock(), "kind": kind, **data}
        event["prev"] = self._last
        event["hash"] = _digest({k: v for k, v in event.items() if k != "hash"}, self._last)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._seq += 1
        self._last = event["hash"]
        return event


def verify_trail(path: Path) -> tuple[bool, int, str | None]:
    """Return ``(ok, event_count, error)`` for a trail file."""
    previous = GENESIS
    count = 0
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return False, count, f"line {number}: invalid JSON"
        if event.get("seq") != count:
            return False, count, f"line {number}: sequence break"
        if event.get("prev") != previous:
            return False, count, f"line {number}: chain broken (prev hash mismatch)"
        body = {k: v for k, v in event.items() if k != "hash"}
        if _digest(body, previous) != event.get("hash"):
            return False, count, f"line {number}: content altered (hash mismatch)"
        previous = event["hash"]
        count += 1
    return True, count, None
