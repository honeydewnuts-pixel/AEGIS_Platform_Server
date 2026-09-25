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
        OHLC evaluation for ROUTABLE_RESEARCH instruments.

        Demo / paper path: when bars are present, emit actionable BUY/SELL so
        Executor can place demo trades. Production live still gated separately
        by production_authorized / subscription plan.
        """
        if not isinstance(market_snapshot, dict):
            return None

        close = market_snapshot.get("close")
        try:
            close_f = float(close) if close is not None else None
        except (TypeError, ValueError):
            close_f = None

        bars = market_snapshot.get("bars") or market_snapshot.get("ohlc") or market_snapshot.get("m1")
        detail_bits = [
            f"OHLC path for {instrument} {timeframe}.",
            f"Rulebooks: {', '.join(rulebook_ids) or 'n/a'}.",
        ]

        # 1) Prefer V2-OPT sequential rulebooks (file on disk or by instrument)
        try:
            from pathlib import Path as _P
            import json as _json
            from app.rulebooks.evaluators.v2opt_sequential import evaluate_v2opt_from_bars

            repo = _P(__file__).resolve().parents[3]
            candidates: list[tuple[str, _P]] = []
            for rid in rulebook_ids or []:
                if not str(rid).startswith("AEGIS-RB-V2OPT-"):
                    continue
                parts = str(rid).split("-")
                inst_guess = parts[3] if len(parts) >= 4 else instrument
                for folder in (inst_guess, instrument):
                    rb_path = repo / "registry" / "v2_opt" / folder / "rulebook.json"
                    if rb_path.exists():
                        candidates.append((str(rid), rb_path))
            # Fallback: instrument folder even if id list has no V2OPT
            fb = repo / "registry" / "v2_opt" / instrument.upper() / "rulebook.json"
            if fb.exists() and not candidates:
                candidates.append((f"AEGIS-RB-V2OPT-{instrument.upper()}-M5", fb))

            if candidates and isinstance(bars, list) and len(bars) >= 30:
                for rid, rb_path in candidates:
                    rb = _json.loads(rb_path.read_text())
                    out = evaluate_v2opt_from_bars(bars, rb)
                    # Promote research signal to demo-executable confidence floor
                    sig = str(out.get("signal") or "HOLD").upper()
                    conf = float(out.get("confidence") or 0.0)
                    # Do not floor confidence — EXEC_MIN_CONFIDENCE gates publish
                    out["market_ohlc_close"] = close_f
                    out["rulebook_ids"] = list(rulebook_ids)
                    out["demo_actionable"] = sig in ("BUY", "SELL")
                    out["production_authorized"] = False
                    if sig in ("BUY", "SELL"):
                        out["details"] = (
                            f"{out.get('details') or ''} Demo-executable {sig} "
                            f"(conf={conf:.2f}). Production authorization remains false."
                        ).strip()
                        return out
        except Exception as e:
            detail_bits.append(f"V2-OPT evaluator error: {e}")

        # 2) Structure + momentum on closed bars (always available from Feed stream)
        if not isinstance(bars, list) or len(bars) < 5:
            if close_f is not None:
                detail_bits.append(f"Last close={close_f}. Need >=5 bars for structure.")
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": "v40_research_ohlc_hold",
                "details": " ".join(detail_bits),
                "market_ohlc_close": close_f,
                "production_authorized": False,
            }

        try:
            closes = [float(b.get("close", b.get("c", 0))) for b in bars[-60:]]
            highs = [float(b.get("high", b.get("h", c))) for b, c in zip(bars[-60:], closes)]
            lows = [float(b.get("low", b.get("l", c))) for b, c in zip(bars[-60:], closes)]
        except (TypeError, ValueError, AttributeError):
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": "v40_research_ohlc_hold",
                "details": " ".join(detail_bits + ["OHLC bars not parseable."]),
                "market_ohlc_close": close_f,
                "production_authorized": False,
            }

        if len(closes) < 5:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": "v40_research_ohlc_hold",
                "details": " ".join(detail_bits + ["Insufficient closes."]),
                "market_ohlc_close": close_f,
                "production_authorized": False,
            }

        # Simple robust demo signal: multi-bar slope + last candle direction
        window = closes[-8:] if len(closes) >= 8 else closes
        slope = window[-1] - window[0]
        last_up = closes[-1] > closes[-2]
        last_down = closes[-1] < closes[-2]
        # ATR14 proxy for confidence scaling
        atr = 0.0
        if len(highs) >= 15:
            ranges = [highs[i] - lows[i] for i in range(-14, 0)]
            atr = sum(ranges) / max(1, len(ranges))
        slope_strength = abs(slope) / atr if atr > 1e-12 else 0.0

        signal = "HOLD"
        confidence = 0.0
        if slope > 0 and last_up:
            signal = "BUY"
            confidence = min(0.85, 0.55 + min(0.25, slope_strength * 0.1))
            detail_bits.append(
                f"Demo structure BUY: positive slope ({slope:.6g}), last bar up, strength={slope_strength:.2f}."
            )
        elif slope < 0 and last_down:
            signal = "SELL"
            confidence = min(0.85, 0.55 + min(0.25, slope_strength * 0.1))
            detail_bits.append(
                f"Demo structure SELL: negative slope ({slope:.6g}), last bar down, strength={slope_strength:.2f}."
            )
        else:
            detail_bits.append("No clear short-window structure — HOLD.")

        detail_bits.append(
            "Demo-actionable when BUY/SELL. Production authorization remains false for live capital."
        )
        return {
            "signal": signal,
            "confidence": confidence,
            "rule_name": "demo_ohlc_structure" if signal in ("BUY", "SELL") else "v40_research_ohlc_hold",
            "details": " ".join(detail_bits),
            "market_ohlc_close": close_f,
            "demo_actionable": signal in ("BUY", "SELL"),
            "production_authorized": False,
            "rulebook_ids": list(rulebook_ids),
        }
