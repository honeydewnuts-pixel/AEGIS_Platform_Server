"""
AEGIS Trade Copier (Duplikium-style master → slave mirroring).

Simple model:
  1. Subscriber activates a Trade Copier add-on on their AEGIS account (master).
  2. They register slave MT5 logins (server + login + risk).
  3. When the master places a market order via AEGIS, the same direction is
     queued to each enabled slave with size = master_lots * risk_value
     (multiplier mode) or fixed risk_value lots.

Full broker connectivity still uses the existing worker pool when a worker
is available for that slave login key; otherwise the copy is recorded as
queued for the next connected worker cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func

from app.db.base import async_session_factory
from app.db.models import TradeCopierAddon, TradeCopierSlave, Subscription
from app.services.plan_catalog import resolve_addon


class TradeCopierService:
    async def get_addon(self, account_id: str) -> dict[str, Any] | None:
        async with async_session_factory() as session:
            row = await session.get(TradeCopierAddon, account_id)
            if not row or row.status != "active":
                return None
            slaves = (
                await session.execute(
                    select(TradeCopierSlave).where(
                        TradeCopierSlave.master_account_id == account_id
                    )
                )
            ).scalars().all()
            return {
                "account_id": account_id,
                "tier": row.tier,
                "status": row.status,
                "max_slaves": row.max_slaves,
                "slave_count": len(slaves),
                "slaves": [
                    {
                        "id": s.id,
                        "label": s.label,
                        "server": s.server,
                        "login": s.login,
                        "broker_name": s.broker_name,
                        "risk_mode": s.risk_mode,
                        "risk_value": s.risk_value,
                        "enabled": s.enabled,
                    }
                    for s in slaves
                ],
            }

    async def activate_addon(self, account_id: str, tier: str = "copier_3") -> dict[str, Any]:
        # Must have an active base subscription (not none)
        async with async_session_factory() as session:
            sub = await session.get(Subscription, account_id)
            if sub is None or sub.status not in ("active", "past_due", "demo"):
                raise ValueError("Activate an AEGIS plan (demo or paid) before Trade Copier.")
            if (sub.plan or "").lower() == "demo":
                # Allow setup on demo for testing; live slave execution still gated elsewhere
                pass
            addon = resolve_addon(tier)
            now = datetime.now(timezone.utc)
            row = await session.get(TradeCopierAddon, account_id)
            if row:
                row.tier = addon["code"]
                row.max_slaves = int(addon["max_slaves"])
                row.status = "active"
                row.updated_at = now
            else:
                session.add(
                    TradeCopierAddon(
                        account_id=account_id,
                        tier=addon["code"],
                        status="active",
                        max_slaves=int(addon["max_slaves"]),
                        updated_at=now,
                    )
                )
            await session.commit()
        return (await self.get_addon(account_id)) or {}

    async def add_slave(
        self,
        master_account_id: str,
        *,
        label: str,
        server: str,
        login: str,
        broker_name: str | None = None,
        risk_mode: str = "multiplier",
        risk_value: float = 1.0,
    ) -> dict[str, Any]:
        async with async_session_factory() as session:
            addon = await session.get(TradeCopierAddon, master_account_id)
            if not addon or addon.status != "active":
                raise ValueError("Trade Copier add-on is not active. Activate a copier tier first.")
            count = (
                await session.execute(
                    select(func.count()).select_from(TradeCopierSlave).where(
                        TradeCopierSlave.master_account_id == master_account_id
                    )
                )
            ).scalar_one()
            if count >= addon.max_slaves:
                raise ValueError(f"Slave limit reached ({addon.max_slaves}). Upgrade copier tier.")
            if risk_mode not in ("multiplier", "fixed_lot"):
                risk_mode = "multiplier"
            now = datetime.now(timezone.utc)
            slave = TradeCopierSlave(
                master_account_id=master_account_id,
                label=(label or "Slave")[:64],
                broker_name=broker_name,
                server=server.strip(),
                login=str(login).strip(),
                risk_mode=risk_mode,
                risk_value=float(risk_value) if risk_value > 0 else 1.0,
                enabled=True,
                created_at=now,
            )
            session.add(slave)
            await session.commit()
            await session.refresh(slave)
            return {
                "id": slave.id,
                "label": slave.label,
                "server": slave.server,
                "login": slave.login,
                "risk_mode": slave.risk_mode,
                "risk_value": slave.risk_value,
            }

    async def remove_slave(self, master_account_id: str, slave_id: int) -> bool:
        async with async_session_factory() as session:
            row = await session.get(TradeCopierSlave, slave_id)
            if not row or row.master_account_id != master_account_id:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def set_slave_enabled(self, master_account_id: str, slave_id: int, enabled: bool) -> bool:
        async with async_session_factory() as session:
            row = await session.get(TradeCopierSlave, slave_id)
            if not row or row.master_account_id != master_account_id:
                return False
            row.enabled = enabled
            await session.commit()
            return True

    async def mirror_market_order(
        self,
        master_account_id: str,
        *,
        symbol: str,
        side: str,
        volume: float,
        job_queue: Any | None = None,
        worker_pool: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Fan-out a master fill to enabled slaves. Best-effort."""
        addon = await self.get_addon(master_account_id)
        if not addon:
            return []
        results: list[dict[str, Any]] = []
        for s in addon.get("slaves") or []:
            if not s.get("enabled"):
                continue
            lots = float(volume)
            if s.get("risk_mode") == "fixed_lot":
                lots = float(s.get("risk_value") or 0.01)
            else:
                lots = max(0.01, float(volume) * float(s.get("risk_value") or 1.0))
            entry = {
                "slave_id": s["id"],
                "label": s["label"],
                "login": s["login"],
                "symbol": symbol,
                "side": side,
                "volume": round(lots, 2),
                "status": "queued",
            }
            # Prefer existing worker identity if slave was connected under master path
            slave_key = f"{master_account_id}:slave:{s['id']}"
            if job_queue is not None and worker_pool is not None:
                try:
                    if await worker_pool.is_running(slave_key):
                        payload = {
                            "symbol": symbol,
                            "side": side,
                            "volume": lots,
                            "comment": f"AEGIS-COPY:{master_account_id}",
                        }
                        r = await job_queue.submit_and_wait(slave_key, "market_order", payload)
                        entry["status"] = "submitted" if r and r.get("success") else "failed"
                        entry["detail"] = (r or {}).get("message")
                    else:
                        entry["status"] = "queued_offline"
                        entry["detail"] = "Slave worker not connected; connect slave credentials when workers are available."
                except Exception as exc:  # noqa: BLE001
                    entry["status"] = "error"
                    entry["detail"] = str(exc)[:200]
            results.append(entry)
        return results
