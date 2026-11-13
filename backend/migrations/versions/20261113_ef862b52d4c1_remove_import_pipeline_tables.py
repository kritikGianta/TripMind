"""remove import pipeline tables (the data pack loader writes the catalog directly)

Revision ID: ef862b52d4c1
Revises: 7ae68f901292
Create Date: 2026-11-13 17:41:19.788905
"""

from collections.abc import Sequence

from alembic import op

revision: str = "ef862b52d4c1"
down_revision: str | None = "7ae68f901292"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The generic import pipeline is gone: the data pack loader writes the catalog directly.
    # Foreign keys first, then the tables they point at (PostgreSQL refuses the other order).
    for table in (
        "airports",
        "attractions",
        "cities",
        "flights",
        "hotel_reviews",
        "hotels",
        "room_types",
        "transfers",
    ):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_import_run_id_import_runs", type_="foreignkey")
            batch_op.drop_column("import_run_id")
    op.drop_table("import_rejects")
    op.drop_table("import_runs")


def downgrade() -> None:
    raise NotImplementedError(
        "The import pipeline was removed; restore it from git history if needed."
    )
