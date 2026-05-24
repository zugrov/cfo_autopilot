"""
Router: /audit — журнал действий компании (owner only).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rbac import OwnerUser

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", summary="Журнал действий компании")
async def list_audit_log(
    current_user: OwnerUser,
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )

    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    result = await db.execute(
        text(
            "SELECT a.id, a.action, a.entity, a.entity_id, a.metadata, a.at, "
            "       u.email AS user_email "
            "FROM audit_log a "
            'LEFT JOIN "user" u ON a.user_id = u.id '
            "WHERE a.company_id = :cid "
            "ORDER BY a.at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"cid": cid, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    count_row = await db.execute(
        text("SELECT COUNT(*) FROM audit_log WHERE company_id = :cid"),
        {"cid": cid},
    )
    total = count_row.scalar() or 0

    return {
        "entries": [
            {
                "id": str(r[0]),
                "action": r[1],
                "entity": r[2],
                "entity_id": str(r[3]) if r[3] else None,
                "metadata": r[4] or {},
                "at": r[5].isoformat() if r[5] else None,
                "user_email": r[6],
            }
            for r in rows
        ],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }
