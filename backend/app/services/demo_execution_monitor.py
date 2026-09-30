"""AEGIS Demo Execution Monitor — stage status for one account.

Aggregates existing OHLC stream + ExecutorSignalService + trade event log.
Does not force trades. Distinguishes:
  NO_SIGNAL | SIGNAL_PENDING | ORDER_REJECTED | TRADE_FILLED | STALE_DATA | EXECUTOR_SILENT
"""
from __future__ import annotations

import time
from typing import Any


# OHLC older than this is STALE for M5
OHLC_STALE_SEC = 600
EXECUTOR_SILENT_SEC = 120


class DemoExecutionMonitor:
    def __init__(self, trade_log: Any | None = None) -> None:
        self.trade_log = trade_log

    def build(
        self,
        *,
        account_id: str,
        ohlc_stream: Any | None,
        executor_signals: Any | None,
        worker_pool: Any | None = None,
    ) -> dict[str, Any]:
        aid = (account_id or "").strip()
        now_ms = int(time.time() * 1000)
        stages: list[dict[str, Any]] = []

        # --- 1. MT5 / OHLC connection ---
        ohlc_rows: list[dict[str, Any]] = []
        freshest_age = None
        if ohlc_stream is not None:
            try:
                st = ohlc_stream.status(aid)
                ohlc_rows = st.get("streams") or st.get("items") or []
                if not ohlc_rows and isinstance(st, dict):
                    # some implementations return list directly under streams
                    if isinstance(st.get("streams"), list):
                        ohlc_rows = st["streams"]
            except Exception as e:  # noqa: BLE001
                ohlc_rows = []
                stages.append(self._stage("mt5_connection", "ERROR", f"ohlc status error: {e}"))

        if ohlc_rows:
            ages = []
            for r in ohlc_rows:
                age = r.get("age_sec")
                if age is None and r.get("updated_at_ms"):
                    age = max(0, (now_ms - int(r["updated_at_ms"])) / 1000.0)
                if age is not None:
                    ages.append(float(age))
            freshest_age = min(ages) if ages else None
            if freshest_age is not None and freshest_age <= OHLC_STALE_SEC:
                stages.append(
                    self._stage(
                        "mt5_connection",
                        "CONNECTED",
                        f"{len(ohlc_rows)} stream(s); freshest age {freshest_age:.0f}s",
                        {"streams": len(ohlc_rows), "freshest_age_sec": freshest_age},
                    )
                )
            else:
                stages.append(
                    self._stage(
                        "mt5_connection",
                        "STALE",
                        f"OHLC age {freshest_age}s exceeds {OHLC_STALE_SEC}s" if freshest_age is not None else "no age",
                        {"streams": len(ohlc_rows), "freshest_age_sec": freshest_age},
                    )
                )
        else:
            stages.append(
                self._stage(
                    "mt5_connection",
                    "DISCONNECTED",
                    "No OHLC streams for this account — attach AEGIS_OHLC_Feed on MT5",
                )
            )

        # --- 2. OHLC feed detail ---
        if ohlc_rows:
            sample = ohlc_rows[0]
            stages.append(
                self._stage(
                    "ohlc_feed",
                    "OK" if (freshest_age is not None and freshest_age <= OHLC_STALE_SEC) else "STALE",
                    f"symbol={sample.get('symbol')} tf={sample.get('timeframe')} bars={sample.get('bar_count', sample.get('bars'))}",
                    {"streams": ohlc_rows[:12]},
                )
            )
        else:
            stages.append(self._stage("ohlc_feed", "MISSING", "No CLOSED/CURRENT bars received"))

        # --- 3–5. Signals / queue ---
        pending: list[dict[str, Any]] = []
        recent: list[dict[str, Any]] = []
        last_poll_ms = None
        if executor_signals is not None:
            try:
                if hasattr(executor_signals, "list_pending_for_account"):
                    pending = executor_signals.list_pending_for_account(aid) or []
                elif hasattr(executor_signals, "pending_for_account"):
                    pending = executor_signals.pending_for_account(aid) or []
                if hasattr(executor_signals, "recent_for_account"):
                    recent = executor_signals.recent_for_account(aid, limit=20) or []
                if hasattr(executor_signals, "last_poll_ms"):
                    last_poll_ms = executor_signals.last_poll_ms(aid)
            except Exception as e:  # noqa: BLE001
                stages.append(self._stage("signal_queue", "ERROR", str(e)))

        if pending:
            stages.append(
                self._stage(
                    "signal_generation",
                    "SIGNAL_PENDING",
                    f"{len(pending)} pending signal(s) awaiting Executor",
                    {"pending": pending[:10]},
                )
            )
            stages.append(
                self._stage(
                    "signal_queue",
                    "QUEUED",
                    "Executor has not yet ACKed these signal_ids",
                    {"count": len(pending)},
                )
            )
        else:
            stages.append(
                self._stage(
                    "signal_generation",
                    "NO_SIGNAL",
                    "No pending BUY/SELL — HOLD or conditions not met (not a transport failure)",
                )
            )
            stages.append(self._stage("signal_queue", "EMPTY", "No queued signals"))

        # --- 6. Executor poll ---
        if last_poll_ms:
            age = (now_ms - int(last_poll_ms)) / 1000.0
            if age <= EXECUTOR_SILENT_SEC:
                stages.append(
                    self._stage(
                        "executor",
                        "POLLING",
                        f"Last poll {age:.0f}s ago",
                        {"last_poll_ms": last_poll_ms, "age_sec": age},
                    )
                )
            else:
                stages.append(
                    self._stage(
                        "executor",
                        "SILENT",
                        f"Last poll {age:.0f}s ago — check EA is attached and WebRequest allowed",
                        {"last_poll_ms": last_poll_ms, "age_sec": age},
                    )
                )
        else:
            stages.append(
                self._stage(
                    "executor",
                    "NO_POLL_YET",
                    "No pending-batch poll recorded for this account",
                )
            )

        # --- 7–9. Recent fills / rejects / ACKs ---
        last_fill = next((r for r in recent if r.get("ok") is True), None)
        last_reject = next((r for r in recent if r.get("ok") is False), None)
        if last_fill:
            stages.append(
                self._stage(
                    "order_submission",
                    "TRADE_FILLED",
                    f"{last_fill.get('side')} {last_fill.get('symbol')} ticket={last_fill.get('ticket') or last_fill.get('position_ticket')}",
                    last_fill,
                )
            )
            stages.append(self._stage("acknowledgement", "ACKED", "Server recorded Executor ACK", last_fill))
        elif last_reject:
            stages.append(
                self._stage(
                    "order_submission",
                    "ORDER_REJECTED",
                    last_reject.get("message") or last_reject.get("detail") or "retcode failed",
                    last_reject,
                )
            )
            stages.append(self._stage("acknowledgement", "ACKED_FAILURE", "Failure ACK recorded", last_reject))
        else:
            stages.append(
                self._stage(
                    "order_submission",
                    "NO_RECENT_ORDER",
                    "No recent fill or reject ACK in memory",
                )
            )
            stages.append(self._stage("acknowledgement", "IDLE", "No recent ACK"))

        # --- 10. Notifications (best-effort flag) ---
        stages.append(
            self._stage(
                "notifications",
                "SEE_INBOX",
                "Use GET /api/notifications for delivery status",
            )
        )

        # Overall diagnosis
        overall = self._overall(stages)

        events = []
        if self.trade_log is not None:
            try:
                events = self.trade_log.for_account(aid, limit=50)
            except Exception:  # noqa: BLE001
                events = []

        return {
            "account_id": aid,
            "ts_ms": now_ms,
            "overall": overall,
            "stages": stages,
            "pending_signals": pending[:20],
            "recent_executions": recent[:20],
            "ohlc_streams": ohlc_rows[:20],
            "recent_events": events,
            "legend": {
                "NO_SIGNAL": "Strategy did not emit BUY/SELL — normal when conditions unmet",
                "SIGNAL_PENDING": "Signal queued; waiting for Executor poll",
                "ORDER_REJECTED": "MT5/broker rejected order — see retcode/message",
                "TRADE_FILLED": "Broker accepted order and server has ACK",
                "STALE": "OHLC older than freshness threshold",
                "SILENT": "Executor has not polled recently",
            },
        }

    @staticmethod
    def _stage(name: str, status: str, detail: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "stage": name,
            "status": status,
            "detail": detail,
            "data": data or {},
            "ts_ms": int(time.time() * 1000),
        }

    @staticmethod
    def _overall(stages: list[dict[str, Any]]) -> dict[str, Any]:
        statuses = {s["stage"]: s["status"] for s in stages}
        if statuses.get("mt5_connection") in ("DISCONNECTED", "ERROR"):
            code = "MT5_DISCONNECTED"
            msg = "OHLC Feed not streaming — no autonomous signals possible"
        elif statuses.get("mt5_connection") == "STALE" or statuses.get("ohlc_feed") == "STALE":
            code = "OHLC_STALE"
            msg = "Market data is stale — check VPS/MT5 Feed timer"
        elif statuses.get("signal_queue") == "QUEUED" and statuses.get("executor") in (
            "SILENT",
            "NO_POLL_YET",
        ):
            code = "EXECUTOR_NOT_POLLING"
            msg = "Signal queued but Executor is not polling pending-batch"
        elif statuses.get("signal_queue") == "QUEUED":
            code = "SIGNAL_AWAITING_EXECUTION"
            msg = "Signal pending — Executor should pick it up on next poll"
        elif statuses.get("order_submission") == "ORDER_REJECTED":
            code = "ORDER_REJECTED"
            msg = "Last order was rejected by broker/EA"
        elif statuses.get("order_submission") == "TRADE_FILLED":
            code = "TRADE_FILLED"
            msg = "Recent trade filled and acknowledged"
        elif statuses.get("signal_generation") == "NO_SIGNAL":
            code = "NO_SIGNAL"
            msg = "Pipeline healthy enough to analyze; no entry signal right now"
        else:
            code = "UNKNOWN"
            msg = "See stage details"
        return {"code": code, "message": msg}
