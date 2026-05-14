"""lobby ownership: creator_id in seasons + season_moderators table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем creator_id в seasons (nullable — для уже созданных сезонов)
    op.add_column(
        "seasons",
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("web_users.id"), nullable=True)
    )

    # Таблица модераторов лобби
    op.create_table(
        "season_moderators",
        sa.Column("id",          sa.Integer(),  nullable=False),
        sa.Column("season_id",   sa.Integer(),  nullable=False),
        sa.Column("web_user_id", sa.Integer(),  nullable=False),
        sa.Column("granted_by",  sa.Integer(),  nullable=True),
        sa.Column("granted_at",  sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["season_id"],   ["seasons.id"],   ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["web_user_id"], ["web_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"],  ["web_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("season_id", "web_user_id", name="uq_season_mod"),
    )


def downgrade() -> None:
    op.drop_table("season_moderators")
    op.drop_column("seasons", "creator_id")
