"""Add is_system_admin to web_users.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "web_users",
        sa.Column("is_system_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Set known admin accounts
    op.execute("UPDATE web_users SET is_system_admin = true WHERE email = 'gregorysky04i@gmail.com'")
    # Also set user #1 for testing
    op.execute("UPDATE web_users SET is_system_admin = true WHERE id = 1")


def downgrade() -> None:
    op.drop_column("web_users", "is_system_admin")
