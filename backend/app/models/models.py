import uuid
from datetime import datetime, date
from typing import Optional
from decimal import Decimal

from sqlalchemy import (
    String, Text, Numeric, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint, Index, JSON, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def now_utc() -> datetime:
    return datetime.utcnow()


class Company(Base):
    __tablename__ = "company"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    settings_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    users: Mapped[list["User"]] = relationship(back_populates="company")
    bank_accounts: Mapped[list["BankAccount"]] = relationship(back_populates="company")


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # role: owner | accountant | viewer
    role: Mapped[str] = mapped_column(String(32), default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    company: Mapped[Company] = relationship(back_populates="users")


class BankAccount(Base):
    __tablename__ = "bank_account"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False, index=True
    )
    bank_name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_number: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    company: Mapped[Company] = relationship(back_populates="bank_accounts")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="bank_account")


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    bank_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_account.id"), nullable=True
    )
    # source_type: bank_csv | client_bank_exchange | onec_file
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # status: pending | processing | done | partial | failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    row_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    imported_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    error_log: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    bank_account: Mapped[Optional[BankAccount]] = relationship()
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="import_batch")


class Transaction(Base):
    __tablename__ = "transaction"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_account.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False
    )
    txn_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # direction: credit | debit
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    counterparty_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # dedupe hash: sha256(company_id, txn_date, amount, direction, counterparty_raw[:64], purpose[:64])
    dedupe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    bank_account: Mapped[BankAccount] = relationship(back_populates="transactions")
    import_batch: Mapped[ImportBatch] = relationship(back_populates="transactions")

    __table_args__ = (
        UniqueConstraint("company_id", "dedupe_hash", name="uq_transaction_dedupe"),
        Index("ix_transaction_company_date", "company_id", "txn_date"),
    )


class Obligation(Base):
    """Ручные плановые обязательства (платёжный календарь)."""
    __tablename__ = "obligation"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    # status: pending | paid | cancelled
    status: Mapped[str] = mapped_column(String(32), default="pending")
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DailyCashSnapshot(Base):
    """Материализованный кеш прогноза по дням."""
    __tablename__ = "daily_cash_snapshot"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, primary_key=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # JSONB: [{date, forecast_balance, scenario}]
    forecast_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditLog(Base):
    """Журнал действий пользователей (write-only из app)."""
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


# Sprint 2+ models (defined now, used in migrations later)

class Counterparty(Base):
    __tablename__ = "counterparty"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    # type: customer | supplier | both
    counterparty_type: Mapped[str] = mapped_column(String(16), default="supplier")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Receivable(Base):
    __tablename__ = "receivable"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # status: open | overdue | collected | written_off
    status: Mapped[str] = mapped_column(String(32), default="open")
    source: Mapped[str] = mapped_column(String(32), default="manual")
    # aging_bucket: 0_30 | 31_60 | 61_90 | 90_plus | unknown
    aging_bucket: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    # expected collection probability (0.000–1.000); None means 0 for forecast
    collection_probability: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True
    )
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    # type: deficit_7d | deficit_14d | deficit_30d | stale_data
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    date_bucket: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        UniqueConstraint("company_id", "alert_type", "date_bucket", name="uq_alert_dedupe"),
    )
