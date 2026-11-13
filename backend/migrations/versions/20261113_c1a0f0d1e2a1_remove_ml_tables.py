"""remove ml tables

The finale rules forbid AI models inside the app, so the preference model and the stay
interaction log it learned from are gone.

Revision ID: c1a0f0d1e2a1
Revises: a55ba690c6d5
Create Date: 2026-11-13 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1a0f0d1e2a1"
down_revision: str | None = "a55ba690c6d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_index("ix_hotel_interactions_user_time", table_name="hotel_interactions")
    op.drop_table("hotel_interactions")


def downgrade() -> None:
    op.create_table(
        "hotel_interactions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("hotel_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('view', 'save', 'book')", name=op.f("ck_hotel_interactions_kind_valid")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_hotel_interactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hotel_interactions")),
    )
    op.create_index(
        "ix_hotel_interactions_user_time",
        "hotel_interactions",
        ["user_id", "occurred_at"],
        unique=False,
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("intercept", sa.Float(), nullable=False),
        sa.Column("positives", sa.Integer(), nullable=False),
        sa.Column("interactions", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_preferences")),
    )
