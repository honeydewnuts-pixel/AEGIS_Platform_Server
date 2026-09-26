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

        Baseline (cash-test methodology): V31 SHORT entry logic used by V53.6
        transfer rulebooks and GBPUSD V31 source lineage.
        Does NOT use demo_ohlc_structure slope BUY/SELL substitute.
        """
        if not isinstance(market_snapshot, dict):
            return None

        close = market_snapshot.get("close")
        try:
            close_f = float(close) if close is not None else None
        except (TypeError, ValueError):
            close_f = None

        bars = market_snapshot.get("bars") or market_snapshot.get("ohlc") or market_snapshot.get("m1")
        ids = [str(x) for x in (rulebook_ids or [])]
        detail_bits = [
            f"OHLC path for {instrument} {timeframe}.",
            f"Rulebooks: {', '.join(ids) or 'n/a'}.",
        ]

        if not isinstance(bars, list) or len(bars) < 5:
            if close_f is not None:
                detail_bits.append(f"Last close={close_f}. Need bars for V31 evaluation.")
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "rule_name": "v40_research_awaiting_ohlc",
                "details": " ".join(detail_bits),
                "market_ohlc_close": close_f,
                "production_authorized": False,
                "methodology": "v31_short_baseline",
            }

        # --- Baseline: V53.6 / V31 SHORT (historical cash-test methodology) ---
        v31_ids = [
            rid for rid in ids
            if "V53.6" in rid or "V53_6" in rid or rid.startswith("AEGIS-RB-V31-")
        ]
        # Prefer explicit V53.6 id, else V31 source, else synthesize from instrument
        if not v31_ids:
            # Router eligible list may use V39 ids; still apply V31 short if
            # registry has V53.6 artifact for this instrument
            from pathlib import Path as _P
            rb_dir = _P(__file__).resolve().parents[3] / "registry" / "v53_6" / instrument.upper()
            if (rb_dir / "rulebook.json").exists():
                import json as _json
                meta = _json.loads((rb_dir / "rulebook.json").read_text())
                v31_ids = [str(meta.get("rulebook_id") or f"AEGIS-RB-V53.6-V31-{instrument.upper()}-5M")]
            elif instrument.upper() == "GBPUSD":
                v31_ids = ["AEGIS-RB-V31-GBPUSD-5M"]

        if v31_ids:
            from app.rulebooks.live_v31_short import evaluate_live_v31_short
            rid = v31_ids[0]
            out = evaluate_live_v31_short(bars, rulebook_id=rid, instrument=instrument)
            out["market_ohlc_close"] = close_f
            out["rulebook_ids"] = list(ids) or [rid]
            out["production_authorized"] = False
            # SHORT only — never promote to BUY
            if str(out.get("signal")).upper() == "BUY":
                out["signal"] = "HOLD"
                out["details"] = (out.get("details") or "") + " BUY suppressed: baseline is SHORT-only."
            return out

        # --- Explicit experimental only: V2-OPT sequential (not baseline) ---
        try:
            from pathlib import Path as _P
            import json as _json
            from app.rulebooks.evaluators.v2opt_sequential import evaluate_v2opt_from_bars
            from app.config import settings

            if not getattr(settings, "ALLOW_V2OPT_LIVE_SIGNALS", False):
                detail_bits.append("V2-OPT live signals disabled (not cash-test baseline).")
            else:
                repo = _P(__file__).resolve().parents[3]
                candidates: list[tuple[str, _P]] = []
                for rid in ids:
                    if not str(rid).startswith("AEGIS-RB-V2OPT-"):
                        continue
                    parts = str(rid).split("-")
                    inst_guess = parts[3] if len(parts) >= 4 else instrument
                    for folder in (inst_guess, instrument):
                        rb_path = repo / "registry" / "v2_opt" / folder / "rulebook.json"
                        if rb_path.exists():
                            candidates.append((str(rid), rb_path))
                if candidates and len(bars) >= 30:
                    for rid, rb_path in candidates:
                        rb = _json.loads(rb_path.read_text())
                        out = evaluate_v2opt_from_bars(bars, rb)
                        out["market_ohlc_close"] = close_f
                        out["rulebook_ids"] = list(ids)
                        out["methodology"] = "v2opt_experimental"
                        out["production_authorized"] = False
                        return out
        except Exception as e:
            detail_bits.append(f"V2-OPT evaluator error: {e}")

        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "v40_research_ohlc_hold",
            "details": " ".join(detail_bits + [
                "No baseline V31/V53.6 rulebook resolved; demo_ohlc_structure is disabled."
            ]),
            "market_ohlc_close": close_f,
            "production_authorized": False,
            "methodology": "v31_short_baseline",
            "rulebook_ids": list(ids),
        }

