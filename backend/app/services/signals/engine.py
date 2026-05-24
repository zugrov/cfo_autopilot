"""
SignalEngine — генерирует сигнал кассового разрыва.

Сигналы idempotent: один сигнал на (company, alert_type, date_bucket).
Sprint A: только cash_gap; stale/no_obligations считаются inline в dashboard.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.signals.cash_gap import compute_cash_gap_signal


@dataclass
class Signal:
    alert_type: str  # cash_gap
    severity: str    # critical | warning | info
    message: str
    date_bucket: date
    payload: dict


async def evaluate_signals(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date,
    forecast_json: dict,
    last_import_at: object = None,  # оставлен для обратной совместимости вызовов
) -> list[Signal]:
    """Вычисляет активные сигналы для компании.

    Единственный персистентный сигнал — cash_gap.
    stale_data и no_obligations — состояние данных, считается inline.
    """
    signals: list[Signal] = []

    gap = compute_cash_gap_signal(forecast_json, as_of)
    if gap is not None:
        verb = {
            "critical": "Кассовый разрыв через",
            "warning": "Кассовый разрыв возможен через",
            "info": "Риск кассового разрыва через",
        }[gap.severity]
        stress_note = " (стресс-сценарий)" if gap.is_stress else ""
        signals.append(
            Signal(
                alert_type="cash_gap",
                severity=gap.severity,
                message=f"{verb} {gap.days_until} дней ({gap.date.strftime('%d.%m.%Y')}){stress_note}",
                date_bucket=gap.date,
                payload={
                    "deficit_date": gap.date.isoformat(),
                    "days_until": gap.days_until,
                    "is_stress": gap.is_stress,
                    "severity": gap.severity,
                },
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
