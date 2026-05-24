"""
ImportService — оркестрирует полный цикл импорта банковской выписки.

1. Создаёт import_batch (status=pending)
2. Парсит файл через ParserRegistry
3. Сохраняет транзакции с dedupe (ON CONFLICT DO NOTHING)
4. Обновляет статус batch
5. Пишет audit_log
6. Ставит задачу ARQ на пересчёт снапшота
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models import ImportBatch, BankAccount
from app.services.ingestion.parser_registry import get_parser
from app.services.ingestion.deduper import compute_dedupe_hash
from app.core.audit import log_action


MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


class ImportService:

    async def _get_or_create_default_account(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        bank_key: str,
    ) -> uuid.UUID:
        result = await db.execute(
            text(
                "SELECT id FROM bank_account WHERE company_id = :cid LIMIT 1"
            ),
            {"cid": company_id},
        )
        row = result.fetchone()
        if row:
            return row[0]
        account_id = uuid.uuid4()
        bank_names = {
            "sber": "Сбербанк", "tinkoff": "Тинькофф",
            "vtb": "ВТБ", "alfa": "Альфа-Банк",
            "cbe": "Банк (ClientBankExchange)",
        }
        await db.execute(
            text(
                "INSERT INTO bank_account (id, company_id, bank_name, account_number, currency, created_at) "
                "VALUES (:id, :cid, :bank_name, :account_number, 'RUB', now())"
            ),
            {
                "id": account_id,
                "cid": company_id,
                "bank_name": bank_names.get(bank_key, bank_key),
                "account_number": "auto",
            },
        )
        return account_id

    async def import_bank_csv(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        bank_key: str,
        filename: str,
        raw_bytes: bytes,
        bank_account_id: uuid.UUID | None = None,
    ) -> ImportBatch:
        if len(raw_bytes) > MAX_FILE_BYTES:
            raise ValueError(f"Файл превышает лимит {MAX_FILE_BYTES // (1024 * 1024)} MB")

        # Создаём batch
        resolved_account_id = bank_account_id or await self._get_or_create_default_account(
            db, company_id, bank_key
        )
        batch = ImportBatch(
            company_id=company_id,
            bank_account_id=bank_account_id,
            source_type="bank_csv",
            filename=filename,
            status="processing",
        )
        db.add(batch)
        await db.flush()

        try:
            parser = get_parser(bank_key)
            parse_result = parser.parse(raw_bytes)

            batch.row_count = len(parse_result.rows) + len(parse_result.errors)
            imported = 0

            for row in parse_result.rows:
                dedupe_hash = compute_dedupe_hash(
                    company_id=company_id,
                    txn_date=row.txn_date,
                    amount=row.amount,
                    direction=row.direction,
                    counterparty_raw=row.counterparty_raw,
                    purpose=row.purpose,
                )
                txn_id = uuid.uuid4()
                txn_account_id = resolved_account_id
                # INSERT ... ON CONFLICT DO NOTHING для idempotency
                insert_result = await db.execute(
                    text(
                        "INSERT INTO transaction "
                        "(id, company_id, bank_account_id, batch_id, txn_date, amount, "
                        " direction, counterparty_raw, purpose, dedupe_hash, created_at) "
                        "VALUES "
                        "(:id, :company_id, :bank_account_id, :batch_id, :txn_date, :amount, "
                        " :direction, :counterparty_raw, :purpose, :dedupe_hash, now()) "
                        "ON CONFLICT (company_id, dedupe_hash) DO NOTHING"
                    ),
                    {
                        "id": txn_id,
                        "company_id": company_id,
                        "bank_account_id": txn_account_id,
                        "batch_id": batch.id,
                        "txn_date": row.txn_date,
                        "amount": row.amount,
                        "direction": row.direction,
                        "counterparty_raw": row.counterparty_raw,
                        "purpose": row.purpose,
                        "dedupe_hash": dedupe_hash,
                    },
                )
                if insert_result.rowcount > 0:
                    imported += 1

            batch.imported_count = imported
            batch.error_log = parse_result.errors[:100] if parse_result.errors else None
            batch.status = "partial" if parse_result.errors else "done"
            batch.updated_at = datetime.utcnow()

        except Exception as exc:
            batch.status = "failed"
            batch.error_log = [{"error": str(exc)}]
            batch.updated_at = datetime.utcnow()
            raise

        finally:
            await db.flush()

        await log_action(
            db,
            company_id=company_id,
            user_id=user_id,
            action="import_bank_csv",
            entity="import_batch",
            entity_id=batch.id,
            metadata={
                "bank": bank_key,
                "filename": filename,
                "status": batch.status,
                "imported": batch.imported_count,
                "errors": len(parse_result.errors) if hasattr(parse_result, "errors") else 0,
            },
        )

        return batch
