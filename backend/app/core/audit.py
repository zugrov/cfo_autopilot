import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def log_action(
    db: AsyncSession,
    company_id: uuid.UUID,
    action: str,
    user_id: uuid.UUID | None = None,
    entity: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Записывает событие в audit_log. Fire-and-forget — не бросает исключений."""
    try:
        entry = AuditLog(
            company_id=company_id,
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            meta=metadata,
            at=datetime.utcnow(),
        )
        db.add(entry)
        await db.flush()
    except Exception:
        pass
