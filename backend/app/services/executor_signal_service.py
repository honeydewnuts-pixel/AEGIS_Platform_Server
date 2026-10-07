"""Pending signals for MT5 AEGIS_Executor — idempotent by signal_id.

Once a signal_id is successfully ACK'd (or permanently failed ACK), it is never
re-issued. Duplicate ACKs are accepted (idempotent).
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from app.utils.symbol_normalize import normalize_symbol


class ExecutorSignalService:
    def __init__(self, max_age_sec: float = 300.0, completed_ttl_sec: float = 86400.0) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}  # account|symbol -> payload
        self._completed: dict[str, dict[str, Any]] = {}  # signal_id -> audit
        self._recent: list[dict[str, Any]] = []  # last N execution events for clients
        self._last_poll_ms: dict[str, int] = {}  # account_id -> ms
        self.event_log: Any | None = None  # optional TradeEventLog
        self.max_age_sec = max_age_sec
        self.completed_ttl_sec = completed_ttl_sec

    @staticmethod
    def _key(account_id: str, symbol: str) -> str:
        return f"{account_id.strip()}|{normalize_symbol(symbol)}"

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return normalize_symbol(symbol)

    def _prune_completed(self) -> None:
        now = time.time()
        dead = [
            sid
            for sid, meta in self._completed.items()
            if now - float(meta.get("completed_at", 0)) > self.completed_ttl_sec
        ]
        for sid in dead:
            self._completed.pop(sid, None)

    def publish(
        self,
        *,
        account_id: str,
        symbol: str,
        side: str,
        confidence: float = 0.0,
        rule_name: str = "",
        volume: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        details: str = "",
        atr14: float | None = None,
        initial_stop_atr_mult: float | None = 1.5,
        max_hold_bars: int | None = 72,
        trail_atr_mult: float | None = 0.75,
        methodology: str | None = None,
        risk_usd_at_open: float | None = None,
        production_authorized: bool = False,
        controlled_demo_authorized: bool = False,
    ) -> str | None:
        side_u = (side or "").strip().upper()
        if side_u not in ("BUY", "SELL"):
            return None
        sym = self.normalize_symbol(symbol)
        if not account_id or not sym:
            return None
        signal_id = str(uuid.uuid4())
        payload = {
            "signal_id": signal_id,
            "account_id": account_id,
            "symbol": sym,
            "side": side_u,
            "confidence": float(confidence or 0),
            "rule_name": rule_name or "",
            "volume": volume,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "details": (details or "")[:500],
            "created_at_ms": int(time.time() * 1000),
            "acked": False,
            # Position-manager fields (V31/V53.6 short baseline)
            "atr14": atr14,
            "initial_stop_atr_mult": initial_stop_atr_mult,
            "max_hold_bars": max_hold_bars if max_hold_bars is not None else 72,
            "trail_atr_mult": trail_atr_mult if trail_atr_mult is not None else 0.75,
            "methodology": methodology or "",
            "risk_usd_at_open": float(risk_usd_at_open) if risk_usd_at_open is not None else None,
            "production_authorized": production_authorized is True,
            # Separate from production: one-shot Demo engineering test only
            "controlled_demo_authorized": controlled_demo_authorized is True,
        }
        with self._lock:
            self._pending[self._key(account_id, sym)] = payload
        self._emit(
            stage="queued",
            account_id=account_id,
            status="QUEUED",
            signal_id=signal_id,
            symbol=sym,
            detail=f"{side_u} conf={confidence:.2f} rule={rule_name}",
            extra={"volume": volume, "stop_loss": stop_loss},
        )
        return signal_id

    @staticmethod
    def is_execution_authorized(row: dict[str, Any] | None) -> bool:
        """Defense-in-depth execution gate.

        Allowed only if:
          A) production_authorized is True AND methodology is not research, OR
          B) controlled_demo_authorized is True AND methodology is exactly
             controlled_demo_test (engineering Demo path — never production).

        Never promotes RSI9 / Native / V53.6 / research to executable status.
        """
        if not row or not isinstance(row, dict):
            return False
        meth = str(row.get("methodology") or "").lower()
        rule = str(row.get("rule_name") or "").lower()
        research_tokens = ("rsi9", "native", "stage3b", "research", "transfer", "v53", "v31")
        # Path B: controlled Demo engineering signal only
        if row.get("controlled_demo_authorized") is True:
            if meth != "controlled_demo_test" and "controlled_demo" not in rule:
                return False
            for token in research_tokens:
                if token in meth or token in rule:
                    return False
            return True
        # Path A: production
        if row.get("production_authorized") is not True:
            return False
        for token in research_tokens:
            if token in meth or token in rule:
                return False
        return True

    def get_pending(self, account_id: str, symbol: str) -> dict[str, Any] | None:
        key = self._key(account_id, symbol)
        now = int(time.time() * 1000)
        self.note_poll(account_id)
        with self._lock:
            self._prune_completed()
            row = self._pending.get(key)
            if not row:
                return None
            sid = row.get("signal_id")
            if sid and sid in self._completed:
                self._pending.pop(key, None)
                return None
            age = (now - int(row.get("created_at_ms") or 0)) / 1000.0
            if age > self.max_age_sec:
                self._pending.pop(key, None)
                return None
            if row.get("acked"):
                return None
            if not self.is_execution_authorized(row):
                # Drop unauthorized from queue so it cannot be polled
                self._pending.pop(key, None)
                return None
            return dict(row)

    def get_pending_many(self, account_id: str, symbols: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sym in symbols:
            base = self.normalize_symbol(sym)
            if not base or base in seen:
                continue
            seen.add(base)
            row = self.get_pending(account_id, base)
            if row:
                out.append(row)
        return out

    def ack(
        self,
        account_id: str,
        signal_id: str,
        *,
        ticket: int = 0,
        order_ticket: int = 0,
        deal_ticket: int = 0,
        position_ticket: int = 0,
        retcode: int = 0,
        ok: bool = True,
        message: str = "",
        symbol: str = "",
        side: str = "",
        volume: float = 0.0,
    ) -> dict[str, Any]:
        """Idempotent ACK. Returns status dict."""
        with self._lock:
            self._prune_completed()
            # Already completed → idempotent success
            if signal_id in self._completed:
                prev = self._completed[signal_id]
                return {
                    "acked": True,
                    "idempotent": True,
                    "signal_id": signal_id,
                    **{k: prev.get(k) for k in ("order_ticket", "deal_ticket", "position_ticket", "ok")},
                }

            found_key = None
            row = None
            for key, r in self._pending.items():
                if r.get("account_id") == account_id and r.get("signal_id") == signal_id:
                    found_key = key
                    row = r
                    break

            audit = {
                "signal_id": signal_id,
                "account_id": account_id,
                "order_ticket": order_ticket or ticket,
                "deal_ticket": deal_ticket,
                "position_ticket": position_ticket,
                "retcode": retcode,
                "ok": ok,
                "message": (message or "")[:300],
                "symbol": symbol or (row or {}).get("symbol", ""),
                "side": side or (row or {}).get("side", ""),
                "volume": volume,
                "risk_usd_at_open": (row or {}).get("risk_usd_at_open"),
                "completed_at": time.time(),
                "completed_at_ms": int(time.time() * 1000),
            }
            self._completed[signal_id] = audit
            if found_key:
                self._pending.pop(found_key, None)
            self._recent.insert(0, dict(audit))
            self._recent = self._recent[:100]
        self._emit(
            stage="ack",
            account_id=account_id,
            status="ACK_OK" if ok else "ACK_FAIL",
            signal_id=signal_id,
            symbol=symbol,
            detail=(message or "")[:300],
            extra={
                "ok": ok,
                "retcode": retcode,
                "order_ticket": order_ticket or ticket,
                "position_ticket": position_ticket,
            },
        )
        return {"acked": True, "idempotent": False, "signal_id": signal_id, **audit}

    def recent_executions(self, account_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = [r for r in self._recent if r.get("account_id") == account_id]
            return rows[:limit]

    def note_poll(self, account_id: str) -> None:
        aid = (account_id or "").strip()
        if not aid:
            return
        with self._lock:
            self._last_poll_ms[aid] = int(time.time() * 1000)

    def last_poll_ms(self, account_id: str) -> int | None:
        with self._lock:
            return self._last_poll_ms.get((account_id or "").strip())

    def list_pending_for_account(self, account_id: str) -> list[dict[str, Any]]:
        aid = (account_id or "").strip()
        now = int(time.time() * 1000)
        out: list[dict[str, Any]] = []
        with self._lock:
            self._prune_completed()
            for key, row in list(self._pending.items()):
                if row.get("account_id") != aid:
                    continue
                sid = row.get("signal_id")
                if sid and sid in self._completed:
                    self._pending.pop(key, None)
                    continue
                age = (now - int(row.get("created_at_ms") or 0)) / 1000.0
                if age > self.max_age_sec:
                    self._pending.pop(key, None)
                    continue
                out.append(dict(row))
        return out

    def recent_for_account(self, account_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.recent_executions(account_id, limit=limit)


    def fleet_poll_snapshot(self, silent_after_sec: float = 120.0) -> dict[str, Any]:
        """All accounts that have polled recently + silent ones."""
        now = int(time.time() * 1000)
        with self._lock:
            polls = dict(self._last_poll_ms)
            pending_n = 0
            pending_by_account: dict[str, int] = {}
            for row in self._pending.values():
                aid = str(row.get("account_id") or "")
                if not aid:
                    continue
                pending_n += 1
                pending_by_account[aid] = pending_by_account.get(aid, 0) + 1
            recent = list(self._recent)[:50]
        active = []
        silent = []
        for aid, ms in polls.items():
            age = (now - int(ms)) / 1000.0
            entry = {
                "account_id": aid,
                "last_poll_ms": ms,
                "age_sec": round(age, 1),
                "pending": pending_by_account.get(aid, 0),
            }
            if age <= silent_after_sec:
                active.append(entry)
            else:
                silent.append(entry)
        active.sort(key=lambda x: x["age_sec"])
        silent.sort(key=lambda x: -x["age_sec"])
        return {
            "polling_accounts": active,
            "silent_accounts": silent,
            "pending_total": pending_n,
            "pending_by_account": pending_by_account,
            "recent_acks": recent,
        }

    def list_all_pending(self, limit: int = 100) -> list[dict[str, Any]]:
        now = int(time.time() * 1000)
        out: list[dict[str, Any]] = []
        with self._lock:
            self._prune_completed()
            for key, row in list(self._pending.items()):
                age = (now - int(row.get("created_at_ms") or 0)) / 1000.0
                if age > self.max_age_sec:
                    self._pending.pop(key, None)
                    continue
                item = dict(row)
                item["age_sec"] = round(age, 1)
                out.append(item)
                if len(out) >= limit:
                    break
        return out

    def _emit(self, **kwargs: Any) -> None:
        log = self.event_log
        if log is None:
            return
        try:
            log.record(**kwargs)
        except Exception:
            pass
