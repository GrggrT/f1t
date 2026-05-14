"""add web_users table

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_users",
        sa.Column("id",              sa.Integer(),    nullable=False),
        sa.Column("email",           sa.String(255),  nullable=True),
        sa.Column("name",            sa.String(100),  nullable=False),
        sa.Column("picture",         sa.Text(),       nullable=True),
        sa.Column("hashed_password", sa.Text(),       nullable=True),
        sa.Column("google_id",       sa.String(100),  nullable=True),
        sa.Column("steam_id64",      sa.String(20),   nullable=True),
        sa.Column("player_id",       sa.Integer(),    nullable=True),
        sa.Column("created_at",      sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_unique_constraint("uq_web_users_email",      "web_users", ["email"])
    op.create_unique_constraint("uq_web_users_google_id",  "web_users", ["google_id"])
    op.create_unique_constraint("uq_web_users_steam_id64", "web_users", ["steam_id64"])


def downgrade() -> None:
    op.drop_table("web_users")
