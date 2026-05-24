"""receivable aging fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receivable",
        sa.Column("aging_bucket", sa.String(16), nullable=True),
    )
    op.add_column(
        "receivable",
        sa.Column("collection_probability", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "receivable",
        sa.Column(
            "import_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_batch.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_receivable_import_batch_id", "receivable", ["import_batch_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_receivable_import_batch_id", table_name="receivable")
    op.drop_column("receivable", "import_batch_id")
    op.drop_column("receivable", "collection_probability")
    op.drop_column("receivable", "aging_bucket")
