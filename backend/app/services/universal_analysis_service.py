"""
V47 — Universal Analysis Runtime (research path).

Screenshot analysis is routed through the V40 Universal Router first.
Eligible instruments use a price/OHLC-oriented research result that does
NOT require V3 visible on-chart indicators.

V3 BrainCV remains available as an explicit legacy engine only.
"""

from __future__ import annotations

from typing import Any

from app.universal_router import UniversalRouter, RouteState


class UniversalAnalysisService:
    """Select analysis path from V40 registry + optional OHLC snapshot."""

    def __init__(self) -> None:
        self._router = UniversalRouter()

    def route(self, instrument: str, timeframe: str = "M5") -> dict[str, Any]:
        inst = (instrument or "").strip().upper() or "UNKNOWN"
        tf = (timeframe or "M5").strip().upper() or "M5"
        decision = self._router.resolve(inst, tf, production_requested=False)
        return decision.to_dict()

    def analyze(
        self,
        *,
        instrument: str,
        timeframe: str = "M5",
        market_snapshot: dict[str, Any] | None = None,
        frame_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Primary analysis for mobile screenshot uploads.

        Returns a unified result dict compatible with /aegis/analyze clients.
        Never requires V3 visible indicators for V40-eligible instruments.
        """
        inst = (instrument or "").strip().upper()
        tf = (timeframe or "M5").strip().upper() or "M5"

        if not inst:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": "instrument_unspecified",
                "details": (
                    "Upload accepted. No instrument/symbol provided — V40 router "
                    "cannot select a rulebook. Set MT5 symbol in the app for "
                    "pair-specific research routing. Plain charts do not use the "
                    "legacy V3 indicator pack."
                ),
                "analysis_path": "v40_router",
                "router_state": "UNKNOWN_INSTRUMENT",
                "rulebook_ids": [],
                "production_authorized": False,
                "pair": None,
                "instrument": None,
                "timeframe": tf,
            }

        decision = self._router.resolve(inst, tf, production_requested=False)
        base = {
            "analysis_path": "v40_router",
            "router_state": decision.state.value,
            "router": decision.to_dict(),
            "rulebook_ids": list(decision.rulebook_ids),
            "production_authorized": False,  # research path never authorizes live
            "pair": inst,
            "instrument": inst,
            "timeframe": tf,
            "registry_status": decision.registry_status,
        }

        # Fail-closed for non-routable instruments
        if decision.state in (
            RouteState.TRADING_DISABLED,
            RouteState.NO_QUALIFIED_RULEBOOK,
            RouteState.UNKNOWN_INSTRUMENT,
            RouteState.UNKNOWN_TIMEFRAME,
            RouteState.INSUFFICIENT_SPREAD_DATA,
            RouteState.RULEBOOK_INTEGRITY_FAILURE,
            RouteState.MODEL_LINEAGE_FAILURE,
        ):
            return {
                **base,
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": decision.state.value.lower(),
                "details": (
                    f"V40 fail-closed: {decision.reason or decision.state.value}. "
                    "No legacy V3 indicator analysis applied."
                ),
            }

        if decision.state == RouteState.PRODUCTION_AUTHORIZATION_REQUIRED:
            # Should not appear with production_requested=False, but keep safe
            return {
                **base,
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": "production_authorization_required",
                "details": decision.reason or "Production authorization required.",
            }

        # ROUTABLE_RESEARCH — eligible for research evaluation
        if decision.state == RouteState.ROUTABLE_RESEARCH:
            ohlc_result = self._evaluate_research_ohlc(inst, tf, decision.rulebook_ids, market_snapshot)
            if ohlc_result is not None:
                return {**base, **ohlc_result, "analysis_path": "v40_research_ohlc"}

            # Plain chart / no worker OHLC: accept upload, do not demand indicators
            return {
                **base,
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": "v40_research_awaiting_ohlc",
                "details": (
                    f"V40 eligible ({', '.join(decision.rulebook_ids) or 'qualified'}). "
                    "Plain MT5 price chart accepted — no indicator pack required. "
                    "Connect MT5 worker + symbol for OHLC-synchronized research evaluation. "
                    f"Registry: {decision.reason}"
                ),
            }

        # Fallback
        return {
            **base,
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "v40_unhandled_state",
            "details": f"Unhandled router state {decision.state.value}: {decision.reason}",
        }

    def _evaluate_research_ohlc(
        self,
        instrument: str,
        timeframe: str,
        rulebook_ids: tuple[str, ...] | list[str],
        market_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """
        Minimal research-safe OHLC evaluation when a market snapshot is present.

        Full deterministic V31/V35/V39 port is a follow-on; this path proves
        V40 routing without the V3 indicator gate and never marks production.
        """
        if not isinstance(market_snapshot, dict):
            return None

        close = market_snapshot.get("close")
        try:
            close_f = float(close) if close is not None else None
        except (TypeError, ValueError):
            close_f = None

        # Optional bar list for structure
        bars = market_snapshot.get("bars") or market_snapshot.get("ohlc") or market_snapshot.get("m1")
        signal = "HOLD"
        confidence = 0.0
        detail_bits = [
            f"Research OHLC path for {instrument} {timeframe}.",
            f"Rulebooks: {', '.join(rulebook_ids) or 'n/a'}.",
            "Production authorization remains false.",
        ]

        if isinstance(bars, list) and len(bars) >= 3:
            try:
                closes = [float(b.get("close", b.get("c", 0))) for b in bars[-5:]]
                if len(closes) >= 3:
                    slope = closes[-1] - closes[0]
                    # Extremely conservative research heuristic — never auto-trade
                    if slope > 0 and closes[-1] > closes[-2]:
                        signal = "HOLD"  # research: surface bias in details only
                        detail_bits.append(f"Short-window close slope positive ({slope:.6f}); research bias BUY (not actionable).")
                    elif slope < 0 and closes[-1] < closes[-2]:
                        signal = "HOLD"
                        detail_bits.append(f"Short-window close slope negative ({slope:.6f}); research bias SELL (not actionable).")
                    else:
                        detail_bits.append("No clear short-window structure.")
            except (TypeError, ValueError, AttributeError):
                detail_bits.append("OHLC bars present but not parseable.")
        elif close_f is not None:
            detail_bits.append(f"Last close={close_f}. Insufficient bars for structure.")
        else:
            return None

        return {
            "signal": signal,
            "confidence": confidence,
            "rule_name": "v40_research_ohlc_hold",
            "details": " ".join(detail_bits),
            "market_ohlc_close": close_f,
        }
