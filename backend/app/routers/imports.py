"""
Router: /imports — загрузка банковских выписок.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import CurrentUser
from app.services.ingestion.import_service import ImportService
from app.services.ingestion.parser_registry import supported_banks

router = APIRouter(prefix="/imports", tags=["imports"])
_import_service = ImportService()


class ImportBatchResponse(BaseModel):
    id: uuid.UUID
    status: str
    filename: str
    row_count: int | None
    imported_count: int | None
    error_log: list | None
    meta: dict | None = None

    model_config = {"from_attributes": True}


@router.get("/banks", summary="Список поддерживаемых банков")
async def list_banks() -> dict:
    return {"banks": supported_banks()}


@router.post(
    "/bank",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить банковскую выписку (CSV)",
)
async def upload_bank_csv(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    bank_key: str = Form(..., description="Ключ банка: sber, tinkoff, vtb, alfa"),
    bank_account_id: str | None = Form(None),
) -> ImportBatchResponse:
    # Устанавливаем RLS-контекст
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(current_user.company_id)},
    )

    raw_bytes = await file.read()
    bank_account_uuid = uuid.UUID(bank_account_id) if bank_account_id else None

    try:
        batch = await _import_service.import_bank_csv(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            bank_key=bank_key,
            filename=file.filename or "upload.csv",
            raw_bytes=raw_bytes,
            bank_account_id=bank_account_uuid,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Пересчитываем снапшот синхронно (ARQ как опциональное ускорение)
    try:
        from app.services.forecast.snapshot import recompute_snapshot
        async with db.begin_nested():
            await recompute_snapshot(db, current_user.company_id)
        await db.commit()
    except Exception:
        pass

    # Ставим задачу ARQ на пересчёт снапшота (опционально)
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import get_settings
        settings = get_settings()
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("task_recompute_snapshot", str(current_user.company_id))
        await redis.aclose()
    except Exception:
        pass  # Не блокируем ответ если Redis недоступен

    return ImportBatchResponse(
        id=batch.id,
        status=batch.status,
        filename=batch.filename,
        row_count=batch.row_count,
        imported_count=batch.imported_count,
        error_log=batch.error_log,
    )


@router.post(
    "/onec",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить выгрузку 1С ОСВ (CSV)",
)
async def upload_onec_osv(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
) -> ImportBatchResponse:
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(current_user.company_id)},
    )

    raw_bytes = await file.read()

    try:
        batch, meta = await _import_service.import_onec_osv(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            filename=file.filename or "osv.csv",
            raw_bytes=raw_bytes,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    try:
        from app.services.forecast.snapshot import recompute_snapshot
        async with db.begin_nested():
            await recompute_snapshot(db, current_user.company_id)
        await db.commit()
    except Exception:
        pass

    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import get_settings
        settings = get_settings()
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("task_recompute_snapshot", str(current_user.company_id))
        await redis.aclose()
    except Exception:
        pass

    return ImportBatchResponse(
        id=batch.id,
        status=batch.status,
        filename=batch.filename,
        row_count=batch.row_count,
        imported_count=batch.imported_count,
        error_log=batch.error_log,
        meta=meta,
    )


@router.get("/history", summary="История загрузок")
async def import_history(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
) -> dict:
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(current_user.company_id)},
    )
    result = await db.execute(
        text(
            "SELECT id, source_type, filename, status, row_count, imported_count, created_at "
            "FROM import_batch "
            "WHERE company_id = :cid "
            "ORDER BY created_at DESC LIMIT :limit"
        ),
        {"cid": current_user.company_id, "limit": limit},
    )
    rows = result.fetchall()
    return {
        "batches": [
            {
                "id": str(r[0]),
                "source_type": r[1],
                "filename": r[2],
                "status": r[3],
                "row_count": r[4],
                "imported_count": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]
    }
