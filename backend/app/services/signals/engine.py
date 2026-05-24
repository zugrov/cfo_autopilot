"""
SignalEngine — генерирует сигналы дефицита и stale data.

Сигналы idempotent: один сигнал на (company, type, date_bucket).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@dataclass
class Signal:
    alert_type: str  # deficit_7d | deficit_14d | deficit_30d | deficit_91d | stale_data
    severity: str    # critical | warning | info
    message: str
    date_bucket: date
    payload: dict


async def evaluate_signals(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date,
    forecast_json: dict,
    last_import_at: datetime | None,
) -> list[Signal]:
    """Вычисляет активные сигналы для компании."""
    signals: list[Signal] = []

    # Сигналы дефицита
    for horizon, key in [(7, "deficit_day_7"), (14, "deficit_day_14"), (30, "deficit_day_30"), (91, "deficit_day_91")]:
        deficit_date = forecast_json.get(key)
        if deficit_date:
            d = date.fromisoformat(deficit_date)
            signals.append(
                Signal(
                    alert_type=f"deficit_{horizon}d",
                    severity="critical" if horizon <= 14 else "warning",
                    message=f"Кассовый разрыв прогнозируется через {(d - as_of).days} дней ({d.strftime('%d.%m.%Y')})",
                    date_bucket=d,
                    payload={"deficit_date": deficit_date, "horizon_days": horizon},
                )
            )

    # Stale data: нет импорта > 24 часов
    if last_import_at:
        hours_stale = (datetime.utcnow() - last_import_at).total_seconds() / 3600
        if hours_stale > 24:
            signals.append(
                Signal(
                    alert_type="stale_data",
                    severity="warning",
                    message=f"Данные не обновлялись {int(hours_stale)} ч.",
                    date_bucket=as_of,
                    payload={"hours_stale": int(hours_stale), "last_import_at": last_import_at.isoformat()},
                )
            )

    # Нет обязательств — прогноз неполный
    if not forecast_json.get("has_obligations"):
        signals.append(
            Signal(
                alert_type="no_obligations",
                severity="info",
                message="Прогноз неполный — добавьте обязательства для точности",
                date_bucket=as_of,
                payload={},
            )
        )

    return signals


async def persist_signals(
    db: AsyncSession,
    company_id: uuid.UUID,
    signals: list[Signal],
) -> int:
    """Сохраняет сигналы в таблицу alert. Idempotent: ON CONFLICT DO NOTHING."""
    import json
    import uuid as uuid_module

    saved = 0
    for sig in signals:
        await db.execute(
            text(
                "INSERT INTO alert (id, company_id, alert_type, date_bucket, payload, created_at) "
                "VALUES (:id, :company_id, :alert_type, :date_bucket, CAST(:payload AS jsonb), now()) "
                "ON CONFLICT (company_id, alert_type, date_bucket) DO NOTHING"
            ),
            {
                "id": uuid_module.uuid4(),
                "company_id": company_id,
                "alert_type": sig.alert_type,
                "date_bucket": sig.date_bucket,
                "payload": json.dumps(sig.payload),
            },
        )
        saved += 1
    return saved
