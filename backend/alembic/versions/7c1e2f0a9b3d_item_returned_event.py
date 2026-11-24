from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c1e2f0a9b3d"
down_revision: str | None = "cfe338c84e6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("consumer", sa.String(length=100), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", "consumer"),
    )
    op.create_table(
        "return_statistics",
        sa.Column(
            "category",
            sa.Enum(
                "electronics",
                "documents",
                "keys",
                "wallet",
                "bag",
                "clothing",
                "other",
                name="itemcategory",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("returned_count", sa.Integer(), nullable=False),
        sa.Column("last_returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("category"),
    )


def downgrade() -> None:
    op.drop_table("return_statistics")
    op.drop_table("processed_events")
