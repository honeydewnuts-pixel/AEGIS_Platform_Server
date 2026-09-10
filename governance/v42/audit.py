"""Append-only in-process V42 operational audit primitives."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, json

@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    client_order_id: str
    timestamp: str
    payload: dict
    previous_hash: str
    event_hash: str

class AuditLedger:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def append(self, event_type: str, client_order_id: str, payload: dict) -> AuditEvent:
        previous = self._events[-1].event_hash if self._events else "GENESIS"
        timestamp = datetime.now(timezone.utc).isoformat()
        event_id = hashlib.sha256(f"{timestamp}|{event_type}|{client_order_id}".encode()).hexdigest()[:24]
        body = {"event_id": event_id, "event_type": event_type, "client_order_id": client_order_id,
                "timestamp": timestamp, "payload": payload, "previous_hash": previous}
        event_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        event = AuditEvent(event_id, event_type, client_order_id, timestamp, payload, previous, event_hash)
        self._events.append(event)
        return event

    def verify_chain(self) -> bool:
        previous = "GENESIS"
        for e in self._events:
            body = {"event_id": e.event_id, "event_type": e.event_type, "client_order_id": e.client_order_id,
                    "timestamp": e.timestamp, "payload": e.payload, "previous_hash": previous}
            if e.previous_hash != previous or hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != e.event_hash:
                return False
            previous = e.event_hash
        return True

class IdempotencyGuard:
    def __init__(self) -> None:
        self._seen: set[str] = set()
    def accept(self, client_order_id: str) -> bool:
        if not client_order_id or client_order_id in self._seen:
            return False
        self._seen.add(client_order_id)
        return True
