"""phase4_telemetry

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lap_telemetry",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("race_id",       sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("vehicle_index", sa.Integer(), nullable=False),
        sa.Column("lap_number",    sa.Integer(), nullable=False),
        sa.Column("lap_time_ms",   sa.Integer(), nullable=True),
        sa.Column("samples",       JSONB(), nullable=False),
    )
    # Индекс для быстрого поиска по гонке + пилоту
    op.create_index("ix_lap_telemetry_race_vehicle", "lap_telemetry", ["race_id", "vehicle_index"])
    op.create_index("ix_lap_telemetry_race_lap",     "lap_telemetry", ["race_id", "vehicle_index", "lap_number"], unique=True)


def downgrade() -> None:
    op.drop_table("lap_telemetry")
