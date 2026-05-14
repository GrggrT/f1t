"""Add lobbies, lobby_members tables and lobby_id FK on seasons.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lobbies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("web_users.id"), nullable=False),
        sa.Column("invite_code", sa.String(20), unique=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lobby_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lobby_id", sa.Integer(), sa.ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("web_user_id", sa.Integer(), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_lobby_members_unique",
        "lobby_members",
        ["lobby_id", "web_user_id"],
        unique=True,
    )

    op.add_column(
        "seasons",
        sa.Column("lobby_id", sa.Integer(), sa.ForeignKey("lobbies.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seasons", "lobby_id")
    op.drop_table("lobby_members")
    op.drop_table("lobbies")
