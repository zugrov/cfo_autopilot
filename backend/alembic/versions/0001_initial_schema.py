"""initial schema with RLS

Revision ID: 0001
Revises:
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── company (не tenant-таблица, глобальная) ─────────────────────────────
    op.create_table(
        "company",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("settings_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── user ─────────────────────────────────────────────────────────────────
    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="owner"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_user_company_id", "user", ["company_id"])

    # ── bank_account ─────────────────────────────────────────────────────────
    op.create_table(
        "bank_account",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_name", sa.String(128), nullable=False),
        sa.Column("account_number", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="RUB"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_account_company_id", "bank_account", ["company_id"])

    # ── import_batch ─────────────────────────────────────────────────────────
    op.create_table(
        "import_batch",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("imported_count", sa.Integer(), nullable=True),
        sa.Column("error_log", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batch_company_id", "import_batch", ["company_id"])

    # ── transaction ──────────────────────────────────────────────────────────
    op.create_table(
        "transaction",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("counterparty_raw", sa.Text(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("dedupe_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_account.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "dedupe_hash", name="uq_transaction_dedupe"),
    )
    op.create_index("ix_transaction_company_date", "transaction", ["company_id", "txn_date"])

    # ── obligation ───────────────────────────────────────────────────────────
    op.create_table(
        "obligation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_obligation_company_id", "obligation", ["company_id"])

    # ── daily_cash_snapshot ──────────────────────────────────────────────────
    op.create_table(
        "daily_cash_snapshot",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("forecast_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("company_id", "snapshot_date"),
    )

    # ── audit_log ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity", sa.String(64), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_company_id", "audit_log", ["company_id"])

    # ── Sprint 2+ tables ─────────────────────────────────────────────────────
    op.create_table(
        "counterparty",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("inn", sa.String(12), nullable=True),
        sa.Column("counterparty_type", sa.String(16), nullable=False, server_default="supplier"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_counterparty_company_id", "counterparty", ["company_id"])

    op.create_table(
        "receivable",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["counterparty_id"], ["counterparty.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receivable_company_id", "receivable", ["company_id"])

    op.create_table(
        "alert",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("date_bucket", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "alert_type", "date_bucket", name="uq_alert_dedupe"),
    )
    op.create_index("ix_alert_company_id", "alert", ["company_id"])

    # ── Row-Level Security (RLS) ─────────────────────────────────────────────
    # Включаем RLS на всех tenant-таблицах
    tenant_tables = [
        '"user"', "bank_account", "import_batch", "transaction",
        "obligation", "daily_cash_snapshot", "audit_log",
        "counterparty", "receivable", "alert",
    ]
    for table in tenant_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (company_id = current_setting('app.company_id', true)::uuid)"
        )

    # audit_log допускает INSERT без ограничения (пишет сервис)
    op.execute(
        "CREATE POLICY audit_log_insert ON audit_log FOR INSERT "
        "WITH CHECK (true)"
    )


def downgrade() -> None:
    tenant_tables = [
        '"user"', "bank_account", "import_batch", "transaction",
        "obligation", "daily_cash_snapshot", "audit_log",
        "counterparty", "receivable", "alert",
    ]
    for table in reversed(tenant_tables):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("alert")
    op.drop_table("receivable")
    op.drop_table("counterparty")
    op.drop_table("audit_log")
    op.drop_table("daily_cash_snapshot")
    op.drop_table("obligation")
    op.drop_table("transaction")
    op.drop_table("import_batch")
    op.drop_table("bank_account")
    op.drop_table("user")
    op.drop_table("company")
