"""
Generalized risk-based position sizing (stop-loss risk, not margin allocation).

Position Size = Risk Budget / Monetary Loss per 1.0 lot at the initial stop

Round DOWN to volume_step. Never round up past the risk budget.
Reject when min volume would exceed risk budget or specs/rates are missing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class InstrumentSpec:
    """Broker or registry contract specification. No instrument is special-cased in formulas."""

    symbol: str
    asset_class: str  # forex | metal | index | crypto | other
    contract_size: float  # units per 1.0 lot
    volume_min: float
    volume_max: float
    volume_step: float
    tick_size: float  # minimum price increment
    tick_value_account: float | None = None  # if set, loss uses ticks * tick_value * lots
    profit_currency: str = "USD"
    margin_currency: str = "USD"
    # Quote currency for FX (pair XXXYYY → YYY). Used when tick_value_account is None.
    quote_currency: str = "USD"
    base_currency: str = "USD"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SizingResult:
    allow: bool
    volume: float
    reason: str
    audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"allow": self.allow, "volume": self.volume, "reason": self.reason, **self.audit}


def _round_down_to_step(volume: float, step: float) -> float:
    if step <= 0:
        return volume
    # avoid float drift
    n = int(volume / step + 1e-12)
    return round(n * step, 10)


def stop_distance(entry: float, stop: float, side: Side) -> float:
    """Positive distance from entry to stop in price units; 0 if invalid for side."""
    if side == "SELL":
        d = float(stop) - float(entry)
    else:
        d = float(entry) - float(stop)
    return d if d > 0 else 0.0


def loss_per_lot_in_profit_ccy(
    entry: float,
    stop: float,
    side: Side,
    spec: InstrumentSpec,
) -> tuple[float | None, str]:
    """
    Monetary loss in the instrument's profit/quote currency for 1.0 lot if stopped out.
    Returns (loss_amount, reason_if_invalid).
    """
    dist = stop_distance(entry, stop, side)
    if dist <= 0:
        return None, "invalid_stop_distance"
    if spec.tick_value_account is not None and spec.tick_size > 0:
        ticks = dist / spec.tick_size
        return float(ticks * spec.tick_value_account), "ok"
    if spec.contract_size <= 0:
        return None, "invalid_contract_size"
    # Generic: loss_in_quote = distance * contract_size (standard FX/metal style)
    return float(dist * spec.contract_size), "ok"


def convert_to_account_currency(
    amount: float,
    from_ccy: str,
    account_ccy: str,
    fx_rates: dict[str, float] | None,
) -> tuple[float | None, str]:
    """
    Convert amount from from_ccy to account_ccy.
    fx_rates keys are pairs like 'EURUSD' meaning 1 EUR = rate USD, or 'USDCHF'.
    Also accepts direct key f"{from}_{to}".
    """
    from_ccy = (from_ccy or "").upper()
    account_ccy = (account_ccy or "").upper()
    if from_ccy == account_ccy:
        return float(amount), "ok"
    rates = {k.upper(): float(v) for k, v in (fx_rates or {}).items()}
    direct = f"{from_ccy}_{account_ccy}"
    if direct in rates and rates[direct] > 0:
        return float(amount) * rates[direct], "ok"
    inv = f"{account_ccy}_{from_ccy}"
    if inv in rates and rates[inv] > 0:
        return float(amount) / rates[inv], "ok"
    pair = f"{from_ccy}{account_ccy}"
    if pair in rates and rates[pair] > 0:
        return float(amount) * rates[pair], "ok"
    pair_inv = f"{account_ccy}{from_ccy}"
    if pair_inv in rates and rates[pair_inv] > 0:
        return float(amount) / rates[pair_inv], "ok"
    return None, "missing_fx_rate"


def size_by_stop_risk(
    *,
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    side: Side,
    spec: InstrumentSpec,
    account_currency: str = "USD",
    fx_rates: dict[str, float] | None = None,
    open_risk_usd: float = 0.0,
    risk_budget_override: float | None = None,
    available_margin: float | None = None,
    margin_per_lot: float | None = None,
    plan_max_volume: float | None = None,
    require_margin_check: bool = False,
) -> SizingResult:
    """
    Core engine: risk budget / loss-per-lot at stop, round down, then margin check.

    Margin behaviour:
    - require_margin_check=False (research / optional pathways): margin is validated
      only when BOTH available_margin and margin_per_lot are supplied; otherwise
      margin is skipped and recorded as not_checked in the audit.
    - require_margin_check=True (execution pathway): BOTH inputs are mandatory.
      Missing either → reject with reason margin_data_missing (fail-closed).
      Both present but required_margin > available → insufficient_margin.
    """
    audit: dict[str, Any] = {
        "instrument": spec.symbol,
        "account_currency": account_currency.upper(),
        "profit_currency": spec.profit_currency.upper(),
        "entry_price": float(entry_price),
        "initial_stop_loss": float(stop_loss),
        "side": side,
        "equity": float(equity),
        "risk_pct": float(risk_pct),
        "open_risk_usd": float(open_risk_usd),
        "volume_min": spec.volume_min,
        "volume_max": spec.volume_max,
        "volume_step": spec.volume_step,
        "contract_size": spec.contract_size,
        "tick_size": spec.tick_size,
        "require_margin_check": bool(require_margin_check),
        "margin_per_lot_supplied": margin_per_lot,
        "available_margin_supplied": available_margin,
    }

    if equity is None or float(equity) <= 0:
        return SizingResult(False, 0.0, "equity_required_for_risk_sizing", audit)
    if risk_pct is None or float(risk_pct) <= 0:
        return SizingResult(False, 0.0, "invalid_risk_pct", audit)
    if entry_price is None or float(entry_price) <= 0:
        return SizingResult(False, 0.0, "invalid_entry_price", audit)
    if stop_loss is None:
        return SizingResult(False, 0.0, "stop_loss_required", audit)

    dist = stop_distance(float(entry_price), float(stop_loss), side)
    audit["stop_distance"] = dist
    if dist <= 0:
        return SizingResult(False, 0.0, "invalid_stop_distance", audit)

    loss_quote, why = loss_per_lot_in_profit_ccy(float(entry_price), float(stop_loss), side, spec)
    if loss_quote is None:
        audit["reject_detail"] = why
        return SizingResult(False, 0.0, why, audit)
    audit["loss_per_lot_profit_ccy"] = loss_quote

    loss_acct, conv_why = convert_to_account_currency(
        loss_quote, spec.profit_currency, account_currency, fx_rates
    )
    if loss_acct is None or loss_acct <= 0:
        audit["reject_detail"] = conv_why
        return SizingResult(False, 0.0, conv_why if loss_acct is None else "invalid_loss_per_lot", audit)
    audit["loss_per_lot_account_ccy"] = loss_acct
    audit["fx_conversion"] = conv_why

    full_budget = float(equity) * float(risk_pct) / 100.0
    remaining = max(0.0, full_budget - float(open_risk_usd or 0.0))
    budget = float(risk_budget_override) if risk_budget_override is not None else remaining
    audit["risk_budget_full"] = full_budget
    audit["risk_budget_used"] = budget

    if budget <= 0:
        return SizingResult(False, 0.0, "insufficient_remaining_risk", audit)

    raw_lots = budget / loss_acct
    audit["raw_lots"] = raw_lots

    vol = _round_down_to_step(raw_lots, spec.volume_step)
    if plan_max_volume is not None:
        vol = min(vol, float(plan_max_volume))
    vol = min(vol, float(spec.volume_max))
    audit["volume_after_round_down"] = vol

    if vol < spec.volume_min - 1e-12:
        audit["estimated_risk_at_min_lot"] = loss_acct * spec.volume_min
        return SizingResult(False, 0.0, "min_lot_exceeds_risk_budget", audit)

    # Re-check risk after rounding
    estimated_risk = loss_acct * vol
    audit["estimated_monetary_risk"] = estimated_risk
    if estimated_risk > budget + 1e-6:
        # should not happen after round-down; still fail closed
        return SizingResult(False, 0.0, "risk_exceeds_budget_after_round", audit)

    # Margin validation (separate from risk-budget / min-lot checks)
    m_lot = float(margin_per_lot) if margin_per_lot is not None else None
    a_mgn = float(available_margin) if available_margin is not None else None
    audit["margin_per_lot"] = m_lot
    audit["available_margin"] = a_mgn
    audit["required_margin"] = (m_lot * vol) if m_lot is not None else None

    if require_margin_check:
        if m_lot is None or a_mgn is None:
            missing = []
            if m_lot is None:
                missing.append("margin_per_lot")
            if a_mgn is None:
                missing.append("available_margin")
            audit["margin_missing_fields"] = missing
            audit["margin_check_status"] = "rejected_missing_data"
            return SizingResult(False, 0.0, "margin_data_missing", audit)
        req = m_lot * vol
        audit["required_margin"] = req
        if req > a_mgn + 1e-6:
            audit["margin_check_status"] = "rejected_insufficient"
            return SizingResult(False, 0.0, "insufficient_margin", audit)
        audit["margin_check_status"] = "passed"
    else:
        # Optional pathway: validate only when both inputs are present
        if m_lot is not None and a_mgn is not None:
            req = m_lot * vol
            audit["required_margin"] = req
            if req > a_mgn + 1e-6:
                audit["margin_check_status"] = "rejected_insufficient"
                return SizingResult(False, 0.0, "insufficient_margin", audit)
            audit["margin_check_status"] = "passed"
        else:
            audit["margin_check_status"] = "skipped_not_required"
            if m_lot is not None or a_mgn is not None:
                audit["margin_partial_inputs"] = True

    audit["final_volume"] = vol
    return SizingResult(True, float(vol), "ok", audit)


# ---------------------------------------------------------------------------
# Default registry — templates only; brokers should overwrite via Feed/API.
# Formulas never special-case a symbol name.
# ---------------------------------------------------------------------------

def default_forex_spec(
    symbol: str,
    *,
    base: str,
    quote: str,
    volume_min: float = 0.01,
    volume_step: float = 0.01,
    volume_max: float = 100.0,
    tick_size: float = 0.00001,
    contract_size: float = 100_000.0,
) -> InstrumentSpec:
    return InstrumentSpec(
        symbol=symbol.upper(),
        asset_class="forex",
        contract_size=contract_size,
        volume_min=volume_min,
        volume_max=volume_max,
        volume_step=volume_step,
        tick_size=tick_size,
        tick_value_account=None,
        profit_currency=quote.upper(),
        margin_currency=base.upper(),
        quote_currency=quote.upper(),
        base_currency=base.upper(),
    )


def default_spec_for_symbol(symbol: str) -> InstrumentSpec | None:
    """Best-effort registry template. Returns None if unknown (caller must reject or supply spec)."""
    s = symbol.upper().split(".")[0]
    # Metals
    if s in ("XAUUSD", "GOLD"):
        return InstrumentSpec(
            symbol=s, asset_class="metal", contract_size=100.0,
            volume_min=0.01, volume_max=50.0, volume_step=0.01,
            tick_size=0.01, profit_currency="USD", margin_currency="USD",
            quote_currency="USD", base_currency="XAU",
        )
    if s in ("XAGUSD", "SILVER"):
        return InstrumentSpec(
            symbol=s, asset_class="metal", contract_size=5000.0,
            volume_min=0.01, volume_max=50.0, volume_step=0.01,
            tick_size=0.001, profit_currency="USD", margin_currency="USD",
            quote_currency="USD", base_currency="XAG",
        )
    # Crypto
    if s in ("BTCUSD", "ETHUSD"):
        return InstrumentSpec(
            symbol=s, asset_class="crypto", contract_size=1.0,
            volume_min=0.01, volume_max=50.0, volume_step=0.01,
            tick_size=0.01, profit_currency="USD", margin_currency="USD",
            quote_currency="USD", base_currency=s[:3],
        )
    # 6-char FX
    if len(s) == 6 and s.isalpha():
        base, quote = s[:3], s[3:]
        # JPY pairs often 2-3 decimal quotes
        tick = 0.001 if quote == "JPY" else 0.00001
        return default_forex_spec(s, base=base, quote=quote, tick_size=tick)
    return None


def fx_rates_for_pair_price(symbol: str, mid_price: float) -> dict[str, float]:
    """
    Build minimal FX map from the traded pair's own mid price so quote→USD
    (or USD→quote) conversion can work without external feeds.
    """
    s = symbol.upper().split(".")[0]
    if len(s) != 6:
        return {}
    base, quote = s[:3], s[3:]
    px = float(mid_price)
    if px <= 0:
        return {}
    rates: dict[str, float] = {s: px, f"{base}_{quote}": px, f"{quote}_{base}": 1.0 / px}
    # If account is USD and quote is USD, no conversion needed.
    # If base is USD (e.g. USDCHF), quote is CHF: 1 CHF = 1/px USD
    if base == "USD":
        rates[f"{quote}_USD"] = 1.0 / px
        rates[f"USD_{quote}"] = px
    if quote == "USD":
        rates[f"{base}_USD"] = px
        rates[f"USD_{base}"] = 1.0 / px
    return rates


def instrument_spec_from_broker(
    symbol: str,
    *,
    contract_size: float,
    volume_min: float,
    volume_max: float,
    volume_step: float,
    tick_size: float,
    tick_value: float | None = None,
    base_currency: str = "USD",
    quote_currency: str = "USD",
    profit_currency: str | None = None,
    asset_class: str = "forex",
) -> InstrumentSpec:
    """Build InstrumentSpec from broker/EA reported fields. No silent defaults for sizes."""
    if contract_size <= 0 or volume_min <= 0 or volume_step <= 0 or tick_size <= 0:
        raise ValueError("invalid_broker_instrument_spec")
    pc = (profit_currency or quote_currency or "USD").upper()
    return InstrumentSpec(
        symbol=symbol.upper().split(".")[0],
        asset_class=asset_class,
        contract_size=float(contract_size),
        volume_min=float(volume_min),
        volume_max=float(volume_max),
        volume_step=float(volume_step),
        tick_size=float(tick_size),
        tick_value_account=float(tick_value) if tick_value is not None else None,
        profit_currency=pc,
        margin_currency=base_currency.upper(),
        quote_currency=quote_currency.upper(),
        base_currency=base_currency.upper(),
    )
