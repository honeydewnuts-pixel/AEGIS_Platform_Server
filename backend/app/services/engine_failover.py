"""
Primary/fallback failover for the V3 rule engine + neural layer.

BACKGROUND - what "primary" and "fallback" actually are here
---------------------------------------------------------------
These are two genuinely different, independently-built implementations,
not two versions of the same one:

  PRIMARY  (signal_rule_engine_v3.py / neural_service.py):
    - Rule engine uses real price_close (approximated from candle body
      pixel color, per brain_cv_service.py's own documented caveat -
      still a screenshot heuristic, not a broker OHLC feed).
    - Neural layer: compact 13-feature single-frame design (5 calibrated
      RSI-scale values + 8 rule-engine flags), model
      aegis_neural_v3_2.3.6.6.json (MLP_13_32_16_3).
    - Currently the only engine wired into BrainCVService.

  FALLBACK (signal_rule_engine_v3_fallback.py / neural_service_v3_fallback.py):
    - Rule engine has no price_close dependency; approximates price
      direction via the price-panel basis line instead.
    - Neural layer: 52-feature temporal-window design (13 channels x
      mean/last/std/slope over 20 frames), model
      aegis_neural_v3_fallback.json (MLP_52_32_16_3).
    - This is the originally-delivered v3 implementation, preserved as
      a rollback/safety net (see FALLBACK_README.md / FALLBACK_MANIFEST.json
      in the source package) - not a newer or "better" model, just a
      different, independently-functioning one to fail over to.

Because the two RuleResult shapes and neural feature signatures differ,
neither can be swapped in as a literal drop-in replacement for the
other. This module normalizes both behind one common interface
(`evaluate(history) -> dict`) so BrainCVService doesn't need to know or
care which one is currently serving requests.

FAILOVER POLICY
-----------------
- Init-time: if the primary fails to construct (missing model file,
  feature_dim mismatch, any other exception), fall back immediately and
  log at CRITICAL - this should be rare and always investigated, not a
  normal operating mode.
- Run-time: a simple consecutive-failure counter. FAILURE_THRESHOLD
  consecutive exceptions from the active engine's evaluate() or neural
  apply() trips the breaker and switches to fallback for all subsequent
  requests.
- Recovery is manual only (force_tier("primary")), not automatic. A
  circuit breaker that silently flips back and forth on an intermittent
  fault is worse than one that fails open to a known-working fallback
  and waits for a human to confirm the primary is actually fixed -
  especially for something feeding trade signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core.logging import configure_logging

FAILURE_THRESHOLD = 3


@dataclass
class EngineStatus:
    active_tier: str                # "primary" or "fallback"
    consecutive_failures: int
    primary_available: bool
    fallback_available: bool
    last_error: str | None


class EngineFailoverManager:
    """Holds both engine pairs and routes evaluate() to whichever is active."""

    def __init__(
        self,
        build_primary: Callable[[], tuple[Any, Any]],
        build_fallback: Callable[[], tuple[Any, Any]],
        logger_name: str = __name__,
    ) -> None:
        self.logger = configure_logging(logger_name)
        self._build_primary = build_primary
        self._build_fallback = build_fallback

        self.primary_rule_engine = None
        self.primary_neural = None
        self.fallback_rule_engine = None
        self.fallback_neural = None

        self.active_tier = "primary"
        self._consecutive_failures = 0
        self._last_error: str | None = None

        self._init_primary()

    # ------------------------------------------------------------
    # Construction / lazy fallback build
    # ------------------------------------------------------------

    def _init_primary(self) -> None:
        try:
            self.primary_rule_engine, self.primary_neural = self._build_primary()
            self.active_tier = "primary"
            self.logger.info("Primary V3 engine initialized successfully.")
        except Exception as exc:  # noqa: BLE001
            self.logger.critical(
                "Primary V3 engine FAILED TO INITIALIZE (%s) - falling back to "
                "the backup V3 engine at startup. This should be investigated; "
                "it is not a normal operating condition.", exc, exc_info=True,
            )
            self._last_error = f"init: {exc}"
            self._ensure_fallback_built()
            self.active_tier = "fallback"

    def _ensure_fallback_built(self) -> None:
        if self.fallback_rule_engine is not None and self.fallback_neural is not None:
            return
        try:
            self.fallback_rule_engine, self.fallback_neural = self._build_fallback()
            self.logger.info("Fallback V3 engine initialized successfully.")
        except Exception as exc:  # noqa: BLE001
            self.logger.critical(
                "Fallback V3 engine ALSO failed to initialize (%s). No working "
                "V3 engine is available - analysis requests will fail.", exc, exc_info=True,
            )
            raise

    # ------------------------------------------------------------
    # Status / manual control
    # ------------------------------------------------------------

    def status(self) -> EngineStatus:
        return EngineStatus(
            active_tier=self.active_tier,
            consecutive_failures=self._consecutive_failures,
            primary_available=self.primary_rule_engine is not None,
            fallback_available=self.fallback_rule_engine is not None,
            last_error=self._last_error,
        )

    def force_tier(self, tier: str) -> EngineStatus:
        tier = tier.strip().lower()
        if tier not in ("primary", "fallback"):
            raise ValueError(f"Unknown tier '{tier}' - expected 'primary' or 'fallback'")
        if tier == "fallback":
            self._ensure_fallback_built()
        else:
            # Don't just check that primary was built at some point - a
            # circuit trip is usually a RUNTIME failure (evaluate() itself
            # throwing), which a successfully-constructed engine can still
            # have. Re-verify it actually works right now with a cheap,
            # safe call before committing to the switch, so an admin
            # can't accidentally "recover" back onto a still-broken engine.
            if self.primary_rule_engine is None:
                self._init_primary()
                if self.active_tier != "primary":
                    raise RuntimeError("Primary engine still fails to initialize - cannot force-select it.")
            else:
                try:
                    self.primary_rule_engine.evaluate([])
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(
                        f"Primary engine still fails on a basic health check ({exc}) - "
                        "refusing to switch back to it. Fix the underlying issue first."
                    ) from exc
        self.active_tier = tier
        self._consecutive_failures = 0
        self.logger.info("Engine tier manually set to %s", tier)
        return self.status()

    # ------------------------------------------------------------
    # Evaluation with automatic failover
    # ------------------------------------------------------------

    def evaluate(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        if self.active_tier == "primary":
            try:
                return self._evaluate_primary(history)
            except Exception as exc:  # noqa: BLE001
                self._record_failure(exc)
                if self._consecutive_failures >= FAILURE_THRESHOLD:
                    self.logger.critical(
                        "Primary V3 engine failed %d times in a row (latest: %s) - "
                        "switching to fallback engine for subsequent requests. "
                        "Call force_tier('primary') once the underlying issue is fixed.",
                        self._consecutive_failures, exc,
                    )
                    self._ensure_fallback_built()
                    self.active_tier = "fallback"
                    return self._evaluate_fallback(history)
                # Below threshold: surface a safe HOLD rather than crash the
                # request, but don't switch tiers yet for a possibly-transient blip.
                self.logger.warning("Primary V3 engine error (%d/%d): %s",
                                     self._consecutive_failures, FAILURE_THRESHOLD, exc)
                return self._safe_hold(f"primary_error: {exc}", len(history))

        return self._evaluate_fallback(history)

    def _evaluate_primary(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        result = self.primary_rule_engine.evaluate(history)
        conf = 0.85 if result.fired else (0.15 if result.rule_name == "warming_up" else 0.0)
        # BUG FIX (see brain_cv_service.py comment): merge rule_flags AND the
        # separate contraction/expansion fields into one flags dict, instead
        # of silently omitting all 8 flag features from the neural input.
        flags = dict(getattr(result, "rule_flags", {}) or {})
        flags["CONTRACTION"] = getattr(result, "contraction", 0)
        flags["EXPANSION"] = getattr(result, "expansion", 0)
        base = {
            "signal": result.signal or "HOLD",
            "confidence": conf,
            "rule_name": result.rule_name,
            "details": f"{result.rule_name}: {result.reason}",
            "frames_in_history": len(history),
            "rule_flags": flags,
            "engine_tier": "primary",
        }
        out = self.primary_neural.apply(history, base)
        self._consecutive_failures = 0
        return out

    def _evaluate_fallback(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        result = self.fallback_rule_engine.evaluate(history)
        base = {
            "signal": result.signal or "HOLD",
            "confidence": 0.85 if result.fired else (0.15 if result.rule_name == "warming_up" else 0.0),
            "rule_name": result.rule_name,
            "details": f"{result.rule_name}: {result.reason}",
            "frames_in_history": len(history),
            "engine_tier": "fallback",
        }
        try:
            return self.fallback_neural.apply(history, base)
        except Exception as exc:  # noqa: BLE001
            # Fallback neural failing is not itself a reason to fail the
            # request - the fallback RULE engine result alone is still a
            # usable, deterministic signal. Degrade gracefully to rule-only.
            self.logger.warning("Fallback neural layer skipped: %s", exc)
            base["neural_applied"] = False
            return base

    def _record_failure(self, exc: Exception) -> None:
        self._consecutive_failures += 1
        self._last_error = str(exc)

    @staticmethod
    def _safe_hold(reason: str, frames_in_history: int) -> dict[str, Any]:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "engine_error",
            "details": reason,
            "frames_in_history": frames_in_history,
            "neural_applied": False,
            "engine_tier": "primary",
        }
