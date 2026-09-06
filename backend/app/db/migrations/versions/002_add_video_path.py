"""Add video_path column to alerts table.

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("video_path", sa.String(500), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("alerts", "video_path")
